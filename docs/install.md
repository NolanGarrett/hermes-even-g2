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
git clone https://github.com/NolanGarrett/hermes-even-g2.git
cd hermes-even-g2
git checkout --detach REVIEWED_FULL_COMMIT
hermes plugins install NolanGarrett/hermes-even-g2 --ref "$(git rev-parse HEAD)" --enable
hermes plugins list
```

Accept the declared Python dependency preparation when prompted. For an unattended install where you intentionally consent to those dependencies, append `--yes-deps` as well as `--enable`. Without dependency consent, upstream can return exit0 with the plugin **installed but disabled**; verify `hermes plugins list --plain --no-bundled` reports `enabled`, then run `hermes even-g2 check`. This behavior was exercised from a clean public install.

The command pins the checked-out source commit. Replace `REVIEWED_FULL_COMMIT` with the full reviewed commit ID; a fresh clone alone follows moving main. Rebuild the companion from that same checkout. Current main is protocol 2; historical `v0.1.0-alpha.1` downloads are protocol 1 and lack the review fixes. Hermes 0.22.5 verifies a full immutable SHA. Do not mix components or infer the source version from unchanged alpha package metadata alone.

Offline/directory alternative: unpack a plugin ZIP built from the intended source commit, containing a top-level `hermes-even-g2/`, into `$HERMES_HOME/plugins/` (normally `~/.hermes/plugins/`), then:

```sh
hermes plugins doctor "${HERMES_HOME:-$HOME/.hermes}/plugins/hermes-even-g2" --ci
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

`origins` means the **page/WebView Origin header**, not necessarily the broker host. Inspect non-sensitive Origin metadata with developer tools; do not log Authorization or request bodies. **Blocking hardware gate:** prove the installed package produces a supported exact HTTPS origin (loopback HTTP is development-only). No such packaged origin has been verified here. `null`, wildcard, arbitrary internet HTTP and trailing slashes are refused. If Even packaging produces an opaque/custom-scheme origin, that mode is unsupported by this build. An HTTPS-hosted development page is not proof of a compatible beta delivery path; do not relax the gate to claim success.

`backend_url` may include a trusted routed profile prefix; remote backends must use HTTPS. The **broker bind** is always loopback. Runtime defaults: request timeout 30s, run timeout 600s, 64 lifetime sessions/device, 10,000 lifetime ledger turns total, 16 active turns total, 16 configured devices. Optional manifest settings `max_sessions` (1..1000) and `max_turns` (1..100000) allow deliberate capacity increases without deleting dedup records. Timeouts remain constructor defaults. Run only one broker owner per ledger; do not share it between concurrent service instances.

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
- Upgrade broker and companion together to protocol 2, retaining the ledger and phone resume IDs. Non-health API calls require `X-Hermes-G2-Protocol: 2`; old companions fail before session admission (426), and new companions refuse protocol-1 health. Do not roll back to alpha1 against a ledger containing new `rejected` rows. Preserve recovery backups, but never restore an older ledger that omits subsequently accepted work.
- Revoke one device by removing its digest and restarting the **broker you operate**, or replace its digest while keeping the device name to retain access to existing device-owned sessions. Removing a token does not stop backend work already accepted. Stop those runs through the supported Hermes control surface first if required.
- Stop your broker, then `hermes plugins disable hermes-even-g2`. Disabling discovery alone does not terminate an already-running process.
- `hermes plugins remove hermes-even-g2` removes installed code. Separately remove the companion and decide whether to retain ledger/backups and upstream Hermes history. Do not delete a ledger with unresolved work merely to retry it.

## Troubleshooting

Each session permits at most 32 missing-intent reconciliation tombstones. This is
a local misuse bound, not a per-device quota; increasing `max_sessions` increases
how much of the shared lifetime turn capacity one authorized device can consume.

For uncertain work or capacity, run `hermes even-g2 inspect` locally in the intended
profile. This read-only command reports counts and unresolved turn/session/run IDs,
including the Hermes session mapping; it neither needs a backend credential nor
changes outcomes. Treat its metadata as private. Inspect those exact sessions via
the supported Hermes control surface. If a known run reaches terminal state,
normal status reconciliation frees its active slot. Truly unknown/unreachable
outcomes remain blocked: there is no override that declares an arbitrary run safe.

At lifetime capacity, increase the supported bounds rather than pruning rows. If
an operator must retire an exhausted or unrecoverable ledger: first stop new
admission and stop/inspect all accepted Hermes work, including sessions without a
run receipt. If effects remain unknown, do not repeat the action. Stop the broker,
archive its entire data directory (including SQLite sidecars), revoke **all** old
device tokens, and provision new device labels/tokens with a fresh data directory.
Keep the retired ledger/history for investigation; do not merge/reset individual
rows. A saved turn first looks up its existing session without creating one. A
missing session stays unknown through repeated reconnect/reload, rather than being
classified as never submitted. The phone then offers **Forget lost session locally**
with an explicit warning/confirmation; it creates a new conversation and does not
clear or resolve the retired server history. Start with explicitly new requests, never a
replay of unknown work. This is an operator-managed retirement, not automated
recovery or evidence that earlier actions did not run. No raw SQL editing is needed.

| Symptom | Action |
|---|---|
| Configuration refused | Check exact origins, 64-character lowercase token hash, backend environment key and loopback bind. Never paste keys into a bug report. |
| Unsupported Hermes version | Use 0.22.5 in isolation. Do not remove the compatibility guard or downgrade production. |
| 401 | Re-enter the current device token. Do not substitute a backend key. |
| 426 / protocol mismatch | Install broker and companion from the same reviewed source commit. Alpha1 and main cannot be mixed. |
| 403 / CORS | Check actual page origin against broker `origins`; separately check app network whitelist. |
| SDK timeout | Open inside the Even App, confirm SDK/app minimum, G2 connection and permissions. Safari is not the Even bridge. |
| No audio | Confirm explicit capture, microphone permission and G2 source. Phone recording is not silently substituted. |
| STT unavailable | Verify provider endpoint/model/key and connectivity server-side. Text fallback can diagnose the rest of the path. |
| Outcome uncertain / unknown | Reconcile with the same IDs. A missing intent is durably sealed; an existing uncertain intent still requires inspection using `inspect`. No automatic submission retry. |
| Broker has no accessible session record | Inspect retired ledger/Hermes. Reconnect/reload cannot recreate the saved turn's session. Use the informed local-forget control only to start a genuinely new conversation, not repeat unknown work. |
| Stop not confirmed | Reconcile again; keep current resume IDs. Stop is not rollback. |
| Unsupported approval | Use the supported server control surface or deny/stop. Never approve blindly or disable policy. |
| 429 / capacity reached | Use `inspect`, reconcile/stop active work, or increase bounded lifetime capacity. Preserve dedup records; see retirement procedure above. |
| Phone locks / app backgrounds | Capture is discarded best-effort; network may stop. Reopen/re-enter token/reconcile. No background guarantee. |
