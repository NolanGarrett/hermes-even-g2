"""Opt-in real public Hermes gateway integration with deterministic MODEL FIXTURE.

Run under the public v0.22.5 runtime with HERMES_TEST_ROOT pointing at its checkout.
No production HOME/config, credentials, memories or services are used.
"""
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import uuid
import io
import wave

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
import pytest
from even_g2.server import create_app
from test_protocol import cfg,TOKEN

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM=os.environ.get('HERMES_TEST_ROOT')
pytestmark=pytest.mark.skipif(not UPSTREAM,reason='Set HERMES_TEST_ROOT to public v0.22.5 checkout for real runtime tests')


def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def environment(home):
    # Deliberate allowlist: never inherit host credentials, routing, plugins or SSH variables.
    return {'PATH':str(Path(sys.executable).parent)+os.pathsep+os.defpath,
            'HOME':str(home),'HERMES_HOME':str(home),'TMPDIR':str(home/'tmp'),
            'LANG':'C.UTF-8','PYTHONUNBUFFERED':'1','API_SERVER_ENABLED':'true',
            'API_SERVER_HOST':'127.0.0.1','API_SERVER_KEY':'synthetic-backend-key-for-tests',
            'HERMES_TEST_MODEL_KEY':'synthetic-model-key'}


class ModelFixture:
    def __init__(self):self.requests=[];self.tool_seen=False;self.context_seen=False
    async def stt(self,request):
        reader=await request.multipart();part=await reader.next()
        with wave.open(io.BytesIO(await part.read())) as audio:
            assert audio.getframerate()==16000 and audio.getnchannels()==1
        return web.json_response({'text':'Remember violet-g2. Run the harmless terminal fixture.'})
    async def models(self,request):return web.json_response({'object':'list','data':[{'id':'g2-fixture','object':'model','context_length':128000}]})
    async def chat(self,request):
        b=await request.json();self.requests.append(b)
        messages=b['messages'];user=[m for m in messages if m.get('role')=='user'];last=str(user[-1].get('content',''))
        tools=[m for m in messages if m.get('role')=='tool']
        last_user=max(i for i,m in enumerate(messages) if m.get('role')=='user')
        if 'approval-fixture-' in last and not any(m.get('role')=='tool' for m in messages[last_user+1:]):
            name='approval-once' if 'approval-fixture-once' in last else 'approval-deny'
            message={'role':'assistant','content':None,'tool_calls':[{'id':'call_'+name,'type':'function','function':{'name':'terminal','arguments':json.dumps({'command':'chmod 777 '+name})}}]}
        elif 'approval-fixture-' in last:
            message={'role':'assistant','content':'MODEL_FIXTURE approval control received.'}
        elif 'followup-marker' in last:
            self.context_seen |= any('violet-g2' in str(m.get('content')) for m in user[:-1]) and bool(tools)
            message={'role':'assistant','content':'MODEL_FIXTURE followup violet-g2 with prior tool history.'}
        elif tools:
            self.tool_seen=any('G2_TOOL_OK' in str(m.get('content')) for m in tools)
            message={'role':'assistant','content':'MODEL_FIXTURE violet-g2; real terminal result received: G2_TOOL_OK.'}
        else:
            message={'role':'assistant','content':None,'tool_calls':[{'id':'call_g2','type':'function','function':{'name':'terminal','arguments':json.dumps({'command':'printf G2_TOOL_OK'})}}]}
        finish='tool_calls' if message.get('tool_calls') else 'stop'
        if b.get('stream'):
            delta={k:v for k,v in message.items() if v is not None}
            if 'tool_calls' in delta:delta['tool_calls']=[{'index':0,**delta['tool_calls'][0]}]
            pieces=[{'id':'chatcmpl-fixture','object':'chat.completion.chunk','model':'g2-fixture','choices':[{'index':0,'delta':delta,'finish_reason':None}]},
                    {'id':'chatcmpl-fixture','object':'chat.completion.chunk','model':'g2-fixture','choices':[{'index':0,'delta':{},'finish_reason':finish}],'usage':{'prompt_tokens':100,'completion_tokens':30,'total_tokens':130}}]
            return web.Response(text=''.join('data: '+json.dumps(p)+'\n\n' for p in pieces)+'data: [DONE]\n\n',content_type='text/event-stream')
        return web.json_response({'id':'chatcmpl-fixture','object':'chat.completion','created':0,'model':'g2-fixture','choices':[{'index':0,'message':message,'finish_reason':finish}],'usage':{'prompt_tokens':100,'completion_tokens':30,'total_tokens':130}})


async def wait_ready(url,proc,log):
    async with aiohttp.ClientSession() as h:
        for _ in range(180):
            if proc.poll() is not None:raise AssertionError('Isolated gateway exited: '+log.read_text()[-7000:])
            try:
                async with h.get(url+'/health') as r:
                    if r.status==200:return
            except aiohttp.ClientError:pass
            await asyncio.sleep(.5)
    raise AssertionError('Isolated gateway readiness timeout: '+log.read_text()[-7000:])


