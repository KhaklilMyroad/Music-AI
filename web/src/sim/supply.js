// Supply propagation. Supply must change what the player can do, so it is
// recomputed from sources every turn rather than stored as a decorative number.

import { UNIT_CAPABILITIES } from './contracts.js';

const SIDE = { allied: 'allied', axis: 'axis' };
export function sideOf(faction) {
  return faction.startsWith('axis_') ? SIDE.axis : SIDE.allied;
}
export function controlSide(control) {
  if (control === 'allied') return SIDE.allied;
  if (control === 'axis') return SIDE.axis;
  return null; // neutral / contested carry no supply for either side
}

/**
 * Recompute tile.supply for one side.
 * A source emits `throughput`; each step costs the destination terrain's
 * supply_draw; a tile not controlled by that side cannot relay supply.
 * Contested tiles may receive supply but never relay it.
 */
export function propagateSupply(campaign, atlas, side, sources) {
  const best = new Map();
  const frontier = [];
  for (const s of sources) {
    if (s.throughput <= 0) continue;
    const t = campaign.tiles[s.tile_id];
    if (!t) continue;
    const v = Math.min(10, s.throughput);
    if ((best.get(s.tile_id) ?? -1) < v) { best.set(s.tile_id, v); frontier.push([s.tile_id, v]); }
  }
  // Dial-style relaxation: deterministic because we always drain the highest
  // remaining value first, with tile_id as the tie-break.
  while (frontier.length) {
    frontier.sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1));
    const [id, val] = frontier.shift();
    if ((best.get(id) ?? -1) > val) continue;
    const tile = campaign.tiles[id];
    if (!tile) continue;
    // only a tile this side controls relays further
    if (controlSide(tile.control) !== side) continue;
    for (const nb of tile.neighbors) {
      const n = campaign.tiles[nb];
      if (!n || !n.passable) continue;
      const draw = atlas.terrain_rules[n.terrain]?.supply_draw ?? 1.0;
      const next = Math.max(0, val - Math.max(0.5, draw));
      if (next <= 0) continue;
      if ((best.get(nb) ?? -1) < next) { best.set(nb, next); frontier.push([nb, next]); }
    }
  }
  return best;
}

export function applySupply(campaign, atlas, sourcesBySide) {
  const alliedMap = propagateSupply(campaign, atlas, SIDE.allied, sourcesBySide.allied || []);
  const axisMap = propagateSupply(campaign, atlas, SIDE.axis, sourcesBySide.axis || []);
  for (const t of Object.values(campaign.tiles)) {
    const side = controlSide(t.control);
    let v = 0;
    if (side === SIDE.allied) v = alliedMap.get(t.tile_id) ?? 0;
    else if (side === SIDE.axis) v = axisMap.get(t.tile_id) ?? 0;
    else v = Math.max(alliedMap.get(t.tile_id) ?? 0, axisMap.get(t.tile_id) ?? 0) * 0.5;
    t.supply = Math.max(0, Math.min(10, Math.round((v - (t.supply_penalty || 0)) * 10) / 10));
  }
  // Unit supply satisfaction: what the tile can give versus what the unit draws.
  for (const u of Object.values(campaign.units)) {
    const t = campaign.tiles[u.tile_id];
    const cap = UNIT_CAPABILITIES[u.unit_type];
    if (!t || !cap) continue;
    if (cap.supply_draw === 0) { u.supply = 1; continue; }     // an underground cell lives off the city, not a depot
    const satisfied = Math.max(0, Math.min(1, t.supply / cap.supply_draw));
    // Change is gradual: a unit does not starve or recover in one week.
    u.supply = Math.round((u.supply * 0.45 + satisfied * 0.55) * 1000) / 1000;
    const isolated = u.supply < 0.25;
    u.status = u.status.filter((s) => s !== 'isolated');
    if (isolated) u.status.push('isolated');
  }
  return { alliedMap, axisMap };
}

/** Dijkstra over move cost, honouring the unit type's movement rules. */
export function reachable(campaign, atlas, unit, budgetOverride) {
  const cap = UNIT_CAPABILITIES[unit.unit_type];
  const budget = budgetOverride ?? unit.move_budget;
  const side = sideOf(unit.faction);
  const dist = new Map([[unit.tile_id, 0]]);
  const prev = new Map();
  const open = [[unit.tile_id, 0]];
  while (open.length) {
    open.sort((a, b) => (a[1] - b[1]) || (a[0] < b[0] ? -1 : 1));
    const [id, d] = open.shift();
    if ((dist.get(id) ?? Infinity) < d) continue;
    for (const nb of campaign.tiles[id].neighbors) {
      const n = campaign.tiles[nb];
      if (!n || !n.passable) continue;
      const rule = atlas.terrain_rules[n.terrain] || { move_cost: 1 };
      let cost = rule.move_cost;
      if (cap.uses_routes) {
        // A regular formation cannot walk into a tile the other side holds
        // unless it is attacking, and it pays extra to enter contested ground.
        const cs = controlSide(n.control);
        if (cs && cs !== side) continue;
        if (n.control === 'contested') cost += 1;
        if (n.supply < 1) cost += 1;                    // off-supply movement is slower
      } else if (cap.uses_access) {
        // Covert movement ignores frontlines but is bounded by access and
        // pays for open ground where it can be seen.
        const conceal = rule.concealment ?? 0.1;
        cost = Math.max(1, Math.round(rule.move_cost * (conceal < 0.3 ? 1.5 : 1.0)));
      }
      const nd = d + cost;
      if (nd <= budget && nd < (dist.get(nb) ?? Infinity)) {
        dist.set(nb, nd); prev.set(nb, id); open.push([nb, nd]);
      }
    }
  }
  dist.delete(unit.tile_id);
  return { dist, prev };
}

export function pathTo(prev, from, to) {
  const path = [to];
  let cur = to;
  while (prev.has(cur)) { cur = prev.get(cur); path.unshift(cur); if (cur === from) break; }
  return path[0] === from ? path : null;
}
