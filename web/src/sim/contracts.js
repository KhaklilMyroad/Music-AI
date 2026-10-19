// Data contracts from the brief, section 16. These are the save contract and the
// interchange format. Scene nodes are views; none of them owns any of this.
//
// Every contract is a plain serialisable object: no node references, no live
// engine resources, no unvalidated dictionaries. Validation is strict on load
// because a damaged save must be detected, not half-applied.

export const SCHEMA_VERSION = 4;       // CampaignState / SaveEnvelope schema
export const RESULT_VERSION = 2;       // MissionResult shape
export const CHECKPOINT_VERSION = 2;   // DistrictCheckpoint shape

export const FACTIONS = [
  'allied_us_army', 'allied_uk_army', 'allied_soviet', 'polish_home_army',
  'french_resistance', 'resistance_cell', 'jewish_fighting_organisations',
  'uk_civil_defence', 'us_home_front_organisations', 'civilian',
  'axis_army', 'axis_police', 'axis_air_force', 'axis_occupation_authority',
];
export const UNIT_TYPES = [
  'infantry_division', 'armoured_division', 'garrison', 'partisan_squad',
  'underground_cell', 'civil_defence_team', 'relief_column', 'supply_column',
];
export const CONTROL = ['allied', 'axis', 'neutral', 'contested'];
export const OUTCOMES = ['success', 'partial_success', 'failure', 'withdrawal'];
export const TRANSITION_STATES = [
  'StrategicReady', 'PreparingMission', 'LoadingMission', 'MissionReady',
  'PlayingMission', 'ResolvingMission', 'Returning', 'TransitionFailed',
];

/** Capabilities per unit type. A civilian group cannot inherit a division's verbs. */
export const UNIT_CAPABILITIES = {
  infantry_division:  { actions: ['move', 'attack', 'defend', 'reconnoitre', 'entrench'], move_budget: 3, supply_draw: 4, can_occupy: true,  visible_on_map: true,  uses_routes: true,  uses_access: false },
  armoured_division:  { actions: ['move', 'attack', 'defend', 'reconnoitre'],             move_budget: 5, supply_draw: 7, can_occupy: true,  visible_on_map: true,  uses_routes: true,  uses_access: false },
  garrison:           { actions: ['defend', 'entrench'],                                  move_budget: 0, supply_draw: 2, can_occupy: true,  visible_on_map: true,  uses_routes: false, uses_access: false },
  partisan_squad:     { actions: ['move', 'sabotage', 'reconnoitre', 'ambush', 'hide'],   move_budget: 2, supply_draw: 1, can_occupy: false, visible_on_map: false, uses_routes: false, uses_access: true },
  underground_cell:   { actions: ['move_covert', 'sabotage', 'courier', 'shelter', 'recruit', 'hide'], move_budget: 1, supply_draw: 0, can_occupy: false, visible_on_map: false, uses_routes: false, uses_access: true },
  civil_defence_team: { actions: ['relieve', 'evacuate', 'treat', 'move'],                move_budget: 2, supply_draw: 1, can_occupy: false, visible_on_map: true,  uses_routes: true,  uses_access: false },
  relief_column:      { actions: ['move', 'relieve', 'deliver'],                          move_budget: 2, supply_draw: 1, can_occupy: false, visible_on_map: true,  uses_routes: true,  uses_access: false },
  supply_column:      { actions: ['move', 'deliver'],                                     move_budget: 3, supply_draw: 1, can_occupy: false, visible_on_map: true,  uses_routes: true,  uses_access: false },
};

// ------------------------------------------------------------------ helpers --
class ValidationError extends Error {
  constructor(issues) {
    super(`contract validation failed:\n - ${issues.join('\n - ')}`);
    this.name = 'ValidationError';
    this.issues = issues;
  }
}
export { ValidationError };

const isStr = (v) => typeof v === 'string' && v.length > 0;
const isInt = (v) => Number.isInteger(v);
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isArr = Array.isArray;
const inRange = (v, lo, hi) => isNum(v) && v >= lo && v <= hi;

function check(cond, issues, msg) { if (!cond) issues.push(msg); return cond; }

