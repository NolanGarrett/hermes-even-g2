# Installation and operation

**HARDWARE UNVERIFIED.** Start in an isolated, least-privilege profile, not your primary assistant. This guide is operator-run; no install script changes host services, network settings or credentials.

## Supported runtime

Use public Hermes Agent **v0.22.5**, Python 3.14. Follow [official installation](https://hermes-agent.nousresearch.com/docs/) or, for an isolated development runtime:

```sh
git clone --branch v0.22.5 --depth 1 https://github.com/NousResearch/hermes-agent.git upstream-hermes
cd upstream-hermes
uv sync --frozen
```

The frozen upstream lock is the tested path. Unconstrained editable pip installation had an upstream dependency-resolution conflict; do not repair that by modifying production or downgrading Hermes. Choose a fresh `HOME`/`HERMES_HOME` and a generic agent configuration with only intended tools. Profile separation is not an OS sandbox.

The agent's authenticated API server must be configured on loopback, normally `127.0.0.1:8642`; use the [official API guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server). `API_SERVER_KEY` is a server secret. `EVEN_G2_BACKEND_KEY` must contain that same key in the broker process environment. In a disposable foreground test, explicitly use:

```sh
hermes gateway run --no-supervise
```

Never use bare `gateway run` for isolation inside a supervised container: the CLI can redirect to an existing host supervisor even with another HERMES_HOME. Our harness uses an allowlisted environment and terminates only its own foreground child. This plugin never launches the gateway for you.

## Plugin install

Recommended supported mechanism, in the intended profile:

```sh
hermes plugins install NolanGarrett/hermes-even-g2 --enable
hermes plugins list
```

For reproducibility append `--ref FULL_40_CHARACTER_RELEASE_COMMIT` using the actual commit shown on the GitHub release (not that placeholder, not a tag). Hermes 0.22.5 verifies a full immutable SHA.

Offline/directory alternative: unpack the release plugin ZIP, containing a top-level `hermes-even-g2/`, into `$HERMES_HOME/plugins/` (normally `~/.hermes/plugins/`), then:

```sh
hermes plugins doctor "$HERMES_HOME/plugins/hermes-even-g2" --ci
hermes plugins enable hermes-even-g2
```

Ensure `aiohttp>=3.13,<4` exists in the same Python environment as Hermes; a minimal public frozen runtime may omit this optional API dependency. Install it explicitly in the intended environment (qualification used aiohttp3.14.5), rather than relying on lazy installation. The plugin does not silently install dependencies. The wheel/package metadata is development metadata; a wheel alone is not the directory plugin distribution.

## Configuration

Merge this section into your chosen profile's `config.yaml`, preserving unrelated plugins/settings:

```yaml
plugins:
  enabled:
    - hermes-even-g2
  entries:
    hermes-even-g2:
      settings:
        backend_url: http://127.0.0.1:8642
        port: 8766
        origins:
          - https://companion.example.com
        device_hashes:
          my-phone: REPLACE_WITH_SHA256_HEX_DIGEST
        stt_url: https://api.openai.com/v1/audio/transcriptions
        stt_model: whisper-1
```

`origins` means the **page/WebView Origin header**, not necessarily the broker host. Use the actual HTTPS origin of your hosted/beta WebView. Inspect non-sensitive Origin metadata with developer tools if necessary; do not log Authorization or request bodies. `null`, wildcard, arbitrary internet HTTP and trailing slashes are refused. If the current Even packaging mode produces an opaque/null origin, that mode is unsupported: use a proper HTTPS-hosted/beta origin, do not relax the gate.

`backend_url` may include a trusted routed profile prefix. Host is always loopback. Runtime defaults: request timeout 30s, run timeout 600s, 64 sessions/device, 10,000 ledger turns total, 16 active turns total, 16 configured devices. Constructor-level bounds are exercised in tests; the manifest exposes only the settings above.

Generate a unique device token with at least 32 characters of cryptographic randomness using your password manager. Keep the original in that manager; enter it on the phone. Compute its SHA-256 digest without including it in shell history:

```sh
python -c 'import getpass,hashlib; print(hashlib.sha256(getpass.getpass("Device token: ").encode()).hexdigest())'
```

Place only the resulting hash in `device_hashes`. Provision backend/STT keys through your service's environment-secret facility or an interactive non-echoing shell input; do not put secrets in source, `.ehpk`, URLs, screenshots or command arguments. The companion device token is **not** the API server key.

```sh
hermes even-g2 check
hermes even-g2 serve
```

`check` validates configuration, exact Hermes version and Runs capabilities; it does not claim STT, provider, TLS from phone or hardware validation. `serve` runs foreground. Deploy HTTPS separately as described in [deployment](deployment.md). No global startup service is installed automatically.

## Upgrade, revoke, disable, uninstall

- Back up the small plugin data directory while the broker is stopped. Preserve the ledger across upgrades: deleting it discards replay protection and ownership mappings.
- Upgrade pinned source explicitly with `hermes plugins install NolanGarrett/hermes-even-g2 --force --ref NEW_FULL_COMMIT`. Review release notes, run doctor/check, and start your broker using your own service lifecycle. No schema upgrade beyond this initial release is promised.
- Revoke one device by removing its digest and restarting the **broker you operate**, or replace its digest while keeping the device name to retain access to existing device-owned sessions. Removing a token does not stop backend work already accepted. Stop those runs through the supported Hermes control surface first if required.
- Stop your broker, then `hermes plugins disable hermes-even-g2`. Disabling discovery alone does not terminate an already-running process.
- `hermes plugins remove hermes-even-g2` removes installed code. Separately remove the companion and decide whether to retain ledger/backups and upstream Hermes history. Do not delete a ledger with unresolved work merely to retry it.

## Troubleshooting

| Symptom | Action |
|---|---|
| Configuration refused | Check exact origins, 64-character lowercase token hash, backend environment key and loopback bind. Never paste keys into a bug report. |
| Unsupported Hermes version | Use 0.22.5 in isolation. Do not remove the compatibility guard or downgrade production. |
| 401 | Re-enter the current device token. Do not substitute a backend key. |
| 403 / CORS | Check actual page origin against broker `origins`; separately check app network whitelist. |
| SDK timeout | Open inside the Even App, confirm SDK/app minimum, G2 connection and permissions. Safari is not the Even bridge. |
| No audio | Confirm explicit capture, microphone permission and G2 source. Phone recording is not silently substituted. |
| STT unavailable | Verify provider endpoint/model/key and connectivity server-side. Text fallback can diagnose the rest of the path. |
| Outcome uncertain / unknown | Inspect the exact backend session/run. No automatic submission retry; do not reset/delete the ledger to force replay. |
| Stop not confirmed | Reconcile again; keep current resume IDs. Stop is not rollback. |
| Unsupported approval | Use the supported server control surface or deny/stop. Never approve blindly or disable policy. |
| 429 / capacity reached | Reconcile/stop active work; review ledger capacity deliberately. No automatic pruning of dedup records. |
| Phone locks / app backgrounds | Capture is discarded best-effort; network may stop. Reopen/re-enter token/reconcile. No background guarantee. |
