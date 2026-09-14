// Mock data for the LINEAGE prototype — "Riya's Case" demo scenario.
// This file is the single source of truth for the no-backend prototype.

export const caseInfo = {
  id: "INC-2024-012",
  name: "Riya's Case",
  status: "Evidence Building",
  createdAt: "14 Oct 2024, 10:32 AM",
  victimRef: "V-2024-012 (pseudonymous)",
};

export interface InvestigationItem {
  id: string;
  title: string;
  description: string;
  mediaType: "Video" | "Image" | "Document" | "Audio";
  status: "Evidence Building" | "In Progress" | "Completed" | "Needs Attention";
  score: number;
  updatedAgo: string;
  updatedDate: string;
}

export const allInvestigationsList: InvestigationItem[] = [
  { id: "INC-2024-012", title: "Riya's Case", description: "Viral video with controversial statements", mediaType: "Video", status: "Evidence Building", score: 87, updatedAgo: "10 minutes ago", updatedDate: "Oct 14, 2024" },
  { id: "INC-2024-011", title: "Political Speech Clip", description: "Suspiciously edited campaign video", mediaType: "Video", status: "In Progress", score: 72, updatedAgo: "2 hours ago", updatedDate: "Oct 14, 2024" },
  { id: "INC-2024-010", title: "City Explosion Image", description: "Image circulating on social media", mediaType: "Image", status: "Completed", score: 15, updatedAgo: "1 day ago", updatedDate: "Oct 13, 2024" },
  { id: "INC-2024-009", title: "Document Verification", description: "Altered government document", mediaType: "Document", status: "In Progress", score: 68, updatedAgo: "2 days ago", updatedDate: "Oct 12, 2024" },
  { id: "INC-2024-008", title: "Audio Recording", description: "Suspicious voice recording", mediaType: "Audio", status: "Completed", score: 8, updatedAgo: "3 days ago", updatedDate: "Oct 11, 2024" },
  { id: "INC-2024-007", title: "Viral Meme Analysis", description: "AI-generated meme content", mediaType: "Image", status: "Needs Attention", score: 91, updatedAgo: "4 days ago", updatedDate: "Oct 10, 2024" },
  { id: "INC-2024-006", title: "CCTV Footage", description: "Potentially manipulated surveillance video", mediaType: "Video", status: "Completed", score: 22, updatedAgo: "5 days ago", updatedDate: "Oct 9, 2024" },
  { id: "INC-2024-005", title: "News Broadcast", description: "Altered news segment", mediaType: "Video", status: "In Progress", score: 64, updatedAgo: "1 week ago", updatedDate: "Oct 7, 2024" },
  { id: "INC-2024-004", title: "Press Conference Audio", description: "Synthetic voice clone in audio file", mediaType: "Audio", status: "Completed", score: 12, updatedAgo: "1 week ago", updatedDate: "Oct 5, 2024" },
  { id: "INC-2024-003", title: "Identity Fraud Verification", description: "Forged credentials and photo ID", mediaType: "Document", status: "In Progress", score: 79, updatedAgo: "2 weeks ago", updatedDate: "Oct 1, 2024" },
  { id: "INC-2024-002", title: "Social Media Deepfake", description: "Face-swap avatar video circulating on forums", mediaType: "Video", status: "Completed", score: 84, updatedAgo: "3 weeks ago", updatedDate: "Sep 24, 2024" },
  { id: "INC-2024-001", title: "Election Campaign Meme", description: "Altered promotional poster", mediaType: "Image", status: "Completed", score: 30, updatedAgo: "1 month ago", updatedDate: "Sep 15, 2024" },
];

export const pipelineStages = [
  { key: "created", label: "Created", done: true },
  { key: "analyzing", label: "Analyzing", done: true },
  { key: "fingerprinted", label: "Fingerprinted", done: true },
  { key: "evidence", label: "Evidence Building", done: true },
  { key: "gap", label: "Gap Reviewed", done: true },
  { key: "report", label: "Report Generated", done: true },
  { key: "closed", label: "Closed / Archived", done: false },
];

