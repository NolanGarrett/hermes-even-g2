"""Useful native plugin surface: validated foreground service and diagnostics."""
import asyncio
import json
from .config import Config, ConfigError
from .ledger import Refusal


def register(ctx):
    def setup(parser):
        parser.add_argument('action', choices=['check', 'serve'])

    def command(args):
        try:
            config = Config.from_context(ctx)
            if args.action == 'check':
                from .backend import Backend
                async def check():
                    client = Backend(config)
                    await client.open()
                    try:
                        await client.capabilities()
                        print('Configuration valid; Hermes Runs API ready. STT and hardware not tested by this command.')
                    finally:
                        await client.close()
                asyncio.run(check())
            else:
                from aiohttp import web
                from .server import create_app
                print('Even G2 broker: loopback only; deploy behind private HTTPS. HARDWARE UNVERIFIED.')
                web.run_app(create_app(config), host=config.host, port=config.port, access_log=None,
                            print=None, shutdown_timeout=5)
        except (ConfigError, Refusal) as exc:
            print(f'Even G2: {exc}')
            raise SystemExit(2) from None

    ctx.register_cli_command(name='even-g2', help='Check or serve the private Even G2 broker',
                             setup_fn=setup, handler_fn=command)
    ctx.register_command('even-g2', lambda raw: (
        'Even G2 uses its own API-owned sessions, not this conversation. '
        'Run hermes even-g2 check or hermes even-g2 serve. Hardware unverified.'),
        description='Explain Even G2 connection and session ownership')
