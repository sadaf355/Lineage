# LINEAGE threat model

Scope: the backend API and the data it holds (uploaded media, evidence, case records). Every mitigation below names
the **code** that implements it and the **test** that proves it. `backend/tests/test_threat_model.py` fails the build
if a referenced file, function or test does not exist, so this document cannot drift away from the code.
A row marked `GAP` is a known weakness with no test yet; it is listed on purpose rather than hidden.

Reference format: `path::symbol` (path relative to `backend/`, or to the repo root for `scripts/` and `.github/`).

## Assets and actors
- **Assets:** evidence media and captured pages (encrypted at rest), case data, investigator accounts, the audit trail.
- **Actors:** an authenticated investigator (trusted for their own cases only), another investigator (must not see those
  cases), an anonymous internet user, a hostile file or web page the system is asked to process, a vulnerable dependency.
- **Out of scope:** a compromised host or database, a malicious administrator, physical access.

## Mitigations

| ID | Threat | Mitigation | Code | Test |
|---|---|---|---|---|
| T-UPLOAD-1 | A renamed `.exe` or script is uploaded as an image, video or audio | Header sniffing; refused with HTTP 415 and audited. Valid odd containers (`.mov`, WAV variants) still pass | `app/services/upload_sniff.py::sniff_media` | `tests/test_upload_sniffing.py::test_disguised_files_are_refused` |
| T-UPLOAD-1b | Same, end to end: nothing is stored | Guard runs before any bytes are written | `app/services/upload_guard.py::guard_media_upload` | `tests/test_upload_sniffing.py::test_api_refuses_exe_renamed_to_png_and_stores_nothing` |
| T-UPLOAD-2 | Valid files wrongly rejected, breaking demos | Reject only when confident; unknown AV containers accepted and flagged; `log` mode for trials | `app/services/upload_sniff.py::detect` | `tests/test_upload_sniffing.py::test_valid_media_is_accepted_and_verified` |
| T-UPLOAD-3 | Executable stored as evidence | Evidence may be PDF or HTML but never executable content | `app/services/upload_sniff.py::sniff_evidence` | `tests/test_upload_sniffing.py::test_api_evidence_refuses_executables_but_accepts_saved_pages` |
| T-UPLOAD-4 | Hostile filename or extension reaches the stored path | Only `.` plus up to 8 alphanumerics is kept | `app/services/upload_sniff.py::safe_ext` | `tests/test_upload_sniffing.py::test_stored_filename_extension_is_sanitised` |
| T-UPLOAD-5 | Oversized request exhausts memory or disk | ASGI body limit, including chunked bodies | `app/main.py::RequestBodyLimitMiddleware` | `tests/test_security_baseline.py::test_oversized_request_body_is_rejected_before_reaching_the_app` |
| T-UPLOAD-6 | Disguised content in a decoded image | Images are fully decoded by Pillow; responses carry `nosniff` | `app/main.py::security_headers` | `tests/test_final_fixes.py::test_api_sends_security_headers_and_docs_are_exempt_from_framing_rules` |
| T-AUTHZ-1 | One investigator reads or deletes another's case | Every route loads the case through an ownership check | `app/routers/incidents.py::_get_owned_incident` | `tests/test_api_phase1.py::test_auth_owner_scope_upload_integrity_delete` |
| T-AUTHZ-2 | Default JWT secret in a real deployment | Process refuses to start outside development/test | `app/core/security.py` | `tests/test_security_baseline.py::test_default_jwt_secret_is_refused_outside_development` |
| T-CSRF-1 | Cross-site request abuses the refresh cookie | Custom header and Origin allow-list on cookie endpoints | `app/routers/auth.py::require_csrf` | `tests/test_final_fixes.py::test_refresh_and_logout_require_the_csrf_header` |
| T-BRUTE-1 | Request flooding / login guessing | Windowed rate limiter | `app/services/redis_rate_limit.py::allow` | `tests/test_integrity_and_limits.py::test_rate_limiter_enforces_real_window_limit` |
| T-SSRF-1 | Trace-by-URL makes the server fetch internal addresses | Public-address check, connect to the validated IP, no redirects, size cap | `app/services/source_tracing.py::_pinned_get` | `tests/test_source_tracing_security.py::test_pinned_fetch_connects_to_validated_ip_and_preserves_tls_hostname` |
| T-SSRF-2 | Private or loopback targets | Rejected before any connection | `app/services/source_tracing.py::_validate_public_url` | `tests/test_source_tracing_security.py::test_private_targets_are_rejected` |
| T-SSRF-3 | Redirect or huge body used to bypass the check | Redirects disabled, streamed read capped | `app/services/source_tracing.py::_read_capped` | `tests/test_source_tracing_security.py::test_trace_url_fetches_images_with_redirects_disabled_and_stream_cap` |
| T-INTEG-1 | A forged "match" is accepted as evidence | HMAC-signed pending match, expiry, replay and tamper checks | `app/services/source_tracing.py::verify_pending_match` | `tests/test_source_tracing_security.py::test_pending_match_signature_round_trip_and_tamper_detection` |
| T-INTEG-2 | A weak match recorded as a source | Strict threshold and three agreeing hashes | `app/services/source_tracing.py::validate_trace_accept_payload` | `tests/test_source_tracing_security.py::test_trace_accept_payload_requires_strict_match` |
| T-INTEG-3 | Evidence file altered after capture | SHA-256 recorded and verified on read | `app/services/integrity.py::verify_sha256` | `tests/test_integrity_and_limits.py::test_sha256_and_integrity_verification_use_real_bytes` |
| T-STORE-1 | Path traversal when deleting stored files | Delete refuses anything outside the uploads directory | `app/services/file_storage.py::delete_encrypted` | `tests/test_api_phase1.py::test_delete_encrypted_refuses_paths_outside_uploads` |
| T-PRIVACY-1 | Image sent to Gemini without consent (web search) | Per-case consent required | `app/routers/web_search.py` | `tests/test_web_search.py` |
| T-PRIVACY-2 | Case facts sent to Anthropic without consent (Copilot) | Copilot falls back to deterministic answers | `app/routers/copilot.py::_llm_needs_consent` | `tests/test_consent_enforcement.py::test_copilot_does_not_call_external_llm_without_consent` |
| T-PRIVACY-3 | Case facts sent to Anthropic in the report summary | LLM summary only when consent is granted | `app/services/report_builder.py::_build_summary` | `tests/test_consent_enforcement.py::test_report_summary_only_uses_llm_when_allowed` |
| T-PRIVACY-4 | Image sent to Google Vision via reverse search without consent | 403 unless consent granted (only when a provider is configured) | `app/routers/phase34.py` | `tests/test_consent_enforcement.py::test_reverse_search_requires_consent_when_provider_configured` |
| T-PRIVACY-5 | Revoked consent still honoured | Latest consent record wins | `app/services/consent.py::has_granted_consent` | `tests/test_consent_enforcement.py::test_revoking_consent_takes_effect` |
| T-PRIVACY-6 | Mistyped consent purpose silently grants nothing | Purposes validated against a fixed list | `app/routers/phase56.py::ConsentIn` | `tests/test_consent_enforcement.py::test_unknown_consent_purpose_is_rejected_known_is_stored` |
| T-AUDIT-1 | An endpoint crashes because its audit action is unregistered | Every `audit.record` action is checked against the registry | `app/services/audit.py` | `tests/test_consent_enforcement.py::test_every_audit_action_used_in_code_is_registered` |
| T-LEAK-1 | Credentials in health or graph responses | Responses carry status only | `app/main.py::health` | `tests/test_phase6_integration.py::test_no_credentials_in_health_or_graph_responses` |
| T-LEAK-2 | Internal errors shown to the user | Generic message for report failures | `app/routers/reports.py` | `tests/test_phase6_integration.py::test_pdf_failure_returns_a_clear_error_without_internals` |
| T-MANIFEST-1 | Case record edited after the fact (a hash, an entry, an added or removed item) without anyone noticing | Ed25519-signed manifest over the canonical JSON of every item; any change breaks the signature | `app/services/manifest.py::verify_envelope` | `tests/test_manifest.py::test_any_tamper_breaks_the_signature` |
| T-MANIFEST-2 | A forger re-signs an edited manifest with their own key so it looks self-consistent | Verification takes the verifier's trusted key (published out-of-band); the embedded key is reported as untrusted | `app/services/manifest.py::verify_envelope` | `tests/test_manifest.py::test_attacker_cannot_swap_in_their_own_key_unnoticed` |
| T-TSA-1 | A TSA reply that does not cover our signature (or replays another request) is stored as a valid timestamp | Imprint and nonce are checked; mismatches are rejected and the signed manifest is kept untimestamped | `app/services/manifest.py::request_timestamp` | `tests/test_manifest.py::test_mismatched_imprint_is_rejected_not_stored` |
| T-SWEEP-1 | Page captures nobody accepted or rejected stay on disk indefinitely | Scheduled sweep deletes unreferenced `*.html.enc` older than a grace period that cannot be set below 60 minutes | `app/services/capture_sweep.py::plan_sweep` | `tests/test_capture_sweep.py::test_grace_cannot_be_configured_below_an_hour` |
| T-SWEEP-2 | The sweep deletes accepted evidence or a media upload still being written | Anything referenced by a MediaItem/EvidenceItem is kept; only the capture file shape is ever removed | `app/services/capture_sweep.py::plan_sweep` | `tests/test_capture_sweep.py::test_accepted_capture_is_never_deleted` |
| T-SUPPLY-1 | Known-vulnerable dependency ships | `pip-audit` and `npm audit` in CI; Dependabot | `scripts/audit_python.py` | GAP: verified by the `dependency-audit` CI job, not by a unit test |
| T-SUPPLY-2 | Untested code grows | Coverage gate at 70% | `.github/workflows/ci.yml` | GAP: enforced by CI (`--cov-fail-under=70`), not by a unit test |
| T-AUDIT-9 | Someone edits or deletes audit rows to hide actions | Per-incident hash chain; `GET /incidents/{id}/audit/verify` reports the first broken link | `app/services/audit_chain.py::verify` | `tests/test_audit_chain.py::test_edited_event_is_detected_at_that_event` |
| T-AUDIT-10 | Rows deleted from the end of the chain go unnoticed | The head hash is signed into every manifest (`audit_anchor`) and the bundle; a rewrite that recomputes every hash no longer matches an earlier anchor | `app/services/audit_chain.py::check_against_anchor` | `tests/test_audit_chain.py::test_full_rewrite_with_recomputed_hashes_is_caught_by_the_anchor` |
| T-BUNDLE-1 | Exported case bundle is altered after export | Bundle carries hashes.sha256 plus a signed manifest and a verifier | `app/services/case_bundle.py::verify_bundle` | `tests/test_legal_packs.py::test_bundle_round_trip_and_tamper_detection` |
| T-META-1 | Metadata XML (XMP) used for an entity-expansion attack | XMP is read with a bounded regex, never an XML parser | `app/services/metadata_forensics.py::analyze` | `tests/test_metadata_forensics.py::test_xml_entity_bomb_in_xmp_is_inert` |
| T-META-2 | Stripped metadata is reported as tampering | A file with no metadata gets `cannot_judge`, never a tamper verdict | `app/services/metadata_forensics.py::analyze` | `tests/test_metadata_forensics.py::test_stripped_file_is_cannot_judge_never_tampered` |
| T-META-3 | Malformed EXIF crashes the report | Reader is bounds-checked and returns a report | `app/services/metadata_forensics.py::analyze` | `tests/test_metadata_forensics.py::test_malformed_exif_does_not_raise` |
| T-LEGAL-1 | A generated notice is mistaken for reviewed legal advice | Every pack carries a DRAFT banner until review status is set; text is escaped | `app/services/legal_packs.py::build_pack` | `tests/test_legal_packs.py::test_every_pack_renders_with_draft_banner_hashes_and_url` |
| T-LEGAL-2 | The report implies the content creator was identified | Hosting section names the host only; creator IP is stated as unavailable | `app/services/origin.py::build_case` | `tests/test_legal_packs.py::test_creator_is_never_identified_in_hosting_section` |
| T-MFA-1 | Stolen password alone gives account access | Optional TOTP second factor checked at login with a +/-1 step window | `app/services/totp.py::verify` | `tests/test_security_services.py::test_totp_verify_window_and_rejects` |
| T-MFA-2 | TOTP implementation is wrong | RFC 6238 test vectors | `app/services/totp.py::totp` | `tests/test_security_services.py::test_rfc6238_vectors` |
| T-PROMPT-1 | Scraped page text carries instructions to the LLM | Untrusted text is delimited, flagged, control-stripped and the model is told it is data | `app/services/prompt_safety.py::wrap_untrusted` | `tests/test_security_services.py::test_prompt_flags_and_wrap` |
| T-PROMPT-2 | Personal data in scraped text is sent to an external LLM | Email, phone and ID patterns are redacted when PROMPT_REDACT_PII is on | `app/services/prompt_safety.py::sanitise` | `tests/test_security_services.py::test_prompt_pii_and_ctrl_and_truncate` |
| T-UPLOAD-7 | Malware test file or a decompression bomb is accepted | Optional EICAR/clamd scan and a header-only pixel limit (MALWARE_SCAN_MODE) | `app/services/upload_scan.py::scan` | `tests/test_security_services.py::test_eicar_and_pixels` |
| T-AUDIT-11 | Two events in one case take the same sequence number and the verifier reports a false tamper | Case row lock, unique index on (incident_id, seq), SAVEPOINT retry on conflict | `app/services/audit.py::record` | `tests/test_audit_db.py::test_two_writers_picking_the_same_seq_do_not_fork_the_chain` |
| T-MFA-3 | A TOTP code is replayed inside its validity window | Each time step can be accepted once; older steps are refused | `app/services/mfa.py::check` | `tests/test_mfa.py::test_a_totp_code_cannot_be_reused_or_replaced_by_an_older_one` |
| T-MFA-4 | Database read exposes TOTP secrets | Secrets are Fernet-encrypted with MFA_ENCRYPTION_KEY; production refuses to start enrolment without a key | `app/services/mfa.py::encrypt_secret` | `tests/test_mfa.py::test_production_without_a_key_refuses_instead_of_deriving_one` |
| T-MFA-5 | Lost phone locks the account for good, or recovery codes are reusable | Ten one-time recovery codes, stored as keyed hashes, consumed on use | `app/services/mfa.py::new_recovery_codes` | `tests/test_mfa.py::test_recovery_codes_work_once_and_only_the_right_ones` |
| T-UPLOAD-8 | A 500 MB upload is read into memory by the scanner | Scan streams in 64 KB chunks and rewinds; size cap | `app/services/upload_scan.py::scan_stream` | `tests/test_security_services.py::test_stream_scan_never_reads_more_than_one_chunk_at_a_time` |
| T-LEGAL-3 | A victim's complaint is given the wrong statutory deadline | India pack splits order (3 h), high-risk complaint (2 h) and other complaint (36 h); default is the high-risk track; counsel caveat kept | `app/services/legal_packs.py::deadline` | `tests/test_legal_packs.py::test_it_rules_deadline_depends_on_what_started_the_request` |
| T-C2PA-1 | An invalid or untrusted Content Credentials signature is shown as valid | Result is valid, invalid, untrusted_signer, error or not_validated; never valid without the library | `app/services/provenance.py::_interpret_reader` | `tests/test_provenance.py::test_validator_present_hash_mismatch_is_invalid` |

## Accepted residual risks (reviewed, not fixed)
1. **ML stack versions.** `torch`, `transformers` and `Pillow` are pinned by `facenet-pytorch 2.6.0` and carry published
   advisories. `scripts/audit_python.py` lists them with a review-by date (2026-12-31) and the build fails when it passes.
   Compensating controls: upload sniffing, size limits, only configured Hugging Face model ids are loaded, no user-supplied
   checkpoints. Fix: replace or fork `facenet-pytorch`.
2. **Header-only sniffing.** A polyglot file with a valid image header and hostile trailing bytes passes the sniff.
   Compensating control: images are fully decoded and never served as executable content (T-UPLOAD-6).
3. **Geocoding and URL tracing** contact third parties but send no case media or case facts (a place name or a public URL).
4. **Frontend dev tooling.** `npm audit` reports advisories in `vite`/`esbuild` (development server only). CI audits shipped
   runtime dependencies; Dependabot tracks the rest.
5. **Detector accuracy** is a triage signal, not proof. See `docs/DETECTOR_MODEL_CARD.md`.
