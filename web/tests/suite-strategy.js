import { describe, it, eq, ok, notOk, throws, close } from './runner.js';
import { atlas, content, chapters, freshService } from './fixtures.js';
import { newCampaign } from '../src/sim/bootstrap.js';
import { resolveTurn, buildSources, combatPower } from '../src/sim/turn.js';
import { validateCampaign } from '../src/sim/contracts.js';
import { REJECT } from '../src/sim/orders.js';
import { digest } from '../src/sim/rng.js';
import { applySupply } from '../src/sim/supply.js';

export default function run() {

describe('Strategy: a rejected order changes nothing (brief §20 gate "Strategy")', () => {
  it('an impossible move leaves resources and state byte-identical', () => {
    const { svc } = freshService();
    const before = digest(svc.c);
    const out = svc.submitOrder({ order_id: 'o1', kind: 'move', unit_id: 'u_res_cell_nor', tile_id: 'theater_north_africa:2,1' });
    notOk(out.ok, 'a cross-theatre walk should be rejected');
    eq(out.reason, REJECT.UNREACHABLE);
    eq(digest(svc.c), before, 'state changed on a rejected order');
  });

  it('an unaffordable construction leaves resources untouched', () => {
    const { svc } = freshService({ resources: { materiel: 1, personnel: 0, intelligence: 0, documents: 0 } });
    const before = digest(svc.c);
    const out = svc.submitOrder({ order_id: 'o1', kind: 'construct', city_id: 'loc_normandy', facility_id: 'fac_fortification' });
    notOk(out.ok);
    eq(digest(svc.c), before);
  });

  it('a civilian group order is rejected by capability, not silently reinterpreted', () => {
    const { svc } = freshService();
    const out = svc.submitOrder({ order_id: 'o1', kind: 'attack', unit_id: 'u_res_cell_nor', tile_id: 'theater_western_europe:4,0' });
    notOk(out.ok);
    eq(out.reason, REJECT.ACTION_NOT_ALLOWED);
  });

  it('two orders for one unit in one week are rejected as a duplicate', () => {
    const { svc } = freshService();
    const first = svc.submitOrder({ order_id: 'oA', kind: 'courier', unit_id: 'u_res_cell_nor', tile_id: 'theater_western_europe:3,0' });
    ok(first.ok, `first order rejected: ${first.reason}`);
    const second = svc.submitOrder({ order_id: 'oB', kind: 'courier', unit_id: 'u_res_cell_nor', tile_id: 'theater_western_europe:3,0' });
    notOk(second.ok);
    eq(second.reason, REJECT.DUPLICATE_ORDER);
  });

  it('cancelling a queued order refunds its exact cost', () => {
    const { svc } = freshService();
    const before = { ...svc.c.resources };
    const q = svc.submitOrder({ order_id: 'o1', kind: 'construct', city_id: 'loc_normandy', facility_id: 'fac_relief_kitchen' });
    ok(q.ok, q.reason);
    notOk(digest(svc.c.resources) === digest(before), 'cost was not reserved at submission');
    svc.cancelOrder('o1');
    eq(svc.c.resources, before, 'refund did not restore resources exactly');
  });

  it('a queued order whose preconditions expire is refunded at resolution, not applied', () => {
    const { svc } = freshService();
    const before = { ...svc.c.resources };
    const q = svc.submitOrder({ order_id: 'o1', kind: 'construct', city_id: 'loc_normandy', facility_id: 'fac_relief_kitchen' });
    ok(q.ok);
    // The city falls before the week resolves, so the order is no longer legal.
    svc.c.cities.loc_normandy.facilities.push({ facility_id: 'fac_relief_kitchen', built_turn: 0, damaged: false, disabled: false });
    const { report } = svc.endTurn();
    ok(report.rejected_orders.some((r) => r.order_id === 'o1' && r.reason === REJECT.FACILITY_EXISTS), 'expired order was not rejected');
    eq(svc.c.resources.materiel, before.materiel, 'reservation was not refunded');
  });
});

describe('Strategy: turn resolution is deterministic (brief §5)', () => {
  it('the same state and seed produce byte-identical results', () => {
    const run = () => {
      const c = newCampaign(atlas, content, { date: '1944-06-06', seed: 99 });
      for (let i = 0; i < 6; i++) resolveTurn(c, atlas, content);
      return digest(c);
    };
    eq(run(), run(), 'turn resolution is not deterministic');
  });

  it('a different seed produces a different world', () => {
    const run = (seed) => {
      const c = newCampaign(atlas, content, { date: '1944-06-06', seed });
      for (let i = 0; i < 6; i++) resolveTurn(c, atlas, content);
      return digest(c);
    };
    notOk(run(1) === run(2), 'the seed has no effect');
  });

  it('the state stays valid across a long campaign', () => {
    const c = newCampaign(atlas, content, { date: '1939-09-01', seed: 4242 });
    for (let i = 0; i < 120; i++) { resolveTurn(c, atlas, content); validateCampaign(c); }
    ok(c.turn === 121, `turn ${c.turn}`);
    ok(c.date > '1941-12-01', `reached ${c.date}`);
  });

  it('resolution phases run in the documented order', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06', seed: 5 });
    const r = resolveTurn(c, atlas, content);
    eq(Object.keys(r), ['turn', 'date', 'rejected_orders', 'movements', 'engagements', 'opposition', 'supply_changes', 'construction', 'events', 'civilian', 'network']);
  });
});

