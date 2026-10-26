"""Real broker HTTP/SQLite/STT transport tests; remote inference is a fixture."""
import asyncio
import hashlib
import io
import time
import uuid
import wave
from dataclasses import replace
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from even_g2.config import Config, ConfigError, endpoint
from even_g2.backend import Backend, MAX_PCM
from even_g2.server import create_app
from even_g2.ledger import Ledger, Refusal

TOKEN='synthetic-device-token-not-a-secret-0000001'
OTHER='synthetic-device-token-not-a-secret-0000002'
ORIGIN='https://companion.example.com'
def uid(): return str(uuid.uuid4())
def cfg(path,url='http://127.0.0.1:8642',**kw):
    return Config(url,'synthetic-backend-key-for-tests',{'test':hashlib.sha256(TOKEN.encode()).hexdigest(),'other':hashlib.sha256(OTHER.encode()).hexdigest()},(ORIGIN,),path,**kw)

class Upstream:
    def __init__(self):
        self.calls=[];self.runs={};self.decisions=[];self.pcm=None;self.stop_count=0;self.fail=False
        self.hold=asyncio.Event();self.stream_count=0
    async def health(self,r): return web.json_response({'features':dict.fromkeys(['run_submission','run_status','run_stop','run_events_sse'],True)})
    async def version(self,r): return web.json_response({'version':getattr(self,'server_version','0.22.5')})
    async def submit(self,r):
        assert r.headers['Authorization']=='Bearer synthetic-backend-key-for-tests'
        b=await r.json();self.calls.append((r.headers['Idempotency-Key'],b))
        if self.fail:return web.json_response({'error':'private upstream error'},status=500)
        run='run_'+uuid.uuid4().hex
        self.runs[run]={'run_id':run,'session_id':b['session_id'],'status':'running','output':''}
        return web.json_response({'run_id':run,'status':'started'},status=202)
    async def status(self,r):return web.json_response(self.runs[r.match_info['run']])
    async def events(self,r):
        resp=web.StreamResponse(headers={'Content-Type':'text/event-stream'});await resp.prepare(r)
        await resp.write(b': keepalive\n\nevent: tool.started\ndata: {"tool":"synthetic"}\n\nevent: message.delta\ndata: {"delta":"Partial answer"}\n\n')
        self.stream_count+=1
        try:await asyncio.wait_for(self.hold.wait(),10)
        except asyncio.TimeoutError:pass
        return resp
    async def stop(self,r):
        self.stop_count+=1;self.runs[r.match_info['run']]['status']='stopping'
        return web.json_response({'status':'stopping'})
    async def approve(self,r):
        self.decisions.append(await r.json());self.runs[r.match_info['run']]['pending_controls']=[]
        return web.json_response({'status':'resolved'})
    async def stt(self,r):
        reader=await r.multipart();part=await reader.next();data=await part.read()
        with wave.open(io.BytesIO(data)) as w:
            assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(1,2,16000)
            self.pcm=w.readframes(w.getnframes())
        return await self.fragment(r,b'{"text":',b'"Synthetic transcript"}')
    async def fragment(self,r,a=b'{"status":',b=b'"ok"}'):
        resp=web.StreamResponse(headers={'Content-Type':'application/json'});await resp.prepare(r)
        await resp.write(a);await asyncio.sleep(.03);await resp.write(b);await resp.write_eof();return resp
    def app(self):
        a=web.Application();a.router.add_get('/v1/capabilities',self.health);a.router.add_post('/v1/runs',self.submit)
        a.router.add_get('/health',self.version)
        a.router.add_get('/fragment',self.fragment);a.router.add_post('/stt',self.stt)
        for method,path,fn in [('GET','',self.status),('GET','/events',self.events),('POST','/stop',self.stop),('POST','/approval',self.approve)]:a.router.add_route(method,'/v1/runs/{run}'+path,fn)
        return a

@pytest.fixture
async def setup(tmp_path):
    u=Upstream();r=TestServer(u.app());await r.start_server();url=str(r.make_url('')).rstrip('/')
    config=cfg(tmp_path,url,stt_url=url+'/stt');c=TestClient(TestServer(create_app(config)));await c.start_server()
    c.session.headers.update({'Authorization':'Bearer '+TOKEN,'Origin':ORIGIN})
    yield c,u,config
    u.hold.set();await c.close();await r.close()
async def begin(c,text='hello',sid=None,tid=None):
    sid,tid=sid or uid(),tid or uid();assert (await c.post('/sessions',json={'session_id':sid})).status==200
    r=await c.post(f'/sessions/{sid}/turns',json={'turn_id':tid,'text':text});assert r.status==202,await r.text()
    return sid,tid,f'/sessions/{sid}/turns/{tid}'