// -------------------------------------------------------------- constructors --
export function makeTileState(o) {
  return {
    tile_id: o.tile_id,                   // stable: "<theater>:<q>,<r>"
    theater: o.theater,
    q: o.q, r: o.r,
    terrain: o.terrain,
    control: o.control,                   // CONTROL
    passable: o.passable !== false,
    naval_only: !!o.naval_only,
    neighbors: o.neighbors || [],          // tile_id[]
    city_id: o.city_id ?? null,
    poi_refs: o.poi_refs || [],
    supply: isNum(o.supply) ? o.supply : 0,          // 0..10 computed each turn
    supply_penalty: o.supply_penalty || 0,            // set by mission effects
    discovered: !!o.discovered,
    contested_since_turn: o.contested_since_turn ?? null,
  };
}

export function makeUnitState(o) {
  const cap = UNIT_CAPABILITIES[o.unit_type];
  if (!cap) throw new ValidationError([`unknown unit_type "${o.unit_type}"`]);
  return {
    unit_id: o.unit_id,
    unit_type: o.unit_type,
    faction: o.faction,
    label_key: o.label_key || `unit.${o.unit_type}`,
    tile_id: o.tile_id,
    strength: isNum(o.strength) ? o.strength : 1.0,   // 0..1 readiness/strength
    supply: isNum(o.supply) ? o.supply : 1.0,         // 0..1 local supply satisfaction
    move_budget: isNum(o.move_budget) ? o.move_budget : cap.move_budget,
    move_budget_max: cap.move_budget,
    allowed_actions: o.allowed_actions || cap.actions.slice(),
    equipment: o.equipment || [],
    status: o.status || [],                            // 'entrenched' | 'isolated' | 'routed' | 'hidden' | 'in_transit'
    transit: o.transit ?? null,                        // { link_id, turns_remaining, to_tile }
  };
}

export function makeCityState(o) {
  return {
    city_id: o.city_id,
    label_key: o.label_key,
    theater: o.theater,
    tile_id: o.tile_id,
    place_date_context: o.place_date_context || null,  // which dated state the city is in
    control: o.control,
    facilities: o.facilities || [],                    // { facility_id, built_turn, damaged, disabled }
    construction_queue: o.construction_queue || [],     // { facility_id, turns_remaining, reserved_cost }
    facilities_max: o.facilities_max ?? 4,
    supply_access: isNum(o.supply_access) ? o.supply_access : 0,
    service_capacity: o.service_capacity || { civilian_health: 0, civilian_food: 0, evacuation: 0 },
    civilian_group_ids: o.civilian_group_ids || [],
    network_ids: o.network_ids || [],
    districts: o.districts || [],
    restriction_level: o.restriction_level ?? 0,       // 0..5, set by dated events
  };
}

export function makeCivilianGroupState(o) {
  return {
    group_id: o.group_id,
    label_key: o.label_key,
    is_fictional: o.is_fictional !== false,
    community_id: o.community_id ?? null,
    household_ids: o.household_ids || [],
    headcount: isInt(o.headcount) ? o.headcount : 1,
    city_id: o.city_id,
    tile_id: o.tile_id,
    // Needs are 0..1 satisfaction, NOT a suffering score. See the editorial rule
    // in docs/08: persecution is never rendered as a measured percentage.
    needs: { food: 1, water: 1, medicine: 1, shelter: 1, ...(o.needs || {}) },
    access_restrictions: o.access_restrictions || [],
    displacement: o.displacement || 'in_place',        // in_place | restricted | displaced | evacuated | unaccounted
    narrative_flags: o.narrative_flags || [],
    relationships: o.relationships || [],              // { to_group_id, kind }
  };
}