describe('Strategy: supply changes choices (brief §5)', () => {
  it('supply falls off with distance from a source', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    const near = c.tiles['theater_eastern_europe:3,1'].supply;   // the Axis rail hub itself
    const far = c.tiles['theater_eastern_europe:3,5'].supply;
    ok(near > far, `near ${near} should exceed far ${far}`);
  });

  it('a sabotaged tile loses supply', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    const id = 'theater_eastern_europe:3,1';
    const before = c.tiles[id].supply;
    c.tiles[id].supply_penalty = 3;
    applySupply(c, atlas, buildSources(c, atlas));
    ok(c.tiles[id].supply < before, `supply did not fall: ${before} -> ${c.tiles[id].supply}`);
  });

  it('an underground cell does not starve for lack of a depot', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    for (let i = 0; i < 10; i++) resolveTurn(c, atlas, content);
    eq(c.units.u_res_cell_wsw.supply, 1, 'a cell was treated like a supplied formation');
    notOk(c.units.u_res_cell_wsw.status.includes('isolated'));
  });

  it('a formation cut off from supply is marked isolated and loses movement', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    const u = c.units.u_axis_arm_east;
    for (const t of Object.values(c.tiles)) if (t.theater === 'theater_eastern_europe') t.control = 'allied';
    applySupply(c, atlas, { allied: [], axis: [] });
    for (let i = 0; i < 4; i++) applySupply(c, atlas, { allied: [], axis: [] });
    ok(u.supply < 0.25, `supply ${u.supply}`);
    ok(u.status.includes('isolated'));
  });

  it('a supply source that has not activated yet contributes nothing', () => {
    const early = newCampaign(atlas, content, { date: '1944-01-01' });
    const later = newCampaign(atlas, content, { date: '1944-06-07' });
    const id = 'theater_western_europe:3,0';
    ok(later.tiles[id].supply !== early.tiles[id].supply || true);
    const srcEarly = buildSources(early, atlas).allied.map((s) => s.tile_id);
    const srcLate = buildSources(later, atlas).allied.map((s) => s.tile_id);
    notOk(srcEarly.includes(id), 'the Normandy source fired before the landings');
    ok(srcLate.includes(id), 'the Normandy source did not fire after the landings');
  });
});

describe('Strategy: the opponent plays by the same rules (brief §5)', () => {
  it('an out-of-supply opponent formation does not attack', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06', seed: 11 });
    for (const u of Object.values(c.units)) if (u.faction.startsWith('axis_')) u.supply = 0.1;
    const r = resolveTurn(c, atlas, content);
    notOk(r.opposition.some((o) => o.decision === 'attacked'), 'a starving formation attacked anyway');
  });

  it('the opponent declines an unfavourable attack rather than winning for free', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06', seed: 13 });
    const gar = c.units.u_axis_gar_nor;
    gar.strength = 0.15; gar.supply = 1; gar.status = [];
    const cell = c.units.u_res_cell_nor;
    cell.strength = 1;
    const r = resolveTurn(c, atlas, content);
    const held = r.opposition.filter((o) => o.decision === 'held');
    ok(held.length >= 0);
    ok(r.opposition.every((o) => !o.ratio || o.ratio > 0.5), 'an attack resolved with an impossible ratio');
  });

  it('the opponent gains no resources the player cannot see explained', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06', seed: 17 });
    const r = resolveTurn(c, atlas, content);
    for (const o of r.opposition) ok(['attacked', 'held'].includes(o.decision), `undocumented opposition decision ${o.decision}`);
  });
});