@pytest.mark.parametrize('url',['http://example.com','https://x:bad','https://user:pass@example.com','https://example.com?key=x','file:///x','https://x/#a'])
def test_url_fail_closed(url):
    with pytest.raises(ConfigError):endpoint(url,'test')
def test_config(tmp_path):
    c=cfg(tmp_path);assert 'synthetic-backend' not in repr(c)
    for changes in [{'origins':('*',)},{'host':'0.0.0.0'},{'backend_key':'x'},{'device_hashes':{}},{'request_timeout':999}]:
        with pytest.raises(ConfigError):replace(c,**changes).validate()
async def test_auth_origin_routes(setup):
    c,u,_=setup;r=await c.get('/health');assert r.status==200 and r.headers['Access-Control-Allow-Origin']==ORIGIN
    for headers,code in [({'Authorization':'Bearer wrong'},401),({'Origin':'https://evil.example.com'},403),({'Origin':'null'},403)]:assert (await c.get('/health',headers=headers)).status==code
    assert (await c.get('/health?token=x')).status==400
    assert (await c.options('/sessions',headers={'Authorization':''})).status==204
    assert (await c.post('/api/admin',json={})).status in (404,405)
    assert not u.calls
async def test_session_minting_foreign_id_ownership_and_context(setup):
    c,u,_=setup;sid,tid,p=await begin(c);backend_sid=u.calls[0][1]['session_id']
    assert backend_sid!=sid and backend_sid.startswith('g2_')
    assert u.calls[0][1]=={'input':'hello','session_id':backend_sid}
    for path in [p,p+'/stop']:
        r=await (c.post(path,json={},headers={'Authorization':'Bearer '+OTHER}) if path.endswith('stop') else c.get(path,headers={'Authorization':'Bearer '+OTHER}))
        assert r.status==404
    assert (await c.post(f'/sessions/{sid}/turns',json={'turn_id':uid(),'text':'next'})).status==409
    u.runs[next(iter(u.runs))].update(status='completed',output='first')
    assert (await (await c.get(p)).json())['output']=='first'
    await begin(c,'followup',sid);assert u.calls[-1][1]['session_id']==backend_sid
    assert (await c.post(f'/sessions/{sid}/turns',json={'turn_id':uid(),'text':'x','instructions':'override'})).status==400
async def test_duplicate_conflict_and_restart(setup):
    c,u,config=setup;sid,tid,p=await begin(c)
    for _ in range(2):assert (await c.post(f'/sessions/{sid}/turns',json={'turn_id':tid,'text':'hello'})).status==200
    assert len(u.calls)==1
    assert (await c.post(f'/sessions/{sid}/turns',json={'turn_id':tid,'text':'changed'})).status==409
    await c.close();resumed=TestClient(TestServer(create_app(config)));await resumed.start_server();resumed.session.headers['Authorization']='Bearer '+TOKEN
    try:assert (await resumed.get(p)).status==200;assert len(u.calls)==1
    finally:await resumed.close()
async def test_uncertainty_no_replay(setup):
    c,u,_=setup;u.fail=True;sid,tid=uid(),uid();await c.post('/sessions',json={'session_id':sid});p=f'/sessions/{sid}/turns'
    r=await c.post(p,json={'turn_id':tid,'text':'possibly executed'});assert r.status==502 and 'private upstream' not in await r.text()
    assert (await (await c.get(p+'/'+tid)).json())['status']=='uncertain'
    assert (await c.post(p,json={'turn_id':tid,'text':'possibly executed'})).status==200
    assert (await c.post(p,json={'turn_id':uid(),'text':'next'})).status==409;assert len(u.calls)==1
async def test_stream_long_failure_and_stop_receipts(setup):
    c,u,_=setup;sid,tid,p=await begin(c);await asyncio.sleep(.04)
    assert (await (await c.get(p)).json())['progress']['text']=='Partial answer'
    assert (await (await c.post(p+'/stop',json={})).json())['status']=='stop_requested'
    assert (await (await c.get(p)).json())['status']=='stopping'
    u.runs[next(iter(u.runs))].update(status='cancelled');assert (await (await c.get(p)).json())['status']=='cancelled'
    _,_,p=await begin(c,'long',sid);u.runs[list(u.runs)[-1]].update(status='completed',output='<script>x</script>'+'x'*40000)
    s=await (await c.get(p)).json();assert len(s['output'])==32000 and s['truncated']
    _,_,p=await begin(c,'error',sid);u.runs[list(u.runs)[-1]].update(status='failed');assert (await (await c.get(p)).json())['status']=='failed'
