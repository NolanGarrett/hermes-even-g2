"""Authenticated broker; all user-triggered inference remains in Hermes."""
import asyncio
import hashlib
import hmac
import json
import re
import time
from contextlib import suppress

from aiohttp import web
from .backend import Backend, NotSubmitted, MAX_PCM, MAX_TEXT, MAX_OUTPUT, clean_text
from .ledger import Ledger, Refusal, TERMINAL

UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
RUN = re.compile(r'^[A-Za-z0-9_-]{1,128}$')


def identifier(value):
    if not isinstance(value, str) or not UUID.fullmatch(value):
        raise Refusal('invalid_identifier', 400)
    return value


async def body(request, fields):
    try:
        value = await request.json()
    except (ValueError, UnicodeError):
        raise Refusal('invalid_json', 400) from None
    if not isinstance(value, dict) or set(value) != set(fields):
        raise Refusal('invalid_fields', 400)
    return value


class Broker:
    def __init__(self, config, backend=None):
        self.config = config.validate()
        self.ledger = Ledger(config.data_dir, config.max_sessions, config.max_turns)
        self.backend = backend or Backend(config)
        self.streams = {}
        self.progress = {}
        self.requests = 0
        self.stt_active = 0
        self.watchdog = None
        self.deadline_stops = {}

    async def start(self, app):
        await self.backend.open()
        self.watchdog = asyncio.create_task(self.expire_runs())

    async def expire_runs(self):
        while True:
            await asyncio.sleep(5)
            rows = self.ledger.db.execute("SELECT * FROM turns WHERE run IS NOT NULL AND status NOT IN ('completed','failed','cancelled','interrupted','rejected') ORDER BY created LIMIT 16").fetchall()
            for row in rows:
                with suppress(Refusal):
                    await self.snapshot(dict(row))

    async def close(self, app):
        tasks = list(self.streams.values())
        if self.watchdog:
            tasks.append(self.watchdog)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.backend.close()
        self.ledger.close()

    def authenticate(self, request):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer ') or not 32 <= len(auth[7:]) <= 256:
            raise Refusal('unauthorized', 401)
        digest = hashlib.sha256(auth[7:].encode()).hexdigest()
        for device, expected in self.config.device_hashes.items():
            if hmac.compare_digest(digest, expected):
                return device
        raise Refusal('unauthorized', 401)

    @web.middleware
    async def boundary(self, request, handler):
        origin = request.headers.get('Origin')
        try:
            # Origin required for browser clients. Missing Origin allowed for authenticated native CLI.
            # Never accept opaque `null` origins, even behind a VPN.
            if origin is not None and origin not in self.config.origins:
                raise Refusal('origin_denied', 403)
            if request.query_string:
                raise Refusal('query_not_allowed', 400)
            if request.method == 'OPTIONS':
                if origin is None:
                    raise Refusal('origin_required', 403)
                response = web.Response(status=204)
            else:
                request['device'] = self.authenticate(request)
                if request.path != '/health' and request.headers.get('X-Hermes-G2-Protocol') != '2':
                    raise Refusal('matching_protocol_2_companion_required', 426)
                if self.requests >= 16:
                    raise Refusal('busy', 429)
                self.requests += 1
                try:
                    response = await asyncio.wait_for(handler(request), self.config.request_timeout + 5)
                finally:
                    self.requests -= 1
        except Refusal as exc:
            response = web.json_response({'error': exc.code}, status=exc.status)
        except web.HTTPException as exc:
            response = web.json_response({'error': 'request_rejected'}, status=exc.status)
        except (asyncio.TimeoutError, TimeoutError):
            response = web.json_response({'error': 'request_timeout_reconcile_before_retry'}, status=504)
        except Exception:
            # Do not log conversation/headers or leak exception text.
            response = web.json_response({'error': 'internal_error'}, status=500)
        if origin in self.config.origins:
            response.headers.update({'Access-Control-Allow-Origin': origin, 'Vary': 'Origin',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Hermes-G2-Protocol',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Max-Age': '600'})
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                  'Referrer-Policy': 'no-referrer'})
        return response

    async def health(self, request):
        await self.backend.capabilities()
        return web.json_response({'protocol': 2, 'status': 'ready', 'hardware': 'unverified',
                                  'approvals': 'phone-only-exact-identity', 'max_audio_bytes': MAX_PCM})

    async def session(self, request):
        data = await body(request, ['session_id'])
        sid = identifier(data['session_id'])
        self.ledger.create_session(request['device'], sid)
        return web.json_response({'session_id': sid})

    async def transcribe(self, request):
        if request.content_type != 'application/octet-stream':
            raise Refusal('expected_raw_pcm', 415)
        if self.stt_active >= 2:
            raise Refusal('transcription_busy', 429)
        self.stt_active += 1
        try:
            pcm = await request.read()
            text = await self.backend.transcribe(pcm)
            return web.json_response({'text': text})
        finally:
            self.stt_active -= 1

    async def existing_session(self, request):
        sid = identifier(request.match_info['sid'])
        try:
            self.ledger.session(request['device'], sid)
        except Refusal:
            raise Refusal('session_continuity_lost', 409) from None
        return web.json_response({'session_id': sid})

    def scope(self, request):
        sid = identifier(request.match_info['sid'])
        tid = identifier(request.match_info['tid'])
        return self.ledger.turn(request['device'], sid, tid)

    async def submit(self, request):
        data = await body(request, ['turn_id', 'text'])
        sid = identifier(request.match_info['sid'])
        tid = identifier(data['turn_id'])
        text = data['text']
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or '\x00' in text:
            raise Refusal('text_required_max_8000', 400)
        digest = hashlib.sha256(text.encode()).hexdigest()
        row, fresh = self.ledger.reserve(request['device'], sid, tid, digest)
        if not fresh:
            return web.json_response(await self.snapshot(row))
        try:
            # The durable reservation is committed BEFORE any network side effect.
            result = await self.backend.submit(text, self.ledger.backend_session(sid), tid)
            run = result.get('run_id')
            if not isinstance(run, str) or not RUN.fullmatch(run):
                raise Refusal('invalid_backend_run', 502)
            self.ledger.update(tid, run=run, status='running')
            self.watch(tid, run)
            return web.json_response({'turn_id': tid, 'session_id': sid, 'status': 'working'}, status=202)
        except NotSubmitted:
            self.ledger.update(tid, status='rejected')
            return web.json_response({'turn_id': tid, 'session_id': sid, 'status': 'rejected'})
        except BaseException:
            self.ledger.update(tid, status='uncertain')
            raise

    def watch(self, tid, run):
        if tid in self.streams or len(self.streams) >= 16:
            return
        async def consume():
            self.progress.pop(tid, None)  # SSE reconnection may replay from the start.
            try:
                async for event, item in self.backend.events(run):
                    progress = self.progress.setdefault(tid, {'text': '', 'event': 'working'})
                    if event == 'message.delta':
                        progress['text'] = clean_text(progress['text'] + clean_text(item.get('delta', item.get('text', ''))), MAX_OUTPUT)
                    if event in {'tool.started', 'tool.completed', 'approval.request', 'run.completed', 'run.failed', 'run.cancelled', 'message.delta'}:
                        progress['event'] = event
                    if event.startswith('run.') and event.split('.')[-1] in TERMINAL:
                        return
            finally:
                self.streams.pop(tid, None)
        self.streams[tid] = asyncio.create_task(consume())

    async def snapshot(self, row):
        result = {'turn_id': row['id'], 'session_id': row['session']}
        if row['status'] == 'rejected':
            return {**result, 'status': 'rejected'}
        if not row['run']:
            return {**result, 'status': 'uncertain', 'message': 'Submission outcome unknown. Do not repeat. Inspect this session in Hermes.'}
        upstream = await self.backend.status(row['run'])
        backend_sid = self.ledger.backend_session(row['session'])
        if upstream.get('session_id') != backend_sid or upstream.get('run_id') != row['run']:
            raise Refusal('backend_identity_mismatch', 502)
        result['hermes_session_id'] = backend_sid
        status = upstream.get('status')
        known = TERMINAL | {'queued', 'started', 'running', 'stopping', 'waiting_for_approval', 'unknown'}
        if status not in known:
            raise Refusal('unknown_backend_state', 502)
        self.ledger.update(row['id'], status=status)
        result['status'] = status
        result['output'] = clean_text(upstream.get('output'))
        result['truncated'] = isinstance(upstream.get('output'), str) and len(upstream['output']) > MAX_OUTPUT
        if status in TERMINAL:
            task = self.streams.pop(row['id'], None)
            if task:
                task.cancel()
            self.progress.pop(row['id'], None)
            self.deadline_stops.pop(row['id'], None)
        else:
            self.watch(row['id'], row['run'])
            result['progress'] = self.progress.get(row['id'], {'event': 'working', 'text': ''})
            if time.time() - row['created'] > self.config.run_timeout and status not in {'unknown', 'stopping'}:
                last = self.deadline_stops.get(row['id'], 0)
                if time.monotonic() - last >= 30:
                    self.deadline_stops[row['id']] = time.monotonic()
                    try:
                        await self.backend.stop(row['run'])
                        result['stop_requested'] = True
                    except Refusal:
                        result['message'] = 'Deadline stop unconfirmed; inspect server. Work may continue.'
        controls = upstream.get('pending_controls', [])
        if isinstance(controls, list):
            result['approvals'] = [self.approval(p, upstream) for p in controls[:8]
                                   if isinstance(p, dict) and p.get('kind') == 'approval']
            result['approvals'] = [p for p in result['approvals'] if p is not None]
            if any(isinstance(p, dict) and p.get('kind') != 'approval' for p in controls):
                result['handoff'] = 'Open the server control surface for clarification.'
        if status == 'waiting_for_approval' and not result.get('approvals'):
            result['handoff'] = 'Approval unavailable here. Use the server control surface or cancel; never repeat the request.'
        return result

    @staticmethod
    def approval(prompt, upstream):
        pid = prompt.get('prompt_id')
        gen = prompt.get('execution_generation')
        if not isinstance(pid, str) or not 1 <= len(pid) <= 256 or type(gen) is not int:
            return None
        if gen != upstream.get('execution_generation'):
            return None
        # v0.22.5 canonical controls are nested in the exact run/session projection;
        # prompts carry command/description/edit directly, not a payload/session field.
        if not all(c in prompt.get('choices', []) for c in ('once', 'deny')):
            return None
        description = json.dumps({k: v for k, v in prompt.items()
                                  if k not in {'prompt_id', 'execution_generation', 'kind'}}, ensure_ascii=False)
        # Never offer approval on a truncated description or diff.
        if len(description) > 16000:
            return None
        return {'request_id': pid, 'execution_generation': gen,
                'description': clean_text(description, 16000)}

    async def status(self, request):
        return web.json_response(await self.snapshot(self.scope(request)))

    async def reconcile(self, request):
        await body(request, [])
        sid = identifier(request.match_info['sid'])
        tid = identifier(request.match_info['tid'])
        row = self.ledger.reconcile(request['device'], sid, tid)
        return web.json_response(await self.snapshot(row))

    async def stop(self, request):
        await body(request, [])
        row = self.scope(request)
        if not row['run']:
            raise Refusal('submission_uncertain_use_server')
        await self.backend.stop(row['run'])
        # Request receipt is not completion. Caller must keep polling.
        return web.json_response({'status': 'stop_requested', 'turn_id': row['id']})

    async def approve(self, request):
        data = await body(request, ['request_id', 'execution_generation', 'choice'])
        row = self.scope(request)
        if data['choice'] not in {'once', 'deny'} or type(data['execution_generation']) is not int or not isinstance(data['request_id'], str):
            raise Refusal('invalid_approval', 400)
        if not row['run']:
            raise Refusal('no_bound_run')
        snapshot = await self.snapshot(row)
        if snapshot['status'] != 'waiting_for_approval' or not any(
                p['request_id'] == data['request_id'] and p['execution_generation'] == data['execution_generation']
                for p in snapshot.get('approvals', [])):
            raise Refusal('stale_or_foreign_approval')
        self.ledger.claim_control(row['id'], data['request_id'], data['execution_generation'])
        await self.backend.approve(row['run'], data)
        return web.json_response({'status': 'decision_submitted'})


def create_app(config, backend=None):
    broker = Broker(config, backend)
    app = web.Application(middlewares=[broker.boundary], client_max_size=MAX_PCM)
    app['broker'] = broker
    app.on_startup.append(broker.start)
    app.on_cleanup.append(broker.close)
    app.router.add_get('/health', broker.health)
    app.router.add_post('/sessions', broker.session)
    app.router.add_get('/sessions/{sid}', broker.existing_session)
    app.router.add_post('/transcribe', broker.transcribe)
    app.router.add_post('/sessions/{sid}/turns', broker.submit)
    app.router.add_get('/sessions/{sid}/turns/{tid}', broker.status)
    app.router.add_post('/sessions/{sid}/turns/{tid}/reconcile', broker.reconcile)
    app.router.add_post('/sessions/{sid}/turns/{tid}/stop', broker.stop)
    app.router.add_post('/sessions/{sid}/turns/{tid}/approval', broker.approve)
    app.router.add_route('OPTIONS', '/{path:.*}', lambda r: web.Response(status=204))
    return app
