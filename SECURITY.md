# Security policy

This is an independent, **HARDWARE UNVERIFIED** prerelease. Reviewed main uses broker protocol 2 with Hermes Agent 0.22.5; the historical 0.1.0a1 release remains protocol 1 and does not contain main's corrections. Install matching source-built components. There is no production suitability or response-time guarantee, and native package Origin compatibility remains a blocking hardware gate.

Do not include credentials, real speech, transcripts, private hostnames, personal information or full configuration in public reports. Use GitHub's private vulnerability reporting if available. If unavailable, open a minimal issue requesting a private reporting channel without exploit details or secrets; never publish working credentials.

## Trust boundaries

- The phone carries a revocable device token, never a Hermes/provider credential. Tokens stay in memory; close/reload requires re-entry. A compromised WebView or malicious trusted-origin script can still steal that in-memory token.
- A token permits that device to use the agent, not just read text. The broker does not sandbox tools. Choose a least-privilege profile; maintain upstream approval policy. Voice/LLM content is untrusted.
- Backend/session identity is server-minted. Clients cannot attach a known foreign upstream session, supply system prompts/history/model overrides, or proxy arbitrary backend paths.
- Exact origins, no wildcard/null, TLS verification, no authorization-bearing redirects, bounded requests/audio/responses/concurrency, constant-time token comparison and per-device session limits are enforced. There is no per-minute billing quota; an authorized device can make repeated sequential requests. Apply provider budgets and proxy throttling for your deployment.
- Canonical approvals are phone-only, complete and generation-bound; stale/cross-session/repeated decisions fail closed. Unsupported or overlong requests require server-side handling. No `always` grant exists in this client.
- Durable intent tracking is not a distributed exactly-once guarantee. Ambiguous submission/approval outcomes block rather than replay. Protect the ledger and backups. Do not reset it to force a retry.
- Missing-intent reconciliation writes a durable rejection tombstone before declaring non-submission; it is not a retry endpoint. Existing uncertain records are not cleared. Keep one broker owner per ledger. Local `inspect` exposes sensitive recovery metadata read-only; never post it publicly. Preserve tombstones during capacity management and upgrades, and never restore a pre-action ledger over newer accepted work.
- API and STT keys are environment-only; access logging is disabled in the broker. Configure your reverse proxy not to log auth headers/bodies. Provider and Hermes retention remain separate.
- This software does not defend against a compromised server, malicious plugin, compromised provider, compromised trusted origin, or an authorized user intentionally asking the agent to act.

## Incident response

Stop using the phone. Remove/rotate its token digest, then restart only your broker through your normal operational process. Independently inspect and stop accepted runs through Hermes if necessary; revocation cannot undo completed effects. Preserve ledger evidence, avoid replay, rotate exposed upstream credentials using your organization's procedures, and review provider/server logs without exposing them publicly.

See [deployment](docs/deployment.md), [privacy/control semantics](docs/privacy-controls.md), and [verification limits](docs/verification.md).
