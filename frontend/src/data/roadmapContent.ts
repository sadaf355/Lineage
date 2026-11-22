export const roadmapItems = [
  { title: "Two-model detection ensemble", detail: "Available when a second Hugging Face classifier is configured; otherwise LINEAGE reports the primary detector honestly.", status: "Built — Phase 3" },
  { title: "Multi-frame video analysis", detail: "Video detection samples 12 frames by default and reports a confidence range instead of relying on one key frame.", status: "Built — Phase 3" },
  { title: "Audio fingerprinting", detail: "Audio uploads receive a deterministic spectrogram fingerprint. Deepfake scoring remains optional and model-dependent.", status: "Built — Phase 3" },
  { title: "Licensed reverse-image search", detail: "Optional Google Cloud Vision Web Detection integration returns candidate pages that still require investigator confirmation.", status: "Built — Phase 3" },
  { title: "Redis-backed protection", detail: "Login, upload, tracing and Copilot have separate limits, with an explicit single-process fallback when Redis is unavailable.", status: "Built — Phase 4" },
  { title: "Short-lived sessions", detail: "Access tokens are short-lived and refresh sessions rotate through an HttpOnly cookie.", status: "Built — Phase 4" },
  { title: "Key rotation", detail: "Current and previous encryption keys can coexist during rotation; direct secrets-manager integration is still planned.", status: "Built — Phase 4" },
  { title: "JS-rendered source tracing", detail: "Optional Playwright rendering is protected by request interception and the same public-network validation rules.", status: "Built — Phase 3" },
  { title: "Automatic platform discovery", detail: "Still requires authorized/licensed platform access; LINEAGE does not claim universal social-platform discovery.", status: "Roadmap" },
  { title: "Audio deepfake benchmark", detail: "Requires a validated labelled dataset and a configured audio-deepfake model before accuracy can be claimed.", status: "Roadmap" },
  { title: "Multi-language incident reports", detail: "Regional-language reports remain a product expansion after the evidence and security foundations.", status: "Roadmap" },
];
