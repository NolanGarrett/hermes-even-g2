import {AudioInputSource, CreateStartUpPageContainer, TextContainerProperty, TextContainerUpgrade, waitForEvenAppBridge, type EvenAppBridge} from '@evenrealities/even_hub_sdk';
import type {Controller, Display} from './controller';

export async function bounded<T>(promise:Promise<T>,ms=5000):Promise<T> {
  let timer:ReturnType<typeof setTimeout>;
  try {return await Promise.race([promise,new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(new Error('SDK timeout')),ms);})]);}
  finally {clearTimeout(timer!);}
}
export class Glasses implements Display {
  private audioUncertain=false;
  private constructor(readonly bridge:EvenAppBridge,readonly preview:(text:string)=>void){}
  static async open(preview:(text:string)=>void,current:()=>Controller|undefined=()=>undefined) {
    const ready=waitForEvenAppBridge().then(bridge=>{
      const glasses=new Glasses(bridge,preview);
      // Bind even if bridge readiness arrives after the caller timed out. Do
      // not leave a native page without root exit while startup is unresolved.
      glasses.bind(current);return glasses;
    });
    const glasses=await bounded(ready,10000);
    const result=await bounded(glasses.bridge.createStartUpPageContainer(new CreateStartUpPageContainer({containerTotalNum:1,textObject:[new TextContainerProperty({
      containerID:1,containerName:'answer',xPosition:0,yPosition:0,width:576,height:288,
      paddingLength:8,isEventCapture:1,content:'Hermes G2\nOpen phone and enter device token.\nDouble tap to exit. Hardware unverified.'
    })]})));
    if(result!==0)throw new Error('G2 startup page refused');
    return glasses;
  }
  async audio(open:boolean){
    if(open&&this.audioUncertain)throw new Error('Prior microphone start remains uncertain; close the app.');
    const operation=this.bridge.audioControl(open,AudioInputSource.Glasses);
    try {
      if(!await bounded(operation))throw new Error('G2 microphone operation refused');
    }catch(error){
      if(open){
        this.audioUncertain=true;
        // A timeout does not cancel native work. Close again after a late open,
        // and forbid another capture until that compensating close succeeds.
        void operation.then(()=>bounded(this.bridge.audioControl(false,AudioInputSource.Glasses))).then(ok=>{
          if(ok)this.audioUncertain=false;
        }).catch(()=>{});
      }
      throw error;
    }
  }
  async exit(){if(!await bounded(this.bridge.shutDownPageContainer(1)))throw new Error('G2 exit dialog refused');}
  async show(text:string){
    this.preview(text);
    if(!await bounded(this.bridge.textContainerUpgrade(new TextContainerUpgrade({containerID:1,containerName:'answer',
      content:text}))))throw new Error('G2 display refused');
  }
  private bind(current:()=>Controller|undefined){
    const disconnected=new Set<string>();
    const off=this.bridge.onEvenHubEvent(event=>{
      const controller=current();
      if(!controller){
        if(event.textEvent?.eventType===3||event.sysEvent?.eventType===3)void this.exit().catch(()=>this.preview('Exit dialog unavailable; close from Even App.'));
        return;
      }
      if(event.audioEvent?.source===AudioInputSource.Glasses)controller.audio(event.audioEvent.audioPcm);
      void controller.gesture(event);
    });
    const offDevice=this.bridge.onDeviceStatusChanged(status=>{
      const controller=current();if(!controller)return;
      if(status.isDisconnected()||status.isConnectionFailed()){
        disconnected.add(status.sn);void controller.background();
      }else if(status.isConnected()&&!['listening','transcribing'].includes(controller.state)&&disconnected.delete(status.sn)){
        void controller.connect();
      }
    });
    return ()=>{off();offDevice();};
  }
}