export const mediaItem = {
  id: "MED-001",
  type: "video",
  filename: "Riya_video.mp4",
  uploadedAt: "14 Oct 2024, 10:32 AM",
  durationSec: 14,
};

export const detectionResult = {
  manipulationLikelihood: 87,
  confidenceLabel: "High",
  detectedRegion: "Face — jawline & lower cheek blend zone",
  likelyTechnique: "Face-swap with temporal smoothing",
  indicators: [
    { label: "Facial blending inconsistency", detail: "Soft edge artifact along the jawline across frames 40–96" },
    { label: "Temporal flicker", detail: "Micro-flicker in skin tone between frames not present in the rest of the clip" },
    { label: "Lighting mismatch", detail: "Light source on the face doesn't match the ambient light on the shoulders/background" },
    { label: "Audio–video sync", detail: "Minor lip-sync drift on plosive sounds ('p', 'b')" },
  ],
};

export const fingerprint = {
  perceptualHash: "8f3a1c9e2b7d4056",
  faceEmbeddingPreview: "[0.183, -0.402, 0.771, 0.056, -0.291, …]",
  faceEmbeddingDims: 128,
  keyframeHashes: [
    { frame: "00:00:02", hash: "a1c9e2b7d4f30856" },
    { frame: "00:00:06", hash: "e2b7d4f3a1c90856" },
    { frame: "00:00:10", hash: "d4f3a1c9e2b70856" },
  ],
  audioFingerprint: "af-7729c1-delta",
};

export type Source = {
  id: string;
  platform: string;
  account: string;
  url: string;
  observedAt: string;
  similarity: number;
  relationship: string;
  seeded: boolean;
};

export const sources: Source[] = [
  { id:"SRC-A", platform:"Instagram", account:"@user_unknown", url:"https://instagram.com/… (preserved)", observedAt:"14 Oct 2024, 10:24 AM", similarity:96, relationship:"Original observed post", seeded:true },
  { id:"SRC-B", platform:"X (Twitter)", account:"@user123", url:"https://x.com/… (preserved)", observedAt:"14 Oct 2024, 11:03 AM", similarity:91, relationship:"Re-upload / re-encoded", seeded:true },
  { id:"SRC-C", platform:"Telegram", account:"Channel A", url:"https://t.me/… (preserved)", observedAt:"14 Oct 2024, 01:15 PM", similarity:87, relationship:"Shared in group", seeded:true },
  { id:"SRC-D", platform:"Reddit", account:"u/anonymous", url:"https://reddit.com/… (preserved)", observedAt:"15 Oct 2024, 09:42 AM", similarity:82, relationship:"Forum post / cropped variant", seeded:true },
  { id:"SRC-E", platform:"YouTube", account:"@clip_channel", url:"https://youtube.com/… (preserved)", observedAt:"15 Oct 2024, 04:21 PM", similarity:78, relationship:"Screen recording / repost", seeded:true },
];

export const sourceRelationships = [
  { from:"SRC-A", to:"SRC-B", type:"repost", confidence:96 },
  { from:"SRC-A", to:"SRC-C", type:"share", confidence:87 },
  { from:"SRC-B", to:"SRC-D", type:"crop + re-share", confidence:82 },
  { from:"SRC-C", to:"SRC-E", type:"screen recording", confidence:78 },
];

export const evidenceItems = [
  { id:"EV-01", sourceId:"SRC-A", type:"Screenshot + fingerprint match", capturedAt:"14 Oct 2024, 10:26 AM" },
  { id:"EV-02", sourceId:"SRC-B", type:"Screenshot + fingerprint match", capturedAt:"14 Oct 2024, 11:05 AM" },
  { id:"EV-03", sourceId:"SRC-C", type:"Screenshot + fingerprint match", capturedAt:"14 Oct 2024, 01:17 PM" },
  { id:"EV-04", sourceId:"SRC-D", type:"Screenshot + fingerprint match", capturedAt:"15 Oct 2024, 09:44 AM" },
  { id:"EV-05", sourceId:"SRC-E", type:"Screen recording + fingerprint match", capturedAt:"15 Oct 2024, 04:23 PM" },
];

