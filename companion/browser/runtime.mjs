// Composed software-path test: real Controller + HttpTransport + broker + Hermes.
// Even bridge/PCM and model/STT providers are deterministic fixtures, NOT hardware/live AI.
import {build} from 'esbuild';
const bundle=await build({stdin:{contents:"export {Controller} from './src/controller'; export {HttpTransport} from './src/http';",resolveDir:process.cwd(),loader:'ts'},bundle:true,platform:'node',format:'esm',write:false,define:{'import.meta.env.DEV':'true'}});
const {Controller,HttpTransport}=await import('data:text/javascript;base64,'+Buffer.from(bundle.outputFiles[0].contents).toString('base64'));
const result=await (async (broker)=>{
    const api=new HttpTransport(broker,'synthetic-device-token-not-a-secret-0000001');
    const mic=[];const frames=[];
    const bridge={audio:async value=>{mic.push(value);},show:async text=>{frames.push(text);}};
    const c=new Controller(api,bridge,undefined,()=>{},()=>{});
    const until=async predicate=>{for(let i=0;i<240;i++){await c.poll();if(predicate())return;await new Promise(r=>setTimeout(r,100));}throw new Error('Runtime timeout: '+c.state+' '+c.message);};
    await c.connect();if(!c.connected)throw new Error(c.message);
    await c.gesture({textEvent:{eventType:0}});
    c.audio(new Uint8Array(3200));await c.finish();
    await until(()=>!c.active);
    if(c.state!=='answering'||!c.answer.join('').includes('G2_TOOL_OK'))throw new Error('Voice/tool failed: '+c.message);
    const session=c.resume.session;
    await c.send('followup-marker: recall our earlier marker and real tool result.');await until(()=>!c.active);
    if(!c.answer.join('').includes('violet-g2')||c.resume.session!==session)throw new Error('Context failed');
    for(const choice of ['deny','once']){
      await c.send('approval-fixture-'+choice);await until(()=>c.state==='approval'||!c.active);
      if(c.state!=='approval'||c.approvals.length!==1)throw new Error('No real pending approval: '+c.message);
      const pending=c.approvals[0];
      let refused=false;
      try{await api.approve(c.resume.session,c.resume.turn,{...pending,execution_generation:pending.execution_generation+1},'once');}catch{refused=true;}
      if(!refused)throw new Error('Stale approval accepted');
      await c.decision(pending,choice);await until(()=>!c.active);
      if(c.state!=='answering')throw new Error('Approval did not resume real run: '+c.message);
    }
    await c.discard();
    if(mic.at(-1)!==false)throw new Error('Microphone not closed');
    return {composed:true,synthetic_pcm:true,real_hermes_tool:true,context:true,real_approval_once_and_deny:true,stale_approval_refused:true,microphone_closed:true,display_updates:frames.length};
  })(process.env.G2_TEST_BROKER);
  console.log(JSON.stringify(result));
