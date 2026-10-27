# Changelog

## Unreleased — reviewed source, protocol 2

**HARDWARE UNVERIFIED.** Install broker and companion from the same source commit.
The historical `v0.1.0-alpha.1` release and its assets remain unchanged.

- Start the native setup page once before phone authentication; reuse it across reconnects. Root double-tap invokes the native exit dialog, preserving active stop intent; pre-auth and disconnected exit remain available.
- Use documented full text replacement, recover the display after transient failure, suppress identical writes, keep approval requests readable across polls, and compensate for late native microphone opens after timeout.
- Distinguish proven backend non-submission from uncertain delivery. Durably seal absent intents before releasing a phone's unknown turn, with delayed/concurrent submit and restart regressions. Never replay actions or erase uncertain records.
- Pair protocol-2 components explicitly; old/new mismatches fail before admission. Add read-only local recovery inventory and bounded configurable lifetime capacities without pruning replay evidence.
- Preserve truncation warnings, estimate line-aware pages, and display recognized speech without claiming a confirmation gate. Deadline-stop failures no longer hide status/approval data.
- Require clean-source, commit-suffixed snapshot packaging; ordinary browser tests no longer overwrite tracked screenshots.
- Keep lost sessions unknown across repeated reconnect/reload; offer informed local reset instead of recreating a saved turn's session. Native exit survives microphone-stop failure and late startup; ordinary device-status pushes no longer interrupt capture. Bound missing-intent tombstones and stop-refusal retries, and rebuild ignored outputs before snapshot packaging.
- Refresh installation, operation, security, privacy, hardware gates and source-vs-release documentation against current official docs. The real packaged WebView Origin remains a blocking unverified deployment gate; no relaxed-origin or marketplace-readiness claim.

## 0.1.0a1 — software preview

**HARDWARE UNVERIFIED.** Initial independent community prerelease.

- Native Hermes 0.22.5 directory plugin and real Even Hub SDK 0.0.16 companion.
- Explicit bounded audio, OpenAI-compatible WAV transcription transport, contextual runs, text fallback, progress and plain-text pagination.
- Revocable device tokens; server-minted upstream session identity; exact origins and loopback broker.
- Durable deduplication and status-only reconnect, uncertain-outcome refusal and acknowledged stop semantics.
- Complete phone-only canonical approvals, bound to prompt/run/session/execution generation; once/deny only.
- Protocol, controller, real-public-runtime composed harness and browser simulator tests; release templates and complete source.

A separate bounded live Anthropic inference run through public Hermes executed a real harmless terminal tool. Not verified: physical G2/R1, actual iPhone/Android behavior, locked/background networking or live STT. Deployment-specific origin rebuild and Even developer/beta access are required. See verification and hardware checklist.
