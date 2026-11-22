# Data protection impact assessment (template, fill in before real victims use the system)

This is a template, not a completed assessment. Have a privacy lawyer review it.

1. **What data:** intimate images of victims (special sensitivity), source URLs, face embeddings, location hints, account emails.
2. **Why, and legal basis:** victim's consent per case; ending abuse; evidence for complaints.
3. **Who sees it:** the account owner only today. No role-based sharing exists yet.
4. **Where it goes:** storage on your server; optional calls to an LLM provider only with consent; hosting lookups send a domain or IP only.
5. **How long:** retention settings in `docs/` and `app/services/retention.py`. State the period you choose.
6. **Risks and controls:** map each risk to a row in `docs/THREAT_MODEL.md`.
7. **Rights:** access, correction, erasure. Describe how a victim asks and who answers within what time.
8. **Children:** the system may hold images of minors. Describe the escalation to the NCMEC/NCPCR route you will use.
9. **Sign-off:** name, date, review date.
