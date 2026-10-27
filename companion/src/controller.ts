import {RequestRefusal} from './http';

export type State = 'idle'|'listening'|'transcribing'|'working'|'answering'|'approval'|'offline'|'error';
export type Approval = {request_id:string; execution_generation:number; description:string};
export type Snapshot = {turn_id:string; session_id:string; status:string; output?:string; truncated?:boolean;
  approvals?:Approval[]; handoff?:string; message?:string; stop_requested?:boolean;
  progress?:{event:string; text:string}};
export interface Transport {
  health():Promise<unknown>;
  session(id:string,existing?:boolean):Promise<unknown>;
  transcribe(pcm:Uint8Array, signal:AbortSignal):Promise<string>;
  submit(session:string, turn:string, text:string):Promise<Snapshot>;
  status(session:string, turn:string):Promise<Snapshot>;
  reconcile(session:string, turn:string):Promise<Snapshot>;
  stop(session:string, turn:string):Promise<unknown>;
  approve(session:string, turn:string, approval:Approval, choice:'once'|'deny'):Promise<unknown>;
}
export interface Display {
  audio(open:boolean):Promise<void>;
  show(text:string):Promise<void>;
  exit():Promise<void>;
}
export interface Resume {session:string; turn?:string; stopRequested?:boolean}
export const MAX_PCM = 960000;
const terminal = new Set(['completed','failed','cancelled','interrupted','rejected']);

export function pages(text:string, size=260):string[] {
  const chars = Array.from(text.replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '')).slice(0,32000);
  const result:string[] = [];
  while(chars.length) {
    let n = Math.min(size, chars.length);
    // Conservative estimate, not a claim about physical font metrics.
    let row=1,column=0;
    for(let i=0;i<n;i++){
      if(chars[i]==='\n'){row++;column=0;}
      else if(++column>42){row++;column=1;}
      if(row>7){n=Math.max(1,i);break;}
    }
    if (n < chars.length) {
      const space = chars.slice(0,n).lastIndexOf(' ');
      if (space > n/2) n = space+1;
    }
    result.push(chars.splice(0,n).join(''));
  }
  return result.length ? result : ['No text returned.'];
}

