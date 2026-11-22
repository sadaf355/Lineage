# Key compromise

| Key | Where | If exposed |
|---|---|---|
| `SECRET_KEY` | env | Rotate. All sessions end. Users log in again. |
| `.file_encryption_key` | `backend/data/` | Evidence files can be read by anyone holding the file plus the disk. Re-encrypt every stored file with a new key (write a one-off script, test on a copy first), then destroy the old key. There is no automatic re-key tool yet. |
| `.manifest_signing_key` | `backend/data/` | Past signed manifests can no longer be trusted as proof of origin. Generate a new key, record the cut-over date in the case log, and tell counsel. |
| `MFA_ENCRYPTION_KEY` | env | Encrypts TOTP secrets and keys the recovery-code hashes. Rotate by setting a new key, then have every user re-enrol (secrets encrypted under the old key become unreadable, so logins with MFA fail until reset by an admin). There is no automatic re-key tool yet. |
| `ANTHROPIC_API_KEY` | env | Revoke at the provider and issue a new one. |

Never ship the key files in a zip. `scripts/make_release_zip.sh` refuses to.