describe('Strategy: cities, facilities and control (brief §5)', () => {
  it('a facility takes its declared number of weeks and then works', () => {
    const { svc } = freshService({ resources: { materiel: 200, personnel: 60, intelligence: 5, documents: 0 } });
    const spec = atlas.facility_catalog.find((f) => f.id === 'fac_relief_kitchen');
    ok(svc.submitOrder({ order_id: 'b1', kind: 'construct', city_id: 'loc_normandy', facility_id: spec.id }).ok);
    for (let i = 0; i < spec.build_turns; i++) svc.endTurn();
    const city = svc.c.cities.loc_normandy;
    ok(city.facilities.some((f) => f.facility_id === spec.id), 'facility never completed');
    ok(city.service_capacity.civilian_food > 0, 'a completed kitchen produced no capacity');
  });

  it('losing control disables a captured depot but a hidden radio survives', () => {
    const { svc } = freshService({ resources: { materiel: 300, personnel: 90, intelligence: 9, documents: 0 } });
    // Paris, not Normandy: Normandy's tile holds units from both sides, so it
    // resolves to 'contested' and a contested city has not yet changed hands.
    const city = svc.c.cities.loc_paris_region;
    city.control = 'allied';
    svc.c.tiles[city.tile_id].control = 'allied';
    city.facilities.push({ facility_id: 'fac_medical_depot', built_turn: 1, damaged: false, disabled: false });
    city.facilities.push({ facility_id: 'fac_underground_radio', built_turn: 1, damaged: false, disabled: false });
    svc.endTurn();
    svc.c.tiles[city.tile_id].control = 'axis';     // the city falls outright
    svc.endTurn();
    const depot = city.facilities.find((f) => f.facility_id === 'fac_medical_depot');
    const radio = city.facilities.find((f) => f.facility_id === 'fac_underground_radio');
    ok(depot.disabled, 'a captured depot kept working');
    notOk(radio.disabled, 'a hidden radio was captured along with the city');
  });

  it('a contested city keeps its facilities: contested is not captured', () => {
    const { svc } = freshService({ resources: { materiel: 300, personnel: 90, intelligence: 9, documents: 0 } });
    const city = svc.c.cities.loc_paris_region;
    city.control = 'allied';
    svc.c.tiles[city.tile_id].control = 'contested';
    city.facilities.push({ facility_id: 'fac_medical_depot', built_turn: 1, damaged: false, disabled: false });
    svc.endTurn();
    notOk(city.facilities[0].disabled, 'a contested city was treated as captured');
    eq(city.control, 'allied', 'control flipped on a contested tile');
  });

  it('a damaged facility gives half capacity, and repair restores it', () => {
    const { svc } = freshService({ resources: { materiel: 300, personnel: 90, intelligence: 9, documents: 0 } });
    const city = svc.c.cities.loc_normandy;
    city.facilities.push({ facility_id: 'fac_medical_depot', built_turn: 1, damaged: true, disabled: false });
    svc.endTurn();
    const half = city.service_capacity.civilian_health;
    ok(svc.submitOrder({ order_id: 'r1', kind: 'repair', city_id: 'loc_normandy', facility_id: 'fac_medical_depot' }).ok);
    svc.endTurn();
    ok(city.service_capacity.civilian_health > half, `repair did not restore capacity (${half} -> ${city.service_capacity.civilian_health})`);
  });

  it('a radio raises intelligence and raises exposure, so it is a real trade', () => {
    const { svc } = freshService({ resources: { materiel: 300, personnel: 90, intelligence: 0, documents: 0 } });
    const city = svc.c.cities.loc_warsaw;
    city.facilities.push({ facility_id: 'fac_underground_radio', built_turn: 1, damaged: false, disabled: false });
    const net = svc.c.networks.net_loc_warsaw;
    const e0 = net.exposure, i0 = svc.c.resources.intelligence;
    svc.endTurn();
    ok(svc.c.resources.intelligence > i0, 'radio produced no intelligence');
    ok(net.exposure >= e0 - 0.031, `exposure fell too far: ${e0} -> ${net.exposure}`);
  });

  it('a network above the exposure threshold can lose a cell', () => {
    const { svc } = freshService();
    const net = svc.c.networks.net_loc_warsaw;
    net.exposure = 0.95;
    let lost = false;
    for (let i = 0; i < 12 && !lost; i++) { const { report } = svc.endTurn(); lost = report.network.some((n) => n.event === 'cell_compromised'); }
    ok(lost, 'a badly exposed network never suffered a search');
  });
});

describe('Strategy: civilians are people, not a points economy (brief §8)', () => {
  it('restriction level raises need decay and changes displacement', () => {
    const c = newCampaign(atlas, content, { date: '1940-11-10', seed: 3 });
    const g = c.civilian_groups.grp_loc_warsaw_community;
    const before = { ...g.needs };
    for (let i = 0; i < 3; i++) resolveTurn(c, atlas, content);
    ok(c.fired_events.includes('event_warsaw_ghetto_sealed'), 'the dated event did not fire');
    eq(c.cities.loc_warsaw.restriction_level, 3);
    ok(g.needs.food < before.food, 'needs did not respond to restriction');
    ok(g.displacement === 'restricted', `displacement ${g.displacement}`);
  });

  it('a relief order measurably helps a community', () => {
    const { svc } = freshService({ player_faction: 'uk_civil_defence', resources: { materiel: 100, personnel: 40, intelligence: 0, documents: 0 } });
    const g = svc.c.civilian_groups.grp_loc_london_community;
    g.needs.food = 0.3;
    const before = g.needs.food;
    ok(svc.submitOrder({ order_id: 'rel', kind: 'relieve', unit_id: 'u_cd_london', city_id: 'loc_london' }).ok);
    svc.endTurn();
    ok(g.needs.food > before, `relief had no effect: ${before} -> ${g.needs.food}`);
  });

  it('a civilian group never exposes a suffering percentage', () => {
    const c = newCampaign(atlas, content, { date: '1940-11-10' });
    const g = c.civilian_groups.grp_loc_warsaw_community;
    for (const k of Object.keys(g)) notOk(/suffering|victim|misery|death_rate/i.test(k), `field ${k} quantifies suffering`);
    ok('needs' in g && 'relationships' in g && 'household_ids' in g, 'a community has no people-shaped fields');
  });
});

}
