import {it,expect,vi,beforeEach,afterEach} from 'vitest';
import type {EvenHubEvent,DeviceStatus} from '@evenrealities/even_hub_sdk';
const mock=vi.hoisted(()=>({
  createStartUpPageContainer:vi.fn(async()=>0),textContainerUpgrade:vi.fn(async()=>true),
  audioControl:vi.fn(async(_open:boolean,_source?:string)=>true),shutDownPageContainer:vi.fn(async()=>true),
  onEvenHubEvent:vi.fn((_cb:(event:EvenHubEvent)=>void)=>()=>{}),onDeviceStatusChanged:vi.fn((_cb:(status:DeviceStatus)=>void)=>()=>{}),
  wait:vi.fn()
}));
vi.mock('@evenrealities/even_hub_sdk',async importOriginal=>({
  ...await importOriginal<typeof import('@evenrealities/even_hub_sdk')>(),waitForEvenAppBridge:()=>mock.wait()
}));
import {Glasses} from '../src/glasses';
import {Controller} from '../src/controller';
import {Simulator} from '../src/simulator';
beforeEach(()=>{vi.clearAllMocks();mock.wait.mockResolvedValue(mock);});
afterEach(()=>{vi.useRealTimers();});
it('actual SDK serializers create setup text and omit partial-update fields',async()=>{
  const g=await Glasses.open(()=>{});const start=mock.createStartUpPageContainer.mock.calls[0] as unknown as [{toJson:()=>Record<string,unknown>}];
  expect(JSON.stringify(start[0].toJson())).toContain('Open phone');
  await g.show('short');const update=mock.textContainerUpgrade.mock.calls[0] as unknown as [{toJson:()=>Record<string,unknown>}];
  expect(JSON.stringify(update[0].toJson())).not.toMatch(/contentOffset|ContentOffset|contentLength|ContentLength/);
  await g.exit();expect(mock.shutDownPageContainer).toHaveBeenCalledWith(1);
});
it('root handler survives pre-auth/disconnect; non-glasses audio is ignored',async()=>{
  let c:Controller|undefined;const g=await Glasses.open(()=>{},()=>c);
  const handler=mock.onEvenHubEvent.mock.calls[0][0];handler({textEvent:{eventType:3}} as EvenHubEvent);
  await vi.waitFor(()=>expect(mock.shutDownPageContainer).toHaveBeenCalledTimes(1));
  const sim=new Simulator(()=>{});c=new Controller(sim,g,undefined,()=>{},()=>{});const audio=vi.spyOn(c,'audio');
  handler({audioEvent:{source:'phone',audioPcm:new Uint8Array(10)}} as EvenHubEvent);expect(audio).not.toHaveBeenCalled();
  handler({audioEvent:{source:'glasses',audioPcm:new Uint8Array(10)}} as EvenHubEvent);expect(audio).toHaveBeenCalledTimes(1);
  c=undefined;handler({sysEvent:{eventType:3}} as EvenHubEvent);await vi.waitFor(()=>expect(mock.shutDownPageContainer).toHaveBeenCalledTimes(2));
});
it('late timed-out native open gets a compensating close and blocks new capture',async()=>{
  vi.useFakeTimers();const g=await Glasses.open(()=>{});let release:(ok:boolean)=>void=()=>{};
  mock.audioControl.mockImplementationOnce(()=>new Promise<boolean>(resolve=>{release=resolve;}));
  const open=g.audio(true);const rejected=expect(open).rejects.toThrow('SDK timeout');
  await vi.advanceTimersByTimeAsync(5001);await rejected;
  await expect(g.audio(true)).rejects.toThrow('uncertain');
  await g.audio(false);release(true);await vi.advanceTimersByTimeAsync(0);
  expect(mock.audioControl.mock.calls.map(c=>c[0])).toEqual([true,false,false]);
  await g.audio(true);await g.audio(false);
});
it('ordinary connected battery/status pushes do not reconnect or discard capture',async()=>{
  const sim=new Simulator(()=>{});const c=new Controller(sim,sim,undefined,()=>{},()=>{});
  await c.connect();await c.start();await Glasses.open(()=>{},()=>c);
  const connect=vi.spyOn(c,'connect');const handler=mock.onDeviceStatusChanged.mock.calls[0][0];
  const status={sn:'synthetic-g2',isDisconnected:()=>false,isConnectionFailed:()=>false,isConnected:()=>true} as DeviceStatus;
  handler(status);handler(status);expect(connect).not.toHaveBeenCalled();expect(sim.recording).toBe(true);
  handler({...status,isDisconnected:()=>true,isConnected:()=>false} as DeviceStatus);
  await vi.waitFor(()=>expect(sim.recording).toBe(false));
  await vi.waitFor(()=>expect(c.state).toBe('idle'));
  handler(status);await vi.waitFor(()=>expect(connect).toHaveBeenCalledOnce());handler(status);expect(connect).toHaveBeenCalledOnce();
});
it('root exit is bound before startup and survives a late startup result',async()=>{
  vi.useFakeTimers();let release:(code:number)=>void=()=>{};
  mock.createStartUpPageContainer.mockImplementationOnce(()=>new Promise<number>(resolve=>{release=resolve;}));
  const open=Glasses.open(()=>{});const rejected=expect(open).rejects.toThrow('SDK timeout');
  await vi.advanceTimersByTimeAsync(5001);await rejected;
  mock.onEvenHubEvent.mock.calls[0][0]({textEvent:{eventType:3}} as EvenHubEvent);
  await vi.advanceTimersByTimeAsync(0);expect(mock.shutDownPageContainer).toHaveBeenCalledWith(1);
  release(0);await vi.advanceTimersByTimeAsync(0);expect(mock.createStartUpPageContainer).toHaveBeenCalledOnce();
});
it('bridge arriving after readiness timeout still installs an exit handler without late startup',async()=>{
  vi.useFakeTimers();let release:(bridge:typeof mock)=>void=()=>{};
  mock.wait.mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;}));
  const open=Glasses.open(()=>{});const rejected=expect(open).rejects.toThrow('SDK timeout');
  await vi.advanceTimersByTimeAsync(10001);await rejected;release(mock);await vi.advanceTimersByTimeAsync(0);
  mock.onEvenHubEvent.mock.calls[0][0]({sysEvent:{eventType:3}} as EvenHubEvent);
  await vi.advanceTimersByTimeAsync(0);expect(mock.shutDownPageContainer).toHaveBeenCalledWith(1);expect(mock.createStartUpPageContainer).not.toHaveBeenCalled();
});
