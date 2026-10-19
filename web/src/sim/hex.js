// Pointy-top hexes in axial coordinates. One module so the map view, the
// pathfinder and the turn resolver cannot disagree about what "adjacent" means.

export const DIRS = [[+1, 0], [+1, -1], [0, -1], [-1, 0], [-1, +1], [0, +1]];

export const key = (q, r) => `${q},${r}`;
export const parseKey = (k) => k.split(',').map(Number);
export const neighbors = (q, r) => DIRS.map(([dq, dr]) => [q + dq, r + dr]);

/** axial -> cube, for distance */
export function distance(aq, ar, bq, br) {
  const ax = aq, az = ar, ay = -ax - az;
  const bx = bq, bz = br, by = -bx - bz;
  return Math.max(Math.abs(ax - bx), Math.abs(ay - by), Math.abs(az - bz));
}

/** pixel centre of a hex, for the map view */
export function toPixel(q, r, size) {
  return { x: size * Math.sqrt(3) * (q + r / 2), y: size * 1.5 * r };
}

/** nearest hex to a pixel point, for tap selection */
export function fromPixel(x, y, size) {
  const q = (x * Math.sqrt(3) / 3 - y / 3) / size;
  const r = (y * 2 / 3) / size;
  // cube rounding
  let cx = q, cz = r, cy = -cx - cz;
  let rx = Math.round(cx), ry = Math.round(cy), rz = Math.round(cz);
  const dx = Math.abs(rx - cx), dy = Math.abs(ry - cy), dz = Math.abs(rz - cz);
  if (dx > dy && dx > dz) rx = -ry - rz;
  else if (dy > dz) ry = -rx - rz;
  else rz = -rx - ry;
  return [rx, rz];
}