export const attributionGap = {
  known: [
    "Media is likely to be manipulated (87% likelihood, face-swap with temporal smoothing).",
    "The same underlying content appears across 5 public sources.",
    "@user_unknown (SRC-A) is the earliest publicly observed source, at 10:24 AM on 14 Oct 2024.",
    "SRC-B, SRC-C, SRC-D and SRC-E are re-encoded, cropped, or re-shared derivatives of SRC-A's version.",
    "Propagation window observed: 14 Oct 2024, 10:24 AM \u2013 15 Oct 2024, 4:21 PM (approximately 30 hours across 5 sources).",
  ],
  unresolved: [
    "The real-world identity of the person behind @user_unknown.",
    "Whether @user_unknown created the manipulated media or obtained it from elsewhere.",
    "IP address, device, or login information for the originating account.",
    "Whether the account is genuine, compromised, or operated anonymously via VPN.",
  ],
  evidenceNeeded: [
    "Account registration & login records — obtainable only via platform legal request or law-enforcement order.",
    "IP / session logs tied to the upload — obtainable only via authorized investigation.",
    "Platform-side original upload metadata (device, timestamp, source IP).",
    "Cross-reference with any prior reports linked to the same account.",
  ],
};

export const incidentReport = {
  generatedAt: "15 Oct 2024, 05:10 PM",
  summary:
    "A 14-second video circulating since 14 Oct 2024 shows strong indicators of face-swap manipulation (87% confidence). The same content has been observed across 5 public sources within a propagation window of roughly 30 hours. @user_unknown is the earliest observed public source; four other accounts appear to have reposted, cropped, re-encoded, or screen-recorded the same underlying content. Real-world attribution of the originating account has not been established and would require platform- or law-enforcement-level access.",
  confidenceBreakdown: [
    { label: "Manipulation detection", value: 87 },
    { label: "Media similarity across sources", value: 93 },
    { label: "Propagation relationship", value: 88 },
    { label: "Earliest observed source", value: 96 },
    { label: "Real-world attribution", value: 0, note: "Not established" },
  ],
  recommendedActions: [
    {
      title: "Preserve every piece of collected evidence",
      detail: "All 5 evidence items are already saved in the Evidence Locker — do not delete the original file.",
    },
    {
      title: "File a complaint at cybercrime.gov.in",
      detail: "Attach the exported incident report and evidence bundle directly to the complaint form.",
    },
    {
      title: "Call the 1930 national cybercrime helpline",
      detail: "Report the incident by phone for a faster initial response alongside the online complaint.",
    },
    {
      title: "Request platform takedown citing the 3-hour rule",
      detail:
        "Under the 2026 IT (Intermediary Guidelines) Amendment Rules, platforms must act on a valid takedown order within 3 hours — reference this explicitly in the takedown request.",
    },
    {
      title: "Reach out to a support organisation",
      detail: "Organisations such as NWM India can help navigate reporting and provide emotional support.",
    },
  ],
};

export const roadmapItems = [
  {
    title: "Licensed cross-platform search",
    detail:
      "Replace the seeded source simulator with licensed reverse-image-search APIs (e.g., TinEye, Google Vision) so new sources are discovered automatically rather than manually added.",
    status: "Roadmap — v2",
  },
  {
    title: "Formal platform partnerships",
    detail:
      "Structured data-sharing agreements with major platforms for faster, authorized lookups — instead of scraping, which would violate most platforms' Terms of Service.",
    status: "Roadmap — v2",
  },
  {
    title: "Live lineage graph",
    detail:
      "Once real search data is available, the propagation graph shown in Demo Mode becomes a live, continuously-updating view.",
    status: "Roadmap — v2",
  },
  {
    title: "Multi-language incident reports",
    detail: "Generate reports and recommended actions in regional languages to widen accessibility.",
    status: "Roadmap — v3",
  },
];