export function makeUndergroundNetworkState(o) {
  return {
    network_id: o.network_id,
    label_key: o.label_key,
    city_id: o.city_id,
    cells: o.cells || [],                              // { cell_id, tile_id, size, compromised }
    contacts: o.contacts || [],                        // { contact_id, role, reliability, compromised }
    area_tiles: o.area_tiles || [],
    access: isInt(o.access) ? o.access : 0,            // 0..5 reach into the city
    intelligence: isInt(o.intelligence) ? o.intelligence : 0,
    resources: { materiel: 0, personnel: 0, documents: 0, ...(o.resources || {}) },
    exposure: inRange(o.exposure, 0, 1) ? o.exposure : 0,
    safe_routes: o.safe_routes || [],                   // { route_id, tile_ids, open }
    compromised_links: o.compromised_links || [],
  };
}

export function makeCampaignState(o) {
  return {
    schema_version: SCHEMA_VERSION,
    campaign_id: o.campaign_id,
    revision: isInt(o.revision) ? o.revision : 0,
    turn: isInt(o.turn) ? o.turn : 1,
    date: o.date,
    mode: o.mode || 'campaign',                        // campaign | sandbox
    player_faction: o.player_faction,
    resources: { materiel: 0, personnel: 0, intelligence: 0, documents: 0, ...(o.resources || {}) },
    tiles: o.tiles || {},                              // tile_id -> TileState
    units: o.units || {},                              // unit_id -> UnitState
    cities: o.cities || {},
    civilian_groups: o.civilian_groups || {},
    networks: o.networks || {},
    fired_events: o.fired_events || [],
    completed_chapters: o.completed_chapters || [],
    unlocked_chapters: o.unlocked_chapters || [],
    unlocked_equipment: o.unlocked_equipment || [],
    history_flags: o.history_flags || {},
    pending_operation: o.pending_operation ?? null,    // the exactly-once record
    committed_operations: o.committed_operations || [], // operation_id[] already applied
    order_queue: o.order_queue || [],
    last_turn_report: o.last_turn_report ?? null,
    rng_seed: isInt(o.rng_seed) ? o.rng_seed : 1,
  };
}

export function makeMissionContext(o) {
  return {
    operation_id: o.operation_id,
    source_revision: o.source_revision,                // campaign revision at entry
    campaign_id: o.campaign_id,
    unit_id: o.unit_id ?? null,
    tile_id: o.tile_id,
    city_id: o.city_id ?? null,
    district_id: o.district_id,
    district_content_version: o.district_content_version,
    chapter_id: o.chapter_id ?? null,
    date: o.date,
    mission_type: o.mission_type,
    seed: o.seed,
    permitted_objectives: o.permitted_objectives || [],
    allowed_outcomes: o.allowed_outcomes || OUTCOMES.slice(),
    // Outcome bounds: the result validator rejects anything outside these. A
    // mission cannot invent a world-state patch.
    outcome_bounds: {
      max_intelligence: 0, max_materiel: 0, max_personnel: 0,
      min_materiel: -999, min_personnel: -999,
      may_remove_attacking_formation: false,
      may_flip_tile_control: false,
      max_civilian_health_delta: 0, min_civilian_health_delta: -999,
      max_network_exposure_delta: 1, max_network_access_delta: 0,
      ...(o.outcome_bounds || {}),
    },
    entry_snapshot: o.entry_snapshot,                  // minimal snapshot for safe return
    reserved_cost: o.reserved_cost || {},
    campaign_time_cost_turns: o.campaign_time_cost_turns ?? 0,
    loadout: o.loadout || [],
  };
}

export function makeMissionResult(o) {
  return {
    result_version: RESULT_VERSION,
    operation_id: o.operation_id,
    source_revision: o.source_revision,
    outcome: o.outcome,
    completed_objectives: o.completed_objectives || [],
    failed_objectives: o.failed_objectives || [],
    metrics: {
      elapsed_mission_seconds: 0, shots_fired: 0, times_detected: 0,
      alarm_raised: false, civilians_assisted: 0, hostiles_neutralised: 0,
      ...(o.metrics || {}),
    },
    declared_losses: { personnel: 0, ...(o.declared_losses || {}) },
    declared_resources: { materiel: 0, intelligence: 0, documents: 0, ...(o.declared_resources || {}) },
    requests: o.requests || {},                        // bounded, validated effect requests only
  };
}

