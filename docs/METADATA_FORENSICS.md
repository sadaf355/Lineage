# Metadata forensics and content origin

What the code does, and what it never claims.

## Tamper checks (`app/services/metadata_forensics.py`)
Nine checks read EXIF, XMP, PNG text chunks and the JPEG structure: editing software, modify date well after capture,
capture date in the future or after the upload, thumbnail that does not match the image, image size differing from the
recorded size, camera fields missing while editing software is present, time zone against GPS longitude, XMP edit history,
and JPEG quantisation tables that point to re-saving.

Verdicts: `cannot_judge`, `no_signals`, `inconsistent_single`, `inconsistent_multiple`.
- A file with no metadata is `cannot_judge`. Stripped is never reported as tampered or changed.
- `inconsistent_multiple` needs signals from at least two different categories at medium severity or higher.
- One high-severity finding on its own gives `inconsistent_single`.
- Every report carries a caveat that these are signals for investigation, not proof.
- XMP is read with a bounded regex. No XML parser is used, so entity-expansion attacks do not apply.

Wording rule (PRD section 9 and 11): without a preserved earlier snapshot of the metadata, LINEAGE may say "inconsistent", never
"changed" or "tampered". `inconsistent_single` and `inconsistent_multiple` are leads. A true "changed against a snapshot" state
uses the preserved MetadataSnapshot recorded at initial upload.

## Content origin (`app/services/origin.py`)
Layers: file, provenance, tamper, hosting, platform. There is **no creator-IP field**. An image file does not contain one.
The uploader's IP exists only in the platform's logs, so the platform layer is filled only after a legal request is answered.
Hosting data (RDAP) identifies the server that serves a page, not the person who posted. RDAP is off by default.

## C2PA (`app/services/provenance.py`)
Structural detection only: the file carries credentials or it does not. Signature validation needs the optional `c2pa`
library and is untested here. "No credentials" does not mean fake, and "has credentials" does not mean real.

## Legal packs (`app/services/legal_packs.py`)
Preservation request, India IT Rules removal notice, US TAKE IT DOWN notice, NCRP complaint summary. Every PDF is marked
DRAFT until a lawyer sets the review status. Deadlines are planning aids. 1930 is for financial fraud, not NCII.
Hindi wording is draft text and needs a human translator's review.

## Signed bundle and audit chain
`GET /incidents/{id}/evidence/bundle` returns a zip with an index, hashes, manifest and a verifier script.
`GET /incidents/{id}/audit/verify` recomputes the per-case hash chain. Record the head hash outside the database.
Events created before the chain existed are counted as legacy, not as failures.
