/**
 * Typed client for the LINEAGE backend API.
 *
 * Everything the UI needs from the server goes through this file — no
 * component calls fetch() directly. That keeps the auth header, base URL,
 * and error shape in exactly one place.
 *
 * The base URL comes from VITE_API_URL (see .env.example); it defaults to
 * the backend's local dev address so `npm run dev` works with no config.
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TOKEN_KEY = "lineage_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  }


/* ---- metadata-change detection and content origin ---- */
export type TamperVerdict = "cannot_judge" | "no_signals" | "inconsistent_single" | "inconsistent_multiple";
export interface TamperFinding { id: string; category: string; title: string; severity: "info" | "low" | "medium" | "high"; evidence: Record<string, unknown>; caveat: string }
export interface MediaOriginAnalysis {
  supported?: boolean;
  note?: string;
  file?: { device: string | null; software: string | null; captured_at: string | null; gps: { latitude: number; longitude: number } | null; reliability: string; metadata_stripped: boolean };
  provenance?: { c2pa: { present: boolean; validation: { status: string; reason?: string }; actions: string[]; claim_generator: string | null; note?: string }; ai_markers: { type: string; value: string; strength: string; note: string }[]; reliability: string };
  tamper: { verdict: TamperVerdict; description?: string; findings: TamperFinding[]; limits: string[]; ruleset_version?: string; reason?: string };
}
export interface OriginReport {
  generated_at: string;
  creator_ip: { available: false; reason: string; how_to_obtain: string };
  layers: {
    file: unknown[];
    provenance: unknown[];
    tamper: { media_id: string; filename: string; verdict: TamperVerdict | null; description: string | null }[];
    hosting: { domain?: string; server_ips?: string[]; country?: string; label: string; enrichment?: { status: string; note?: string } }[];
    platform: { status: string; note: string; legal_review_status: string };
  };
  signals_found: string[];
  limits: string[];
}
export interface LegalPackRequest {
  regime: "preservation" | "it_rules" | "tida" | "ncrp";
  platform?: string; requester_name?: string; requester_contact?: string; requester_relationship?: string; order_received_at?: string; track?: "order" | "high_risk_complaint" | "individual_complaint"; notes?: string;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// Required by the backend on cookie-authenticated calls (refresh, logout). A cross-site page cannot set it.
const CSRF_HEADERS: Record<string, string> = { "X-Lineage-CSRF": "1" };

async function request<T>(
  path: string,
  options: RequestInit = {},
  { raw = false }: { raw?: boolean } = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(options.body instanceof FormData) && options.body) {
    headers["Content-Type"] = "application/json";
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" });
  } catch {
    // Network-level failure — the server isn't running or isn't reachable.
    // Surfaced explicitly rather than as a confusing generic error, since
    // "did you start the backend?" is by far the most common cause.
    throw new ApiError(
      `Could not reach the LINEAGE API at ${API_BASE}. Is the backend running?`,
      0
    );
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* response wasn't JSON — keep the status-based message */
    }
    throw new ApiError(detail, res.status);
  }

  if (raw) return (await res.blob()) as unknown as T;
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

/* ---------------------------------- types --------------------------------- */

export type User = { id: string; email: string; display_name: string | null; mfa_enabled?: boolean | null; mfa_setup_required?: boolean };
export type Health = { status: string; env: string; neo4j: string; graph_backend: string; detector: { mode: string; model_id: string; loaded: boolean; fallback: boolean; note: string }; offline_demo?: boolean };

export type DetectorMetrics = {
  samples: number; accuracy: number; precision: number; recall: number; f1: number; roc_auc: number | null;
  true_positive: number; true_negative: number; false_positive: number; false_negative: number;
  confusion_matrix: number[][];
};
export type DetectorInterval = { point: number | null; low: number | null; high: number | null };
export type DetectorModelReport = Partial<DetectorMetrics> & {
  rows_total: number; unscored: number; by_condition?: Record<string, DetectorMetrics>;
  threshold?: number;
  ci?: { level: number; n_boot: number; n_groups: number; method?: string; metrics: Record<string, DetectorInterval> };
};
export type DetectorEvaluationReport = {
  generated_at: string; threshold: number; images: number; sources: string[]; conditions: string[];
  models: Record<string, DetectorModelReport>; warning: string;
  // Present when the report used a calibration/test split (the default protocol).
  images_test?: number; originals_test?: number; originals_calib?: number;
  protocol?: { name?: string; seed: string; threshold_source: string; groups: { calib: number; test: number } };
};
export type DetectorEvaluationLatest = {
  available: boolean;
  smoke_test?: boolean;
  report: DetectorEvaluationReport | null;
  configured_models: { primary: string; second: string | null; ensemble_active: boolean };
  how_to_generate: string | null;
};

export type IncidentStatus =
  | "created"
  | "analyzing"
  | "fingerprinted"
  | "evidence_building"
  | "gap_reviewed"
  | "report_generated"
  | "closed";

export type Incident = {
  id: string;
  title: string;
  description: string | null;
  victim_ref: string | null;
  status: IncidentStatus;
  created_at: string;
  updated_at: string;
};

