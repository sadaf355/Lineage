# Incident response (security incident or suspected data exposure)

Owner: fill in a named person and a deputy. Keep their phone numbers somewhere that does not depend on this system.

1. **Contain (first hour).** Revoke access: rotate `SECRET_KEY` (invalidates all tokens), disable the affected account
   (`is_active=false`), block the source IP at the proxy. Do not delete anything.
2. **Preserve.** Take a backup with `scripts/backup.sh`. Export logs. Record the audit head hash for affected cases
   (`GET /incidents/{id}/audit/verify`).
3. **Assess.** Which cases, which data (media, evidence, personal data), which period. Check `audit/verify` for broken
   chains on affected cases.
4. **Notify.** India's DPDP rules expect notice to the Data Protection Board and affected people for a personal data
   breach; the Board's initial intimation is due without delay and the detailed report within 72 hours.
   **Confirm the exact current obligation with counsel.** This runbook is not legal advice.
   Also tell the affected victims directly and in plain words, and any NGO partner.
5. **Recover.** Restore from a verified backup into a new location (`scripts/restore.sh`), rotate keys (see KEY_COMPROMISE).
6. **Review.** Write down timeline, cause, fix. Add a threat-model row and a test.
