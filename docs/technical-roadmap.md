# Technical Roadmap

## Near term

- Replace the fixed backend port with a negotiated or injected runtime port
- Add backend supervision and restart logic in the packaged app
- Add code signing, notarization, and Windows installer hardening
- Add connection test flow for remote model providers

## Product hardening

- Improve tool sandboxing beyond workspace boundary checks
- Add approval expiration, retries, and concurrent decision protection
- Expand timeline filters and support diagnostics export
- Add better frontend recovery actions for failed backend startup

## Agent depth

- Integrate more of the Nanobot runtime where it does not break SQLite-first boundaries
- Add first-class session summaries and message pagination
- Add richer budget accounting when providers expose real usage/costs
- Introduce recovery and retry controls for task runs

## Operational maturity

- Add release automation and artifact verification
- Add smoke tests for packaged bundles in CI
- Add structured support bundles for logs, config, and diagnostics
- Prepare updater-safe data migrations and rollback rules
