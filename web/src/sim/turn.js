// Deterministic turn resolution.
//
// Phase order is fixed and documented in docs/03-TURN-RESOLUTION-SPEC.md:
//   1 validate queued orders
//   2 reserve or spend their costs
//   3 resolve movement and encounters
//   4 resolve strategic opposition
//   5 update supply and recovery
//   6 advance construction and research
//   7 trigger dated events
//   8 present a readable turn report
//   9 commit the checkpoint
//
// Given the same (state, seed) the output is identical. Every iteration over a
// collection is sorted by stable id first, because object key order is not a
// contract.

import { makeRng } from './rng.js';
import { addDays, isOnOrAfter, inWindow } from './dates.js';
import { validateOrder, refund } from './orders.js';
import { applySupply, sideOf, controlSide } from './supply.js';
import { UNIT_CAPABILITIES } from './contracts.js';

const byId = (o) => Object.keys(o).sort().map((k) => o[k]);

/** Combat strength: readiness x supply x terrain x fortification. No hidden bonuses. */
export function combatPower(campaign, atlas, unit, asDefender) {
  const tile = campaign.tiles[unit.tile_id];
  const rule = atlas.terrain_rules[tile.terrain] || {};
  const cap = UNIT_CAPABILITIES[unit.unit_type];
  let base = unit.strength * (0.35 + 0.65 * unit.supply);
  if (cap.unit_type === 'armoured_division') base *= 1.0;
  if (asDefender) {
    base *= 1 + (rule.cover ?? 0);
    if (unit.status.includes('entrenched')) base *= 1.3;
    const city = tile.city_id ? campaign.cities[tile.city_id] : null;
    const fort = city?.facilities.find((f) => f.facility_id === 'fac_fortification' && !f.disabled);
    if (fort) {
      const spec = atlas.facility_catalog.find((f) => f.id === 'fac_fortification');
      base *= fort.damaged ? 1 + (spec.benefit.defence_multiplier - 1) * 0.5 : spec.benefit.defence_multiplier;
    }
  }
  return Math.max(0.01, base);
}

