# Contributing

Keep the project independent and hardware claims evidence-based. Read the architecture, security policy and verification guide first.

Use public Hermes v0.22.5, isolated disposable HOME/HERMES_HOME, a sanitized environment and explicit `gateway run --no-supervise`. Never test against a personal/production agent or use its auth/config/data as fixtures. Synthetic inputs only. Do not weaken exact origin, TLS, session ownership, approval or replay guards to make a test pass.

Run Python protocol/runtime tests, TypeScript tests/build, browser simulator, npm audit and package build as documented in [verification](docs/verification.md). Add a focused regression for behavior changes. Keep all writes in one source branch; do not publish generated logs with host paths or credentials.

Pull requests should describe the changed boundary, actual commands/results, mocked versus live parts, and hardware status. Report only hardware combinations you personally tested (app/SDK/firmware/phone OS and foreground/background state). Screenshots must contain synthetic data and clearly identify simulation.

Original contributions are MIT licensed. Preserve third-party license notices. Do not copy unlicensed integrations or infer a software license from a data-only NOTICE file. No account setup, marketplace submission or package-registry release is part of CI.
