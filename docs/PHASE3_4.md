# LINEAGE Phase 3 + 4

## Phase 3 — stronger detection and tracing

- Image detection supports a configurable second Hugging Face classifier. The API only labels a two-model ensemble when two configured models actually return recognized manipulation scores.
- Video detection samples a configurable set of 12 frames by default and aggregates model scores with a confidence band. The code keeps the frame count explicit; it does not claim benchmark accuracy without a labelled evaluation set.
- `/incidents/{id}/detection/evaluation/run` accepts a labelled JSON or CSV manifest and reports accuracy, precision, recall and F1 for that supplied set.
- Audio uploads are accepted. Spectrogram fingerprints are computed deterministically. Optional audio-deepfake scoring is enabled only when `AUDIO_DEEPFAKE_MODEL_ID` is configured and successfully loads.
- `/reverse-search` provides an optional licensed Google Cloud Vision Web Detection adapter. Returned pages are candidates and require investigator confirmation.
- URL tracing connects to the exact public IP selected during validation for normal HTTP(S) requests, preserving the original hostname for Host/SNI/certificate verification. This closes the hostname-validation/DNS-rebinding gap for the normal tracer. Optional Playwright rendering adds request interception and the same public-network validation; browser-level DNS pinning remains a deployment hardening consideration.

## Phase 4 — security and privacy

- Redis-backed rate limiting is used when `REDIS_URL` is configured, with an explicit single-process fallback when Redis is unavailable.
- Login, upload, URL tracing and Copilot requests have separate limits.
- Uploads are streamed to authenticated encrypted chunks instead of first buffering the entire plaintext upload. Legacy Fernet files remain readable.
- Access tokens are short-lived and refresh tokens rotate through an HttpOnly cookie.
- Production refuses placeholder JWT and encryption secrets. Encryption-key rotation is supported through `FILE_ENCRYPTION_KEY_PREVIOUS`: new writes use the current key and reads accept current/previous keys. Direct AWS/Azure secrets-manager integration is planned; the current deployment reads the key from environment configuration.
- Request body size is bounded even for chunked requests; upload/evidence persistence streams plaintext into authenticated encrypted chunks and file-backed analysis avoids a second whole-file plaintext buffer.
- Sensitive actions remain review-gated. Accepting a traced source requires an explicit `review_confirmed=true` action after inspecting the candidate evidence, and face-similarity results are not identity proof.
- Retention settings are explicit and a user can trigger a retention purge for an eligible case.

## Optional integrations

Playwright browser binaries must be installed separately on hosts that enable `TRACE_USE_HEADLESS_BROWSER`:

```bash
playwright install chromium
```

For Google Cloud Vision, install the optional package and configure application credentials before setting `REVERSE_SEARCH_PROVIDER=google_vision`.

## Claims to use

Use: **"multi-frame detection with configurable model ensemble"**, **"optional licensed reverse-image candidates"**, **"encrypted streaming uploads"**, **"Redis-backed rate limits"**, and **"review-gated investigator workflow"**.

Do not claim universal reverse-image search, benchmark accuracy, automatic identity attribution, or audio-deepfake accuracy unless a labelled evaluation has actually been run and recorded.

## Verification checklist

Run these optional integrations independently before enabling them in a demo or deployment:

1. **Second detector:** set `DETECTOR_SECOND_MODEL_ID`, start the API, upload a known image, and confirm the detection response names the two-model ensemble only when both models return recognized manipulation scores.
2. **Audio scoring:** set `AUDIO_DEEPFAKE_MODEL_ID` to a validated audio-deepfake classifier, upload a test clip, and call `/audio-analysis`. Do not report accuracy until a labelled evaluation has been run.
3. **Google Vision:** install `google-cloud-vision`, configure application credentials, set `REVERSE_SEARCH_PROVIDER=google_vision`, and confirm candidate pages are returned as unconfirmed evidence.
4. **Headless tracing:** install Playwright and Chromium with `playwright install chromium`, set `TRACE_USE_HEADLESS_BROWSER=true`, and test against a controlled JS-rendered page.
5. **Evaluation:** prepare a labelled JSON/CSV manifest with normalized `real/fake` (or `0/1`) labels, run `/detection/evaluation/run`, and record the resulting metrics with the dataset description.

Automatic retention scheduling is intentionally not enabled yet; retention is user-triggered until the Phase 5 background-job system is in place.