export type MediaItem = {
  id: string;
  kind: "image" | "video" | "audio";
  original_filename: string;
  file_size_bytes: number;
  width: number | null;
  height: number | null;
  sha256: string | null;
  uploaded_at: string;
};

export type DetectionResult = {
  id: string;
  manipulation_likelihood: number;
  edge_irregularity: number | null;
  compression_density: number | null;
  detected_region: string | null;
  likely_technique: string | null;
  model_name: string;
  explanation: string | null;
  explainability_json: string | null;
  created_at: string;
};

export type Fingerprint = {
  id: string;
  average_hash: string;
  perceptual_hash: string | null;
  difference_hash: string | null;
  face_embedding_json: string | null;
  keyframe_hashes_json: string | null;
  audio_fingerprint: string | null;
  created_at: string;
};

export type FaceEmbeddingInfo = {
  found_face: boolean;
  embedding?: number[] | null;
  box?: number[] | null;
  detection_confidence?: number | null;
  error?: string;
};

export type Source = {
  id: string;
  platform: string;
  account_identifier: string | null;
  url: string | null;
  observed_at: string;
  similarity_score: number | null;
  relationship_label: string | null;
  is_seeded: boolean;
  page_sha256: string | null;
};

export type SourceRelationship = {
  id: string;
  from_source_id: string;
  to_source_id: string;
  relationship_type: string;
  confidence: number | null;
};

export type EvidenceItem = {
  id: string;
  source_id: string | null;
  item_type: string;
  notes: string | null;
  captured_at: string;
  sha256: string | null;
};

export type AttributionGapEntry = {
  id: string;
  category: "known" | "unresolved" | "evidence_needed";
  statement: string;
};

export type IncidentReport = {
  id: string;
  incident_id: string;
  generated_at: string;
  payload: {
    summary: string;
    confidence_breakdown: { label: string; value: number; note: string | null }[];
    recommended_actions: { title: string; detail: string }[];
    source_count: number;
    evidence_count: number;
  };
};

export type WebSearchQuery = {
  query: string;
  google_url: string;
  bing_url: string;
};

export type PendingTraceMatch = { url:string; platform:string; observed_at:string; similarity_score:number; method:string; agreeing_hashes:number; page_sha256:string; page_storage_path:string; matched_image_url:string; issued_at:number; signature:string };


export type WebSearchRun = {
  id: string;
  image_description: string;
  summary: string;
  model_name: string;
  created_at: string;
  search_queries: WebSearchQuery[];
};


/* ------------------------------ geo / propagation ------------------------------ */

export type GeoTier = "verified" | "investigator" | "inferred" | "mixed";
export type GeoEdgeMode = "confirmed" | "inferred" | "undirected";

export type GeoObservation = {
  source_id: string;
  label: string;
  platform: string;
  account: string | null;
  observed_at: string;
  tier: Exclude<GeoTier, "mixed">;
  provenance: string;
  confidence: number;
  basis: string | null;
  evidence_ids: string[];
  evidence_labels: string[];
  // Phase 2 provenance extras (present on /geo-stats records)
  location_id?: string | null;
  city?: string | null;
  region?: string | null;
  country?: string | null;
  place_name?: string | null;
  latitude?: number;
  longitude?: number;
  location_recorded_at?: string | null;
};

export type GeoNode = {
  id: string;
  name: string;
  has_name: boolean;
  country: string | null;
  latitude: number;
  longitude: number;
  observation_count: number;
  verified_observation_count: number;
  platforms: string[];
  first_observed: string;
  last_observed: string;
  tier: GeoTier;
  confidence: number;
  confidence_label: "High" | "Medium" | "Low";
  observations: GeoObservation[];
};

export type GeoEdgeRelationship = {
  relationship_id: string;
  from_label: string;
  to_label: string;
  from_platform: string;
  to_platform: string;
  type: string;
  confidence: number | null;
  from_observed: string;
  to_observed: string;
  similarity: number | null;
  evidence_labels: string[];
};

export type GeoEdge = {
  id: string;
  source: string;
  target: string;
  mode: GeoEdgeMode;
  basis: string;
  count: number;
  platforms: string[];
  types: string[];
  first_timestamp: string;
  last_timestamp: string;
  similarity: number | null;
  confidence: number | null;
  relationships: GeoEdgeRelationship[];
};

export type GeoData = {
  nodes: GeoNode[];
  edges: GeoEdge[];
  unlocated_sources: { source_id: string; label: string; platform: string; account: string | null; observed_at: string }[];
  stats: {
    source_count: number; located_sources: number; unlocated_sources: number;
    node_count: number; edge_count: number; directed_edges: number; inferred_edges: number;
    undirected_edges: number; verified_locations: number; investigator_locations: number;
    inferred_locations: number; relationships_without_locations: number;
  };
  time_range: { start: string | null; end: string | null };
};

/* ---- Phase 2: geographic intelligence (/geo-stats) ---- */
export type GeoLevel = "high" | "medium" | "low";
export type GeoMetric = "observations" | "unique_sources" | "propagation_events";
export type TierFilter = "all" | "verified" | "investigator" | "inferred";

