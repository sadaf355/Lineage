/** Turn a real hex hash into its bits, so the Fingerprint screen can draw the actual hash (not a decoration). */
export function hexToBits(hex: string | null | undefined): number[] | null {
  if (!hex || !/^[0-9a-fA-F]+$/.test(hex)) return null;
  const bits: number[] = [];
  for (const ch of hex) {
    const n = parseInt(ch, 16);
    for (let b = 3; b >= 0; b--) bits.push((n >> b) & 1);
  }
  return bits;
}

/** Grid width for n bits: 8 columns for the 64-bit hashes LINEAGE produces; a square-ish fallback otherwise. */
export function gridColumns(bitCount: number): number {
  if (bitCount % 8 === 0 && bitCount <= 256) return 8;
  return Math.max(1, Math.round(Math.sqrt(bitCount)));
}

/** Hamming-style popcount, shown as a real statistic about the hash. */
export function popcount(bits: number[]): number {
  return bits.reduce((a, b) => a + b, 0);
}
