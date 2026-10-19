// Order validation and cost reservation.
//
// Contract tested by the acceptance matrix: a REJECTED order leaves resources
// and state byte-for-byte unchanged. Validation therefore runs entirely on a
// read-only view before anything is written, and reservation is a single
// atomic step at the end.

import { UNIT_CAPABILITIES } from './contracts.js';
import { reachable, pathTo, sideOf, controlSide } from './supply.js';

export const ORDER_KINDS = ['move', 'attack', 'defend', 'entrench', 'reconnoitre', 'sabotage', 'move_covert', 'courier', 'construct', 'repair', 'relieve', 'evacuate', 'transit'];

/** Human-readable reason codes. The UI maps these to localised strings; it never invents its own. */
export const REJECT = {
  UNKNOWN_UNIT: 'reject.unknown_unit',
  WRONG_FACTION: 'reject.wrong_faction',
  ACTION_NOT_ALLOWED: 'reject.action_not_allowed',
  NO_MOVE_BUDGET: 'reject.no_move_budget',
  UNREACHABLE: 'reject.unreachable',
  IMPASSABLE: 'reject.impassable',
  OUT_OF_SUPPLY: 'reject.out_of_supply',
  IN_TRANSIT: 'reject.in_transit',
  ROUTED: 'reject.routed',
  NOT_ADJACENT: 'reject.not_adjacent',
  NO_TARGET: 'reject.no_target',
  INSUFFICIENT_RESOURCES: 'reject.insufficient_resources',
  CITY_NOT_CONTROLLED: 'reject.city_not_controlled',
  FACILITY_SLOTS_FULL: 'reject.facility_slots_full',
  FACILITY_EXISTS: 'reject.facility_exists',
  FACILITY_PREREQ_SUPPLY: 'reject.facility_prereq_supply',
  FACILITY_PREREQ_ACCESS: 'reject.facility_prereq_access',
  DUPLICATE_ORDER: 'reject.duplicate_order',
  MISSION_ACTIVE: 'reject.mission_active',
  UNKNOWN_KIND: 'reject.unknown_kind',
};

const costOf = (o) => ({ materiel: 0, personnel: 0, intelligence: 0, documents: 0, ...(o || {}) });
const canAfford = (res, cost) => Object.entries(cost).every(([k, v]) => (res[k] ?? 0) >= v);

/**
 * Pure validation. Returns { ok, reason, detail, cost, plan } and NEVER mutates.
 * `plan` carries whatever the resolver needs so it does not recompute (and so
 * the cost preview the player confirmed is the cost that gets charged).
 */