export type ActivityFactor = { key: GeoMetric; label: string; value: number; weight: number; points: number };
export type NodeActivity = {
  score: number; raw: number; capped: boolean; cap: number; level: GeoLevel; level_label: string; factors: ActivityFactor[];
};
export type GeoStatsNode = GeoNode & {
  city: string | null; region: string | null;
  unique_sources: number; propagation_events: number;
  tier_counts: Record<"verified" | "investigator" | "inferred", number>;
  source_ids: string[]; source_labels: string[]; evidence_ids: string[]; evidence_labels: string[];
  activity: NodeActivity;
};
export type Hotspot = {
  rank: number; id: string; name: string; level: GeoLevel; level_label: string; score: number;
  observations: number; unique_sources: number; propagation_events: number;
};
export type HeatPoint = { id: string; latitude: number; longitude: number; value: number; weight: number; level: GeoLevel };
export type GeoConfig = { weights: Record<GeoMetric, number>; score_cap: number; thresholds: { high: number; medium: number } };
export type EmptyReason = null | "no_locations" | "no_platform" | "no_verified" | "no_investigator" | "no_inferred" | "no_time_range";

export type GeoStats = {
  filters: { start: string | null; end: string | null; platform: string | null; tier: string | null; metric: GeoMetric };
  config: GeoConfig;
  summary: {
    observations: number; unique_sources: number; platforms: string[]; unique_platforms: number;
    propagation_events: number; cross_location_events: number; locations: number;
    verified_observations: number; investigator_observations: number; inferred_observations: number;
    first_observed: string | null; last_observed: string | null; total_sources: number | null; located_sources: number;
    relationships_without_locations: number; high_activity: number; medium_activity: number; low_activity: number;
  };
  available: {
    platforms: { platform: string; observations: number }[];
    tiers: Record<"verified" | "investigator" | "inferred", number>;
    time_range: { start: string | null; end: string | null };
    total_observations: number;
  };
  nodes: GeoStatsNode[];
  edges: GeoEdge[];
  hotspots: Hotspot[];
  earliest_observed: { node_id: string; name: string; observed_at: string; source_id: string; source_label: string; platform: string; tier: string } | null;
  heat: { metric: GeoMetric; max: Record<GeoMetric, number>; points: HeatPoint[] };
  time_index: string[];
  timeline_events: { t: string; source_id: string; label: string; platform: string; tier: string; node_id: string }[];
  empty_reason: EmptyReason;
};

export type GeoStatsQuery = { start?: string; end?: string; platform?: string; tier?: TierFilter; metric?: GeoMetric };

export type GeocodeResult = {
  display_name: string; name: string; country: string | null; city?: string | null; region?: string | null;
  latitude: number; longitude: number;
};

export type LocationInput = {
  latitude: number; longitude: number; place_name?: string; city?: string; region?: string; country?: string;
  confidence?: number; basis?: string;
};

/* ---- Phase 3A/3B: graph backend + Investigation Copilot ---- */
export type GraphSource = { backend: "neo4j" | "memory"; neo4j: string; fallback: boolean; reason: string | null; synced_at?: string | null };
export type GraphHealth = {
  status: "connected" | "fallback"; neo4j: "connected" | "unavailable" | "not_configured";
  graph_backend: "neo4j" | "memory"; auto_sync: boolean; database: string | null; error: string | null;
};
export type CopilotCategory = "VERIFIED_FACT" | "INFERENCE" | "UNKNOWN";
export type CopilotFact = {
  statement: string; category: CopilotCategory; status: string | null; section: string;
  relationship_ids: string[]; relationships: { type: string; source: string; target: string; status: string }[];
  node_ids: string[]; evidence_ids: string[]; source_ids: string[]; location_ids: string[];
};
export type CopilotEvidence = { id: string; node_id: string | null; code: string | null; item_type: string | null; captured_at: string | null; source_id: string | null; has_file: boolean | null; notes: string | null };
export type CopilotSource = { id: string; node_id: string; code: string | null; label: string; platform: string | null; account: string | null; url: string | null; observed_at: string | null; located: boolean; map_node_id: string | null; location_status: string | null };
export type CopilotLocation = { id: string; map_node_id: string | null; label: string; latitude: number; longitude: number; city: string | null; region: string | null; country: string | null; tier: string; confidence: number | null; source_ids: string[] };
export type CopilotGap = { kind: string; gap: string; node_ids: string[]; relationship_id?: string };
export type CopilotRelationship = { id: string; type: string; source: string; target: string; status: string; confidence: number | null; timestamp: string | null; evidence_id: string | null; directed: boolean };
export type CopilotAnswer = {
  question: string; intents: string[]; answer: string; answer_source: "llm" | "deterministic"; insufficient_evidence: boolean;
  verified_facts: CopilotFact[]; inferences: CopilotFact[]; unknowns: CopilotFact[];
  evidence_used: CopilotEvidence[]; sources_used: CopilotSource[]; locations_used: CopilotLocation[];
  graph_context: {
    graph_source: GraphSource; nodes: { id: string; type: string; label: string; code: string | null }[]; relationships: CopilotRelationship[];
    paths: { nodes: string[]; relationship_ids: string[]; statuses: string[]; weakest_status: string }[];
  };
  evidence_gaps: CopilotGap[];
  llm: { used: boolean; provider: string; model: string | null; status: string; reason: string | null };
};

