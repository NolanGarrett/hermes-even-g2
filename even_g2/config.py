"""Strict configuration. Credentials are environment-only and never serialized."""
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
import os
import re


class ConfigError(ValueError):
    pass


def endpoint(value: str, name: str, *, origin=False) -> str:
    try:
        u = urlsplit(value)
        port = u.port
    except ValueError:
        raise ConfigError(f'{name}: invalid URL') from None
    if (u.scheme not in {'https', 'http'} or not u.hostname or u.username or
            u.password or u.query or u.fragment or
            (u.scheme == 'http' and u.hostname not in {'127.0.0.1', 'localhost', '::1'}) or
            (origin and u.path not in {'', '/'})):
        raise ConfigError(f'{name}: use an exact HTTPS URL (HTTP only on loopback), no credentials/query/fragment')
    return value.rstrip('/')


@dataclass(frozen=True)
class Config:
    backend_url: str
    backend_key: str = field(repr=False)
    device_hashes: dict[str, str] = field(repr=False)
    origins: tuple[str, ...]
    data_dir: Path
    stt_url: str = 'https://api.openai.com/v1/audio/transcriptions'
    stt_key: str = field(default='', repr=False)
    stt_model: str = 'whisper-1'
    host: str = '127.0.0.1'
    port: int = 8766
    request_timeout: float = 30
    run_timeout: float = 600
    max_sessions: int = 64
    max_turns: int = 10000

    def validate(self):
        endpoint(self.backend_url, 'backend_url')
        endpoint(self.stt_url, 'stt_url')
        if not self.origins or any(endpoint(x, 'origins', origin=True) != x for x in self.origins):
            raise ConfigError('origins: exact normalized origins required')
        if self.host not in {'127.0.0.1', '::1'}:
            raise ConfigError('host: broker binds loopback only; use an HTTPS reverse proxy')
        if not 1 <= self.port <= 65535:
            raise ConfigError('port: expected 1..65535')
        if len(self.backend_key) < 16:
            raise ConfigError('EVEN_G2_BACKEND_KEY: set the server-side Hermes API key (16+ characters)')
        if not self.device_hashes or len(self.device_hashes) > 16 or any(
            not re.fullmatch(r'[a-z0-9_-]{1,32}', k) or not re.fullmatch(r'[0-9a-f]{64}', v)
            for k, v in self.device_hashes.items()
        ):
            raise ConfigError('device_hashes: map 1..16 device names to SHA256 hex digests of unique random 32+ character device tokens')
        if len(set(self.device_hashes.values())) != len(self.device_hashes):
            raise ConfigError('device_hashes: each device must have a distinct token')
        if not 1 <= self.request_timeout <= 120 or not 30 <= self.run_timeout <= 3600:
            raise ConfigError('timeouts: request 1..120 and run 30..3600 seconds')
        if not 1 <= self.max_sessions <= 1000 or not 1 <= self.max_turns <= 100000:
            raise ConfigError('resource bounds: sessions 1..1000, turns 1..100000')
        return self

    @classmethod
    def from_context(cls, ctx):
        from plugins.plugin_storage import plugin_data_dir
        get = ctx.get_config
        # Only declared, operator-provisioned variables; never read auth/config files.
        return cls(
            backend_url=get('backend_url', default='http://127.0.0.1:8642'),
            backend_key=os.environ.get('EVEN_G2_BACKEND_KEY', ''),
            device_hashes=get('device_hashes', default={}),
            origins=tuple(get('origins', default=[])),
            data_dir=plugin_data_dir('hermes-even-g2'),
            stt_url=get('stt_url', default='https://api.openai.com/v1/audio/transcriptions'),
            stt_key=os.environ.get('EVEN_G2_STT_KEY', ''),
            stt_model=get('stt_model', default='whisper-1'),
            port=get('port', default=8766),
        ).validate()