async def test_public_runtime_plugin_cli_real_tool_and_history(tmp_path):
    upstream=Path(UPSTREAM).resolve()
    assert subprocess.check_output(['git','describe','--tags','--exact-match'],cwd=upstream,text=True).strip()=='v0.22.5'
    home=tmp_path/'home';home.mkdir();(home/'tmp').mkdir();work=tmp_path/'work';work.mkdir()
    plugin=home/'plugins'/'hermes-even-g2';plugin.mkdir(parents=True)
    for name in ['__init__.py','plugin.yaml']:shutil.copy2(ROOT/name,plugin/name)
    shutil.copytree(ROOT/'even_g2',plugin/'even_g2',ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['approval-once','approval-deny']:
        marker=work/name;marker.write_text('synthetic approval fixture');marker.chmod(0o600)
    fixture=ModelFixture();mock=web.Application();mock.router.add_post('/v1/chat/completions',fixture.chat);mock.router.add_get('/v1/models',fixture.models);mock.router.add_post('/stt',fixture.stt)
    provider=TestServer(mock);await provider.start_server();api_port=port();api_url=f'http://127.0.0.1:{api_port}'
    broker_port=port();broker_url=f'http://127.0.0.1:{broker_port}'
    web_port=port();web_url=f'http://127.0.0.1:{web_port}'
    config={'model':{'provider':'custom','default':'g2-fixture','base_url':str(provider.make_url('/v1')),'key_env':'HERMES_TEST_MODEL_KEY','context_length':128000},
            'agent':{'max_turns':4},'terminal':{'backend':'local','cwd':str(work)},
            'toolsets':['terminal'],'gateway':{'api_server':{'enabled':True,'host':'127.0.0.1','port':api_port}},
            'plugins':{'enabled':['hermes-even-g2'],'entries':{'hermes-even-g2':{'settings':{'backend_url':api_url,'port':broker_port,'stt_url':str(provider.make_url('/stt')),'origins':['https://companion.example.com',web_url],'device_hashes':cfg(tmp_path).device_hashes}}}},
            'memory':{'provider':'none'},'security':{'allow_lazy_installs':False}}
    (home/'config.yaml').write_text(json.dumps(config))
    env=environment(home);env['API_SERVER_PORT']=str(api_port)
    cli=str(Path(sys.executable).parent/'hermes')
    doctor=await asyncio.to_thread(subprocess.run,[cli,'plugins','doctor',str(plugin),'--ci'],env=env,cwd=work,capture_output=True,text=True,timeout=60)
    assert doctor.returncode==0,doctor.stdout+doctor.stderr
    command=await asyncio.to_thread(subprocess.run,[cli,'even-g2','check'],env=env,cwd=work,capture_output=True,text=True,timeout=60)
    assert command.returncode==2 and 'EVEN_G2_BACKEND_KEY' in command.stdout,command.stdout+command.stderr
    log=tmp_path/'gateway.log';handle=log.open('w');proc=subprocess.Popen([cli,'gateway','run','--no-supervise'],env=env,cwd=work,stdout=handle,stderr=subprocess.STDOUT)
    client=None;broker_proc=None
    try:
        await wait_ready(api_url,proc,log)
        env['EVEN_G2_BACKEND_KEY']='synthetic-backend-key-for-tests'
        broker_proc=subprocess.Popen([cli,'even-g2','serve'],env=env,cwd=work,stdout=handle,stderr=subprocess.STDOUT)
        client=aiohttp.ClientSession(base_url=broker_url,headers={'Authorization':'Bearer '+TOKEN})
        for _ in range(60):
            try:
                async with client.get('/health') as response:
                    if response.status==200:break
            except aiohttp.ClientError:pass
            await asyncio.sleep(.25)
        r=await client.get('/health');assert r.status==200,await r.text()
        sid=str(uuid.uuid4());await client.post('/sessions',json={'session_id':sid})
        async def turn(text):
            tid=str(uuid.uuid4());p=f'/sessions/{sid}/turns'
            r=await client.post(p,json={'turn_id':tid,'text':text});assert r.status==202,await r.text()
            for _ in range(160):
                r=await client.get(p+'/'+tid);s=await r.json()
                if s.get('status') in {'completed','failed','cancelled','interrupted'}:return s
                await asyncio.sleep(.25)
            raise AssertionError('Turn timed out '+str(s)+' '+log.read_text()[-4000:])
        first=await turn('Remember violet-g2. Run the harmless terminal fixture.')
        assert first['status']=='completed',str(first)+' '+log.read_text()[-4000:]
        assert fixture.tool_seen and 'G2_TOOL_OK' in first['output'],str(first)+' '+log.read_text()[-4000:]
        second=await turn('followup-marker: recall our earlier marker and real tool result.')
        assert second['status']=='completed' and fixture.context_seen, (second, [[{'role':m.get('role'),'content':str(m.get('content'))[:400]} for m in r['messages'] if m.get('role')!='system'] for r in fixture.requests])
        assert first['hermes_session_id']==second['hermes_session_id'] and first['hermes_session_id']!=sid
        env['EVEN_G2_BACKEND_KEY']='synthetic-backend-key-for-tests'
        checked=await asyncio.to_thread(subprocess.run,[cli,'even-g2','check'],env=env,cwd=work,capture_output=True,text=True,timeout=30)
        assert checked.returncode==0,checked.stdout+checked.stderr
        browser_env={**env,'G2_TEST_BROKER':broker_url}
        browser=await asyncio.to_thread(subprocess.run,[shutil.which('node'),'browser/runtime.mjs'],env=browser_env,cwd=ROOT/'companion',capture_output=True,text=True,timeout=180)
        assert browser.returncode==0,browser.stdout+browser.stderr+' '+log.read_text()[-5000:]
        assert json.loads(browser.stdout.strip())['composed']
        assert (work/'approval-deny').stat().st_mode & 0o777 == 0o600
        assert (work/'approval-once').stat().st_mode & 0o777 == 0o777
    finally:
        if client:await client.close()

        if broker_proc:
            broker_proc.terminate()
            try:await asyncio.to_thread(broker_proc.wait,timeout=10)
            except subprocess.TimeoutExpired:broker_proc.kill();await asyncio.to_thread(broker_proc.wait)
        proc.terminate()
        try:await asyncio.to_thread(proc.wait,timeout=20)
        except subprocess.TimeoutExpired:proc.kill();await asyncio.to_thread(proc.wait)
        handle.close();await provider.close()
