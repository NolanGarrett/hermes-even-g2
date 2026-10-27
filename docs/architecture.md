# Architecture and compatibility

Status: HARDWARE UNVERIFIED prerelease. Independent community project, not an official Even Realities or Nous Research product.

## Decision

A native Hermes directory plugin registers `hermes even-g2 check|serve|inspect`. Its explicitly started, in-process, loopback HTTP service is a narrow authenticated broker; registration never starts listeners or changes host settings. The open-source TypeScript companion runs in the Even App's Hub WebView and uses the real Even Hub SDK. No extra relay, account service, or cloud database is needed. A small plugin-owned SQLite intent ledger is necessary to prevent lost replies and restarts from replaying actions; it contains identifiers and request digests, not transcripts or audio.

Data flow:

    G2 microphone / optional R1 gestures
        -> Even App WebView (SDK, memory-only device token)
        -> private HTTPS reverse proxy -> plugin broker (loopback)
        -> configured STT endpoint (WAV, ephemeral)
        -> existing Hermes /v1/runs -> configured agent/tools/policies
        <- authenticated status + bounded event snapshots <- paginated G2 text

The API's full backend credential and STT provider credential never reach the companion. The device credential is revocable separately and can access only that device's broker-created sessions/runs. It still authorizes speech-driven use of the configured agent's tools: it is not a read-only agent or an operating-system sandbox.

Hermes support is deliberately bounded to **0.22.5 only** (`>=0.22.5,<0.22.6`). The bridge uses documented HTTP Runs APIs, not agent monkeypatches. API-owned conversations keep real server-side history, skills, memory, and tools; this is not attachment to an existing CLI/Desktop conversation. No client-supplied history, system prompt, model overrides, arbitrary upstream paths, or admin methods are forwarded.

Approvals are phone-only and fail closed. Only canonical pending prompts with exact run/session/prompt/generation identity can be answered, and only `once` or `deny`. Glasses show a handoff, never auto-approve. Unsupported/legacy approval shapes require the server's supported control surface. Stop is a request, not rollback: a `stopping` acknowledgement is not a terminal `cancelled` receipt.

Reconnect never resubmits work. Intent is committed before submission. A preflight failure or failure to establish the backend connection is positively unsubmitted and stored as terminal `rejected` with its tombstone retained. A lost upstream submission receipt remains uncertain and blocks subsequent turns. A phone-to-broker failure may leave no intent at all: after an authenticated 404, the client POSTs `/sessions/{sid}/turns/{tid}/reconcile`. That lookup either returns an existing scoped intent or durably inserts a rejection tombstone before saying it was not submitted. A late original POST cannot execute against the sealed ID. A bare 404, arbitrary 4xx, or network exception never authorizes clearing uncertainty. Phone storage retains only connection/session/turn identifiers and stop intent, never a bearer, prompt, PCM, or answer.

Protocol 2 explicitly pairs the reviewed components: health advertises `protocol: 2`, and non-health requests require `X-Hermes-G2-Protocol: 2`. Old alpha1 companions cannot admit work to the new broker; new companions reject an old broker. Keep a single broker owner per ledger. `inspect` is a local read-only recovery inventory; capacity increases and safe retirement are documented, not implicit eviction.

The native page starts once at WebView load, before phone authentication, with setup instructions. Reconnect reuses that page and transport; a failed display can be probed without recreating startup. Root double-tap discards capture, preserves/requests stop for active work, and invokes the native exit dialog without waiting for a network stop receipt. Exiting is not cancellation confirmation. Matching text writes are suppressed and phone approval DOM stays stable across identical polls.

Saved turns use read-only `GET /sessions/{sid}` before reconciliation. Missing
sessions remain unknown; they are not recreated by Connect or reload. The durable
missing-intent rejection guarantee assumes the session's accepted ledger history
has been preserved. Restoring an older backup that omits accepted turns is forbidden;
session existence alone cannot detect that rollback. Local reset starts a new
conversation only after an informed phone confirmation, never claiming old effects
did not occur.

## Source grounding

Inspected public Hermes tag v0.22.5, commit `bf0203a794a07aac3ff764972ab9087baa4e4f4e`, including plugin guide, API server documentation and canonical run-control implementation. Official references:

- [Plugin contract](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/): manifest, `register(ctx)`, CLI registration and isolated doctor.
- [API server](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server): capabilities, durable idempotency, status/events/stop, pending-controls approval binding, API-owned session history.
- [Even device APIs](https://hub.evenrealities.com/docs/build/device-apis): startup page before glasses audio; signed 16-bit little-endian mono PCM at 16 kHz; long press 9/release 10 on sysEvent; click zero can normalize to undefined only within an actual text event.
- [Networking](https://hub.evenrealities.com/docs/build/networking): exact origin whitelist plus independent CORS gate.
- [Packaging](https://hub.evenrealities.com/docs/ship/packaging): `app.json`, permissions, `.ehpk`, SDK-derived app floor.
- [Beta testing](https://hub.evenrealities.com/docs/test/beta-testing): promoted Beta build and Active tester required for menu/lifecycle testing.
- [Page lifecycle](https://hub.evenrealities.com/docs/build/page-lifecycle): startup exactly once and root `shutDownPageContainer(1)` exit dialog.
- [Display system](https://hub.evenrealities.com/docs/build/display): full text replacement omits partial-update offset/length fields.
- [Contextual menu](https://hub.evenrealities.com/docs/build/contextual-menu): OS-provided Close item; no redundant custom Exit. Overlay enter/exit events are not app teardown.
- [Background lifecycle](https://hub.evenrealities.com/docs/build/background-lifecycle) and [FAQ](https://hub.evenrealities.com/docs/reference/faq): conflicting iOS network/background descriptions; no locked-phone guarantee.

SDK TypeScript declarations define callable shapes. Pin `@evenrealities/even_hub_sdk` 0.0.16 (Even App floor 2.2.10). G2 has no speakers or camera. R1 is optional and cannot be assumed to deliver OS-intercepted gestures or launch an inactive app. OcuClaw was considered as a reference, but no implementation was reused because a redistribution license was not established.