export function makeDistrictCheckpoint(o) {
  return {
    checkpoint_version: CHECKPOINT_VERSION,
    district_id: o.district_id,
    district_content_version: o.district_content_version,
    saved_at_boundary: o.saved_at_boundary || 'safe_action_boundary',
    player: {
      position: o.player?.position || [0, 0, 0],
      yaw: o.player?.yaw ?? 0, pitch: o.player?.pitch ?? 0,
      posture: o.player?.posture || 'stand',
      health: o.player?.health ?? 100,
      condition: o.player?.condition || { fatigue: 0, warmth: 1, hunger: 0, thirst: 0 },
      equipped: o.player?.equipped ?? null,
    },
    inventory: o.inventory || {},                      // item_id -> count
    weapon_states: o.weapon_states || {},              // weapon_id -> { loaded, reserve, chambered }
    mission_flags: o.mission_flags || {},              // objective_id -> true (prevents double rewards)
    poi_states: o.poi_states || {},
    door_states: o.door_states || {},
    container_states: o.container_states || {},
    local_entities: o.local_entities || [],            // patrol/civilian persisted state
    local_time_hours: o.local_time_hours ?? 8,
    weather: o.weather || 'clear_morning',
    interrupted_action: o.interrupted_action ?? null,  // { kind, progress, revert_to }
  };
}

export function makeSaveEnvelope(o) {
  const payload = o.payload;
  const env = {
    schema_version: SCHEMA_VERSION,
    content_versions: o.content_versions || {},
    save_id: o.save_id,
    slot: o.slot ?? 'auto',
    mode: o.mode || 'campaign',
    revision: o.revision ?? payload?.campaign?.revision ?? 0,
    saved_at: o.saved_at,                              // ISO wall-clock, display only
    engine_build: o.engine_build || 'unknown',
    payload,                                           // { campaign, district_checkpoint|null }
    recovery: { is_last_known_good: !!o.is_last_known_good, write_complete: true, previous_save_id: o.previous_save_id ?? null },
    integrity: null,
  };
  return env;
}

// ---------------------------------------------------------------- validators --
export function validateTile(t, issues = [], path = 'tile') {
  check(isStr(t.tile_id), issues, `${path}.tile_id must be a non-empty string`);
  check(isInt(t.q) && isInt(t.r), issues, `${path}.q/r must be integers`);
  check(isStr(t.terrain), issues, `${path}.terrain required`);
  check(CONTROL.includes(t.control), issues, `${path}.control must be one of ${CONTROL}`);
  check(isArr(t.neighbors), issues, `${path}.neighbors must be an array`);
  check(inRange(t.supply, 0, 10), issues, `${path}.supply must be 0..10 (got ${t.supply})`);
  return issues;
}

export function validateUnit(u, issues = [], path = 'unit') {
  check(isStr(u.unit_id), issues, `${path}.unit_id required`);
  check(UNIT_TYPES.includes(u.unit_type), issues, `${path}.unit_type invalid: ${u.unit_type}`);
  check(FACTIONS.includes(u.faction), issues, `${path}.faction invalid: ${u.faction}`);
  check(isStr(u.tile_id), issues, `${path}.tile_id required`);
  check(inRange(u.strength, 0, 1), issues, `${path}.strength must be 0..1`);
  check(inRange(u.supply, 0, 1), issues, `${path}.supply must be 0..1`);
  const cap = UNIT_CAPABILITIES[u.unit_type];
  if (cap) {
    check(inRange(u.move_budget, 0, cap.move_budget), issues, `${path}.move_budget ${u.move_budget} exceeds ${u.unit_type} max ${cap.move_budget}`);
    const stray = (u.allowed_actions || []).filter((a) => !cap.actions.includes(a));
    check(stray.length === 0, issues, `${path}.allowed_actions contains actions ${u.unit_type} cannot perform: ${stray}`);
  }
  return issues;
}

