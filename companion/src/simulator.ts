// Deterministic software harness. No live microphone, model, tools or network.
import type {Transport,Snapshot,Approval,Display} from './controller';
export class Simulator implements Transport,Display {
  recording=false;
  turns=new Map<string,Snapshot>();
  texts:string[]=[];
  constructor(readonly preview:(s:string)=>void){}
  async health(){return {simulated:true};}
  async session(_id:string,_existing=false){return {};}
  async audio(open:boolean){this.recording=open;}
  async show(text:string){this.preview(text);}
  async exit(){this.preview('SIMULATED system exit dialog. No native app was closed.');}
  async transcribe(_pcm:Uint8Array,_signal:AbortSignal){return 'Synthetic voice input from the simulator.';}
  async submit(session:string,turn:string,text:string){
    this.texts.push(text);
    const s:Snapshot={session_id:session,turn_id:turn,status:'running'};
    this.turns.set(turn,s);
    if(text.includes('approval')){
      s.status='waiting_for_approval';s.approvals=[{request_id:'synthetic-approval',execution_generation:1,
        description:'SIMULATED consent: a harmless demonstration tool. No real action will occur.'}];
    } else if(text.includes('error'))s.status='failed';
    else if(!text.includes('wait')){
      s.status='completed';s.output=text.includes('long')?
        'SIMULATED long answer. This demonstrates paginated plain text, not inference. '.repeat(45):
        `SIMULATED answer. Turn ${this.texts.length}. Prior simulator inputs: ${this.texts.slice(0,-1).join(' / ')||'none'}. Voice input and tools are mocked.`;
    }
    return {...s};
  }
  async status(_session:string,turn:string){const s=this.turns.get(turn);if(!s)throw new Error('Simulator resets on reload');return {...s};}
  async reconcile(session:string,turn:string){return this.status(session,turn);}
  async stop(_session:string,turn:string){const s=this.turns.get(turn);if(s)s.status='cancelled';return {};}
  async approve(_session:string,turn:string,_approval:Approval,choice:'once'|'deny'){
    const s=this.turns.get(turn)!;s.approvals=[];s.status='completed';s.output=`SIMULATED approval decision: ${choice}. No tool ran.`;return {};
  }
}
