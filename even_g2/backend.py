"""Narrow HTTP/STT client. Never follows redirects with credentials."""
import asyncio
import io
import json
import re
import wave
from urllib.parse import quote

import aiohttp
from .ledger import Refusal

MAX_PCM = 16000 * 2 * 30
MAX_TEXT = 8000
MAX_OUTPUT = 32000


async def bounded_body(response, limit):
    data = bytearray()
    async for chunk in response.content.iter_chunked(8192):
        data.extend(chunk)
        if len(data) > limit:
            raise Refusal('backend_response_too_large', 502)
    return bytes(data)


def clean_text(value, limit=MAX_OUTPUT):
    if not isinstance(value, str):
        return ''
    # Plain text only; the companion never inserts this into HTML.
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', value)[:limit]


class Backend:
    def __init__(self, config):
        self.config = config
        self.http = None
        self.stream_http = None

    async def open(self):
        self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.config.request_timeout),
                                          connector=aiohttp.TCPConnector(limit=16), trust_env=False)
        self.stream_http = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=16), trust_env=False)

    async def close(self):
        if self.http:
            await self.http.close()
        if self.stream_http:
            await self.stream_http.close()

    async def json(self, method, path, body=None, key=None):
        headers = {'Authorization': 'Bearer ' + self.config.backend_key}
        if key:
            headers['Idempotency-Key'] = key
        try:
            async with self.http.request(method, self.config.backend_url + path, json=body,
                                         headers=headers, allow_redirects=False) as r:
                raw = await bounded_body(r, 1_048_576)
                if r.status >= 300:
                    # Never expose upstream errors, tokens, paths or tool arguments.
                    raise Refusal('backend_refused_' + str(r.status), 502)
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError()
                return result
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise Refusal('backend_unavailable', 503) from None

    async def capabilities(self):
        health = await self.json('GET', '/health')
        if health.get('version') != '0.22.5':
            raise Refusal('unsupported_hermes_version_requires_0.22.5', 503)
        caps = await self.json('GET', '/v1/capabilities')
        features = caps.get('features', {})
        if not all(features.get(k) for k in ('run_submission', 'run_status', 'run_stop', 'run_events_sse')):
            raise Refusal('unsupported_backend_capabilities', 503)
        return caps

    async def submit(self, text, sid, tid):
        await self.capabilities()
        return await self.json('POST', '/v1/runs', {'input': text, 'session_id': sid}, key=tid)

    async def status(self, run):
        return await self.json('GET', '/v1/runs/' + quote(run, safe=''))

    async def stop(self, run):
        return await self.json('POST', '/v1/runs/' + quote(run, safe='') + '/stop', {})

    async def approve(self, run, body):
        return await self.json('POST', '/v1/runs/' + quote(run, safe='') + '/approval', body)

    async def events(self, run):
        headers = {'Authorization': 'Bearer ' + self.config.backend_key}
        timeout = aiohttp.ClientTimeout(total=self.config.run_timeout, sock_read=35)
        try:
            async with self.stream_http.get(self.config.backend_url + '/v1/runs/' + quote(run, safe='') + '/events',
                                     headers=headers, allow_redirects=False, timeout=timeout) as r:
                if r.status != 200:
                    return
                event, data = '', []
                async for raw in r.content:
                    if len(raw) > 65536:
                        return
                    line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
                    if not line:
                        if data:
                            try:
                                item = json.loads('\n'.join(data))
                                if isinstance(item, dict):
                                    yield event or item.get('event', ''), item
                            except ValueError:
                                pass
                        event, data = '', []
                    elif line.startswith('event:'):
                        event = line[6:].strip()
                    elif line.startswith('data:'):
                        data.append(line[5:].lstrip())
                        if sum(map(len, data)) > 65536:
                            return
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return  # Status polling is authoritative; never resubmit after SSE loss.

    async def transcribe(self, pcm):
        if not pcm or len(pcm) % 2 or len(pcm) > MAX_PCM:
            raise Refusal('invalid_audio_16khz_s16le_mono_max_30s', 400)
        wav = io.BytesIO()
        with wave.open(wav, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm)
        form = aiohttp.FormData()
        form.add_field('file', wav.getvalue(), filename='speech.wav', content_type='audio/wav')
        form.add_field('model', self.config.stt_model)
        form.add_field('response_format', 'json')
        headers = {'Authorization': 'Bearer ' + self.config.stt_key} if self.config.stt_key else {}
        try:
            async with self.http.post(self.config.stt_url, data=form, headers=headers,
                                      allow_redirects=False) as r:
                raw = await bounded_body(r, 65536)
                if r.status != 200:
                    raise Refusal('transcription_failed', 502)
                text = clean_text(json.loads(raw).get('text'), MAX_TEXT).strip()
                if not text:
                    raise Refusal('no_speech_detected', 422)
                return text
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, AttributeError):
            raise Refusal('transcription_unavailable', 503) from None