export function validateCivilianGroup(g, issues = [], path = 'civilian_group') {
  check(isStr(g.group_id), issues, `${path}.group_id required`);
  check(isInt(g.headcount) && g.headcount >= 0, issues, `${path}.headcount must be a non-negative integer`);
  for (const k of ['food', 'water', 'medicine', 'shelter']) {
    check(inRange(g.needs?.[k], 0, 1), issues, `${path}.needs.${k} must be 0..1`);
  }
  check(['in_place', 'restricted', 'displaced', 'evacuated', 'unaccounted'].includes(g.displacement), issues, `${path}.displacement invalid: ${g.displacement}`);
  // Guard against the bug the brief calls out by name.
  check(!('strength' in g), issues, `${path} must not carry a military 'strength' field; civilian condition is never inferred from unit strength`);
  return issues;
}

export function validateNetwork(n, issues = [], path = 'network') {
  check(isStr(n.network_id), issues, `${path}.network_id required`);
  check(inRange(n.exposure, 0, 1), issues, `${path}.exposure must be 0..1`);
  check(isInt(n.access) && n.access >= 0 && n.access <= 5, issues, `${path}.access must be 0..5`);
  return issues;
}

export function validateCampaign(c) {
  const issues = [];
  check(c.schema_version === SCHEMA_VERSION, issues, `schema_version must be ${SCHEMA_VERSION}, got ${c.schema_version}`);
  check(isStr(c.campaign_id), issues, 'campaign_id required');
  check(isInt(c.revision) && c.revision >= 0, issues, 'revision must be a non-negative integer');
  check(isInt(c.turn) && c.turn >= 1, issues, 'turn must be >= 1');
  check(/^\d{4}-\d{2}-\d{2}$/.test(c.date || ''), issues, `date must be ISO yyyy-mm-dd, got ${c.date}`);
  check(['campaign', 'sandbox'].includes(c.mode), issues, `mode invalid: ${c.mode}`);
  check(FACTIONS.includes(c.player_faction), issues, `player_faction invalid: ${c.player_faction}`);
  check(isObj(c.tiles) && isObj(c.units) && isObj(c.cities), issues, 'tiles/units/cities must be objects keyed by stable id');

  for (const [id, t] of Object.entries(c.tiles || {})) {
    check(id === t.tile_id, issues, `tiles key "${id}" does not match tile_id "${t.tile_id}"`);
    validateTile(t, issues, `tiles[${id}]`);
    for (const nb of t.neighbors) check(!!c.tiles[nb], issues, `tiles[${id}].neighbors references missing tile "${nb}"`);
    if (t.city_id) check(!!c.cities[t.city_id], issues, `tiles[${id}].city_id references missing city "${t.city_id}"`);
  }
  for (const [id, u] of Object.entries(c.units || {})) {
    check(id === u.unit_id, issues, `units key "${id}" does not match unit_id`);
    validateUnit(u, issues, `units[${id}]`);
    check(!!c.tiles[u.tile_id], issues, `units[${id}].tile_id references missing tile "${u.tile_id}"`);
  }
  for (const [id, g] of Object.entries(c.civilian_groups || {})) {
    validateCivilianGroup(g, issues, `civilian_groups[${id}]`);
    check(!!c.cities[g.city_id], issues, `civilian_groups[${id}].city_id references missing city`);
  }
  for (const [id, n] of Object.entries(c.networks || {})) validateNetwork(n, issues, `networks[${id}]`);
  for (const [id, city] of Object.entries(c.cities || {})) {
    check(!!c.tiles[city.tile_id], issues, `cities[${id}].tile_id references missing tile`);
    check(city.facilities.length <= city.facilities_max, issues, `cities[${id}] has ${city.facilities.length} facilities over max ${city.facilities_max}`);
  }
  if (c.pending_operation) {
    check(isStr(c.pending_operation.operation_id), issues, 'pending_operation.operation_id required');
    check(TRANSITION_STATES.includes(c.pending_operation.state), issues, `pending_operation.state invalid: ${c.pending_operation.state}`);
  }
  if (issues.length) throw new ValidationError(issues);
  return c;
}