/* ---- Phase 4: ML Intelligence ---- */
export type MLProvenance = { model_name: string; model_version: string; computed_at: string; score?: number; method?: string };
export type MLFactor = { name: string; value: unknown; detail?: string; seconds?: number };
export type MLLocation = { location_node_id: string; map_node_id: string | null; label: string; latitude: number; longitude: number; city: string | null; region: string | null; country: string | null; status: string; confidence: number | null };
export type MLSource = { source_id: string; node_id: string; incident_id: string; code: string | null; label: string; platform: string | null; account: string | null; observed_at: string | null; location: MLLocation | null; evidence: { evidence_id: string; code: string | null; item_type: string | null }[]; appears_in_status?: string };
export type MLMediaSide = { media_id: string; filename: string; incident_id: string; incident_title?: string; same_investigation?: boolean; sources: MLSource[]; platforms: string[]; locations: MLLocation[]; evidence: { evidence_id: string; code: string | null }[] };
export type MLSimilarity = { id: string; kind: "similarity"; score: number; label: string; media: MLMediaSide; match: MLMediaSide; factors: MLFactor[]; explanation: string; evidence_refs: { fingerprint_ids: string[]; evidence_ids: string[] }; provenance: MLProvenance };
export type MLAnomaly = { id: string; kind: "anomaly"; type: string; title: string; score: number; factors: MLFactor[]; explanation: string; window: { start: string; end: string }; source_ids: string[]; node_ids: string[]; location_node_ids: string[]; relationship_ids: string[]; evidence_ids: string[]; provenance: MLProvenance };
export type MLCluster = { id: string; kind: "cluster"; score: number; size: number; members: { media_id: string; filename: string; incident_id: string; incident_title: string }[]; source_count: number; sources: MLSource[]; platforms: string[]; locations: MLLocation[]; similarity_range: { min: number; max: number }; investigations: string[]; factors: MLFactor[]; explanation: string; evidence_refs: { fingerprint_ids: string[]; evidence_ids: string[] }; provenance: MLProvenance };
export type MLAnalysis<T> = { analysis: string; status: "ok" | "insufficient_data"; message: string | null; computed_at: string; provenance: MLProvenance; disclaimer: string; results: T[]; detectors?: { detector: string; status: string; reason?: string; baseline?: Record<string, unknown> }[] };
export type MLAll = { similarity: MLAnalysis<MLSimilarity>; anomalies: MLAnalysis<MLAnomaly>; clusters: MLAnalysis<MLCluster> };

/* ---- Phase 5: Investigation Automation ---- */
export type WorkflowInfo = { state: string; label: string; stored_status: string; states: { key: string; label: string }[]; note: string };
export type Gap = { id: string; kind: string; gap: string; node_ids: string[]; origin: string; finding_id?: string; relationship_id?: string };
export type TimelineEvent = { timestamp: string | null; event: string; basis: "OBSERVED" | "RECORDED" | "CONFIRMED" | "INFERRED" | "UNKNOWN"; source: { code: string; source_id: string; node_id: string } | null; platform: string | null; location: { location_node_id: string; label: string; map_node_id: string | null; status: string } | null; node_ids: string[]; evidence_ids: string[]; record_id: string | null; status?: string };
export type SummaryFact = { statement: string; category: string; status: string | null; relationship_ids: string[]; node_ids: string[]; evidence_ids: string[]; source_ids: string[]; location_ids: string[] };
export type MLDigestItem = { id: string; kind: string; type?: string; score: number; label: string; explanation: string; model_name: string; model_version: string; computed_at: string; evidence_ids: string[]; source_ids: string[]; reviewed: { at: string; by: string } | null };
export type CaseSummary = {
  investigation: { id: string; title: string; workflow: WorkflowInfo };
  graph_source: GraphSource;
  media: { media_id: string; filename: string; uploaded_at: string | null; detections: { detection_id: string; model_name: string; manipulation_likelihood: number | null; note: string }[]; evidence_ids: string[] }[];
  sources: MLSource[];
  platforms: { platform: string; source_count: number }[];
  locations: { location_node_id: string; map_node_id: string | null; label: string; tier: string; confidence: number | null; links: { source_code: string; status: string }[] }[];
  propagation: { relationships: { relationship_graph_id: string; type: string; status: string; from: string; to: string; from_node: string; relationship_type: string }[] };
  ml_findings: Record<"similarity" | "anomalies" | "clusters", { status: string; message: string | null; model_name: string; model_version: string; computed_at: string; disclaimer: string; results: MLDigestItem[] }>;
  evidence: { evidence_id: string; code: string; item_type: string; captured_at: string | null; source_id: string | null }[];
  verified_facts: SummaryFact[]; inferences: SummaryFact[]; unknowns: SummaryFact[];
  evidence_gaps: Gap[]; disclaimer: string; generated_at: string;
};
export type ReportRecord = { id: string; incident_id: string; version: number; generated_at: string; report: { recommended_actions: { action: string; basis_gap_ids: string[] }[]; disclaimer: string } & Record<string, unknown> };
export type AlertDraft = {
  id: string; status: "draft" | "approved"; banner: string; summary_text: string; request_text: string; sent: false;
  created_at: string; approved_at: string | null; approved_by_email: string | null; exported_at: string | null;
  content: { transmission: string; observed_platforms: string[]; sources: { code: string; platform: string; account: string | null; observed_at: string }[]; relevant_locations: { label: string; statuses: string[] }[]; evidence_references: { evidence_id: string; code: string; item_type: string }[]; timeline: { timestamp: string; event: string; basis: string }[]; detection_findings: { model_name: string; manipulation_likelihood: number | null; note: string }[] };
};
export type AuditEventT = { id: string; action: string; target_type: string | null; target_id: string | null; actor: { user_id: string; email: string } | null; details: Record<string, unknown> | null; created_at: string };

