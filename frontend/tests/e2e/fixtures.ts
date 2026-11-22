import type { Page, Route } from "@playwright/test";

/** Deterministic API fixtures so e2e/a11y runs need no backend. Values are test data only; never shipped to the app. */
export const INCIDENT_ID = "inc-1234abcd";
const now = "2026-01-05T10:00:00";
const incident = { id: INCIDENT_ID, title: "Test case — fabricated video", description: "Fixture", victim_ref: "V-1", status: "evidence_preserved", created_at: now, updated_at: now };
const media = { id: "m1", kind: "image", original_filename: "sample.png", file_size_bytes: 20480, width: 640, height: 480, sha256: "ab".repeat(32), uploaded_at: now };
const detection = { id: "d1", manipulation_likelihood: 72.4, edge_irregularity: 41, compression_density: 33, detected_region: "face", likely_technique: "face swap", model_name: "fixture-model", explanation: "Fixture explanation.", explainability_json: null, created_at: now };
const fingerprint = { id: "f1", average_hash: "f0e0c0c0e0f0f8f8", perceptual_hash: "d1a5c3e18f0b2d47", difference_hash: "0f1e3c78f0e1c387", face_embedding_json: null, keyframe_hashes_json: JSON.stringify(["a", "b", "c"]), audio_fingerprint: null, created_at: now };
const sources = [
  { id: "s1", platform: "Telegram", account_identifier: "@origin", url: "https://example.test/a", observed_at: now, similarity_score: 94, relationship_label: "Earliest observed", is_seeded: false, page_sha256: "cd".repeat(32) },
  { id: "s2", platform: "X", account_identifier: "@repost", url: null, observed_at: "2026-01-05T12:00:00", similarity_score: 81, relationship_label: "Repost", is_seeded: false, page_sha256: null },
  { id: "s3", platform: "Facebook", account_identifier: "@other", url: null, observed_at: "2026-01-06T09:00:00", similarity_score: null, relationship_label: null, is_seeded: false, page_sha256: null },
];
const relationships = [{ id: "r1", from_source_id: "s1", to_source_id: "s2", relationship_type: "reposted", confidence: 80 }];
const evidence = [{ id: "e1", source_id: "s1", item_type: "screenshot", notes: "Captured page", captured_at: now, sha256: "ef".repeat(32) }];
const gap = [{ id: "g1", category: "known", statement: "Earliest observed on Telegram.", created_at: now }];

type Body = unknown;
function respond(method: string, path: string): { status: number; body: Body } {
  const m = (re: RegExp) => re.test(path);
  if (m(/^\/auth\/me$/)) return { status: 200, body: { id: "u1", email: "demo@lineage.app", display_name: "Demo" } };
  if (path === "/incidents" && method === "GET") return { status: 200, body: [incident] };
  if (m(/^\/incidents\/web-search\/status$/)) return { status: 200, body: { configured: false, provider: "none" } };
  if (m(/^\/incidents\/[^/]+$/)) return { status: 200, body: incident };
  if (m(/\/media$/)) return { status: 200, body: [media] };
  if (m(/\/detection$/)) return { status: 200, body: detection };
  if (m(/\/fingerprint$/)) return { status: 200, body: fingerprint };
  if (m(/\/sources$/)) return { status: 200, body: sources };
  if (m(/\/sources\/relationships$/)) return { status: 200, body: relationships };
  if (m(/\/evidence$/)) return { status: 200, body: evidence };
  if (m(/\/attribution-gap$/)) return { status: 200, body: gap };
  if (m(/\/web-search$/)) return { status: 200, body: null };
  if (m(/\/(report|timeline|alerts|jobs|footprints|ml|graph|geo|copilot)/)) return { status: 404, body: { detail: "Not generated yet" } };
  return { status: 404, body: { detail: "Not found (fixture)" } };
}

export async function mockApi(page: Page, { signedIn = true }: { signedIn?: boolean } = {}) {
  if (signedIn) await page.addInitScript(() => localStorage.setItem("lineage_token", "fixture-token"));
  await page.route("http://localhost:8000/**", async (route: Route) => {
    const req = route.request();
    const cors = { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true", "access-control-allow-headers": "authorization,content-type", "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS" };
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const { pathname } = new URL(req.url());
    if (/\/(file|thumbnail|frame)/.test(pathname)) return route.fulfill({ status: 404, headers: cors, contentType: "application/json", body: JSON.stringify({ detail: "no file in fixtures" }) });
    const { status, body } = respond(req.method(), pathname);
    return route.fulfill({ status, headers: cors, contentType: "application/json", body: JSON.stringify(body) });
  });
}
