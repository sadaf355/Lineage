# Evidence integrity: signed manifest and trusted timestamp (Phase E)

## What exists
| Layer | What it proves | Where |
|---|---|---|
| SHA-256 per item | The stored bytes still match what was uploaded | `services/integrity.py`, Fingerprint → *Verify integrity* |
| **Signed manifest (Ed25519)** | This deployment produced this exact list of items and hashes, and it has not been edited since | `services/manifest.py`, `POST /incidents/{id}/evidence/manifest` |
| **RFC 3161 timestamp (optional)** | An independent authority saw the *signature* at a stated time, so the signing could not have been back-dated | `?timestamp=true`, needs `MANIFEST_TSA_URL` |

## What it does not prove
* It does not prove the content is authentic, lawfully obtained, or admissible. It proves the record has not changed.
* The key inside an envelope is a convenience. **Verify against the key published out-of-band** (`GET /trust/manifest-key`,
  and print the `key_id` on every report). Verifying only against the embedded key proves self-consistency, nothing more.
* The in-process timestamp check reads the imprint, nonce and time. It does **not** validate the TSA's CMS signature or
  certificate chain. Do that with OpenSSL (below). The API reports `tsa_signature_verified: false` until you have.

## Operating it
1. Generate a key once and store it in your secret manager (never in git):
   `python -c "import base64,secrets;print(base64.b64encode(secrets.token_bytes(32)).decode())"` → `MANIFEST_SIGNING_KEY`.
   Outside development the app refuses to sign without it. In development a key is created at `data/.manifest_signing_key`.
2. Publish the public key: `GET /trust/manifest-key` returns `key_id`, base64 key and PEM. Record the `key_id` somewhere an
   attacker with database access cannot rewrite (a signed release note, the court filing, a registry).
3. Optional timestamp: set `MANIFEST_TSA_URL` to a TSA you have chosen and reviewed. Nothing is sent unless it is set.
   A TSA outage does not block signing: the envelope is stored without a timestamp and carries `timestamp_error`.
4. **Key rotation:** a new key gets a new `key_id`. Old envelopes still verify against the old public key, so keep every
   retired public key. Never delete one.
5. Re-sign after the case changes. `POST .../manifests/{id}/verify` reports additions, removals and changed hashes since signing.

## Verify offline (no LINEAGE code, no network)
```bash
curl -s https://YOUR-HOST/incidents/$ID/evidence/manifests/$MID -H "Authorization: Bearer $TOKEN" > envelope.json
python scripts/verify_manifest.py envelope.json --public-key "<base64 key published by the operator>"
```

## Validate the timestamp authority's signature (OpenSSL)
```bash
python - <<'PY' > resp.tsr
import json,base64,sys; sys.stdout.buffer.write(base64.b64decode(json.load(open("envelope.json"))["timestamp"]["response_der"]))
PY
python - <<'PY' > sig.sha256
import json,base64,hashlib; print(hashlib.sha256(base64.b64decode(json.load(open("envelope.json"))["signature"]["value"])).hexdigest())
PY
openssl ts -verify -in resp.tsr -digest "$(cat sig.sha256)" -CAfile tsa-ca-chain.pem
```
`Verification: OK` means the TSA's signature and chain are valid for that digest. Obtain the TSA's CA chain from the TSA itself.

## Known limits
* Ed25519 and SHA-256 are the only algorithms. There is no post-quantum or long-term (LTV/archive timestamp) renewal.
* The in-process DER reader handles definite-length encodings only. A TSA that replies with indefinite-length BER is
  stored as received and marked `tst_info_parsed: false`; verify it with OpenSSL.
* Not tested against a live TSA from this repository's environment (no network). The request format was validated with
  `openssl ts -query -text` and the reply parser with a synthetic reply. Run one real request against your chosen TSA
  before relying on it, and record the result.
