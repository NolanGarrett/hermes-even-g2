import {Controller,type Resume} from './controller';
import {HttpTransport} from './http';
import {Glasses} from './glasses';
import {Simulator} from './simulator';
import './style.css';

const el=<T extends HTMLElement>(id:string)=>document.getElementById(id) as T;
const simulator=new URLSearchParams(location.search).get('simulator')==='1';
let controller:Controller|undefined;
let transport:HttpTransport|undefined;
let unbind=()=>{};
let connecting=false;
let boundOrigin='';
const preview=(text:string)=>{el('display').textContent=text;};
const status=(text:string)=>{el('status').textContent=text;};

function changed(){
  if(!controller)return;
  el('state').textContent=controller.state;
  status(controller.message);
  el('session').textContent=`Session: ${controller.resume.session}\nTurn: ${controller.resume.turn??'none'}`;
  const area=el('approvals');area.replaceChildren();
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
    if(controller&&!await controller.discard())return;
    unbind();transport?.forget();
    const origin=el<HTMLInputElement>('endpoint').value.trim();
    boundOrigin=origin;
    const key=`hermes-g2-resume:${origin}`;
    const token=el<HTMLInputElement>('token').value;
    el<HTMLInputElement>('token').value='';
    if(simulator){
      const sim=new Simulator(preview);
      controller=new Controller(sim,sim,undefined,()=>{},changed);
    }else{
      transport=new HttpTransport(origin,token);
      status('Waiting for Even App bridge. Open inside Even Hub, not Safari.');
      const glasses=await Glasses.open(preview);
      controller=new Controller(transport,glasses,restore(key),s=>{
        try{localStorage.setItem(key,JSON.stringify(s));}catch{status('Resume storage unavailable. Keep this page open until the run finishes.');}
      },changed);
      unbind=glasses.bind(controller);
    }
    await controller.connect();
  }catch(e){status(e instanceof Error?e.message:'Connection failed');transport?.forget();}
  finally{connecting=false;}
}
el('connect').onclick=()=>void connect();
el('reconnect').onclick=()=>void controller?.connect();
el('record').onclick=()=>void (controller?.state==='listening'?controller.finish():controller?.start());
el('cancel').onclick=()=>void controller?.cancel();
el('dismiss').onclick=()=>void controller?.dismiss();
el('new').onclick=()=>void controller?.newSession();
el('previous').onclick=()=>controller?.scroll(-1);
el('next').onclick=()=>controller?.scroll(1);
el('send').onclick=()=>{const input=el<HTMLTextAreaElement>('text');const text=input.value;input.value='';void controller?.send(text);};
el('disconnect').onclick=async()=>{
  if(controller&&!await controller.discard())return;
  unbind();transport?.forget();
  if(controller)controller.connected=false;
  status('Disconnected locally. Backend work, if any, continues. Re-enter token to recover after reload.');
  // Do not delete resume identifiers: reload with token restores status, never replays an action.
  controller=undefined;preview('DISCONNECTED\nMicrophone stopped; backend may still be running.');
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