export function resolveTurn(campaign, atlas, content) {
  const rng = makeRng(campaign.rng_seed ^ (campaign.turn * 0x9e3779b1));
  const report = {
    turn: campaign.turn, date: campaign.date,
    rejected_orders: [], movements: [], engagements: [], opposition: [],
    supply_changes: [], construction: [], events: [], civilian: [], network: [],
  };

  // -- phase 1: re-validate everything still queued -------------------------
  const accepted = [];
  for (const q of campaign.order_queue) {
    // Re-validate against the state as it is NOW. A queued order whose
    // preconditions expired is refunded, never silently applied.
    const probe = { ...q.order };
    const tmpQueue = campaign.order_queue;
    campaign.order_queue = campaign.order_queue.filter((x) => x.order_id !== q.order_id);
    const v = validateOrder(campaign, atlas, probe);
    campaign.order_queue = tmpQueue;
    if (!v.ok) {
      refund(campaign, q.cost);                       // phase 2 counterpart: release the reservation
      report.rejected_orders.push({ order_id: q.order_id, reason: v.reason, detail: v.detail, refunded: q.cost });
    } else {
      accepted.push({ ...q, plan: v.plan });
    }
  }
  campaign.order_queue = [];

  // -- phase 2: costs are already reserved at submission; spend them now ----
  // (reserve() ran in CampaignService.submitOrder; nothing further to deduct.
  //  The refunds above are the only resource movement in this phase.)

  // -- phase 3: movement, then encounters ----------------------------------
  const moves = accepted.filter((a) => a.plan.kind === 'move' || a.plan.kind === 'move_covert');
  moves.sort((a, b) => (a.plan.unit_id < b.plan.unit_id ? -1 : 1));
  for (const m of moves) {
    const unit = campaign.units[m.plan.unit_id];
    if (!unit) continue;
    const from = unit.tile_id;
    unit.tile_id = m.plan.path[m.plan.path.length - 1];
    unit.move_budget = Math.max(0, unit.move_budget - m.plan.move_cost);
    unit.status = unit.status.filter((s) => s !== 'entrenched');
    const dest = campaign.tiles[unit.tile_id];
    const cap = UNIT_CAPABILITIES[unit.unit_type];
    if (cap.can_occupy && !controlSide(dest.control)) {
      dest.control = sideOf(unit.faction);             // claim unheld ground
    }
    report.movements.push({ unit_id: unit.unit_id, from, to: unit.tile_id, cost: m.plan.move_cost });
  }
  for (const t of byId(campaign.tiles)) {
    const occupants = byId(campaign.units).filter((u) => u.tile_id === t.tile_id);
    const sides = new Set(occupants.map((u) => sideOf(u.faction)));
    if (sides.size > 1) {
      if (t.control !== 'contested') { t.control = 'contested'; t.contested_since_turn = campaign.turn; }
      report.engagements.push({ tile_id: t.tile_id, kind: 'contact', unit_ids: occupants.map((u) => u.unit_id) });
    }
  }

  const transits = accepted.filter((a) => a.plan.kind === 'transit');
  for (const t of transits) {
    const unit = campaign.units[t.plan.unit_id];
    if (!unit) continue;
    unit.status = [...unit.status.filter((s) => s !== 'in_transit'), 'in_transit'];
    unit.transit = { link_id: t.plan.link.label_key, turns_remaining: t.plan.turns, to_tile: `${t.plan.link.to.theater}:${t.plan.link.to.q},${t.plan.link.to.r}` };
  }
  for (const u of byId(campaign.units)) {
    if (u.transit) {
      u.transit.turns_remaining -= 1;
      if (u.transit.turns_remaining <= 0) {
        if (campaign.tiles[u.transit.to_tile]) u.tile_id = u.transit.to_tile;
        u.status = u.status.filter((s) => s !== 'in_transit');
        report.movements.push({ unit_id: u.unit_id, from: 'sea_link', to: u.tile_id, cost: 0, by: u.transit.link_id });
        u.transit = null;
      }
    }
  }

  // attacks
  for (const a of accepted.filter((x) => x.plan.kind === 'attack').sort((x, y) => (x.plan.unit_id < y.plan.unit_id ? -1 : 1))) {
    const attacker = campaign.units[a.plan.unit_id];
    if (!attacker) continue;
    const tile = campaign.tiles[a.plan.tile_id];
    const defenders = a.plan.defender_ids.map((id) => campaign.units[id]).filter(Boolean);
    const ap = combatPower(campaign, atlas, attacker, false);
    const dp = defenders.reduce((s, d) => s + combatPower(campaign, atlas, d, true), 0);
    const roll = rng.fork(`attack:${a.plan.unit_id}:${campaign.turn}`).float(0.85, 1.15);
    const ratio = (ap * roll) / Math.max(0.01, dp || 0.2);
    let outcome;
    if (ratio >= 1.6) outcome = 'attacker_takes_tile';
    else if (ratio >= 1.05) outcome = 'defender_pushed';
    else if (ratio >= 0.7) outcome = 'stalemate';
    else outcome = 'attack_repulsed';

    const lossA = outcome === 'attack_repulsed' ? 0.18 : outcome === 'stalemate' ? 0.11 : 0.07;
    const lossD = outcome === 'attacker_takes_tile' ? 0.26 : outcome === 'defender_pushed' ? 0.16 : outcome === 'stalemate' ? 0.10 : 0.04;
    attacker.strength = Math.max(0, Math.round((attacker.strength - lossA) * 1000) / 1000);
    for (const d of defenders) {
      d.strength = Math.max(0, Math.round((d.strength - lossD) * 1000) / 1000);
      if (d.strength <= 0.12) { d.status = [...d.status.filter((s) => s !== 'routed'), 'routed']; }
    }
    if (outcome === 'attacker_takes_tile' && defenders.every((d) => d.strength <= 0.12)) {
      for (const d of defenders) delete campaign.units[d.unit_id];
      attacker.tile_id = tile.tile_id;
      tile.control = sideOf(attacker.faction);
    } else if (outcome === 'defender_pushed') {
      tile.control = 'contested'; tile.contested_since_turn = campaign.turn;
    }
    if (attacker.strength <= 0.12) attacker.status = [...attacker.status.filter((s) => s !== 'routed'), 'routed'];
    report.engagements.push({ tile_id: tile.tile_id, kind: outcome, attacker: attacker.unit_id, ratio: Math.round(ratio * 100) / 100, defenders: defenders.map((d) => d.unit_id) });
  }

  // covert actions
  for (const a of accepted.filter((x) => ['sabotage', 'reconnoitre', 'courier'].includes(x.plan.kind))) {
    const unit = campaign.units[a.plan.unit_id];
    if (!unit) continue;
    const net = byId(campaign.networks).find((n) => n.cells.some((c) => c.tile_id === unit.tile_id)) || byId(campaign.networks)[0];
    const sub = rng.fork(`covert:${a.plan.kind}:${unit.unit_id}:${campaign.turn}`);
    const base = a.plan.kind === 'sabotage' ? 0.55 : 0.75;
    const ok = sub.chance(Math.min(0.95, base + 0.08 * (net?.access ?? 0) - 0.4 * (net?.exposure ?? 0)));
    if (a.plan.kind === 'sabotage') {
      if (ok) { const t = campaign.tiles[a.plan.tile_id]; t.supply_penalty = Math.min(4, (t.supply_penalty || 0) + 1); }
      if (net) net.exposure = Math.min(1, Math.round((net.exposure + (ok ? 0.05 : 0.14)) * 1000) / 1000);
    } else if (a.plan.kind === 'reconnoitre') {
      if (ok) { campaign.resources.intelligence += 1; campaign.tiles[a.plan.tile_id].discovered = true; }
      if (net) net.exposure = Math.min(1, Math.round((net.exposure + (ok ? 0.01 : 0.07)) * 1000) / 1000);
    } else {
      if (ok && net) net.access = Math.min(5, net.access + (net.access < 3 ? 1 : 0));
      if (net && !ok) net.exposure = Math.min(1, Math.round((net.exposure + 0.1) * 1000) / 1000);
    }
    report.network.push({ unit_id: unit.unit_id, action: a.plan.kind, succeeded: ok, exposure: net?.exposure ?? null });
  }

  for (const a of accepted.filter((x) => ['defend', 'entrench', 'hide'].includes(x.plan.kind))) {
    const unit = campaign.units[a.plan.unit_id];
    if (!unit) continue;
    if (a.plan.kind === 'entrench' && !unit.status.includes('entrenched')) unit.status.push('entrenched');
    if (a.plan.kind === 'hide' && !unit.status.includes('hidden')) unit.status.push('hidden');
  }
  for (const a of accepted.filter((x) => ['relieve', 'evacuate'].includes(x.plan.kind))) {
    const city = campaign.cities[a.plan.city_id];
    if (!city) continue;
    const groups = (city.civilian_group_ids || []).map((id) => campaign.civilian_groups[id]).filter(Boolean);
    for (const g of groups) {
      if (a.plan.kind === 'relieve') {
        g.needs.food = Math.min(1, Math.round((g.needs.food + 0.3) * 1000) / 1000);
        g.needs.medicine = Math.min(1, Math.round((g.needs.medicine + 0.2) * 1000) / 1000);
      } else if (g.displacement === 'restricted' || g.displacement === 'displaced') {
        const route = city.facilities.find((f) => f.facility_id === 'fac_escape_route' && !f.disabled);
        if (route) { g.displacement = 'evacuated'; report.civilian.push({ group_id: g.group_id, change: 'evacuated' }); }
      }
    }
  }

  // -- phase 4: strategic opposition ---------------------------------------
  // The opponent is bound by the same movement, supply and adjacency rules.
  const oppSide = sideOf(campaign.player_faction) === 'allied' ? 'axis' : 'allied';
  for (const u of byId(campaign.units).filter((x) => sideOf(x.faction) === oppSide && !x.status.includes('in_transit') && !x.status.includes('routed'))) {
    const cap = UNIT_CAPABILITIES[u.unit_type];
    if (!cap.actions.includes('attack') || u.supply < 0.25 || u.move_budget <= 0) continue;
    const tile = campaign.tiles[u.tile_id];
    const targets = tile.neighbors
      .map((id) => campaign.tiles[id])
      .filter((t) => t && t.passable && byId(campaign.units).some((x) => x.tile_id === t.tile_id && sideOf(x.faction) !== oppSide))
      .sort((a, b) => (a.tile_id < b.tile_id ? -1 : 1));
    if (!targets.length) continue;
    const target = targets[0];
    const defenders = byId(campaign.units).filter((x) => x.tile_id === target.tile_id && sideOf(x.faction) !== oppSide);
    const ap = combatPower(campaign, atlas, u, false);
    const dp = defenders.reduce((s, d) => s + combatPower(campaign, atlas, d, true), 0);
    if (ap < dp * 0.8) { report.opposition.push({ unit_id: u.unit_id, decision: 'held', reason: 'unfavourable' }); continue; }
    const roll = rng.fork(`opp:${u.unit_id}:${campaign.turn}`).float(0.85, 1.15);
    const ratio = (ap * roll) / Math.max(0.01, dp);
    for (const d of defenders) {
      d.strength = Math.max(0, Math.round((d.strength - (ratio > 1.2 ? 0.2 : 0.11)) * 1000) / 1000);
      if (d.strength <= 0.12) d.status = [...d.status.filter((s) => s !== 'routed'), 'routed'];
    }
    u.strength = Math.max(0, Math.round((u.strength - (ratio > 1.2 ? 0.06 : 0.13)) * 1000) / 1000);
    u.move_budget = 0;
    if (target.control !== 'contested') { target.control = 'contested'; target.contested_since_turn = campaign.turn; }
    report.opposition.push({ unit_id: u.unit_id, decision: 'attacked', tile_id: target.tile_id, ratio: Math.round(ratio * 100) / 100 });
  }

  // -- phase 5: supply and recovery ----------------------------------------
  const before = Object.fromEntries(byId(campaign.tiles).map((t) => [t.tile_id, t.supply]));
  applySupply(campaign, atlas, buildSources(campaign, atlas));
  for (const t of byId(campaign.tiles)) {
    if (Math.abs((before[t.tile_id] ?? 0) - t.supply) >= 0.5) report.supply_changes.push({ tile_id: t.tile_id, from: before[t.tile_id], to: t.supply });
  }
  for (const u of byId(campaign.units)) {
    const cap = UNIT_CAPABILITIES[u.unit_type];
    u.move_budget = u.status.includes('in_transit') ? 0 : Math.max(0, Math.round(cap.move_budget * (0.4 + 0.6 * u.supply)));
    if (u.supply > 0.6 && u.strength < 1) {
      const city = campaign.tiles[u.tile_id].city_id ? campaign.cities[campaign.tiles[u.tile_id].city_id] : null;
      const med = city?.facilities.find((f) => f.facility_id === 'fac_medical_depot' && !f.disabled);
      const bonus = med ? (med.damaged ? 0.09 : 0.18) : 0;
      u.strength = Math.min(1, Math.round((u.strength + 0.05 + bonus) * 1000) / 1000);
      if (u.strength > 0.3) u.status = u.status.filter((s) => s !== 'routed');
    }
  }
  // civilian needs decay, offset by facilities actually standing
  for (const g of byId(campaign.civilian_groups)) {
    const city = campaign.cities[g.city_id];
    const kitchen = city?.facilities.find((f) => f.facility_id === 'fac_relief_kitchen' && !f.disabled);
    const depot = city?.facilities.find((f) => f.facility_id === 'fac_medical_depot' && !f.disabled);
    const restriction = (city?.restriction_level ?? 0) / 5;
    const decay = 0.06 + 0.10 * restriction;
    g.needs.food = clamp01(g.needs.food - decay + (kitchen ? (kitchen.damaged ? 0.05 : 0.12) : 0));
    g.needs.water = clamp01(g.needs.water - decay * 0.7 + (city?.supply_access > 2 ? 0.08 : 0));
    g.needs.medicine = clamp01(g.needs.medicine - decay * 0.6 + (depot ? (depot.damaged ? 0.04 : 0.11) : 0));
    g.needs.shelter = clamp01(g.needs.shelter - (city?.control === 'contested' ? 0.1 : 0.02));
    if (g.needs.food < 0.25 && g.displacement === 'in_place') { g.displacement = 'restricted'; report.civilian.push({ group_id: g.group_id, change: 'restricted', cause: 'food' }); }
  }
  for (const n of byId(campaign.networks)) {
    const city = campaign.cities[n.city_id];
    const radio = city?.facilities.find((f) => f.facility_id === 'fac_underground_radio' && !f.disabled);
    if (radio && !radio.damaged) {
      const spec = atlas.facility_catalog.find((f) => f.id === 'fac_underground_radio');
      campaign.resources.intelligence += spec.benefit.intelligence_per_turn;
      n.exposure = Math.min(1, Math.round((n.exposure + spec.risk.exposure_per_turn) * 1000) / 1000);
    }
    n.exposure = Math.max(0, Math.round((n.exposure - 0.03) * 1000) / 1000);   // quiet weeks cool a network down
    if (n.exposure >= 0.8) {
      const sub = rng.fork(`search:${n.network_id}:${campaign.turn}`);
      const cell = n.cells.filter((c) => !c.compromised).sort((a, b) => (a.cell_id < b.cell_id ? -1 : 1))[0];
      if (cell && sub.chance(0.5)) {
        cell.compromised = true;
        n.access = Math.max(0, n.access - 1);
        n.exposure = Math.max(0, n.exposure - 0.25);
        report.network.push({ network_id: n.network_id, event: 'cell_compromised', cell_id: cell.cell_id });
      }
    }
  }

  // -- phase 6: construction and research ---------------------------------
  for (const a of accepted.filter((x) => x.plan.kind === 'construct')) {
    const city = campaign.cities[a.plan.city_id];
    city.construction_queue.push({ facility_id: a.plan.facility_id, turns_remaining: a.plan.turns, reserved_cost: a.cost });
    report.construction.push({ city_id: city.city_id, facility_id: a.plan.facility_id, started: true, turns: a.plan.turns });
  }
  for (const a of accepted.filter((x) => x.plan.kind === 'repair')) {
    const city = campaign.cities[a.plan.city_id];
    const f = city.facilities.find((x) => x.facility_id === a.plan.facility_id);
    if (f) { f.damaged = false; f.disabled = false; report.construction.push({ city_id: city.city_id, facility_id: f.facility_id, repaired: true }); }
  }
  for (const city of byId(campaign.cities)) {
    const still = [];
    for (const q of city.construction_queue) {
      q.turns_remaining -= 1;
      if (q.turns_remaining <= 0) {
        city.facilities.push({ facility_id: q.facility_id, built_turn: campaign.turn, damaged: false, disabled: false });
        report.construction.push({ city_id: city.city_id, facility_id: q.facility_id, completed: true });
      } else still.push(q);
    }
    city.construction_queue = still;
    recomputeCityServices(city, atlas);
    const tile = campaign.tiles[city.tile_id];
    city.supply_access = tile.supply;
    if (controlSide(city.control) !== controlSide(tile.control) && controlSide(tile.control)) {
      city.control = tile.control;
      applyControlChangeToFacilities(city, atlas, report);
    }
  }

  // -- phase 7: dated events ----------------------------------------------
  campaign.turn += 1;
  campaign.date = addDays(campaign.date, content.turn_length_days ?? 7);
  for (const ev of (content.timeline_events || []).slice().sort((a, b) => (a.date < b.date ? -1 : 1))) {
    if (campaign.fired_events.includes(ev.id)) continue;
    if (!isOnOrAfter(campaign.date, ev.date)) continue;
    campaign.fired_events.push(ev.id);
    applyEvent(campaign, atlas, ev, report);
    report.events.push({ id: ev.id, date: ev.date, label_key: ev.label_key, sensitivity: ev.sensitivity ?? null });
  }
  // chapter availability follows date + prerequisites, never a hidden unlock
  for (const ch of content.chapters || []) {
    if (campaign.unlocked_chapters.includes(ch.id) || campaign.completed_chapters.includes(ch.id)) continue;
    const dateOk = inWindow(campaign.date, ch.date_window.from, ch.date_window.to);
    const evOk = ch.prerequisites.events.every((e) => campaign.fired_events.includes(e));
    const chOk = ch.prerequisites.chapters.every((c) => campaign.completed_chapters.includes(c));
    const intelOk = (campaign.resources.intelligence ?? 0) >= (ch.prerequisites.min_intelligence ?? 0);
    if (dateOk && evOk && chOk && intelOk) {
      campaign.unlocked_chapters.push(ch.id);
      report.events.push({ id: ch.id, label_key: ch.label_key, kind: 'chapter_available' });
    }
  }

  // -- phase 8 + 9: report, then commit -----------------------------------
  campaign.revision += 1;
  campaign.last_turn_report = report;
  return report;
}