export function validateMissionContext(m) {
  const issues = [];
  check(isStr(m.operation_id), issues, 'operation_id required');
  check(isInt(m.source_revision), issues, 'source_revision must be an integer');
  check(isStr(m.district_id), issues, 'district_id required');
  check(isStr(m.district_content_version), issues, 'district_content_version required (a mission must know which content it was built for)');
  check(isInt(m.seed), issues, 'seed must be an integer so the mission is reproducible');
  check(isArr(m.permitted_objectives) && m.permitted_objectives.length > 0, issues, 'permitted_objectives must be non-empty');
  check(isArr(m.allowed_outcomes) && m.allowed_outcomes.every((o) => OUTCOMES.includes(o)), issues, `allowed_outcomes must be a subset of ${OUTCOMES}`);
  check(isObj(m.entry_snapshot), issues, 'entry_snapshot required for safe return');
  if (issues.length) throw new ValidationError(issues);
  return m;
}

/**
 * Validate a MissionResult against the context that produced it. This is the
 * gate that stops a mission scene from writing arbitrary campaign state.
 * Returns a clamped, safe copy; throws if the result is structurally wrong or
 * belongs to a different operation/revision.
 */
export function validateMissionResult(result, context) {
  const issues = [];
  check(result.result_version === RESULT_VERSION, issues, `result_version must be ${RESULT_VERSION}`);
  check(result.operation_id === context.operation_id, issues, `result.operation_id "${result.operation_id}" does not match context "${context.operation_id}"`);
  check(result.source_revision === context.source_revision, issues, `result.source_revision ${result.source_revision} does not match context ${context.source_revision}`);
  check(context.allowed_outcomes.includes(result.outcome), issues, `outcome "${result.outcome}" is not permitted by this mission (allowed: ${context.allowed_outcomes})`);
  const strayObj = (result.completed_objectives || []).filter((o) => !context.permitted_objectives.includes(o));
  check(strayObj.length === 0, issues, `result claims objectives this mission does not define: ${strayObj}`);
  check(!('world_patch' in result) && !('campaign' in result), issues, 'a MissionResult may not carry a world-state patch');
  if (issues.length) throw new ValidationError(issues);

  const b = context.outcome_bounds;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v || 0));
  const safe = {
    ...result,
    declared_resources: {
      materiel: clamp(result.declared_resources.materiel, b.min_materiel, b.max_materiel),
      intelligence: clamp(result.declared_resources.intelligence, 0, b.max_intelligence),
      documents: clamp(result.declared_resources.documents, 0, b.max_intelligence),
    },
    declared_losses: { personnel: clamp(result.declared_losses.personnel, 0, Math.abs(b.min_personnel)) },
    requests: {
      remove_attacking_formation: !!result.requests?.remove_attacking_formation && b.may_remove_attacking_formation,
      flip_tile_control_to: b.may_flip_tile_control ? (result.requests?.flip_tile_control_to ?? null) : null,
      civilian_health_delta: clamp(result.requests?.civilian_health_delta, b.min_civilian_health_delta, b.max_civilian_health_delta),
      network_exposure_delta: clamp(result.requests?.network_exposure_delta, 0, b.max_network_exposure_delta),
      network_access_delta: clamp(result.requests?.network_access_delta, 0, b.max_network_access_delta),
      supply_penalty: clamp(result.requests?.supply_penalty, 0, 4),
    },
  };
  const clamped = [];
  if ((result.declared_resources.intelligence || 0) !== safe.declared_resources.intelligence) clamped.push('intelligence');
  if ((result.declared_resources.materiel || 0) !== safe.declared_resources.materiel) clamped.push('materiel');
  if ((result.requests?.remove_attacking_formation) && !safe.requests.remove_attacking_formation) clamped.push('remove_attacking_formation');
  return { safe, clamped };
}

export function validateSaveEnvelope(env) {
  const issues = [];
  check(isInt(env.schema_version), issues, 'schema_version required');
  check(isStr(env.save_id), issues, 'save_id required');
  check(isObj(env.payload), issues, 'payload required');
  check(env.recovery?.write_complete === true, issues, 'recovery.write_complete is false: this save was interrupted mid-write');
  check(isStr(env.integrity), issues, 'integrity digest missing');
  if (issues.length) throw new ValidationError(issues);
  return env;
}