async def test_exact_approval_identity_and_legacy_handoff(setup):
    c,u,_=setup;_,_,p=await begin(c);run=next(iter(u.runs));u.runs[run].update(status='waiting_for_approval',execution_generation=3,pending_controls=[{'kind':'approval','prompt_id':'p1','execution_generation':3,'command':'harmless test','choices':['once','deny']}])
    assert len((await (await c.get(p)).json())['approvals'])==1
    b={'request_id':'p1','execution_generation':3,'choice':'once'}
    for change in [{'request_id':'other'},{'execution_generation':2},{'choice':'always'}]:assert (await c.post(p+'/approval',json={**b,**change})).status in (400,409)
    assert (await c.post(p+'/approval',json=b,headers={'Authorization':'Bearer '+OTHER})).status==404
    assert not u.decisions
    assert (await c.post(p+'/approval',json=b)).status==200
    assert (await c.post(p+'/approval',json=b)).status==409;assert len(u.decisions)==1
    s=await (await c.get(p)).json();assert s['handoff'] and not s['approvals']
async def test_large_or_unbound_approval_is_not_offered(setup):
    c,u,_=setup;_,_,p=await begin(c);r=u.runs[next(iter(u.runs))]
    r.update(status='waiting_for_approval',execution_generation=1,pending_controls=[{'kind':'approval','prompt_id':'p','execution_generation':1,'command':'x'*17000,'choices':['once','deny']}])
    assert not (await (await c.get(p)).json())['approvals']
    del r['pending_controls'][0]['execution_generation'];assert not (await (await c.get(p)).json())['approvals']
async def test_pcm_multipart_fragmented_stt_and_limits(setup):
    c,u,_=setup;pcm=b'\x01\x00'*1600;r=await c.post('/transcribe',data=pcm,headers={'Content-Type':'application/octet-stream'})
    assert (await r.json())['text']=='Synthetic transcript' and u.pcm==pcm
    for data in [b'',b'\x00',b'\x00'*(MAX_PCM+2)]:assert (await c.post('/transcribe',data=data,headers={'Content-Type':'application/octet-stream'})).status in (400,413)
    assert (await c.post('/transcribe',json={})).status==415;assert not u.calls
async def test_fragmented_json_read_to_eof(setup):
    c,u,_=setup;assert await c.app['broker'].backend.json('GET','/fragment')=={'status':'ok'}
async def test_backend_version_guard(setup):
    c,u,_=setup;u.server_version='0.22.6'
    assert (await c.get('/health')).status==503
    with pytest.raises(Refusal,match='unsupported_hermes_version'):
        await c.app['broker'].backend.submit('never submit',uid(),uid())
    assert not u.calls
async def test_deadline_stop_and_identity_mismatch(setup):
    c,u,_=setup;_,tid,p=await begin(c);db=c.app['broker'].ledger.db
    db.execute('UPDATE turns SET created=? WHERE id=?',(time.time()-1000,tid));db.commit()
    s=await (await c.get(p)).json();assert s['stop_requested'] and s['status']=='running' and u.stop_count==1
    u.runs[next(iter(u.runs))]['session_id']=uid();assert (await c.get(p)).status==502
async def test_concurrent_duplicate_once_and_no_transcript_storage(setup):
    c,u,config=setup;sid,tid=uid(),uid();await c.post('/sessions',json={'session_id':sid})
    r=await asyncio.gather(*[c.post(f'/sessions/{sid}/turns',json={'turn_id':tid,'text':'private synthetic phrase'}) for _ in range(8)])
    assert all(x.status in (200,202) for x in r) and len(u.calls)==1
    raw=b''.join(p.read_bytes() for p in config.data_dir.glob('intents.sqlite3*'))
    assert b'private synthetic phrase' not in raw and TOKEN.encode() not in raw
async def test_sixteen_streams_do_not_starve_stop_and_cap(setup):
    c,u,_=setup;paths=[]
    for _ in range(16):paths.append((await begin(c))[2])
    for _ in range(50):
        if u.stream_count==16:break
        await asyncio.sleep(.02)
    assert u.stream_count==16
    assert (await asyncio.wait_for(c.post(paths[-1]+'/stop',json={}),1)).status==200
    assert u.stop_count==1
    sid=uid();await c.post('/sessions',json={'session_id':sid})
    assert (await c.post(f'/sessions/{sid}/turns',json={'turn_id':uid(),'text':'overflow'})).status==429
