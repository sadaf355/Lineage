# LINEAGE — Demo Deck Updates

Use these claims as the current code-backed version.

## Slide: What LINEAGE does

**Detect → Fingerprint → Trace → Preserve → Act**

- Multi-frame image/video detection with an explicit real-model/fallback state.
- pHash + dHash + aHash fingerprints for visual evidence.
- SHA-256 on uploads, evidence, and captured source pages.
- Paste a public URL to verify its page images against case media; matches require ≥85% similarity and at least two agreeing hashes.
- Investigator confirmation is required before a traced source becomes part of the evidence graph.

## Slide: Attribution Gap

**Knowing what happened is not the same as proving where it came from.**

LINEAGE separates:
- Known facts
- Unresolved attribution
- Evidence still required

Do not present a suspected source as the origin unless the evidence supports that conclusion.

## Slide: Why existing tools fall short

| Workflow need | Typical gap | LINEAGE approach |
|---|---|---|
| Detection | One-off classifier output | Detection + confidence band + sampled video frames |
| Re-identification | Recompression breaks exact hashes | pHash + dHash + aHash ensemble |
| Web tracing | Search links are not evidence | Paste URL → inspect page images → review → accept |
| Evidence integrity | Hash hidden in storage | SHA-256 visible + re-verification |
| Investigation | Separate tools and notes | Case, sources, evidence, lineage and report in one workspace |

## Slide: Evidence integrity

**Every preserved artifact has a cryptographic identity.**

- SHA-256 generated when bytes enter LINEAGE.
- Evidence Locker displays the digest.
- Investigator can re-hash the decrypted stored bytes.
- Mismatch is surfaced explicitly.
- PDF report includes the integrity manifest.

## Slide: Limitations & roadmap

**Current build**
- Public URL verification works on accessible HTML pages and image metadata.
- Social platforms requiring login/client-side rendering may not expose usable image URLs.
- Audio fingerprinting is not implemented.
- Automatic cross-platform discovery is not implemented.
- Crop/rotation robustness helpers exist, but are not yet the production matching path.
- Hindi/regional-language reports remain roadmap work.

**Next**
- Licensed reverse-image search integration.
- Production-grade crop/rotation/embedding retrieval.
- Audio deepfake fingerprinting.
- Regional-language reporting.

## Copy corrections

Use:
- **Generative** (not “Genrative”)
- **investigate** (not “innvestigate”)
- **all kinds of evidence** (not “all kind of evidences”)
- Remove “supports audio” from current capability claims.

## Demo wording

Say:
> “Paste a public URL and LINEAGE checks its accessible page images against the evidence. A match is only added after investigator confirmation.”

Do not say:
> “LINEAGE automatically discovers the original source across social media.”

## Phase 2 additions now implemented

- **Metadata footprint:** camera/software/timestamps when present, generator tags, C2PA marker presence, and a metadata-stripped flag.
- **Hosting footprint:** traced-source domain, resolved public server IPs, capture time, and the explicit label “Hosting server, not the creator.” Country remains “not resolved” unless a future hosting-geolocation provider is configured.
- **Attribution Gap:** creator IP/account identity is explicitly marked as requiring platform disclosure via an authorized/legal process.
- **Request Pack:** downloadable investigator-support PDF containing source URLs, SHA-256 hashes, timestamps and hosting details.
- **Takedown drafts:** reviewable platform-specific drafts generated from accepted live sources; nothing is sent automatically.
- **Verify all:** evidence integrity can be checked in one action; an exportable JSON hash manifest is available.
- **Sensitive media:** evidence previews default to blurred display with an explicit reveal control.
- **Victim support:** links to StopNCII, Take It Down, India's National Cyber Crime Reporting Portal, and 1930 are presented as informational resources.
- **Quick exit:** clears the local session and returns to the neutral landing page.
- **Crop robustness:** the live URL-trace matcher now evaluates original/cropped/mirrored/rotated variants while retaining the 85% + 2-of-3 hash acceptance rule. This is robustness testing, not automatic reverse-image discovery.
