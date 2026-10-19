// Procedural materials. The brief's art bar needs production-authored textures;
// this prototype generates them so that surfaces still read as stone, render,
// timber and slate rather than as flat grey, and so the page stays self-
// contained. They are placeholders and are labelled as such in the UI.

let THREE;
export function initMaterials(three) { THREE = three; }

const cache = new Map();

function noiseCanvas(size, fn) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(size, size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const i = (y * size + x) * 4;
    const [r, g, b, a] = fn(x, y, size);
    img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b; img.data[i + 3] = a ?? 255;
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

// value noise with a few octaves — enough for grain, not a terrain system
function hash2(x, y) { const n = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return n - Math.floor(n); }
function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash2(xi, yi), b = hash2(xi + 1, yi), c = hash2(xi, yi + 1), d = hash2(xi + 1, yi + 1);
  return a * (1 - u) * (1 - v) + b * u * (1 - v) + c * (1 - u) * v + d * u * v;
}
function fbm(x, y, oct = 4) {
  let s = 0, amp = 0.5, f = 1;
  for (let i = 0; i < oct; i++) { s += vnoise(x * f, y * f) * amp; f *= 2.07; amp *= 0.5; }
  return s;
}

function texture(key, size, fn, repeat = [1, 1]) {
  const ck = `${key}:${size}:${repeat.join('x')}`;
  if (cache.has(ck)) return cache.get(ck);
  const t = new THREE.CanvasTexture(noiseCanvas(size, fn));
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat[0], repeat[1]);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  cache.set(ck, t);
  return t;
}

const mix = (a, b, t) => a + (b - a) * t;