async function download(path: string, filename: string) {
  const blob = await request<Blob>(path, {}, { raw: true });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/* ----------------------------------- api ---------------------------------- */


export type SecurityStatus = { rate_limiting: { backend: string; distributed: boolean }; trace_limit_per_minute: number; copilot_limit_per_minute: number; upload_limit_per_minute: number; access_token_minutes: number; refresh_token_days: number; sensitive_action_review: boolean; data_retention_days: number; key_provider: string };
export type ReverseSearchResult = { configured: boolean; provider?: string | null; message?: string; pages?: { url: string; title: string }[]; entities?: { description: string; score: number }[]; error?: string };
export type AudioAnalysis = { fingerprint: string; deepfake_detection: { configured: boolean; score: number | null; model_id: string | null; message?: string; error?: string }; note: string };

export const api = {
  /* auth */
  async register(email: string, password: string, displayName?: string): Promise<User> {
    return request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName ?? null }),
    });
  },

  async login(email: string, password: string, otp?: string): Promise<string> {
    // The backend's /auth/login uses OAuth2's form format, where the
    // "username" field carries the email address.
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", ...(otp ? { "X-Lineage-OTP": otp } : {}) },
      body: form.toString(),
      credentials: "include",
    }).catch(() => {
      throw new ApiError(`Could not reach the LINEAGE API at ${API_BASE}. Is the backend running?`, 0);
    });

    if (!res.ok) {
      let detail = "Incorrect email or password.";
      try {
        const body = await res.json();
        if (body?.detail) detail = body.detail;
      } catch { /* keep default */ }
      throw new ApiError(detail, res.status);
    }
    const data = await res.json();
    setToken(data.access_token);
    return data.access_token;
  },

  mfaSetup: () => request<{ secret: string; otpauth_uri: string }>("/auth/mfa/setup", { method: "POST" }),
  mfaStatus: () => request<{ enabled: boolean; required: boolean; recovery_codes_remaining: number }>("/auth/mfa/status"),
  mfaEnable: (code: string) => request<{ mfa_enabled: boolean; recovery_codes: string[]; note: string }>("/auth/mfa/enable", { method: "POST", body: JSON.stringify({ code }) }),
  mfaNewRecoveryCodes: (code: string) => request<{ recovery_codes: string[] }>("/auth/mfa/recovery-codes", { method: "POST", body: JSON.stringify({ code }) }),
  mfaDisable: (code: string) => request<{ mfa_enabled: boolean }>("/auth/mfa/disable", { method: "POST", body: JSON.stringify({ code }) }),

  async refresh(): Promise<string> { const data = await request<{access_token:string}>("/auth/refresh", { method:"POST", headers: CSRF_HEADERS }); setToken(data.access_token); return data.access_token; },

  logoutServer: () => request<void>("/auth/logout", { method: "POST", headers: CSRF_HEADERS }),

  async me(): Promise<User> {
    return request<User>("/auth/me");
  },

  health: () => request<Health>("/health"),
  detectorEvaluationLatest: () => request<DetectorEvaluationLatest>("/detection/evaluation/latest"),

  /* incidents */
  listIncidents: () => request<Incident[]>("/incidents"),
  getIncident: (id: string) => request<Incident>(`/incidents/${id}`),
  createIncident: (title: string, description?: string, victimRef?: string) =>
    request<Incident>("/incidents", {
      method: "POST",
      body: JSON.stringify({ title, description: description ?? null, victim_ref: victimRef ?? null }),
    }),

  /* media + analysis */
  listMedia: (incidentId: string) => request<MediaItem[]>(`/incidents/${incidentId}/media`),
  getMediaPreview: (incidentId: string, mediaId: string) =>
    request<Blob>(`/incidents/${incidentId}/media/${mediaId}/file`, {}, { raw: true }),
  verifyMediaIntegrity: (incidentId: string, mediaId: string) => request<{verified:boolean;stored_sha256:string|null;actual_sha256:string;filename:string}>(`/incidents/${incidentId}/media/${mediaId}/integrity`),
  deleteMedia: (incidentId: string, mediaId: string) => request<void>(`/incidents/${incidentId}/media/${mediaId}`, { method: "DELETE" }),
  deleteIncident: (incidentId: string) => request<void>(`/incidents/${incidentId}`, { method: "DELETE" }),
  getAnalysisFrame: (incidentId: string, mediaId: string) =>
    request<Blob>(`/incidents/${incidentId}/media/${mediaId}/analysis-frame`, {}, { raw: true }),
  uploadMedia: (incidentId: string, file: File) => {
    const fd = new FormData(); fd.append("file", file);
    return request<MediaItem>(`/incidents/${incidentId}/media`, { method: "POST", body: fd });
  },
  reverseSearch: (incidentId: string, mediaId: string) => request<ReverseSearchResult>(`/incidents/${incidentId}/media/${mediaId}/reverse-search`, { method: "POST" }),
  audioAnalysis: (incidentId: string, mediaId: string) => request<AudioAnalysis>(`/incidents/${incidentId}/media/${mediaId}/audio-analysis`),
  securityStatus: (incidentId: string) => request<SecurityStatus>(`/incidents/${incidentId}/security/status`),
  detectionEvaluation: (incidentId: string, manifest: File) => { const fd = new FormData(); fd.append("manifest", manifest); return request<any>(`/incidents/${incidentId}/detection/evaluation/run`, { method: "POST", body: fd }); },
  runDetection: (incidentId: string, mediaId: string) =>
    request<DetectionResult>(`/incidents/${incidentId}/media/${mediaId}/detect`, { method: "POST" }),
  getDetection: (incidentId: string, mediaId: string) =>
    request<DetectionResult>(`/incidents/${incidentId}/media/${mediaId}/detection`),
  runFingerprint: (incidentId: string, mediaId: string) =>
    request<Fingerprint>(`/incidents/${incidentId}/media/${mediaId}/fingerprint`, { method: "POST" }),
  getFingerprint: (incidentId: string, mediaId: string) =>
    request<Fingerprint>(`/incidents/${incidentId}/media/${mediaId}/fingerprint`),

  /* consent-gated Gemini query generation for manual public-web search */
  getWebSearchStatus: () => request<{ configured: boolean; provider: string }>("/incidents/web-search/status"),
  generateImageSearchLinks: (incidentId: string, mediaId: string) =>
    request<WebSearchRun>(`/incidents/${incidentId}/media/${mediaId}/web-search`, {
      method: "POST",
      body: JSON.stringify({ consent: true }),
    }),
  getLatestWebSearch: (incidentId: string, mediaId: string) =>
    request<WebSearchRun | null>(`/incidents/${incidentId}/media/${mediaId}/web-search`),

  /* sources + lineage */
  listSources: (incidentId: string) => request<Source[]>(`/incidents/${incidentId}/sources`),
  traceSourceUrl: (incidentId: string, url: string) => request<{ matched: boolean; source: Source | null; matches: { url: string; similarity: number; method: string; agreeing_hashes: number }[]; pending_match?: PendingTraceMatch; message?: string }>(`/incidents/${incidentId}/sources/trace-url`, { method: "POST", body: JSON.stringify({ url }) }),
  acceptTracedSource: (incidentId: string, pending: PendingTraceMatch) => request<Source>(`/incidents/${incidentId}/sources/trace-url/accept`, { method: "POST", body: JSON.stringify({ ...pending, review_confirmed: true }) }),
  rejectTracedSource: (incidentId: string, pending: PendingTraceMatch) => request<void>(`/incidents/${incidentId}/sources/trace-url/reject`, { method: "POST", body: JSON.stringify(pending) }),
  listRelationships: (incidentId: string) =>
    request<SourceRelationship[]>(`/incidents/${incidentId}/sources/relationships`),

  /* evidence */
  listEvidence: (incidentId: string) => request<EvidenceItem[]>(`/incidents/${incidentId}/evidence`),
  downloadEvidenceFile: (incidentId: string, evidenceId: string) =>
    request<Blob>(`/incidents/${incidentId}/evidence/${evidenceId}/file`, {}, { raw: true }),
  verifyEvidenceIntegrity: (incidentId: string, evidenceId: string) =>
    request<{verified:boolean;stored_sha256:string|null;actual_sha256:string;filename:string}>(`/incidents/${incidentId}/evidence/${evidenceId}/integrity`),
  deleteEvidence: (incidentId: string, evidenceId: string) =>
    request<void>(`/incidents/${incidentId}/evidence/${evidenceId}`, { method: "DELETE" }),
  verifyAllEvidenceIntegrity: (incidentId: string) => request<{investigation_id:string;verified:boolean;results:{id:string;verified:boolean;stored_sha256:string|null;actual_sha256:string|null;error?:string}[]}>(`/incidents/${incidentId}/evidence/integrity/verify-all`),
  getFootprints: (incidentId: string) => request<any>(`/incidents/${incidentId}/footprints`),
  compareMetadata: (incidentId: string, mediaId: string, file?: File) => {
    const body = new FormData();
    if (file) body.append("file", file);
    return request<{ media_id: string; snapshot_id: string | null; recheck_source: string; state: "unknown" | "unchanged" | "changed against snapshot" | "stripped" | "inconsistent"; reason: string; changed_fields?: string[] }>(
      `/incidents/${incidentId}/media/${mediaId}/metadata/compare`, { method: "POST", body });
  },
  getMetadataReport: (incidentId: string, mediaId: string, lang: "en" | "hi" = "en") =>
    request<MediaOriginAnalysis & { media_id: string; filename: string; sha256: string | null }>(`/incidents/${incidentId}/media/${mediaId}/metadata-report?lang=${lang}`),
  getOrigin: (incidentId: string, lang: "en" | "hi" = "en") => request<OriginReport>(`/incidents/${incidentId}/origin?lang=${lang}`),
  downloadLegalPack: (incidentId: string, body: LegalPackRequest) =>
    request<Blob>(`/incidents/${incidentId}/automation/legal-pack`, { method: "POST", body: JSON.stringify(body) }, { raw: true }),
  downloadCaseBundle: (incidentId: string, includeFiles = false) =>
    request<Blob>(`/incidents/${incidentId}/evidence/bundle?include_files=${includeFiles ? "true" : "false"}`, {}, { raw: true }),
  getTakedownDrafts: (incidentId: string) => request<{drafts:any[];count:number}>(`/incidents/${incidentId}/automation/takedown-drafts`),
  getHashManifest: (incidentId: string) => request<any>(`/incidents/${incidentId}/automation/hash-manifest`),
  downloadRequestPack: (incidentId: string) => request<Blob>(`/incidents/${incidentId}/automation/request-pack/pdf`, {}, { raw: true }),

  /* attribution gap */
  generateAttributionGap: (incidentId: string) =>
    request<AttributionGapEntry[]>(`/incidents/${incidentId}/attribution-gap`, { method: "POST" }),
  getAttributionGap: (incidentId: string) =>
    request<AttributionGapEntry[]>(`/incidents/${incidentId}/attribution-gap`),

  /* report */
  generateReport: (incidentId: string) =>
    request<IncidentReport>(`/incidents/${incidentId}/report`, { method: "POST" }),
  getReport: (incidentId: string) => request<IncidentReport>(`/incidents/${incidentId}/report`),
  downloadReportPdf: async (incidentId: string, language: "en" | "hi" = "en"): Promise<Blob> =>
    request<Blob>(`/incidents/${incidentId}/report/pdf?language=${language}`, {}, { raw: true }),

  /* sources — real, user-entered */
  addSource: (
    incidentId: string,
    source: {
      platform: string;
      account_identifier?: string;
      url?: string;
      observed_at: string;
      similarity_score?: number;
      relationship_label?: string;
    }
  ) =>
    request<Source>(`/incidents/${incidentId}/sources`, {
      method: "POST",
      body: JSON.stringify({ ...source, is_seeded: false }),
    }),

  addRelationship: (
    incidentId: string,
    rel: { from_source_id: string; to_source_id: string; relationship_type: string; confidence?: number }
  ) =>
    request<SourceRelationship>(`/incidents/${incidentId}/sources/relationships`, {
      method: "POST",
      body: JSON.stringify(rel),
    }),
  /* geo / propagation map */
  getGeo: (incidentId: string) => request<GeoData>(`/incidents/${incidentId}/geo`),
  getGeoStats: (incidentId: string, q: GeoStatsQuery = {}) => {
    const p = new URLSearchParams();
    if (q.start) p.set("start", q.start);
    if (q.end) p.set("end", q.end);
    if (q.platform && q.platform !== "all") p.set("platform", q.platform);
    if (q.tier && q.tier !== "all") p.set("tier", q.tier);
    if (q.metric) p.set("metric", q.metric);
    const qs = p.toString();
    return request<GeoStats>(`/incidents/${incidentId}/geo-stats${qs ? `?${qs}` : ""}`);
  },
  setSourceLocation: (incidentId: string, sourceId: string, loc: LocationInput) =>
    request<GeoData>(`/incidents/${incidentId}/sources/${sourceId}/location`, {
      method: "PUT",
      body: JSON.stringify(loc),
    }),
  deleteSourceLocation: (incidentId: string, sourceId: string) =>
    request<GeoData>(`/incidents/${incidentId}/sources/${sourceId}/location`, { method: "DELETE" }),
  confirmDirection: (incidentId: string, relationshipId: string, note?: string) =>
    request<GeoData>(`/incidents/${incidentId}/sources/relationships/${relationshipId}/direction`, {
      method: "PUT",
      body: JSON.stringify({ note: note ?? null }),
    }),
  revokeDirection: (incidentId: string, relationshipId: string) =>
    request<GeoData>(`/incidents/${incidentId}/sources/relationships/${relationshipId}/direction`, { method: "DELETE" }),
  geocode: (q: string) =>
    request<{ results: GeocodeResult[]; attribution: string }>(`/geo/geocode?q=${encodeURIComponent(q)}`),

  /* Phase 3A: graph persistence status + Phase 3B: Investigation Copilot */
  getGraphHealth: () => request<GraphHealth>("/graph/health"),
  syncGraph: (incidentId: string, rebuild = false) =>
    request<{ status: string; nodes: number; relationships: number }>(`/incidents/${incidentId}/graph/sync${rebuild ? "?rebuild=true" : ""}`, { method: "POST" }),
  askCopilot: (incidentId: string, question: string) =>
    request<CopilotAnswer>(`/incidents/${incidentId}/copilot`, { method: "POST", body: JSON.stringify({ question }) }),

  /* Phase 4: ML Intelligence (analysis only) */
  getML: (incidentId: string) => request<MLAll>(`/incidents/${incidentId}/ml`),

  /* Phase 5: Investigation Automation (nothing is ever sent externally) */
  getCaseSummary: (incidentId: string) => request<CaseSummary>(`/incidents/${incidentId}/automation/summary`),
  getTimeline: (incidentId: string) =>
    request<{ events: TimelineEvent[]; undated: TimelineEvent[]; legend: Record<string, string> }>(`/incidents/${incidentId}/automation/timeline`),
  generateInvestigationReport: (incidentId: string) =>
    request<ReportRecord>(`/incidents/${incidentId}/automation/reports`, { method: "POST" }),
  getLatestInvestigationReport: (incidentId: string) => request<ReportRecord>(`/incidents/${incidentId}/automation/reports/latest`),
  downloadInvestigationReportPdf: (incidentId: string, reportId: string, version: number) =>
    download(`/incidents/${incidentId}/automation/reports/${reportId}/pdf`, `investigation-report-v${version}.pdf`),
  listAlertDrafts: (incidentId: string) => request<AlertDraft[]>(`/incidents/${incidentId}/automation/alert-drafts`),
  createAlertDraft: (incidentId: string) => request<AlertDraft>(`/incidents/${incidentId}/automation/alert-drafts`, { method: "POST" }),
  editAlertDraft: (incidentId: string, id: string, patch: { summary_text?: string; request_text?: string }) =>
    request<AlertDraft>(`/incidents/${incidentId}/automation/alert-drafts/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  approveAlertDraft: (incidentId: string, id: string) =>
    request<AlertDraft>(`/incidents/${incidentId}/automation/alert-drafts/${id}/approve`, { method: "POST" }),
  exportAlertDraft: (incidentId: string, id: string, format: "json" | "pdf") =>
    download(`/incidents/${incidentId}/automation/alert-drafts/${id}/export?format=${format}`, `alert-draft-${id.slice(0, 8)}.${format}`),
  exportInvestigation: (incidentId: string, format: "json" | "pdf") =>
    download(`/incidents/${incidentId}/automation/export?format=${format}`, `lineage-investigation-${incidentId.slice(0, 8)}.${format}`),
  getWorkflow: (incidentId: string) => request<WorkflowInfo>(`/incidents/${incidentId}/workflow`),
  setWorkflow: (incidentId: string, state: string, note?: string) =>
    request<WorkflowInfo>(`/incidents/${incidentId}/workflow`, { method: "PUT", body: JSON.stringify({ state, note: note ?? null }) }),
  recordReview: (incidentId: string, target_type: "evidence" | "ml_finding" | "report_finding" | "gap", target_id: string, decision = "reviewed") =>
    request<AuditEventT>(`/incidents/${incidentId}/reviews`, { method: "POST", body: JSON.stringify({ target_type, target_id, decision }) }),
  getAudit: (incidentId: string) => request<{ events: AuditEventT[] }>(`/incidents/${incidentId}/audit`),
  getTrustStatus: (incidentId: string) => request<any>(`/incidents/${incidentId}/trust/status`),
  getVictimSupport: (incidentId: string) => request<any>(`/incidents/${incidentId}/victim-support`),
  getBsaCertificate: (incidentId: string) => request<any>(`/incidents/${incidentId}/evidence/bsa63-certificate`, { method: "POST" }),
  listConsents: (incidentId: string) => request<{ purpose: string; granted: boolean; created_at: string }[]>(`/incidents/${incidentId}/privacy/consents`),
  recordConsent: (incidentId: string, purpose: string, granted = true) => request<any>(`/incidents/${incidentId}/privacy/consent`, { method: "POST", body: JSON.stringify({ purpose, granted }) }),
  queueReport: (incidentId: string) => request<any>(`/incidents/${incidentId}/jobs/report`, { method: "POST" }),
  getJob: (incidentId: string, jobId: string) => request<any>(`/incidents/${incidentId}/jobs/${jobId}`),
  getManifestKey: () => request<ManifestKeyInfo>("/trust/manifest-key"),
  listManifests: (incidentId: string) => request<ManifestRow[]>(`/incidents/${incidentId}/evidence/manifests`),
  createManifest: (incidentId: string, timestamp = false) => request<any>(`/incidents/${incidentId}/evidence/manifest${timestamp ? "?timestamp=true" : ""}`, { method: "POST" }),
  verifyManifest: (incidentId: string, manifestId: string) => request<ManifestVerification>(`/incidents/${incidentId}/evidence/manifests/${manifestId}/verify`, { method: "POST" }),

};

export type ManifestKeyInfo = { algorithm: string; key_id: string; public_key: string; public_key_pem: string };
export type ManifestRow = { id: string; key_id: string; manifest_sha256: string; has_timestamp: boolean; created_at: string };
export type ManifestVerification = {
  id: string;
  verification: { signature_valid: boolean; key_trusted: boolean; key_matches_embedded: boolean; key_id: string; manifest_sha256_matches: boolean; entries_digest_matches: boolean };
  timestamp: any;
  case_drift_since_signing: { unchanged: boolean; added: string[]; removed: string[]; hash_changed: string[] };
  note: string;
};

export { API_BASE };
