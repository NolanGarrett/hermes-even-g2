# Hardware acceptance checklist

**HARDWARE UNVERIFIED — none of the physical checks below have been completed.** Software test success is not a substitute.

Record G2/R1 firmware, Even App version (>=2.2.10), phone model/OS, SDK0.0.16, exact project commit, network topology and foreground/background state. Use synthetic/non-sensitive requests and a constrained test agent.

- [ ] Approved developer enrollment; correct app package and permissions; exact origin whitelist and broker CORS.
- [ ] Beta build promoted Private→Beta and tester Active; actual installation and glasses-menu launch.
- [ ] **Blocking before functional claims:** record actual packaged WebView Origin and prove strict authenticated CORS/whitelist access. Opaque/null/custom origins are unsupported; do not claim a hosted beta workaround without evidence. Pair protocol-2 broker/companion from the same source commit.
- [ ] Cold launch displays phone setup instructions before authentication; Connect/reconcile does not recreate startup. Root double-tap opens system exit dialog before auth, after local disconnect, while idle, during capture and with an unresolved run; stop intent survives without claiming cancellation. Check native OS Close action separately.
- [ ] Temple tap start/finish; optional R1 tap/scroll; long-press9/release10; OS-intercepted tap-then-hold fallback.
- [ ] No unintended capture on launch, absent SDK events, reconnect, page change or notification.
- [ ] G2 mic PCM received at expected format; live STT intelligibility; silence/noise/error handling; never phone-mic fallback.
- [ ] Capture LED/physical microphone behavior stops on cancel, 30s cap, display failure, disconnect, pagehide and app dismissal.
- [ ] Late `audioControl(true)` after timeout is compensated by close; no resumed recording. Test overlay events4/5 without confusing them with teardown; capture must not restart automatically. Check whether CLICK precedes DOUBLE_CLICK on target firmware.
- [ ] Readable 576×288 text: <=260 code-point pages, estimated seven body rows/42 columns, newline-heavy lists, Unicode, long words, page count, truncation marker, swipes and phone paging. Full replacements must clear long-to-short stale tails.
- [ ] Real model + harmless tool answer; follow-up context preserved; new session separate; no prior Desktop/CLI session attachment.
- [ ] Real phone approval full text visible; deny/once; stale prompt and wrong device rejected; no glasses autoapprove.
- [ ] Scroll long phone approvals across multiple polls without losing position; recognized transcript visible with actual submission status (not tap-to-confirm).
- [ ] Stop requested vs acknowledged vs cancelled; in-flight submission stop; already-completed effects not represented as rolled back.
- [ ] Loss of Wi-Fi/cellular/VPN, tunnel reconnect and broker restart: reconcile same IDs, no action replay.
- [ ] Device connected/battery pushes do not discard capture. Lost-session local reset shows and honors the informed confirmation in the actual WebView (`window.confirm` host behavior is unverified); Cancel preserves IDs and Continue creates a new conversation without resolving old effects.
- [ ] App background, locked iPhone, 1/5/15-minute idle and return: record failures honestly. No guarantee inferred from docs.
- [ ] Token lost on app termination, correct re-entry, revocation/rotation; no bearer in storage/URLs/logs.
- [ ] TLS validation from actual WebView, including private CA if used; no mixed content or null-origin workaround.
- [ ] R1 absent/unpaired and G2 disconnected: safe errors and phone controls; no assumption ring can launch inactive app.
- [ ] Android separately validated before any Android-support claim.

A native Even AI endpoint test is separate: approved Agent Configuration access, full chat-completions URL and dedicated key, response/continuation behavior. Passing that route does not validate Hub approval/run control.
