/** Small, dependency-free fuzzy matcher for the Ctrl+K palette. */
export type Command = { id: string; label: string; hint?: string; group: string; keywords?: string[]; run: () => void };

/** Higher is better; -1 = no match. Prefix > word-start > substring > in-order subsequence. */
export function score(query: string, text: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 0;
  const t = text.toLowerCase();
  if (t === q) return 1000;
  if (t.startsWith(q)) return 800 - t.length;
  const wi = t.split(/[\s/_-]+/).findIndex((w) => w.startsWith(q));
  if (wi >= 0) return 600 - wi * 10;
  const at = t.indexOf(q);
  if (at >= 0) return 400 - at;
  let i = 0, gaps = 0, last = -1;
  for (const ch of q) {
    const f = t.indexOf(ch, i);
    if (f < 0) return -1;
    if (last >= 0 && f > last + 1) gaps++;
    last = f; i = f + 1;
  }
  return 200 - gaps * 10 - (t.length - q.length);
}

export function filterCommands(commands: Command[], query: string): Command[] {
  if (!query.trim()) return commands;
  return commands
    .map((c) => ({ c, s: Math.max(score(query, c.label), ...(c.keywords ?? []).map((k) => score(query, k) - 50), score(query, c.hint ?? "") - 100) }))
    .filter((x) => x.s >= 0)
    .sort((a, b) => b.s - a.s)
    .map((x) => x.c);
}
