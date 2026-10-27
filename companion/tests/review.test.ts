import {it,expect,vi,afterEach} from 'vitest';
import {Controller,pages} from '../src/controller';
import {Simulator} from '../src/simulator';
import {HttpTransport,RequestRefusal} from '../src/http';

async function setup(){const sim=new Simulator(()=>{});const c=new Controller(sim,sim,undefined,()=>{},()=>{});await c.connect();return {c,sim};}
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});

it('root double tap opens exit and also discards capture/requests active stop',async()=>{
  const {c,sim}=await setup();const exit=vi.spyOn(sim,'exit');
  await c.gesture({textEvent:{eventType:3}});expect(exit).toHaveBeenCalledTimes(1);
  await c.start();await c.gesture({sysEvent:{eventType:3}});expect(sim.recording).toBe(false);expect(exit).toHaveBeenCalledTimes(2);
  await c.send('wait');await c.gesture({textEvent:{eventType:3}});expect(exit).toHaveBeenCalledTimes(3);expect(c.resume.stopRequested).toBe(true);await c.poll();expect(c.active).toBe(false);
});
it('uncertain run does not prevent native exit or erase resume/stop intent',async()=>{
  const {c,sim}=await setup();sim.submit=async()=>{throw new Error('lost');};await c.send('effect');
  sim.stop=async()=>{throw new Error('offline');};const exit=vi.spyOn(sim,'exit');const tid=c.resume.turn;
  await c.gesture({textEvent:{eventType:3}});expect(exit).toHaveBeenCalledOnce();expect(c.resume).toMatchObject({turn:tid,stopRequested:true});expect(c.active).toBe(true);
});
it('new companion refuses historical protocol1 broker before admitting a session',async()=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({protocol:1}),{status:200}));
  const api=new HttpTransport('https://g2.example.com','synthetic-device-token-not-a-secret-0000001');
  await expect(api.health()).rejects.toThrow('matching_protocol_2_broker_required');
});
it.each([4,5])('overlay event %s discards without resuming microphone or submitting',async eventType=>{
  const {c,sim}=await setup();await c.start();c.audio(new Uint8Array(10));
  await c.gesture({sysEvent:{eventType}});expect(sim.recording).toBe(false);expect(sim.texts).toHaveLength(0);
});
it('definitive rejected snapshot frees admission but retains the sealed turn identity',async()=>{
  const {c,sim}=await setup();sim.submit=async(session,turn)=>({session_id:session,turn_id:turn,status:'rejected'});
  await c.send('not submitted');expect(c.active).toBe(false);expect(c.resume.turn).toBeTruthy();expect(c.message).toContain('sealed');
});
it('bare 404 cannot release uncertainty; only successful atomic reconciliation can',async()=>{
  const {c,sim}=await setup();sim.submit=async()=>{throw new Error('network');};await c.send('maybe');
  sim.status=async()=>{throw new RequestRefusal(404,'not_found');};sim.reconcile=async()=>{throw new Error('unavailable');};
  await c.poll();expect(c.active).toBe(true);
  sim.reconcile=async(session,turn)=>({session_id:session,turn_id:turn,status:'rejected'});await c.poll();expect(c.active).toBe(false);
});
it('existing uncertain snapshot remains blocked and never calls reconciliation',async()=>{
  const {c,sim}=await setup();await c.send('wait');const reconcile=vi.spyOn(sim,'reconcile');
  sim.status=async(session,turn)=>({session_id:session,turn_id:turn,status:'uncertain'});await c.poll();expect(c.active).toBe(true);expect(reconcile).not.toHaveBeenCalled();
});
it('display failure can be probed and recovered without replacing transport',async()=>{
  const {c,sim}=await setup();const show=sim.show.bind(sim);sim.show=async()=>{throw new Error('BLE lost');};await c.dismiss();
  await vi.waitFor(()=>expect(c.state).toBe('error'));sim.show=show;await c.connect();await c.start();expect(sim.recording).toBe(true);await c.cancel();
});
it('identical status polls do not send duplicate display writes',async()=>{
  const {c,sim}=await setup();await c.send('wait');await c.poll();await new Promise(r=>setTimeout(r,0));const show=vi.spyOn(sim,'show');
  await c.poll();await c.poll();await new Promise(r=>setTimeout(r,0));expect(show).not.toHaveBeenCalled();
});
it('truncation marker survives maximum output, newlines and Unicode are bounded',async()=>{
  const {c,sim}=await setup();sim.submit=async(session,turn)=>({session_id:session,turn_id:turn,status:'completed',output:'x'.repeat(32000),truncated:true});
  await c.send('long');expect(c.answer.at(-1)).toContain('truncated');
  const text='line\n'.repeat(100);const p=pages(text);expect(p.join('')).toBe(text);expect(p.every(s=>s.split('\n').length<=7)).toBe(true);
  expect(pages('😀'.repeat(32001)).join('')).toBe('😀'.repeat(32000));
});
it('speech is visible on phone, and a failed microphone stop is not mislabeled STT',async()=>{
  const {c,sim}=await setup();await c.start();c.audio(new Uint8Array(10));await c.finish();expect(c.transcript).toContain('Synthetic voice');
  await c.start();sim.audio=async()=>{throw new Error('stop failed');};await c.finish();expect(c.message).toContain('Microphone stop unconfirmed');expect(c.transcript).toBe('');
});
it('HTTP refusals carry only bounded safe status/code, never arbitrary error contents',async()=>{
  const api=new HttpTransport('https://g2.example.com','synthetic-device-token-not-a-secret-0000001');
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({error:'session_capacity_operator_cleanup_required'}),{status:429}));
  await expect(api.health()).rejects.toMatchObject({status:429,code:'session_capacity_operator_cleanup_required'});
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({error:'private text <unsafe>'}),{status:500}));
  await expect(api.health()).rejects.toMatchObject({status:500,code:'request_refused'});
});
it('missing saved session cannot be recreated on repeated connect or restored controller',async()=>{
  const {sim}=await setup();const saved={session:crypto.randomUUID(),turn:crypto.randomUUID()};
  const session=vi.spyOn(sim,'session').mockImplementation(async(_id,existing)=>{
    if(existing)throw new RequestRefusal(409,'session_continuity_lost');return {};
  });
  const reconcile=vi.spyOn(sim,'reconcile');
  for(let reload=0;reload<2;reload++){
    const c=new Controller(sim,sim,{...saved},()=>{},()=>{});await c.connect();await c.connect();await c.poll();
    expect(c.active).toBe(true);expect(c.continuityLost).toBe(true);expect(c.message).toContain('Outcome unknown');
    await c.forgetLostSession(false);expect(c.resume.turn).toBe(saved.turn);
  }
  expect(reconcile).not.toHaveBeenCalled();expect(session.mock.calls.every(args=>args[1]===true)).toBe(true);
  const c=new Controller(sim,sim,{...saved},()=>{},()=>{});await c.connect();await c.forgetLostSession(true);
  expect(c.resume.session).not.toBe(saved.session);expect(c.resume.turn).toBeUndefined();expect(c.active).toBe(false);
});
it('root exit remains available after unconfirmed microphone close',async()=>{
  const {c,sim}=await setup();await c.start();sim.audio=async()=>{throw new Error('close failed');};const exit=vi.spyOn(sim,'exit');
  await c.gesture({textEvent:{eventType:3}});expect(exit).toHaveBeenCalledOnce();expect(c.message).toContain('stop unconfirmed');
});
it('health omits new protocol header for real legacy CORS negotiation',async()=>{
  const fetch=vi.fn(async()=>new Response(JSON.stringify({protocol:2}),{status:200}));vi.stubGlobal('fetch',fetch);
  const api=new HttpTransport('https://g2.example.com','synthetic-device-token-not-a-secret-0000001');
  await api.health();expect((fetch.mock.calls[0] as any)[1].headers['X-Hermes-G2-Protocol']).toBeUndefined();
  await api.session(crypto.randomUUID());expect((fetch.mock.calls[1] as any)[1].headers['X-Hermes-G2-Protocol']).toBe('2');
});
it('unknown-run stop refusal is not retried on every unchanged poll',async()=>{
  const {c,sim}=await setup();await c.send('wait');
  sim.status=async(session,turn)=>({session_id:session,turn_id:turn,status:'uncertain'});
  const stop=vi.spyOn(sim,'stop').mockRejectedValue(new RequestRefusal(409,'submission_uncertain_use_server'));
  await c.cancel();await c.poll();await c.poll();expect(stop).toHaveBeenCalledOnce();expect(c.resume.stopRequested).toBe(true);
});
it('speech rejected before submit leaves transcription state with truthful feedback',async()=>{
  const {c,sim}=await setup();await c.start();c.audio(new Uint8Array(10));
  sim.transcribe=async()=>{c.connected=false;return 'not sent';};await c.finish();expect(c.state).toBe('error');expect(c.message).toContain('not submitted');expect(sim.texts).toHaveLength(0);
});
