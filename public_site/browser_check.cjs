// Local release check. Set NODE_PATH to an installed Playwright package directory.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.env.TERRA_TEST_URL||'http://127.0.0.1:8768/TerraNepal/';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`)});
  await page.goto(base);await page.getByRole('heading',{name:/A clearer view/}).waitFor();
  await page.getByRole('link',{name:'Rivers',exact:true}).click();
  await page.locator('#search').fill('Karnali');assert.match(await page.locator('#result-count').innerText(),/\d+ stations/);
  await page.locator('#search').fill('no-such-station-123');assert.equal(await page.locator('#result-count').innerText(),'0 stations');
  await page.locator('#search').fill('');await page.locator('#state').selectOption('stale');
  assert.ok(await page.locator('#station-rows tr').count()>0);
  await page.getByRole('link',{name:'Weather outlook',exact:true}).click();
  await page.getByRole('button',{name:'Pokhara',exact:true}).press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'place-pokhara','Location selection preserves keyboard focus');
  await page.getByRole('button',{name:'Next 72 hours'}).press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'hours-72','Duration selection preserves keyboard focus');
  await page.getByRole('button',{name:'Next 24 hours'}).press('Enter');
  await page.getByText('Read hourly precipitation data',{exact:true}).first().click();
  assert.equal(await page.locator('.weather-grid table tbody tr').first().count(),1);
  assert.ok(await page.locator('.weather-grid table tbody tr').count()>=24);
  await page.getByRole('link',{name:'Evidence',exact:true}).click();await page.getByRole('heading',{name:'Known historical coverage gaps'}).waitFor();
  await page.setViewportSize({width:390,height:844});
  for(const hash of ['overview','rivers','weather','evidence']){
   await page.goto(base+'#'+hash);await page.locator('#content h1').waitFor();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No horizontal overflow: '+hash);
  }
  assert.deepEqual(errors,[]);
  // A stale build may load successfully but must not show current weather totals.
  const stale=await browser.newPage();await stale.clock.install({time:new Date(Date.now()+48*3600*1000)});
  await stale.goto(base+'#weather');await stale.locator('#content h1').waitFor();
  assert.match(await stale.locator('#status').innerText(),/needs an update/);
  assert.equal(await stale.getByText('Summary withheld: stale, missing or incomplete forecast.',{exact:true}).count(),2);
  // A tab open across deployments refreshes data while retaining the active filter.
  const fixture=await (await page.request.get(base+'data/snapshot.json')).json();
  const poll=await browser.newPage();await poll.clock.install({time:new Date()});
  let requests=0,offline=false,malformed=false;
  await poll.route('**/data/snapshot.json',async route=>{
   requests++;
   if(offline){await route.abort();return}
   const next=structuredClone(fixture);
   if(requests>1){next.built_at=new Date(Date.now()+1000).toISOString();next.rivers[0].name='Automatic refresh test station'}
   if(malformed)delete next.weather;
   await route.fulfill({contentType:'application/json',body:JSON.stringify(next)});
  });
  await poll.goto(base+'#rivers');await poll.locator('#search').waitFor();
  await poll.locator('#search').fill('Automatic refresh test station');
  assert.equal(await poll.locator('#result-count').innerText(),'0 stations');
  await poll.clock.runFor(300100);await poll.waitForFunction(()=>document.querySelector('#result-count')?.textContent==='1 stations');
  assert.equal(await poll.locator('#search').inputValue(),'Automatic refresh test station');assert.ok(requests>=2);
  offline=true;await poll.clock.runFor(300100);await poll.waitForFunction(()=>document.querySelector('#status').textContent.includes('refresh failed'));
  assert.equal(await poll.locator('#result-count').innerText(),'1 stations');
  offline=false;malformed=true;await poll.clock.runFor(300100);
  assert.equal(await poll.locator('#result-count').innerText(),'1 stations');
  assert.match(await poll.locator('#status').innerText(),/refresh failed/);
  if(fixture.schema_version===2){
   await page.goto(base+'#weather');await page.getByRole('heading',{name:'Seven model days of river discharge'}).waitFor();
   const dischargePanel=page.locator('section').filter({has:page.getByRole('heading',{name:'Seven model days of river discharge'})});
   const unverified=fixture.discharge.filter(f=>f.normalized.reach_verified!==true).length;
   assert.equal(await dischargePanel.locator('summary').filter({hasText:'mapping unverified'}).count(),unverified);
   for(const detail of await dischargePanel.locator('details').all()){
    if((await detail.locator('summary').innerText()).includes('mapping unverified')){
     await detail.locator('summary').click();
     for(const cell of await detail.locator('tbody td:nth-child(2), tbody td:nth-child(3)').all())assert.ok(!(await cell.innerText()).match(/[0-9]/),'Unverified reach has no numeric public forecast');
    }
   }
   await page.goto(base+'#evidence');await page.getByRole('heading',{name:'Automatic collection & retained history'}).waitFor();
   await page.getByRole('heading',{name:'Regional earthquake catalog'}).waitFor();
  }
  // Initial mobile failure must retain an actual official destination, without a snapshot.
  const outage=await browser.newPage({viewport:{width:390,height:844}});
  await outage.route('**/data/snapshot.json',route=>route.abort());
  await outage.goto(base);await outage.getByRole('alert').waitFor();
  assert.ok(await outage.getByRole('link',{name:'Check official Nepal DHM information'}).isVisible());
  assert.ok(await outage.getByRole('link',{name:'Official DHM ↗',exact:true}).isVisible());
  // Expiry cannot be suspended by focus inside the weather view or an open disclosure.
  const expiry=await browser.newPage();const fixed=new Date('2026-11-15T00:00:00Z');
  await expiry.clock.install({time:fixed});
  const expiryFixture=structuredClone(fixture);expiryFixture.built_at=fixed.toISOString();
  expiryFixture.weather=expiryFixture.weather.map(source=>({...source,fetched_at:fixed.toISOString(),normalized:{...source.normalized,points:Array.from({length:96},(_,i)=>{const epoch=fixed.getTime()/1000+(i+1)*3600;return {epoch,at:new Date(epoch*1000).toISOString(),precipitation:1,temperature_2m:15,wind_gusts_10m:2}})}}));
  await expiry.route('**/data/snapshot.json',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(expiryFixture)}));
  await expiry.goto(base+'#weather');await expiry.locator('#place-kathmandu').waitFor();
  await expiry.locator('#weather-data-ecmwf_ifs025').click();
  await expiry.locator('#hours-24').press('Enter');
  assert.equal(await expiry.getByText('Forecast precipitation over the selected future window.',{exact:true}).count(),2);
  await expiry.clock.runFor(6*3600000+60001);
  assert.equal(await expiry.getByText('Summary withheld: stale, missing or incomplete forecast.',{exact:true}).count(),2);
  assert.equal(await expiry.evaluate(()=>document.activeElement.id),'hours-24');
  assert.ok(await expiry.locator('#weather-data-ecmwf_ifs025').evaluate(el=>el.parentElement.open));
  console.log('PASS: four views, search, filters, model tabs, repository path, mobile overflow, stale snapshots, automatic refresh/filter retention, offline fallback, mobile official links, keyboard focus, accessible chart tables, focused forecast expiry and no browser errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
