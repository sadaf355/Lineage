# Phase 3 + 4 Release Notes

This release builds on the Phase 1–2 LINEAGE release and includes the Phase 3/4 detection, tracing, security, and privacy work.

## Phase 3
- Configurable two-model image detector ensemble.
- Configurable 12-frame video sampling with aggregated confidence range.
- Labelled-set detector evaluation with accuracy, precision, recall, F1, ROC-AUC and condition breakdowns.
- Audio uploads, deterministic spectrogram fingerprinting, and optional configured audio classifier scoring.
- Optional licensed Google Cloud Vision Web Detection candidates.
- Optional JavaScript-rendered tracing through Playwright.
- Normal HTTP(S) tracing pins the connection to the public IP selected during validation while retaining the original hostname for TLS SNI/certificate verification.

## Phase 4
- Redis-backed rate limits with safe in-memory fallback.
- Short-lived access tokens and rotating, server-revocable HttpOnly refresh sessions.
- Chunk-aware request-size enforcement and streaming encrypted upload storage.
- Current/previous encryption-key rotation support; direct secrets-manager integration remains planned.
- Private decrypted-analysis temp directory with stale-file cleanup at startup.
- Explicit review confirmation before accepting traced matches.
- Retention purge reuses incident file cleanup.
- Production rejection of placeholder JWT/encryption secrets.

## Validation
- Backend source compiles with `python -m compileall`.
- Source-tracing/evaluation security tests pass in the available environment.
- Full pytest and frontend build should be run in CI or a development environment with the locked Python/npm dependencies installed.
- Optional second-model, audio-model, Vision, and Playwright integrations must be validated independently before being enabled in a production demo.
