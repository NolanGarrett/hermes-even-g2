import {AudioInputSource, CreateStartUpPageContainer, TextContainerProperty, TextContainerUpgrade, waitForEvenAppBridge, type EvenAppBridge} from '@evenrealities/even_hub_sdk';
import type {Controller, Display} from './controller';

export async function bounded<T>(promise:Promise<T>,ms=5000):Promise<T> {
  let timer:ReturnType<typeof setTimeout>;
  try {return await Promise.race([promise,new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(new Error('SDK timeout')),ms);})]);}
  finally {clearTimeout(timer!);}
}
export class Glasses implements Display {
  private constructor(readonly bridge:EvenAppBridge,readonly preview:(text:string)=>void){}
  static async open(preview:(text:string)=>void) {
    const bridge=await bounded(waitForEvenAppBridge(),10000);
    const result=await bounded(bridge.createStartUpPageContainer(new CreateStartUpPageContainer({containerTotalNum:1,textObject:[new TextContainerProperty({
      containerID:1,containerName:'answer',xPosition:0,yPosition:0,width:576,height:288,
      paddingLength:8,isEventCapture:1,content:'Hermes G2\nConnect on your phone. Hardware unverified.'
    })]})));
    if(result!==0)throw new Error('G2 startup page refused');
    return new Glasses(bridge,preview);
  }
  async audio(open:boolean){
    if(!await bounded(this.bridge.audioControl(open,AudioInputSource.Glasses)))throw new Error('G2 microphone operation refused');
  }
  async show(text:string){
    this.preview(text);
    if(!await bounded(this.bridge.textContainerUpgrade(new TextContainerUpgrade({containerID:1,containerName:'answer',
      contentOffset:0,content:text}))))throw new Error('G2 display refused');
  }
  bind(controller:Controller){
    const off=this.bridge.onEvenHubEvent(event=>{
      if(event.audioEvent?.source===AudioInputSource.Glasses)controller.audio(event.audioEvent.audioPcm);
      void controller.gesture(event);
    });
    const offDevice=this.bridge.onDeviceStatusChanged(status=>{
      if(status.isDisconnected()||status.isConnectionFailed())void controller.background();
    });
    return ()=>{off();offDevice();};
  }
}
