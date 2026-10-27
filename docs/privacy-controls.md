# Privacy, sessions and controls

## Audio and retention

Only an explicit tap/hold/phone-button starts glasses microphone capture. There is no ambient listener/hotword. The SDK supplies 16 kHz signed 16-bit little-endian mono PCM. Capture is bounded to 30 seconds / 960,000 bytes. Cancel, background and connection-error paths attempt microphone shutdown and discard unsent audio; no browser code can guarantee execution after OS suspension.

The broker wraps PCM as WAV and sends it to a configured OpenAI-compatible multipart transcription endpoint (`file`, `model`, `response_format=json`). Default: `https://api.openai.com/v1/audio/transcriptions`, model `whisper-1`; the operator supplies a key. A local loopback compatible STT service can avoid cloud transcription; another remote provider must use HTTPS and the same API contract. Only the transport/WAV path was tested with synthetic PCM and a deterministic STT fixture, not live provider accuracy or retention.

The companion and broker do not intentionally write audio, prompts or answers to disk. Audio/transcripts temporarily exist in memory, and your OS may swap/crash-dump memory. The STT provider receives audio; the configured Hermes model provider receives text/tool context. Hermes itself normally keeps session history and tool outputs, and providers have their own retention/policies. This project neither erases those records nor changes those policies. Do not interpret “no companion conversation database” as end-to-end zero retention.

Phone localStorage contains only origin-bound session/turn IDs and pending stop intent. The device token stays in JavaScript memory, never localStorage; re-enter it after reload/close. Disconnect clears it. The broker's restricted-permission SQLite ledger retains device labels, IDs, server-minted backend mappings, request digests, run/control state and timestamps, but not raw tokens, transcripts or answers. These metadata can still be sensitive; protect backups. No automatic ledger pruning exists because pruning can undermine deduplication; at capacity new work is refused until an operator deliberately manages state.

## Sessions and reconnect

Before restoring a saved turn, the client looks up its existing broker session
without creating one. Missing or inaccessible sessions remain unknown across
reconnect/reload. The explicit phone-only local-forget confirmation starts a new
conversation; it neither declares prior effects absent nor alters server history.
Missing-intent reconciliation is valid only within a session the current ledger
still holds. Restoring an older ledger that omits accepted work is forbidden:
an existence lookup cannot detect rollback within an otherwise known session.

Recognized speech is submitted immediately, not held for confirmation. A bounded
"Heard" preview appears on the glasses while submitting and the full recognized
text stays visible on the phone for the current turn. It is memory-only and clears
on the next capture/text turn, new session or local disconnect. This improves
visibility but cannot prevent a tool action caused by misrecognition; keep agent
permissions and approvals appropriately constrained.

The broker mints a private backend session ID independent of the phone-facing UUID. Each device can access only its own broker sessions. Follow-ups continue the real API-owned Hermes history. New session starts a new conversation; it does not erase old history. Existing CLI/Desktop or other-device sessions cannot be attached.

Before submitting, the broker commits intent keyed by device/session/turn and digest. An identical duplicate returns the recorded turn; conflicting content is rejected. At most one unresolved turn per session and 16 globally are admitted. A restart/status loss never blindly repeats a run submission. A lost upstream receipt becomes uncertain: inspect the exact Hermes session before doing anything that could repeat effects. There is intentionally no “force retry unknown action” button.

Only positive pre-submission evidence (backend preflight/connection-establishment failure) creates terminal `rejected`. When the broker has no intent for a phone's saved ID, reconciliation durably seals that ID as rejected **before** releasing the client; a delayed original POST is refused. A 404 alone is never proof of non-submission. Existing uncertain rows are never auto-cleared, and no HTTP status class is assumed to mean an upstream action could not have run. Use `hermes even-g2 inspect` and the [operator procedure](install.md) for genuinely unresolved work or capacity. Tombstones are retained, not pruned.

Readback can recover outputs from Hermes while they remain available. The local ledger is not an answer archive. Display text is limited to 32,000 characters, paged to at most 260 code points and an estimated seven body lines at 42 columns; a separate final page preserves a truncation warning. These are conservative software budgets, not measured font metrics. Larger answers require the full server-side record. Rendering uses text nodes, never HTML. Actual font fit/readability requires hardware validation.

## Stop, dismissal and failure

- Stop during recording: discard audio, no new run.
- Root double-tap: discard audio, persist/request stop if a run is active, and open the native exit dialog without awaiting network acknowledgement. Phone Stop/discard does not request exit. Resume and pending-stop IDs survive native exit.
- Stop during submission: remember stop intent, dispatch after run acknowledgement; a failed stop remains unconfirmed and is reconciled later.
- Backend stop receipt: accepted/stopping, not proof of terminal cancellation. Continue status polling until terminal state.
- Dismiss: clear/reduce display state; backend work continues.
- Disconnect/reload: not cancellation. Resume IDs remain so you can re-enter the token and reconcile.
- Timeout/watchdog: requests backend stop for aged work with a 30s retry interval; stop failures do not hide authoritative status/approvals. Unresolved/unreachable work still consumes admission rather than silently allowing another side effect.

Stop never rolls back completed tool actions. Errors are sanitized; operator diagnosis belongs on the trusted server.

## Approval boundary

The broker rereads authoritative canonical pending controls. Only terminal-command/file-edit approval prompts with a complete renderable request and exact prompt ID/execution generation are eligible. Controls must offer both once and deny. Phone users see the full JSON-formatted request; content over 16,000 characters is rejected, not truncated. Other/unrecognized controls show a server handoff.

Decisions are bound to the device's session/run and current canonical prompt. The decision intent is durably recorded before forwarding. Duplicate, stale, cross-session, mismatched-generation and unsupported choices are refused. Unknown decision outcomes are not replayed. Glasses never expose an “approve” gesture. Do not approve content you did not intend; speech can be misrecognized and prompt injection can appear in tool data. Upstream Hermes remains the final policy authority.
