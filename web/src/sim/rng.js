// Deterministic, seedable PRNG. The turn resolver and every mission seed depend
// on this: the same (state, seed) must always produce the same outcome, because
// docs/03-TURN-RESOLUTION-SPEC.md promises determinism and the acceptance matrix
// tests it. Math.random() is never used in simulation code.

/** mulberry32: small, fast, well-distributed for gameplay use. Not cryptographic. */
export function makeRng(seed) {
  let a = (seed >>> 0) || 0x9e3779b9;
  const next = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    /** integer in [lo, hi] inclusive */
    int: (lo, hi) => lo + Math.floor(next() * (hi - lo + 1)),
    float: (lo, hi) => lo + next() * (hi - lo),
    /** stable shuffle (Fisher-Yates), does not mutate the input */
    shuffled: (arr) => {
      const out = arr.slice();
      for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        [out[i], out[j]] = [out[j], out[i]];
      }
      return out;
    },
    chance: (p) => next() < p,
    /** fork a labelled sub-stream so adding a system cannot shift other systems' numbers */
    fork: (label) => makeRng(hashString(label) ^ ((a * 2654435761) >>> 0)),
  };
}

/** FNV-1a. Used for sub-stream labels and for the save integrity digest. */
export function hashString(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** Stable JSON: object keys sorted recursively, so a digest of equal states matches. */
export function stableStringify(value) {
  const walk = (v) => {
    if (v === null || typeof v !== 'object') return v;
    if (Array.isArray(v)) return v.map(walk);
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = walk(v[k]);
    return out;
  };
  return JSON.stringify(walk(value));
}

/** Content digest for SaveEnvelope.integrity. An integrity tool, not a security control. */
export function digest(value) {
  const s = stableStringify(value);
  // 64-bit-ish: two independently seeded FNV passes, hex-joined.
  let h1 = 0x811c9dc5, h2 = 0x01000193;
  for (let i = 0; i < s.length; i++) {
    h1 ^= s.charCodeAt(i); h1 = Math.imul(h1, 0x01000193);
    h2 += s.charCodeAt(i) * (i + 1); h2 = Math.imul(h2, 0x85ebca6b);
  }
  return ((h1 >>> 0).toString(16).padStart(8, '0')) + ((h2 >>> 0).toString(16).padStart(8, '0'));
}
