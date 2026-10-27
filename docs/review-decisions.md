# Review decisions for unreleased source

This note records material design decisions, not a hardware certification. Main is
protocol 2; the historical alpha1 release remains unchanged. Use matching source
commits for broker and companion. Full test boundaries are in [verification](verification.md).

## Accepted and corrected

- Native lifecycle: create the setup page once at WebView startup, independently of
  phone authentication. Reconnect reuses it and can probe/recover a failed display.
  Root double-tap discards capture, persists/requests active stop, then requests the
  native system exit dialog without waiting on the backend. The pre-auth and
  disconnected page retains an exit handler, even after startup/bridge timeout.
  Failed microphone close does not remove the exit path. OS Close remains available; no custom
  Exit menu is added. No physical dialog behavior has been verified.
- Display and input: use basic full replacement without partial-string offset or
  length fields; suppress identical writes; keep approval DOM nodes stable across
  unchanged polls; preserve truncation notices and estimate line-aware pagination.
  Show recognized speech with actual request status, not as a false confirmation gate.
  Ordinary connected device/battery pushes do not interrupt capture or reconnect.
  Compensate for a native microphone open that resolves after its timeout, and
  refuse new capture while that operation is unresolved.
- Admission: distinguish a proven pre-submission failure from an uncertain request.
  Retain a terminal rejection record for the former. A missing broker intent is
  sealed durably before releasing the client, so delayed delivery cannot run it.
  Existing uncertain reservations never become rejected merely because a status
  request failed. Protocol pairing prevents historical clients misreading the new
  state or calling a nonexistent reconciliation route.
  A saved turn first requires a read-only lookup of its existing session. A missing
  session is never recreated before reconciliation, including repeated Connect and
  reload. Only an informed phone-only reset creates a new conversation, without
  claiming the old work did not execute. A per-session cap bounds empty tombstones.
- Operations: local read-only inspection exposes recovery IDs and counts; lifetime
  bounds can be increased without deleting dedup records. Deadline-stop failures
  no longer hide status/approvals, and retries are bounded in frequency. Source
  packages require clean committed files, rebuild ignored companion output, and use
  commit-suffixed snapshot names. A no-run stop refusal is not repeated on every
  unchanged poll; the durable stop intent remains for inspection/recovery.

## Narrowed or rejected suggestions

- Do not clear an unknown turn on a generic 404 or treat every 4xx as proof of
  non-execution. A delayed POST can race a lookup; a proxy can change failure
  semantics. The durable rejection handshake is the narrower safe fix.
- Do not re-POST an uncertain action using presumed durable upstream idempotency.
  Credential/profile scope and availability can change, and this ledger intentionally
  does not retain raw prompt bodies. Inspect the original session instead.
- Do not prune terminal records or add an override that invents completed/failed
  outcomes. An old authorized request can replay after dedup deletion. The install
  guide describes capacity increases and deliberate credential-separated retirement
  with preserved evidence; unresolved effects are not declared safe.
- Do not enable opaque/null origins or custom schemes merely because a native
  package might use them. The actual installed WebView Origin must be measured.
  Compatible package networking is a blocking hardware gate, not an inferred fact.
- Do not persist a bearer to satisfy setup convenience. Memory-only entry is an
  explicit security/UX tradeoff; this preview does not claim seamless remembered
  authentication or public marketplace readiness.

## Official-source precedence

The [page lifecycle](https://hub.evenrealities.com/docs/build/page-lifecycle),
[display](https://hub.evenrealities.com/docs/build/display),
[device APIs](https://hub.evenrealities.com/docs/build/device-apis), and
[contextual menu](https://hub.evenrealities.com/docs/build/contextual-menu) pages
supply the specific contracts, with actual SDK 0.0.16 declarations/serialization
checked. Current FAQ and background pages disagree about background networking;
foreground-only remains the supported assumption. Device APIs place long-press
9/release10 on sysEvent while FAQ routing and SDK event-source comments differ;
we do not require source metadata and never turn an absent sysEvent type into a
click. Explicit double-click 3 is accepted on textEvent or sysEvent. Overlay events
4/5 conservatively discard capture but are not interpreted as proof of teardown.
These discrepancies remain on the physical checklist, not papered over by mocks.

The supported Hermes plugin storage helper and CLI registration remain documented
public APIs; no core monkeypatch or private runtime dependency was introduced.
Dependency versions/licenses are unchanged, and bundled notices remain intact.