function clamp01(v) { return Math.max(0, Math.min(1, Math.round(v * 1000) / 1000)); }

export function recomputeCityServices(city, atlas) {
  const cap = { civilian_health: 0, civilian_food: 0, evacuation: 0 };
  for (const f of city.facilities) {
    if (f.disabled) continue;
    const spec = atlas.facility_catalog.find((x) => x.id === f.facility_id);
    if (!spec) continue;
    const scale = f.damaged ? 0.5 : 1;
    cap.civilian_health += (spec.benefit.civilian_health_capacity ?? 0) * scale;
    cap.civilian_food += (spec.benefit.civilian_food_capacity ?? 0) * scale;
    cap.evacuation += (spec.benefit.civilian_evacuation_per_turn ?? 0) * scale;
  }
  city.service_capacity = { civilian_health: Math.round(cap.civilian_health * 10) / 10, civilian_food: Math.round(cap.civilian_food * 10) / 10, evacuation: Math.round(cap.evacuation * 10) / 10 };
  return city.service_capacity;
}

export function applyControlChangeToFacilities(city, atlas, report) {
  for (const f of city.facilities) {
    const spec = atlas.facility_catalog.find((x) => x.id === f.facility_id);
    if (!spec) continue;
    switch (spec.on_control_change) {
      case 'captured_disabled': f.disabled = true; break;
      case 'captured_intact': break;
      case 'survives_hidden': break;
      default: f.disabled = true;
    }
    report?.construction.push({ city_id: city.city_id, facility_id: f.facility_id, control_change: spec.on_control_change });
  }
  recomputeCityServices(city, atlas);
}

