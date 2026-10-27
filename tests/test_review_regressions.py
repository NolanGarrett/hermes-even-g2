"""Review regressions: explicit non-submission, sealed reconciliation and diagnostics."""
import asyncio
import hashlib
import time
from dataclasses import replace
import pytest
from aiohttp import ClientConnectorError
from aiohttp.client_reqrep import ConnectionKey
from even_g2.backend import NotSubmitted
from even_g2.config import ConfigError
from even_g2.inspect import inventory
from even_g2.ledger import Ledger, Refusal
from test_protocol import setup, begin, uid, cfg, OTHER


async def test_preflight_rejection_releases_session_but_preserves_intent(setup):
    c,u,config=setup
    u.server_version='0.22.6'
    sid,tid=uid(),uid();await c.post('/sessions',json={'session_id':sid})
    path=f'/sessions/{sid}/turns'
    response=await c.post(path,json={'turn_id':tid,'text':'not sent'})
    assert (await response.json())['status']=='rejected'
    assert not u.calls
    u.server_version='0.22.5'
    assert (await (await c.post(path,json={'turn_id':tid,'text':'not sent'})).json())['status']=='rejected'
    assert not u.calls
    await begin(c,'new intentional turn',sid)
    assert len(u.calls)==1
    assert inventory(config.data_dir)['turns']==2


async def test_connector_failure_is_positive_not_submitted_evidence(setup,monkeypatch):
    c,u,_=setup;backend=c.app['broker'].backend
    def refuse(*args,**kwargs):
        raise ClientConnectorError(ConnectionKey('127.0.0.1',1,False,False,None,None,None),OSError('refused'))
    monkeypatch.setattr(backend.http,'request',refuse)
    with pytest.raises(NotSubmitted):
        await backend.json('POST','/v1/runs',{})
    assert not u.calls


@pytest.mark.parametrize('protocol',['','1'])
async def test_historical_companion_refused_before_session_admission(setup,protocol):
    c,u,_=setup
    assert (await (await c.get('/health')).json())['protocol']==2
    r=await c.post('/sessions',json={'session_id':uid()},headers={'X-Hermes-G2-Protocol':protocol})
    assert r.status==426 and (await r.json())['error']=='matching_protocol_2_companion_required'
    assert not u.calls


async def test_missing_reconcile_seals_delayed_post_and_survives_restart(setup):
    c,u,config=setup;sid,tid=uid(),uid();await c.post('/sessions',json={'session_id':sid})
    path=f'/sessions/{sid}/turns/{tid}'
    assert (await c.get(path)).status==404
    assert (await c.post(path+'/reconcile',json={},headers={'Authorization':'Bearer '+OTHER})).status==404
    assert (await (await c.post(path+'/reconcile',json={})).json())['status']=='rejected'
    assert (await c.post(f'/sessions/{sid}/turns',json={'turn_id':tid,'text':'delayed original'})).status==409
    assert not u.calls
    second=Ledger(config.data_dir)
    try:
        assert second.turn('test',sid,tid)['status']=='rejected'
        with pytest.raises(Refusal,match='idempotency_conflict'):second.reserve('test',sid,tid,hashlib.sha256(b'delayed original').hexdigest())
    finally:second.close()
    await begin(c,'new intentional turn',sid)


async def test_reconcile_existing_uncertain_never_clears_it(setup):
    c,u,_=setup;u.fail=True;sid,tid=uid(),uid();await c.post('/sessions',json={'session_id':sid})
    path=f'/sessions/{sid}/turns'
    await c.post(path,json={'turn_id':tid,'text':'possibly executed'})
    assert (await (await c.post(path+'/'+tid+'/reconcile',json={})).json())['status']=='uncertain'
    assert (await c.post(path,json={'turn_id':uid(),'text':'new'})).status==409
    assert len(u.calls)==1


