import {Controller,type Resume} from './controller';
import {HttpTransport} from './http';
import {Glasses} from './glasses';
import {Simulator} from './simulator';
import './style.css';

const el=<T extends HTMLElement>(id:string)=>document.getElementById(id) as T;
const simulator=new URLSearchParams(location.search).get('simulator')==='1';
let controller:Controller|undefined;
let transport:HttpTransport|undefined;
let connecting=false;
let boundOrigin='';
let approvalKey='';
const preview=(text:string)=>{el('display').textContent=text;};
const status=(text:string)=>{el('status').textContent=text;};
// Native page lifetime is independent of backend connection/token lifetime.
// Cache rejection too: a timed-out native startup must not be sent twice.
const glassesReady=simulator?undefined:Glasses.open(preview,()=>controller);
void glassesReady?.catch(()=>status('Glasses startup unavailable. Check Even App/connection, then close and reopen the app.'));

function changed(){
  if(!controller)return;
  el('state').textContent=controller.state;
  status(controller.message);
  el('heard').textContent=controller.transcript?`Recognized speech — see request status: ${controller.transcript}`:'';
  el<HTMLButtonElement>('forget-lost').hidden=!controller.continuityLost;
  el('session').textContent=`Session: ${controller.resume.session}\nTurn: ${controller.resume.turn??'none'}`;
  const key=JSON.stringify(controller.approvals);
  const area=el('approvals');
  if(key!==approvalKey){
    approvalKey=key;area.replaceChildren();
    for(const p of controller.approvals){
    const article=document.createElement('article');
    const text=document.createElement('pre');text.textContent=p.description;article.append(text);
    const hint=document.createElement('p');hint.textContent='Read the complete request above. Approval is for this prompt and generation only; never approve an action you did not intend.';article.append(hint);
    for(const choice of ['deny','once'] as const){
      const button=document.createElement('button');button.textContent=choice==='once'?'Approve once':'Deny';
      button.onclick=()=>void controller?.decision(p,choice);article.append(button);
    }
    area.append(article);
    }
  }
  el<HTMLButtonElement>('record').disabled=!controller.connected||controller.active||controller.state==='transcribing';
  el<HTMLButtonElement>('record').textContent=controller.state==='listening'?'Finish & send':'Tap to speak';
  el<HTMLButtonElement>('send').disabled=!controller.connected||controller.active||['listening','transcribing'].includes(controller.state);
}
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function restore(key:string):Resume|undefined {
  try{const s=JSON.parse(localStorage.getItem(key)||'null');
    if(s&&UUID.test(s.session)&&(!s.turn||UUID.test(s.turn)))return {session:s.session,...(s.turn?{turn:s.turn}:{}),...(s.stopRequested===true?{stopRequested:true}:{})};
  }catch{}return undefined;
}
async function connect(){
  const requestedOrigin=el<HTMLInputElement>('endpoint').value.trim();
  if(connecting||(controller?.active&&boundOrigin!==requestedOrigin)){status('Reconcile the active turn before changing connection.');return;}
  connecting=true;
  try{
    if(controller&&boundOrigin===requestedOrigin){
      const token=el<HTMLInputElement>('token').value;
      if(token&&transport){transport.replaceToken(token);el<HTMLInputElement>('token').value='';}
      await controller.connect();return;
    }
    if(controller&&!await controller.discard())return;
    const origin=el<HTMLInputElement>('endpoint').value.trim();
    const key=`hermes-g2-resume:${origin}`;
    const token=el<HTMLInputElement>('token').value;

    if(simulator){
      const sim=new Simulator(preview);
      controller=new Controller(sim,sim,undefined,()=>{},changed);
    }else{
      const nextTransport=new HttpTransport(origin,token);
      transport?.forget();transport=nextTransport;
      el<HTMLInputElement>('token').value='';
      status('Waiting for Even App bridge. Open inside Even Hub, not Safari.');
      const glasses=await glassesReady!;
      controller=new Controller(transport,glasses,restore(key),s=>{
        try{localStorage.setItem(key,JSON.stringify(s));}catch{status('Resume storage unavailable. Keep this page open until the run finishes.');}
      },changed);

    }
    boundOrigin=origin;
    await controller.connect();
  }catch(e){status(e instanceof Error?e.message:'Connection failed');}
  finally{connecting=false;}
}
el('connect').onclick=()=>void connect();
el('reconnect').onclick=()=>void controller?.connect();
el('record').onclick=()=>void (controller?.state==='listening'?controller.finish():controller?.start());
el('cancel').onclick=()=>void controller?.cancel();
el('dismiss').onclick=()=>void controller?.dismiss();
el('new').onclick=()=>void controller?.newSession();
el('forget-lost').onclick=()=>void controller?.forgetLostSession(window.confirm('This forgets only the lost local session. Earlier work may have run. Inspect the retired ledger/Hermes first; do not repeat unknown actions. Continue with a new conversation?'));
el('previous').onclick=()=>controller?.scroll(-1);
el('next').onclick=()=>controller?.scroll(1);
el('send').onclick=()=>{const input=el<HTMLTextAreaElement>('text');const text=input.value;input.value='';void controller?.send(text);};
el('disconnect').onclick=async()=>{
  if(controller&&!await controller.discard())return;
  transport?.forget();
  if(controller)controller.connected=false;
  status('Disconnected locally. Backend work, if any, continues. Re-enter token to recover after reload.');
  // Do not delete resume identifiers: reload with token restores status, never replays an action.
  controller=undefined;approvalKey='';el('approvals').replaceChildren();el('heard').textContent='';el('session').textContent='';el('state').textContent='offline';
  el('forget-lost').hidden=true;
  const text='DISCONNECTED\nMicrophone stopped; backend may still be running.\nOpen phone to reconnect; double tap to exit.';
  preview(text);void glassesReady?.then(g=>g.show(text)).catch(()=>status('Glasses display unavailable. Close from Even App.'));
};
setInterval(()=>{if(controller?.active)void controller.poll();},1500);
document.addEventListener('visibilitychange',()=>{if(document.hidden)void controller?.background();else if(controller?.active)void controller.poll();});
window.addEventListener('pagehide',()=>{void controller?.background();transport?.forget();});
window.addEventListener('offline',()=>void controller?.background());
if(simulator){
  el('mode').textContent='SOFTWARE SIMULATOR — mock STT, inference and tools. No hardware.';
  el('credentials').hidden=true;el('simulation').hidden=false;
  el('synthetic').onclick=()=>{if(controller?.state==='listening')controller.audio(new Uint8Array(3200));};
  for(const [id,event] of Object.entries({tap:{textEvent:{}},hold:{sysEvent:{eventType:9}},release:{sysEvent:{eventType:10}},double:{textEvent:{eventType:3}}})){
    el(id).onclick=()=>void controller?.gesture(event);
  }
  void connect();
}
