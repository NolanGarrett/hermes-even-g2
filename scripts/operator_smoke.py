"""Operator-run live smoke. Sends two explicit prompts to YOUR configured broker.

Requires EVEN_G2_SMOKE_URL and EVEN_G2_DEVICE_TOKEN in memory-only environment.
Uses real configured STT only with --wav (16kHz/16-bit/mono, <=30s).
This does not change approval policy or automatically approve pending actions.
"""
import argparse
import asyncio
import os
import uuid
import wave
import aiohttp

async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wav',help='Optional non-sensitive 16kHz mono signed16 WAV; sends audio to configured STT provider')
    args=parser.parse_args()
    origin=os.environ['EVEN_G2_SMOKE_URL'].rstrip('/')
    if not origin.startswith('https://'):raise SystemExit('A trusted HTTPS broker is required')
    token=os.environ['EVEN_G2_DEVICE_TOKEN']
    sid=str(uuid.uuid4())
    async with aiohttp.ClientSession(headers={'Authorization':'Bearer '+token,'X-Hermes-G2-Protocol':'2'},timeout=aiohttp.ClientTimeout(total=35),trust_env=False) as http:
        async def request(method,path,**kw):
            async with http.request(method,origin+path,allow_redirects=False,**kw) as response:
                if response.status>=300:raise SystemExit(f'Broker refused ({response.status}); do not blindly retry')
                return await response.json()
        if (await request('GET','/health')).get('protocol')!=2:raise SystemExit('Matching protocol 2 broker required')
        await request('POST','/sessions',json={'session_id':sid})
        text='Remember the synthetic marker violet-g2. Use the terminal tool to run exactly printf G2_TOOL_OK in your configured test workspace, then report the result. Do not perform any other action.'
        if args.wav:
            with wave.open(args.wav) as audio:
                if (audio.getframerate(),audio.getsampwidth(),audio.getnchannels())!=(16000,2,1) or audio.getnframes()>480000:raise SystemExit('Expected <=30s 16kHz signed16 mono WAV')
                pcm=audio.readframes(audio.getnframes())
            text=(await request('POST','/transcribe',data=pcm,headers={'Content-Type':'application/octet-stream'}))['text']
        for prompt in [text,'What was the synthetic marker and the real tool result in our previous turn? Do not call another tool.']:
            tid=str(uuid.uuid4());path=f'/sessions/{sid}/turns'
            await request('POST',path,json={'turn_id':tid,'text':prompt})
            for _ in range(120):
                s=await request('GET',path+'/'+tid)
                if s['status']=='waiting_for_approval' or s.get('handoff'):raise SystemExit('Approval requires trusted phone/server review; no automatic approval. Inspect session '+sid)
                if s['status'] in {'completed','failed','cancelled','interrupted','rejected','uncertain','unknown'}:
                    print('Status:',s['status'],'Session:',sid,'Turn:',tid)
                    if s['status']!='completed':raise SystemExit('Inspect exact run before retrying')
                    print('Answer:',s.get('output',''));break
                await asyncio.sleep(1)
            else:raise SystemExit('Timed out; work may continue. Inspect session '+sid)
    print('Live transport finished. Independently inspect actual tool event/result and follow-up; model prose alone is not proof.')

if __name__=='__main__':asyncio.run(main())