@pytest.mark.parametrize('reconcile_first',[True,False])
async def test_concurrent_submit_reconcile_never_executes_a_sealed_turn(setup,reconcile_first):
    c,u,_=setup;sid,tid=uid(),uid();await c.post('/sessions',json={'session_id':sid})
    path=f'/sessions/{sid}/turns'
    submit=lambda:c.post(path,json={'turn_id':tid,'text':'once'})
    seal=lambda:c.post(path+'/'+tid+'/reconcile',json={})
    await asyncio.gather(*(fn() for fn in ([seal,submit] if reconcile_first else [submit,seal])))
    row=c.app['broker'].ledger.turn('test',sid,tid)
    assert len(u.calls)<=1
    assert (row['status']=='rejected' and not u.calls) or (row['run'] and len(u.calls)==1)


async def test_reserved_inflight_turn_not_rejected_by_reconcile(setup,monkeypatch):
    c,u,_=setup;broker=c.app['broker'];original=broker.backend.submit
    entered,release=asyncio.Event(),asyncio.Event()
    async def held(*args):entered.set();await release.wait();return await original(*args)
    monkeypatch.setattr(broker.backend,'submit',held)
    sid,tid=uid(),uid();await c.post('/sessions',json={'session_id':sid});path=f'/sessions/{sid}/turns'
    request=asyncio.create_task(c.post(path,json={'turn_id':tid,'text':'once'}))
    await entered.wait()
    assert (await (await c.post(path+'/'+tid+'/reconcile',json={})).json())['status']=='uncertain'
    release.set();assert (await request).status==202
    assert len(u.calls)==1


async def test_deadline_stop_failure_does_not_hide_status_or_approval(setup,monkeypatch):
    c,u,_=setup;_,tid,path=await begin(c);broker=c.app['broker'];calls=[]
    broker.ledger.db.execute('UPDATE turns SET created=? WHERE id=?',(time.time()-1000,tid));broker.ledger.db.commit()
    async def fail(run):calls.append(run);raise Refusal('backend_unavailable',503)
    monkeypatch.setattr(broker.backend,'stop',fail)
    for _ in range(3):
        r=await c.get(path);assert r.status==200;assert (await r.json())['status']=='running'
    assert len(calls)==1


def test_inspection_and_capacity_are_bounded_without_pruning(tmp_path):
    assert inventory(tmp_path)['turns']==0
    ledger=Ledger(tmp_path,max_sessions=1,max_turns=1);sid,tid=uid(),uid()
    ledger.create_session('test',sid);ledger.reconcile('test',sid,tid)
    with pytest.raises(Refusal,match='session_capacity'):ledger.create_session('test',uid())
    with pytest.raises(Refusal,match='intent_capacity'):ledger.reconcile('test',sid,uid())
    assert inventory(tmp_path)=={'sessions':1,'turns':1,'unresolved':[]}
    ledger.close()
    for kw in [{'port':'8766'},{'port':True},{'max_turns':'10000'},{'max_sessions':False}]:
        with pytest.raises(ConfigError):replace(cfg(tmp_path),**kw).validate()


async def test_existing_session_lookup_never_recreates_lost_or_foreign_session(setup):
    c,u,config=setup;sid=uid()
    for _ in range(3):
        response=await c.get('/sessions/'+sid)
        assert response.status==409 and (await response.json())['error']=='session_continuity_lost'
    assert inventory(config.data_dir)=={'sessions':0,'turns':0,'unresolved':[]}
    await c.post('/sessions',json={'session_id':sid})
    assert (await c.get('/sessions/'+sid)).status==200
    assert (await c.get('/sessions/'+sid,headers={'Authorization':'Bearer '+OTHER})).status==409


def test_missing_intent_tombstones_have_per_session_cap(tmp_path):
    ledger=Ledger(tmp_path);sid=uid();ledger.create_session('test',sid)
    for _ in range(32):ledger.reconcile('test',sid,uid())
    with pytest.raises(Refusal,match='reconciliation_capacity'):ledger.reconcile('test',sid,uid())
    assert inventory(tmp_path)['turns']==32
    # Ordinary intentional admission still works; the cap does not delete evidence.
    ledger.reserve('test',sid,uid(),'synthetic-digest');ledger.close()
