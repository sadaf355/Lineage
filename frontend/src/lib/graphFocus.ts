/** Which nodes/edges stay bright when one source is focused on the Lineage graph. Pure, so it is unit-testable. */
export type Edge = { id: string; fromId: string; toId: string };

export function connectedIds(focusId: string | null, edges: Edge[]): Set<string> | null {
  if (!focusId) return null; // nothing focused: nothing is dimmed
  const out = new Set<string>([focusId]);
  for (const e of edges) {
    if (e.fromId === focusId) out.add(e.toId);
    if (e.toId === focusId) out.add(e.fromId);
  }
  return out;
}

export function nodeOpacity(id: string, connected: Set<string> | null): number {
  return !connected || connected.has(id) ? 1 : 0.25;
}

export function edgeState(e: Edge, focusId: string | null): "idle" | "focused" | "dimmed" {
  if (!focusId) return "idle";
  return e.fromId === focusId || e.toId === focusId ? "focused" : "dimmed";
}