export function validateOrder(campaign, atlas, order) {
  const fail = (reason, detail) => ({ ok: false, reason, detail: detail ?? null });

  if (!ORDER_KINDS.includes(order.kind)) return fail(REJECT.UNKNOWN_KIND, order.kind);
  if (campaign.pending_operation && campaign.pending_operation.state !== 'StrategicReady') {
    return fail(REJECT.MISSION_ACTIVE, campaign.pending_operation.operation_id);
  }
  if (campaign.order_queue.some((q) => q.order_id === order.order_id)) return fail(REJECT.DUPLICATE_ORDER, order.order_id);

  // ---- construction / repair are city orders ----
  if (order.kind === 'construct' || order.kind === 'repair') {
    const city = campaign.cities[order.city_id];
    if (!city) return fail(REJECT.NO_TARGET, order.city_id);
    const spec = atlas.facility_catalog.find((f) => f.id === order.facility_id);
    if (!spec) return fail(REJECT.NO_TARGET, order.facility_id);
    const tile = campaign.tiles[city.tile_id];
    const playerSide = sideOf(campaign.player_faction);

    if (order.kind === 'construct') {
      if (city.facilities.some((f) => f.facility_id === order.facility_id)) return fail(REJECT.FACILITY_EXISTS, order.facility_id);
      if (city.construction_queue.some((f) => f.facility_id === order.facility_id)) return fail(REJECT.DUPLICATE_ORDER, order.facility_id);
      if (city.facilities.length + city.construction_queue.length >= city.facilities_max) return fail(REJECT.FACILITY_SLOTS_FULL, `${city.facilities_max}`);
      const pre = spec.prerequisites;
      if (pre.requires_control === 'owner' && controlSide(city.control) !== playerSide) return fail(REJECT.CITY_NOT_CONTROLLED, city.city_id);
      if (tile.supply < (pre.min_supply ?? 0)) return fail(REJECT.FACILITY_PREREQ_SUPPLY, `${tile.supply} < ${pre.min_supply}`);
      if (pre.requires_network_access != null) {
        const nets = (city.network_ids || []).map((id) => campaign.networks[id]).filter(Boolean);
        const access = Math.max(0, ...nets.map((n) => n.access), 0);
        if (access < pre.requires_network_access) return fail(REJECT.FACILITY_PREREQ_ACCESS, `${access} < ${pre.requires_network_access}`);
      }
      const cost = costOf(spec.cost);
      if (!canAfford(campaign.resources, cost)) return fail(REJECT.INSUFFICIENT_RESOURCES, JSON.stringify(cost));
      return { ok: true, cost, plan: { kind: 'construct', city_id: city.city_id, facility_id: spec.id, turns: spec.build_turns } };
    }
    const built = city.facilities.find((f) => f.facility_id === order.facility_id);
    if (!built) return fail(REJECT.NO_TARGET, order.facility_id);
    if (!built.damaged && !built.disabled) return fail(REJECT.NO_TARGET, 'facility.undamaged');
    const cost = costOf(spec.repair_cost);
    if (!canAfford(campaign.resources, cost)) return fail(REJECT.INSUFFICIENT_RESOURCES, JSON.stringify(cost));
    return { ok: true, cost, plan: { kind: 'repair', city_id: city.city_id, facility_id: spec.id, turns: 1 } };
  }

  // ---- everything else is a unit order ----
  const unit = campaign.units[order.unit_id];
  if (!unit) return fail(REJECT.UNKNOWN_UNIT, order.unit_id);
  if (unit.faction !== campaign.player_faction) return fail(REJECT.WRONG_FACTION, unit.faction);
  if (unit.status.includes('in_transit')) return fail(REJECT.IN_TRANSIT, unit.transit?.link_id);
  if (unit.status.includes('routed')) return fail(REJECT.ROUTED, unit.unit_id);
  const cap = UNIT_CAPABILITIES[unit.unit_type];
  const verb = order.kind === 'move' && cap.actions.includes('move_covert') && !cap.actions.includes('move') ? 'move_covert' : order.kind;
  if (!unit.allowed_actions.includes(verb)) return fail(REJECT.ACTION_NOT_ALLOWED, `${unit.unit_type}:${verb}`);
  if (campaign.order_queue.some((q) => q.unit_id === unit.unit_id)) return fail(REJECT.DUPLICATE_ORDER, unit.unit_id);

  if (verb === 'move' || verb === 'move_covert') {
    const dest = campaign.tiles[order.tile_id];
    if (!dest) return fail(REJECT.NO_TARGET, order.tile_id);
    if (!dest.passable) return fail(REJECT.IMPASSABLE, dest.tile_id);
    if (unit.move_budget <= 0) return fail(REJECT.NO_MOVE_BUDGET, '0');
    const { dist, prev } = reachable(campaign, atlas, unit);
    if (!dist.has(dest.tile_id)) return fail(REJECT.UNREACHABLE, `${dest.tile_id} beyond budget ${unit.move_budget}`);
    const path = pathTo(prev, unit.tile_id, dest.tile_id);
    if (!path) return fail(REJECT.UNREACHABLE, dest.tile_id);
    return { ok: true, cost: costOf(), plan: { kind: verb, unit_id: unit.unit_id, path, move_cost: dist.get(dest.tile_id) } };
  }

  if (verb === 'attack') {
    const dest = campaign.tiles[order.tile_id];
    if (!dest) return fail(REJECT.NO_TARGET, order.tile_id);
    if (!campaign.tiles[unit.tile_id].neighbors.includes(dest.tile_id)) return fail(REJECT.NOT_ADJACENT, dest.tile_id);
    const defenders = Object.values(campaign.units).filter((u) => u.tile_id === dest.tile_id && sideOf(u.faction) !== sideOf(unit.faction));
    const hostileGround = controlSide(dest.control) && controlSide(dest.control) !== sideOf(unit.faction);
    if (!defenders.length && !hostileGround) return fail(REJECT.NO_TARGET, dest.tile_id);
    if (unit.supply < 0.25) return fail(REJECT.OUT_OF_SUPPLY, `${unit.supply}`);
    const cost = costOf({ materiel: 6 });
    if (!canAfford(campaign.resources, cost)) return fail(REJECT.INSUFFICIENT_RESOURCES, JSON.stringify(cost));
    return { ok: true, cost, plan: { kind: 'attack', unit_id: unit.unit_id, tile_id: dest.tile_id, defender_ids: defenders.map((d) => d.unit_id) } };
  }

  if (verb === 'sabotage' || verb === 'reconnoitre' || verb === 'courier') {
    const dest = campaign.tiles[order.tile_id ?? unit.tile_id];
    if (!dest) return fail(REJECT.NO_TARGET, order.tile_id);
    const d = Math.abs(dest.q - campaign.tiles[unit.tile_id].q) + Math.abs(dest.r - campaign.tiles[unit.tile_id].r);
    if (d > 2) return fail(REJECT.UNREACHABLE, `${d} tiles from the cell's area of operation`);
    const cost = verb === 'sabotage' ? costOf({ materiel: 4 }) : costOf();
    if (!canAfford(campaign.resources, cost)) return fail(REJECT.INSUFFICIENT_RESOURCES, JSON.stringify(cost));
    return { ok: true, cost, plan: { kind: verb, unit_id: unit.unit_id, tile_id: dest.tile_id } };
  }

  if (verb === 'defend' || verb === 'entrench' || verb === 'hide') {
    return { ok: true, cost: costOf(), plan: { kind: verb, unit_id: unit.unit_id } };
  }

  if (verb === 'relieve' || verb === 'evacuate') {
    const city = campaign.cities[order.city_id];
    if (!city) return fail(REJECT.NO_TARGET, order.city_id);
    const cost = costOf({ materiel: verb === 'relieve' ? 5 : 2, personnel: 1 });
    if (!canAfford(campaign.resources, cost)) return fail(REJECT.INSUFFICIENT_RESOURCES, JSON.stringify(cost));
    return { ok: true, cost, plan: { kind: verb, unit_id: unit.unit_id, city_id: city.city_id } };
  }

  if (verb === 'transit') {
    const link = (atlas.sea_links || []).find((l) => l.label_key === order.link_key || l.id === order.link_id);
    if (!link) return fail(REJECT.NO_TARGET, order.link_id);
    const cost = costOf({ materiel: 3 });
    if (!canAfford(campaign.resources, cost)) return fail(REJECT.INSUFFICIENT_RESOURCES, JSON.stringify(cost));
    return { ok: true, cost, plan: { kind: 'transit', unit_id: unit.unit_id, link, turns: link.transit_turns } };
  }

  return fail(REJECT.UNKNOWN_KIND, verb);
}

/** Atomic reservation. Only called after validateOrder returned ok. */
export function reserve(campaign, cost) {
  for (const [k, v] of Object.entries(cost)) if (v) campaign.resources[k] = (campaign.resources[k] ?? 0) - v;
}
export function refund(campaign, cost) {
  for (const [k, v] of Object.entries(cost)) if (v) campaign.resources[k] = (campaign.resources[k] ?? 0) + v;
}
