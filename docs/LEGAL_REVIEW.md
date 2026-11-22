# Legal review of the BSA Section 63 certificate (Phase E)

**Status: NOT reviewed.** A lawyer review cannot be performed by the developers or by software. This file is the package
to hand to counsel, and the code is built so the product cannot claim a review that has not happened.

## How the product enforces honesty
* `LEGAL_REVIEW_STATUS` defaults to `pending`. The certificate banner reads *DRAFT — not reviewed by counsel…*.
* The banner changes only when **both** `LEGAL_REVIEW_STATUS=approved` **and** `LEGAL_REVIEWED_TEMPLATE_VERSION` equals the
  running `BSA_CERTIFICATE_TEMPLATE_VERSION`. Edit the template, bump its version, and the approval lapses automatically.
  (`routers/phase56.py::legal_status_text`, tested in `tests/test_legal_status.py`.)
* Even when approved, the signer must complete the statutory declarations. The output states it is not legal advice.

## What to give counsel
1. A sample certificate: `POST /incidents/{id}/evidence/bsa63-certificate?format=text` on a seeded demo case.
2. A signed manifest for the same case and `docs/EVIDENCE_INTEGRITY.md` (what the technical evidence does and does not show).
3. `docs/THREAT_MODEL.md` and the retention policy (`DATA_RETENTION_DAYS`, the capture sweep).
4. The current certificate source: `routers/phase56.py::bsa_certificate` (fields, checklist, wording).

## Questions for counsel (not answered here)
* Does the certificate structure satisfy Section 63 of the Bharatiya Sakshya Adhiniyam, 2023, including the schedule format
  and the requirement for both a person responsible for the device/system and an expert? Who must sign, and in what capacity?
* Are the device and system particulars sufficient (currently only application name and runtime platform)?
* Is hashing at upload plus an Ed25519 manifest adequate to describe the integrity of the record, and should the wording
  avoid or require the term "hash value" as the schedule uses it?
* What should the certificate say about records the investigator added manually versus ones LINEAGE captured itself?
* Is a third-party RFC 3161 timestamp helpful, neutral or a liability in the target forums?
* Retention and deletion: does auto-deleting cases (30 days) conflict with preservation duties when a complaint is filed?
* Language requirements for filing (Hindi or regional language versions).

## After review
Record in the repo: reviewer, date, template version reviewed, and the changes requested. Then set
`LEGAL_REVIEWED_TEMPLATE_VERSION` and `LEGAL_REVIEW_STATUS=approved` in the deployment environment.
