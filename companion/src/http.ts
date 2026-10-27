import type {Transport,Snapshot,Approval} from './controller';
import manifest from '../app.json';

export class RequestRefusal extends Error {
  constructor(readonly status:number,readonly code:string){super(`Request refused (${status}: ${code}). Reconcile before a new request.`);}
}

export class HttpTransport implements Transport {
  constructor(readonly origin:string, private token:string) {
    const u=new URL(origin);
    const allowed=manifest.permissions.find(p=>p.name==='network')?.whitelist??[];
    const local=import.meta.env.DEV&&['127.0.0.1','localhost','[::1]'].includes(u.hostname)&&u.protocol==='http:';
    if(u.origin!==origin||u.username||u.password||(!local&&(u.protocol!=='https:'||!allowed.includes(origin))))
      throw new Error('Endpoint must be an exact HTTPS origin in app.json. Rebuild for your server.');
    if(token.length<32||token.length>256)throw new Error('Enter the device token, not a Hermes/provider key.');
  }
  forget(){this.token='';}
  replaceToken(token:string){if(token.length<32||token.length>256)throw new Error('Enter a valid device token.');this.token=token;}
  private async request(path:string,method='GET',body?:unknown,signal?:AbortSignal):Promise<any> {
    const abort=new AbortController();
    const timer=setTimeout(()=>abort.abort(),35000);
    const cancel=()=>abort.abort();signal?.addEventListener('abort',cancel,{once:true});
    if(signal?.aborted)abort.abort();
    try {
      const binary=body instanceof Uint8Array;
      const r=await fetch(this.origin+path,{method,headers:{Authorization:`Bearer ${this.token}`,
        ...(path!=='/health'?{'X-Hermes-G2-Protocol':'2'}:{}),
        ...(body!==undefined?{'Content-Type':binary?'application/octet-stream':'application/json'}:{})},
        body:body===undefined?undefined:binary?new Blob([body as Uint8Array<ArrayBuffer>]):JSON.stringify(body),
        signal:abort.signal,credentials:'omit',redirect:'error',cache:'no-store',referrerPolicy:'no-referrer'});
      if(!r.body)throw new Error('Missing response body');
      const reader=r.body.getReader();const decoder=new TextDecoder();let text='',bytes=0;
      try {while(true){const {value,done}=await reader.read();if(done)break;
        bytes+=value.byteLength;if(bytes>200000){await reader.cancel();throw new Error('Response too large');}
        text+=decoder.decode(value,{stream:true});}text+=decoder.decode();}
      finally {reader.releaseLock();}
      const result=JSON.parse(text);
      if(!r.ok)throw new RequestRefusal(r.status,
        typeof result.error==='string'&&/^[a-z0-9_]{1,100}$/.test(result.error)?result.error:'request_refused');
      return result;
    } finally {clearTimeout(timer);signal?.removeEventListener('abort',cancel);}
  }
  async health(){const result=await this.request('/health');if(result.protocol!==2)throw new RequestRefusal(426,'matching_protocol_2_broker_required');return result;}
  session(id:string,existing=false){return existing?this.request(`/sessions/${id}`):this.request('/sessions','POST',{session_id:id});}
  async transcribe(pcm:Uint8Array,signal:AbortSignal){return (await this.request('/transcribe','POST',pcm,signal)).text as string;}
  submit(session:string,turn:string,text:string):Promise<Snapshot>{return this.request(`/sessions/${session}/turns`,'POST',{turn_id:turn,text});}
  status(session:string,turn:string):Promise<Snapshot>{return this.request(`/sessions/${session}/turns/${turn}`);}
  reconcile(session:string,turn:string):Promise<Snapshot>{return this.request(`/sessions/${session}/turns/${turn}/reconcile`,'POST',{});}
  stop(session:string,turn:string){return this.request(`/sessions/${session}/turns/${turn}/stop`,'POST',{});}
  approve(session:string,turn:string,p:Approval,choice:'once'|'deny'){
    return this.request(`/sessions/${session}/turns/${turn}/approval`,'POST',{
      request_id:p.request_id,execution_generation:p.execution_generation,choice});
  }
}
