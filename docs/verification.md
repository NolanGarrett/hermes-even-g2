# Verification and release

**HARDWARE UNVERIFIED.** This file separates software behavior from platform documentation and physical/live-provider validation.

## Capability matrix

| Capability | Evidence category | What the evidence means |
|---|---|---|
| Native plugin manifest, doctor, registration, `check` and `serve` | VERIFIED SOFTWARE | Loaded by public Hermes v0.22.5 in a disposable home; CLI broker actually served requests |
| Explicit voice state machine, PCM/WAV transport, context, progress and paging | VERIFIED SOFTWARE | Actual controller/transport/broker exercised; PCM/display/STT/model fixtures are synthetic |
| Real Hermes tools and contextual history | VERIFIED SOFTWARE | Actual public gateway executed harmless `printf G2_TOOL_OK`; deterministic model fixture requested it; next turn contained real prior user/tool history |
| Canonical pending approval / once / deny / stale refusal | VERIFIED SOFTWARE | Actual Hermes pending controls for chmod on disposable dummy files; stale generation refused, deny preserved0600, once changed only intended dummy to0777 |
| Device ownership, server-minted session mapping, dedup/restart, cancel, timeout, CORS, resource bounds | VERIFIED SOFTWARE | Real HTTP/SQLite tests plus controller regression suite; no hardware assumption |
| Mobile-width simulator phone UI | VERIFIED SOFTWARE | Headless Chromium, synthetic scenarios and no horizontal overflow; screenshot visibly labeled simulation |
| G2 audio/gesture/display APIs, app floor, beta lifecycle | DOCUMENTED PLATFORM CAPABILITY | Official docs and SDK declarations; not physical proof |
| Ring/temple gestures, readability, microphone shutdown, Bluetooth | HARDWARE REQUIRED | Checklist pending |
| iPhone locked/idle/background, network transition; Android | HARDWARE REQUIRED | No guarantee; conflicting official iOS background descriptions |
| Live model and real terminal tool | VERIFIED SOFTWARE — LIVE PROVIDER | Separate bounded public-Hermes API run using supported Anthropic provider, `claude-haiku-4-5-20251001`: completed, actual disposable file contained `G2_LIVE_OK`, model returned `G2_LIVE_DONE`; existing credential was memory-only, no refresh/copy, no raw credential persisted |
| Live STT provider | NOT VERIFIED | No live STT credential provisioned; synthetic PCM/WAV and deterministic HTTP transcription fixture only |
| Even enrollment/approval, beta installation, native Agent Configuration | ACCOUNT + HARDWARE REQUIRED | No account or marketplace submission performed |

The composed harness runs the real TypeScript Controller and HttpTransport compiled in Node against the installed broker and actual public Hermes gateway. It does not replace that transport with the demo Simulator. It injects a synthetic display/audio adapter and deterministic model/STT HTTP fixtures. Browser rendering and the live-provider probe are exercised separately. Do not describe the deterministic composed harness itself as live inference or full hardware end-to-end validation.

## Reproduce

From the source root, with Node22.12+ and public Hermes v0.22.5 installed in a sibling `upstream-hermes/` using `uv sync --frozen`:

```sh
cd companion
npm ci
npm test
npm run build
npm audit --audit-level=high
npx playwright install chromium
npx playwright test
npm run pack
cd ..
HERMES_TEST_ROOT="$(cd ../upstream-hermes && pwd)" ../upstream-hermes/.venv/bin/python -m pytest -q
```

Install `aiohttp==3.14.5`, `pytest==9.1.1` and `pytest-asyncio==1.4.1` explicitly into that disposable upstream environment after frozen sync. For uv use `uv --no-config pip install --python ../upstream-hermes/.venv/bin/python aiohttp==3.14.5 pytest==9.1.1 pytest-asyncio==1.4.1` to avoid applying the upstream development upload-age cutoff to these supplemental test pins. Without `HERMES_TEST_ROOT`, runtime integration is explicitly skipped; a protocol-only green run is not full qualification. The composed Node harness needs `npm ci` but no browser. Linux browser dependencies can be installed in a disposable CI runner via Playwright `--with-deps`; do not alter a production host merely to obtain a screenshot.

The initial local qualification ran Python3.14, Node26.7 and Chromium141; CI uses Node22 and the frozen public upstream runtime. Current suite: 20 protocol/config cases +1 composed runtime case, 21 controller/transport cases and 1 browser simulator scenario. The workflow on the exact release commit is authoritative for CI status. Tests remain finite, use synthetic inputs, sanitize subprocess environments, explicitly pass `--no-supervise`, bind only loopback, and terminate only owned children. No production config/auth/memory is copied.

## Live operator test

Provision a dedicated least-privilege test profile and your own supported live model/STT provider through official Hermes configuration. Start the broker as documented. Put the broker HTTPS URL and narrow device token in `EVEN_G2_SMOKE_URL` and `EVEN_G2_DEVICE_TOKEN` using a non-echoing/environment-secret mechanism, then:

```sh
python scripts/operator_smoke.py
```

This explicitly sends a bounded request to run `printf G2_TOOL_OK` and a contextual follow-up. Inspect the actual server tool event/result: model claims alone do not prove tool execution. It does not autoapprove any pending action. To exercise live STT, add `--wav /path/to/non-sensitive-test.wav` with <=30s signed16 mono16kHz audio saying the test request. That audio is sent to your configured STT provider. The separate live qualification above establishes one real model/tool run, not this operator script's execution in your deployment or live speech accuracy.

## Build and publication

`python scripts/package_release.py` uses explicit tracked public files and the current Git HEAD to build:

- Directory plugin ZIP (native manifest, registration, Python source, docs/licenses).
- Built companion web ZIP and `.ehpk`, both deployment templates using reserved origin.
- Complete source ZIP from exact HEAD.
- SHA256SUMS for download integrity.

Run it only after staging/committing reviewed public files and building/packing the companion. The repo has no registry/marketplace deployment workflow. CI has read-only repository permission and uploads only test-built artifacts.

Before first push/release inspect tracked files and all history, generated bundle text/maps, fixtures, screenshot, notices and archives for credentials/private identifiers/paths. Keep runtime environments, caches, logs, auth, ledgers and private operator instructions out. Source maps are disabled. Preserve third-party notices. Read back repository owner/visibility/license, exact-head CI, tag/release and asset metadata; download public assets into a clean location, verify checksums and smoke directory-plugin loading/companion content. Upload success alone is not release verification.

## Remaining limits

Not a background voice assistant, OS sandbox, universal version bridge, general proxy, or existing-session attachment. Text is bounded; unknown outcomes require operator reconciliation. No automatic ledger pruning/migration policy beyond this initial schema. App origins and deployment-specific TLS are operator responsibilities. A valid packaged template is not proof that your developer account can install it. See [hardware checklist](hardware-checklist.md).
