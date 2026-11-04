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
  await page.getByRole('button',{name:'Pokhara',exact:true}).click();
  await page.getByRole('button',{name:'Next 72 hours'}).click();
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
  let requests=0,offline=false;
  await poll.route('**/data/snapshot.json',async route=>{
   requests++;
   if(offline){await route.abort();return}
   const next=structuredClone(fixture);
   if(requests>1){next.built_at=new Date(Date.now()+1000).toISOString();next.rivers[0].name='Automatic refresh test station'}
   await route.fulfill({contentType:'application/json',body:JSON.stringify(next)});
  });
  await poll.goto(base+'#rivers');await poll.locator('#search').waitFor();
  await poll.locator('#search').fill('Automatic refresh test station');
  assert.equal(await poll.locator('#result-count').innerText(),'0 stations');
  await poll.clock.runFor(300100);await poll.waitForFunction(()=>document.querySelector('#result-count')?.textContent==='1 stations');
  assert.equal(await poll.locator('#search').inputValue(),'Automatic refresh test station');assert.ok(requests>=2);
  offline=true;await poll.clock.runFor(300100);await poll.waitForFunction(()=>document.querySelector('#status').textContent.includes('refresh failed'));
  assert.equal(await poll.locator('#result-count').innerText(),'1 stations');
  if(fixture.schema_version===2){
   await page.goto(base+'#weather');await page.getByRole('heading',{name:'Seven model days of river discharge'}).waitFor();
   await page.goto(base+'#evidence');await page.getByRole('heading',{name:'Automatic collection & retained history'}).waitFor();
   await page.getByRole('heading',{name:'Regional earthquake catalog'}).waitFor();
  }
  console.log('PASS: four views, search, filters, model tabs, repository path, mobile overflow, stale snapshots, automatic refresh/filter retention, offline fallback and no browser errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
