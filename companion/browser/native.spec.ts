import {test,expect} from '@playwright/test';

test('real SDK with synthetic native host: cold startup, repeated connect, exit and stable approval DOM',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const w=window as any;w.nativeCalls=[];
    w.flutter_inappwebview={callHandler:async(_name:string,raw:string)=>{
      const message=JSON.parse(raw);w.nativeCalls.push(message);
      return message.method==='createStartUpPageContainer'?0:true;
    }};
  });
  let session='',turn='';
  const approval={request_id:'synthetic-long-approval',execution_generation:1,description:'Read complete synthetic request.\n'.repeat(100)};
  await page.route('https://g2.example.com/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    let body:unknown={};
    if(path==='/health')body={protocol:2};
    else if(path==='/sessions'){session=request.postDataJSON().session_id;body={session_id:session};}
    else if(path.endsWith('/turns')){turn=request.postDataJSON().turn_id;body={session_id:session,turn_id:turn,status:'waiting_for_approval',approvals:[approval]};}
    else body={session_id:session,turn_id:turn,status:'waiting_for_approval',approvals:[approval]};
    await route.fulfill({json:body});
  });
  await page.goto('/');
  await expect.poll(()=>page.evaluate(()=>(window as any).nativeCalls)).toEqual(expect.arrayContaining([expect.objectContaining({method:'createStartUpPageContainer'})]));
  const startup=await page.evaluate(()=>(window as any).nativeCalls.find((c:any)=>c.method==='createStartUpPageContainer'));
  expect(JSON.stringify(startup)).toContain('Open phone');
  await page.evaluate(()=>window.dispatchEvent(new CustomEvent('evenHubEvent',{detail:{textEvent:{eventType:3}}})));
  await expect.poll(()=>page.evaluate(()=>(window as any).nativeCalls.filter((c:any)=>c.method==='shutDownPageContainer').length)).toBe(1);
  for(let i=0;i<2;i++){
    await page.locator('#token').fill('synthetic-device-token-not-a-secret-0000001');await page.locator('#connect').click();
    await expect(page.locator('#state')).toHaveText('idle');
  }
  expect(await page.evaluate(()=>(window as any).nativeCalls.filter((c:any)=>c.method==='createStartUpPageContainer').length)).toBe(1);
  await page.locator('#text').fill('approval');await page.locator('#send').click();
  await expect(page.locator('#state')).toHaveText('approval');
  await page.locator('#approvals pre').evaluate(node=>{node.scrollTop=100;(window as any).approvalNode=node;});
  await page.waitForTimeout(3300);
  expect(await page.locator('#approvals pre').evaluate(node=>node===(window as any).approvalNode&&node.scrollTop===100)).toBe(true);
  const updates=await page.evaluate(()=>(window as any).nativeCalls.filter((c:any)=>c.method==='textContainerUpgrade'));
  expect(updates.length).toBeGreaterThan(0);expect(JSON.stringify(updates)).not.toMatch(/contentOffset|contentLength/);
  await page.locator('#disconnect').click();
  await expect(page.locator('#approvals')).toBeEmpty();await expect(page.locator('#state')).toHaveText('offline');
  await page.evaluate(()=>window.dispatchEvent(new CustomEvent('evenHubEvent',{detail:{sysEvent:{eventType:3}}})));
  await expect.poll(()=>page.evaluate(()=>(window as any).nativeCalls.filter((c:any)=>c.method==='shutDownPageContainer').length)).toBe(2);
  expect(errors).toEqual([]);
});

test('lost ledger stays uncertain through second connect and reload until explicit local reset',async({page})=>{
  await page.addInitScript(()=>{(window as any).flutter_inappwebview={callHandler:async(_name:string,raw:string)=>JSON.parse(raw).method==='createStartUpPageContainer'?0:true};});
  const requests:string[]=[];const created:string[]=[];
  await page.route('https://g2.example.com/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;requests.push(`${request.method()} ${path}`);
    if(path==='/health')await route.fulfill({json:{protocol:2}});
    else if(path==='/sessions'){
      const session=request.postDataJSON().session_id;created.push(session);await route.fulfill({json:{session_id:session}});
    }else await route.fulfill({status:409,json:{error:'session_continuity_lost'}});
  });
  await page.goto('/');
  const old=await page.evaluate(()=>{
    const resume={session:crypto.randomUUID(),turn:crypto.randomUUID()};localStorage.setItem('hermes-g2-resume:https://g2.example.com',JSON.stringify(resume));return resume;
  });
  for(let reload=0;reload<2;reload++){
    await page.reload();
    for(let connect=0;connect<2;connect++){
      await page.locator('#token').fill('synthetic-device-token-not-a-secret-0000001');await page.locator('#connect').click();
      await expect(page.locator('#state')).toHaveText('error');await expect(page.locator('#status')).toContainText('Outcome unknown');
    }
    expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('hermes-g2-resume:https://g2.example.com')!))).toEqual(old);
  }
  expect(created).toEqual([]);expect(requests.some(path=>path.includes('/reconcile'))).toBe(false);
  page.once('dialog',dialog=>dialog.dismiss());await page.locator('#forget-lost').click();expect(created).toEqual([]);
  page.once('dialog',dialog=>dialog.accept());await page.locator('#forget-lost').click();await expect(page.locator('#state')).toHaveText('idle');
  expect(created).toHaveLength(1);expect(created[0]).not.toBe(old.session);
});