export function buildSources(campaign, atlas) {
  const out = { allied: [], axis: [] };
  for (const th of atlas.theaters) {
    for (const s of th.supply_sources || []) {
      if (s.activates_on && !isOnOrAfter(campaign.date, s.activates_on)) continue;
      const tile_id = `${th.id}:${s.q},${s.r}`;
      const extra = (campaign.history_flags.supply_overrides || {})[tile_id];
      const throughput = extra ?? s.throughput;
      if (throughput <= 0) continue;
      out[sideOf(s.faction)].push({ tile_id, throughput });
    }
  }
  return out;
}

export function applyEvent(campaign, atlas, ev, report) {
  const e = ev.effects || {};
  for (const th of e.opens_theaters || []) campaign.history_flags[`theater_open:${th}`] = true;
  for (const [city_id, state] of Object.entries(e.city_state || {})) {
    const c = campaign.cities[city_id];
    if (c) c.place_date_context = state;
  }
  for (const [city_id, lvl] of Object.entries(e.civilian_restriction_level || {})) {
    const c = campaign.cities[city_id];
    if (!c) continue;
    c.restriction_level = lvl;
    for (const gid of c.civilian_group_ids) {
      const g = campaign.civilian_groups[gid];
      if (!g) continue;
      if (lvl >= 3 && g.displacement === 'in_place') g.displacement = 'restricted';
      if (!g.access_restrictions.includes(`restriction_level_${lvl}`)) g.access_restrictions.push(`restriction_level_${lvl}`);
    }
  }
  for (const [district_id, state] of Object.entries(e.district_state || {})) campaign.history_flags[`district_state:${district_id}`] = state;
  for (const s of e.supply_source_activate || []) {
    campaign.history_flags.supply_overrides = campaign.history_flags.supply_overrides || {};
    campaign.history_flags.supply_overrides[`${s.theater}:${s.q},${s.r}`] = s.throughput;
  }
  for (const eq of e.unlock_equipment || []) if (!campaign.unlocked_equipment.includes(eq)) campaign.unlocked_equipment.push(eq);
  if (e.theater_control) {
    for (const [th, side] of Object.entries(e.theater_control)) {
      for (const t of byId(campaign.tiles).filter((x) => x.theater === th && x.passable)) t.control = side;
      report?.events.push({ id: ev.id, kind: 'theater_control', theater: th, to: side });
    }
  }
  if (e.campaign_phase) campaign.history_flags.campaign_phase = e.campaign_phase;
}