export class Controller {
  state:State = 'idle';
  message = 'Tap to speak. Double tap cancels. Swipe changes page.';
  transcript = '';
  answer:string[] = [];
  page = 0;
  approvals:Approval[] = [];
  resume:Resume;
  active = false;
  connected = false;
  continuityLost = false;
  stopRequested = false;
  private stopAcknowledged = false;
  private stopSending = false;
  private stopBlocked = false;
  private submitting = false;
  private microphonePending = false;
  private displayHealthy = true;
  private epoch = 0;
  private chunks:Uint8Array[] = [];
  private bytes = 0;
  private captureTimer?:ReturnType<typeof setTimeout>;
  private abort?:AbortController;
  private micQueue:Promise<void> = Promise.resolve();
  private painting:Promise<void> = Promise.resolve();
  private painted = '';
  private exiting = false;
  private polling = false;
  private busyGesture = false;
  private lastTap = 0;
  constructor(readonly api:Transport, readonly display:Display, saved:Resume|undefined,
              readonly save:(state:Resume)=>void, readonly changed:()=>void) {
    this.resume = saved ?? {session:crypto.randomUUID()};
    this.active = Boolean(this.resume.turn);
    this.stopRequested = Boolean(this.resume.stopRequested);
  }
  private async mic(open:boolean) {
    const next = this.micQueue.catch(()=>{}).then(async()=>{
      await this.display.audio(open);
      this.microphonePending=open;
    });
    this.micQueue = next;
    return next;
  }
  private render() {
    this.changed();
    if(!this.displayHealthy)return;
    const text = this.state === 'answering'
      ? `${this.page+1}/${this.answer.length}\n${this.answer[this.page]}`
      : `${this.state.toUpperCase()}\n${this.message}`;
    // Sequential SDK writes avoid out-of-order display completion.
    this.painting = this.painting.catch(()=>{}).then(async()=>{
      if(!this.displayHealthy||text===this.painted)return;
      await this.display.show(text);this.painted=text;
    }).catch(()=>{
      this.displayHealthy=false;
      this.state = 'error'; this.message = 'Display disconnected. Stopping microphone; check phone.';
      this.changed(); void this.discard();
    });
  }
  private set(state:State,message:string) {this.state=state;this.message=message;this.render();}
  async connect() {
    if(!await this.discard())return;
    try {
      await this.painting;
      if(!this.displayHealthy){await this.display.show('RECONNECTING\nChecking status, never replaying work.');this.displayHealthy=true;this.painted='';}
      await this.api.health();
      await this.api.session(this.resume.session,Boolean(this.resume.turn));
      this.continuityLost=false;
      this.connected = true;
      this.save(this.resume);
      if (this.resume.turn) await this.poll();
      else this.set('idle','Tap to speak. Hold/release also supported.');
    } catch(e) {
      this.connected=false;
      if(e instanceof RequestRefusal&&e.code==='session_continuity_lost'){
        this.continuityLost=true;
        this.set('error','Broker has no accessible record of this session. Outcome unknown: inspect retired ledger/Hermes. Never repeat blindly.');
      }else this.set('offline',e instanceof RequestRefusal?e.message:'Connection failed. Check token, TLS, origin and network.');
    }
  }
  async start() {
    if (!this.connected || this.active || this.exiting || this.microphonePending || !this.displayHealthy || ['listening','transcribing'].includes(this.state)) return;
    const epoch = ++this.epoch;
    this.chunks=[];this.bytes=0;this.answer=[];this.approvals=[];this.transcript='';
    this.microphonePending=true;
    this.set('listening','Listening (30 seconds max). Tap to send; double tap discards.');
    this.captureTimer=setTimeout(()=>void this.finish(),30000);
    try {
      await this.mic(true);
      if(epoch!==this.epoch) await this.mic(false);
    } catch {await this.discard();this.set('error','Microphone could not start. Check G2 permission and connection.');}
  }
  audio(pcm:Uint8Array) {
    if(this.state!=='listening') return;
    if(pcm.byteLength%2 || this.bytes+pcm.byteLength>MAX_PCM) {void this.finish();return;}
    this.chunks.push(pcm.slice());this.bytes+=pcm.byteLength;
  }
  async finish() {
    if(this.state!=='listening') return;
    const epoch=this.epoch;
    clearTimeout(this.captureTimer);
    this.set('transcribing','Microphone stopping; transcribing speech.');
    try {
      try {await this.mic(false);} catch {
        this.set('error','Microphone stop unconfirmed. Close the app / disconnect glasses.');return;
      }
      if(epoch!==this.epoch) return;
      const pcm=new Uint8Array(this.bytes);
      let offset=0;for(const chunk of this.chunks){pcm.set(chunk,offset);offset+=chunk.length;}
      this.chunks=[];this.bytes=0;
      if(!pcm.length){this.set('error','No audio received. Check glasses microphone permission.');return;}
      this.abort=new AbortController();
      const text=await this.api.transcribe(pcm,this.abort.signal);
      if(epoch!==this.epoch) return;
      this.transcript=text;
      await this.send(text, true);
    } catch {if(epoch===this.epoch)this.set('error','Transcription failed. No agent request was submitted.');}
    finally {this.chunks=[];this.bytes=0;}
  }
  async send(text:string, fromSpeech=false) {
    if(this.active || this.exiting || !this.connected || !text.trim() || Array.from(text).length>8000 ||
       (['listening','transcribing'].includes(this.state) && !fromSpeech)) {
      if(fromSpeech)this.set('error','Recognized speech was not submitted. Check connection, length and current turn.');
      return;
    }
    this.active=true;this.stopRequested=false;this.stopAcknowledged=false;this.stopBlocked=false;this.approvals=[];this.submitting=true;
    delete this.resume.stopRequested;
    this.resume.turn=crypto.randomUUID();this.save(this.resume);
    if(!fromSpeech)this.transcript='';
    this.set('working',fromSpeech?`Heard: ${Array.from(text).slice(0,120).join('')}\nDouble tap stops (not rollback).`:'Request submitted. Double tap requests stop (not rollback).');
    try {
      const snap=await this.api.submit(this.resume.session,this.resume.turn,text);
      this.apply(snap);
    } catch(e) {this.set('offline',e instanceof RequestRefusal?e.message:'Submission outcome uncertain. Reconnect checks status; do not repeat.');}
    finally {this.submitting=false;if(this.stopRequested&&this.active)await this.requestStop();}
  }
  async discard() {
    ++this.epoch;clearTimeout(this.captureTimer);this.abort?.abort();
    this.chunks=[];this.bytes=0;
    if(!this.microphonePending)return true;
    try {await this.mic(false);} catch {
      this.set('error','Microphone stop unconfirmed. Close the app / disconnect glasses.');return false;
    }
    return true;
  }
  async cancel() {
    const stopped=await this.discard();
    if(this.active && this.resume.turn) {
      this.stopRequested=true;
      this.resume.stopRequested=true;this.save(this.resume);
      this.set('working','Stop requested; waiting for backend acknowledgement. Effects already performed remain.');
      if(!this.submitting)await this.requestStop();
    } else if(stopped) this.set('idle','Recording discarded. No new agent request.');
  }
  private async requestStop(){
    if(!this.resume.turn||this.stopSending||this.stopAcknowledged||this.stopBlocked||!this.active)return;
    this.stopSending=true;
    try {await this.api.stop(this.resume.session,this.resume.turn);this.stopAcknowledged=true;
      this.set('working','Backend accepted stop. Waiting for terminal status; this is not rollback.');
    } catch(e) {
      if(e instanceof RequestRefusal&&e.code==='submission_uncertain_use_server'){
        this.stopBlocked=true;this.set('error','Stop requires server inspection: submission outcome unknown. Stop intent retained; do not repeat.');
      }else this.set('offline','Stop not confirmed. Reconnect and inspect server; do not repeat the action.');
    }
    finally {this.stopSending=false;}
  }
  async dismiss() {
    if(!await this.discard())return;
    // Dismissal is not a cancellation of work already submitted.
    this.set(this.active?'working':'idle',this.active?'Display dismissed; backend continues. Use Stop to cancel.':'Tap to speak.');
  }
  async background() {
    if(this.microphonePending||this.state==='transcribing') {
      const ok=await this.discard();
      if(ok)this.set('idle','Recording discarded on background/exit.');
    }
  }
  async poll() {
    if(!this.resume.turn || this.polling || !this.connected || this.continuityLost) return;
    this.polling=true;
    try {
      let snapshot:Snapshot;
      try {snapshot=await this.api.status(this.resume.session,this.resume.turn);}
      catch(e){
        if(!(e instanceof RequestRefusal)||e.status!==404||e.code!=='not_found')throw e;
        // A bare 404 is not proof of non-submission: seal a missing intent
        // atomically so a delayed original POST cannot execute afterwards.
        snapshot=await this.api.reconcile(this.resume.session,this.resume.turn);
      }
      this.apply(snapshot);
      if(this.stopRequested&&!this.submitting)await this.requestStop();}
    catch {this.set('offline','Status unavailable. Work may continue. Reconnect never resubmits.');}
    finally {this.polling=false;}
  }
  private apply(s:Snapshot) {
    if(s.session_id!==this.resume.session || s.turn_id!==this.resume.turn) {
      this.set('error','Response identity mismatch. Stop using this connection.');this.connected=false;return;
    }
    this.approvals=s.approvals??[];
    if(!['uncertain','unknown'].includes(s.status))this.stopBlocked=false;
    if(terminal.has(s.status)) {
      this.active=false;
      delete this.resume.stopRequested;this.save(this.resume);
      if(s.status==='completed') {
        this.answer=pages(s.output||'No text returned.');
        if(s.truncated)this.answer.push('[Display truncated. Full answer in Hermes.]');
        this.page=0;this.set('answering','');
      } else if(s.status==='rejected') {
        this.set('idle','Not submitted. This intent is sealed against delayed delivery. Fix the connection, then start a new turn.');
      } else this.set(s.status==='cancelled'?'idle':'error',
          s.status==='cancelled'?'Backend confirmed cancelled. Earlier effects are not undone.':`Backend ${s.status}. Inspect Hermes before repeating.`);
    } else if(s.status==='waiting_for_approval' || s.handoff) {
      this.set('approval',s.handoff??'Approval needed. Open phone, read full request, choose once or deny.');
    } else if(['uncertain','unknown'].includes(s.status)) {
      this.set('error','Outcome unknown. Inspect exact session in Hermes. Do not repeat or reset to retry.');
    } else {
      this.set('working',s.status==='stopping'||this.stopRequested||s.stop_requested?'Stopping; awaiting terminal acknowledgement.':
        (s.message?s.message:s.progress?.event?.startsWith('tool.')?'Hermes is using a tool.':
        s.progress?.text?`Partial: ${s.progress.text.slice(-200)}`:'Hermes is working.'));
    }
  }
  async decision(approval:Approval,choice:'once'|'deny') {
    if(this.state!=='approval'||!this.resume.turn||!this.approvals.some(p=>
      p.request_id===approval.request_id&&p.execution_generation===approval.execution_generation)) return;
    this.approvals=[];this.render();
    try {await this.api.approve(this.resume.session,this.resume.turn,approval,choice);await this.poll();}
    catch {this.set('error','Decision not confirmed or stale. Reconcile on phone/server; never auto-approve.');}
  }
  async newSession() {
    if(this.active) {this.set('error','Resolve or stop the current turn before starting a new session.');return;}
    if(!await this.discard()) return;
    this.resume={session:crypto.randomUUID()};this.save(this.resume);this.answer=[];this.approvals=[];this.transcript='';
    await this.connect();
  }
  async forgetLostSession(acknowledged:boolean){
    if(!this.continuityLost||!acknowledged||!await this.discard())return;
    this.resume={session:crypto.randomUUID()};this.save(this.resume);
    this.active=false;this.stopRequested=false;this.stopBlocked=false;this.stopAcknowledged=false;
    this.continuityLost=false;this.answer=[];this.approvals=[];this.transcript='';
    await this.connect();
  }
  scroll(direction:number) {
    if(this.state!=='answering') return;
    this.page=Math.max(0,Math.min(this.answer.length-1,this.page+direction));this.render();
  }
  async gesture(event:{textEvent?:{eventType?:number};sysEvent?:{eventType?:number}}) {
    const sys=event.sysEvent?.eventType;
    if([4,5,6,7].includes(sys??-1)){await this.background();return;}
    if(sys===3||event.textEvent?.eventType===3){
      if(!this.exiting){
        this.exiting=true;
        try {
          const stopped=await this.discard();
          // Persist stop intent before the native dialog; do not wait for the
          // network to let users exit. Backend receipt is still not rollback.
          if(this.active){
            this.stopRequested=true;this.resume.stopRequested=true;this.save(this.resume);
            if(!this.submitting)void this.requestStop();
          }else if(stopped)this.set('idle','Recording discarded. Exit dialog requested.');
          await this.display.exit();
        }
        catch {this.set('error','Exit dialog unavailable. Close from the Even App.');}
        finally {this.exiting=false;}
      }
      return;
    }
    if(sys===9){await this.start();return;}
    if(sys===10){await this.finish();return;}
    if(!event.textEvent) return; // An absent event must never become a click.
    const kind=event.textEvent.eventType??0;

    if(kind===1){this.scroll(-1);return;}
    if(kind===2){this.scroll(1);return;}
    if(kind!==0||this.busyGesture||Date.now()-this.lastTap<250)return;
    this.lastTap=Date.now();this.busyGesture=true;
    try {if(this.state==='listening')await this.finish();else await this.start();}
    finally {this.busyGesture=false;}
  }
}