/** Material library keyed by the ids the district data uses. */
export function material(id, opts = {}) {
  const ck = `mat:${id}:${JSON.stringify(opts)}`;
  if (cache.has(ck)) return cache.get(ck);
  let m;
  switch (id) {
    case 'mat_limestone_render': {
      const map = texture('render', 128, (x, y, s) => {
        const n = fbm(x / s * 7, y / s * 7, 5);
        const patch = fbm(x / s * 2.1 + 11, y / s * 2.1, 3);
        const base = mix(196, 168, n * 0.8) * mix(1, 0.86, Math.max(0, patch - 0.55) * 2);
        return [base, base * 0.965, base * 0.9];
      }, [3, 2]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.92, metalness: 0 });
      break;
    }
    case 'mat_limestone_block': {
      const map = texture('block', 192, (x, y, s) => {
        const bh = 24, bw = 48;
        const row = Math.floor(y / bh);
        const off = (row % 2) * bw / 2;
        const inJoint = ((y % bh) < 2) || (((x + off) % bw) < 2);
        const n = fbm(x / s * 9, y / s * 9, 4);
        let base = mix(206, 176, n);
        if (inJoint) base *= 0.72;
        return [base, base * 0.97, base * 0.92];
      }, [2, 1.4]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.88 });
      break;
    }
    case 'mat_rubble_stone': {
      const map = texture('rubble', 192, (x, y, s) => {
        const cellX = Math.floor(x / 16 + fbm(x / s * 3, y / s * 3) * 1.2);
        const cellY = Math.floor(y / 14 + fbm(x / s * 3 + 5, y / s * 3) * 1.2);
        const stone = hash2(cellX, cellY);
        const n = fbm(x / s * 14, y / s * 14, 3);
        const base = mix(mix(120, 186, stone), 150, n * 0.5);
        return [base, base * 0.96, base * 0.88];
      }, [2.2, 1.6]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.95 });
      break;
    }
    case 'mat_plank_timber': {
      const map = texture('plank', 128, (x, y, s) => {
        const plank = Math.floor(y / 11);
        const grain = fbm(x / s * 30, plank * 3.3, 3);
        const base = mix(96, 134, grain) * (0.92 + 0.08 * hash2(plank, 3));
        const gap = (y % 11) < 1 ? 0.6 : 1;
        return [base * gap, base * 0.74 * gap, base * 0.52 * gap];
      }, [2, 2]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.85 });
      break;
    }
    case 'mat_slate': {
      const map = texture('slate', 128, (x, y, s) => {
        const row = Math.floor(y / 14), off = (row % 2) * 10;
        const tile = hash2(Math.floor((x + off) / 20), row);
        const n = fbm(x / s * 16, y / s * 16, 3);
        const edge = ((y % 14) < 1.5) ? 0.6 : 1;
        const base = mix(52, 84, tile * 0.7 + n * 0.3) * edge;
        return [base * 0.95, base, base * 1.08];
      }, [4, 3]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.74 });
      break;
    }
    case 'mat_clay_tile': {
      const map = texture('clay', 128, (x, y, s) => {
        const row = Math.floor(y / 12);
        const wave = Math.sin((x / 16) * Math.PI * 2) * 0.5 + 0.5;
        const t = hash2(Math.floor(x / 16), row);
        const base = mix(118, 166, wave * 0.6 + t * 0.4);
        return [base, base * 0.6, base * 0.44];
      }, [4, 3]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.8 });
      break;
    }
    case 'mat_corrugated': {
      const map = texture('corr', 64, (x, y, s) => {
        const wave = Math.sin((y / 8) * Math.PI * 2) * 0.5 + 0.5;
        const rust = Math.max(0, fbm(x / s * 5, y / s * 5, 3) - 0.55) * 2;
        const base = mix(108, 152, wave);
        return [mix(base, 128, rust), mix(base, 86, rust), mix(base, 58, rust)];
      }, [3, 3]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.6, metalness: 0.35 });
      break;
    }
    case 'surf_grass': case 'surf_crop': {
      const crop = id === 'surf_crop';
      const map = texture(id, 256, (x, y, s) => {
        const n = fbm(x / s * 22, y / s * 22, 4);
        const clump = fbm(x / s * 5 + 3, y / s * 5, 3);
        const g = mix(crop ? 128 : 84, crop ? 168 : 126, n * 0.7 + clump * 0.3);
        return [g * (crop ? 0.92 : 0.66), g, g * (crop ? 0.42 : 0.44)];
      }, [16, 14]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 1 });
      break;
    }
    case 'surf_dirt_track': {
      const map = texture(id, 256, (x, y, s) => {
        const rut = Math.abs(Math.sin((x / s) * Math.PI * 2)) * 0.4;
        const n = fbm(x / s * 18, y / s * 18, 4);
        const base = mix(96, 136, n * 0.8 + rut * 0.2);
        return [base, base * 0.86, base * 0.66];
      }, [10, 10]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.98 });
      break;
    }
    case 'surf_cobble': {
      const map = texture(id, 256, (x, y, s) => {
        const cx = Math.floor(x / 11 + fbm(x / s * 7, y / s * 7) * 0.9);
        const cy = Math.floor(y / 11 + fbm(x / s * 7 + 9, y / s * 7) * 0.9);
        const st = hash2(cx, cy);
        const n = fbm(x / s * 26, y / s * 26, 2);
        const base = mix(mix(74, 128, st), 102, n * 0.4);
        return [base, base * 0.98, base * 0.92];
      }, [12, 12]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.82 });
      break;
    }
    case 'surf_packed_earth': {
      const map = texture(id, 192, (x, y, s) => {
        const n = fbm(x / s * 16, y / s * 16, 4);
        const base = mix(104, 146, n);
        return [base, base * 0.88, base * 0.7];
      }, [8, 8]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.96 });
      break;
    }
    case 'surf_board_floor': {
      const map = texture(id, 192, (x, y, s) => {
        const plank = Math.floor(y / 16);
        const grain = fbm(x / s * 34, plank * 4.1, 3);
        const base = mix(84, 128, grain) * (0.9 + 0.1 * hash2(plank, 7));
        const gap = (y % 16) < 1.2 ? 0.5 : 1;
        return [base * gap, base * 0.72 * gap, base * 0.5 * gap];
      }, [4, 4]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.78 });
      break;
    }
    case 'surf_stone_floor': {
      const map = texture(id, 192, (x, y, s) => {
        const g = 32;
        const inJoint = (x % g) < 2 || (y % g) < 2;
        const st = hash2(Math.floor(x / g), Math.floor(y / g));
        const n = fbm(x / s * 20, y / s * 20, 3);
        let base = mix(mix(96, 142, st), 118, n * 0.5);
        if (inJoint) base *= 0.76;
        return [base, base * 0.98, base * 0.94];
      }, [3, 3]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 0.86 });
      break;
    }
    case 'mat_hedge': {
      const map = texture('hedge', 128, (x, y, s) => {
        const n = fbm(x / s * 26, y / s * 26, 5);
        const g = mix(34, 92, n);
        return [g * 0.62, g, g * 0.4];
      }, [4, 2]);
      m = new THREE.MeshStandardMaterial({ map, roughness: 1 });
      break;
    }
    case 'mat_leaded_glass':
      m = new THREE.MeshStandardMaterial({ color: 0x9fb4c4, roughness: 0.25, metalness: 0.1, transparent: true, opacity: 0.4 });
      break;
    case 'mat_wood_dark':
      m = new THREE.MeshStandardMaterial({ color: 0x4a3524, roughness: 0.8 });
      break;
    case 'mat_metal_dull':
      m = new THREE.MeshStandardMaterial({ color: 0x5a5a5e, roughness: 0.5, metalness: 0.65 });
      break;
    case 'mat_cloth':
      m = new THREE.MeshStandardMaterial({ color: 0x6d6a55, roughness: 0.95 });
      break;
    case 'mat_skin':
      m = new THREE.MeshStandardMaterial({ color: 0xc69b7b, roughness: 0.62 });
      break;
    case 'mat_uniform_axis':
      m = new THREE.MeshStandardMaterial({ color: 0x5a5f4d, roughness: 0.9 });
      break;
    case 'mat_uniform_civ':
      m = new THREE.MeshStandardMaterial({ color: 0x6b5a46, roughness: 0.92 });
      break;
    default:
      m = new THREE.MeshStandardMaterial({ color: opts.color ?? 0x8a8a80, roughness: opts.roughness ?? 0.85 });
  }
  if (opts.color) m.color = new THREE.Color(opts.color);
  cache.set(ck, m);
  return m;
}

export function disposeMaterials() {
  for (const v of cache.values()) { v.dispose?.(); v.map?.dispose?.(); }
  cache.clear();
}
