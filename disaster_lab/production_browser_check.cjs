const {chromium}=require(process.env.LAB_PLAYWRIGHT_PATH||'playwright');
const path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  // The test proxy uses its own local CA, never a remote production certificate.
  const page=await browser.newPage({ignoreHTTPSErrors:true,viewport:{width:1280,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base=process.env.LAB_TEST_URL;
  if(!base.startsWith('https://localhost:'))throw Error('This test accepts localhost TLS only');
  await page.goto(base,{waitUntil:'networkidle'});
  await page.getByLabel('Workspace password').waitFor();
  await page.screenshot({path:path.join(__dirname,'reports/production-login.png')});
  await page.getByLabel('Workspace password').fill(process.env.LAB_TEST_PASSWORD);
  await page.getByRole('button',{name:'Open workspace'}).click();
  await page.getByRole('heading',{name:/See the signals/}).waitFor();
  await page.locator('nav a[href="#operations"]').click();
  await page.getByRole('heading',{name:'Service health',exact:true}).waitFor();
  if((await page.locator('.stats').innerText()).includes('NaN'))throw Error('Invalid service metric');
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile service page overflow');
  await page.locator('#logout').click();
  await page.getByLabel('Workspace password').waitFor();
  if(errors.length)throw Error(errors.join('\n'));
  console.log('Production browser login, operations and logout passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
