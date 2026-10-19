// Transition state machine and exactly-once consequence commit (brief §17).
//
//   StrategicReady -> PreparingMission -> LoadingMission -> MissionReady
//                  -> PlayingMission -> ResolvingMission -> Returning -> StrategicReady
//
// Three hard rules, each with a test in web/tests:
//   1. A double tap cannot create two active operations.
//   2. Delivering the same MissionResult twice applies its effects once.
//   3. An interrupted return either resumes the pending commit or loads the
//      already-committed result. Completion is never inferred from a missing scene.

import { makeMissionContext, makeMissionResult, validateMissionContext, validateMissionResult, ValidationError } from './contracts.js';
import { validateOrder, reserve, refund } from './orders.js';
import { sideOf, controlSide } from './supply.js';
import { hashString } from './rng.js';
import { addDays } from './dates.js';
import { recomputeCityServices } from './turn.js';

export const S = {
  READY: 'StrategicReady', PREPARING: 'PreparingMission', LOADING: 'LoadingMission',
  READY_MISSION: 'MissionReady', PLAYING: 'PlayingMission', RESOLVING: 'ResolvingMission',
  RETURNING: 'Returning', FAILED: 'TransitionFailed',
};

const LEGAL = {
  [S.READY]: [S.PREPARING],
  [S.PREPARING]: [S.LOADING, S.FAILED, S.READY],
  [S.LOADING]: [S.READY_MISSION, S.FAILED],
  [S.READY_MISSION]: [S.PLAYING, S.FAILED],
  [S.PLAYING]: [S.RESOLVING, S.FAILED],
  [S.RESOLVING]: [S.RETURNING, S.FAILED],
  [S.RETURNING]: [S.READY],
  [S.FAILED]: [S.READY, S.LOADING],
};

export class TransitionError extends Error {
  constructor(code, detail) { super(`${code}${detail ? `: ${detail}` : ''}`); this.name = 'TransitionError'; this.code = code; this.detail = detail; }
}

export const T_ERR = {
  OPERATION_ACTIVE: 'transition.operation_already_active',
  ILLEGAL_STATE: 'transition.illegal_state',
  ORDER_REJECTED: 'transition.order_rejected',
  NO_PENDING: 'transition.no_pending_operation',
  CONTEXT_MISMATCH: 'transition.context_mismatch',
  CONTENT_MISSING: 'transition.content_missing',
  NOT_PLAYABLE: 'transition.not_playable',
};

function stepTo(pending, next) {
  if (!LEGAL[pending.state]?.includes(next)) throw new TransitionError(T_ERR.ILLEGAL_STATE, `${pending.state} -> ${next}`);
  pending.state = next;
  pending.history.push({ state: next, at: pending.history.length });
  return pending;
}

/** Deterministic operation id: same campaign revision + nonce always yields the same id. */
export function operationId(campaign, nonce) {
  const h = hashString(`${campaign.campaign_id}|${campaign.revision}|${campaign.turn}|${nonce}`);
  return `op_${campaign.revision.toString(36)}_${h.toString(36)}`;
}

/**
 * Build the mission's outcome bounds from its chapter. The bounds are the only
 * thing that lets a mission change the campaign, and they come from authored
 * content, never from the mission scene.
 */
export function boundsForChapter(chapter) {
  const eff = chapter?.strategic_effects || {};
  const all = Object.values(eff);
  const maxOf = (f, d = 0) => all.reduce((m, e) => Math.max(m, Number(e?.[f] ?? d)), d);
  const minOf = (f, d = 0) => all.reduce((m, e) => Math.min(m, Number(e?.[f] ?? d)), d);
  return {
    max_intelligence: maxOf('intelligence'),
    max_materiel: maxOf('materiel'),
    min_materiel: minOf('materiel'),
    max_personnel: maxOf('personnel'),
    min_personnel: minOf('personnel'),
    may_remove_attacking_formation: all.some((e) => e?.removes_attacking_formation === true),
    may_flip_tile_control: all.some((e) => !!e?.tile_control_flip_to),
    max_civilian_health_delta: maxOf('civilian_health_delta'),
    min_civilian_health_delta: minOf('civilian_health_delta'),
    max_network_exposure_delta: maxOf('network_exposure', 0) || 0,
    max_network_access_delta: maxOf('network_access', 0) || 0,
  };
}

/** Step 1: validate, create the id, reserve the cost, write a durable entry checkpoint. */
export function beginOperation(campaign, atlas, content, request, { nonce, persist }) {
  if (campaign.pending_operation && campaign.pending_operation.state !== S.READY) {
    throw new TransitionError(T_ERR.OPERATION_ACTIVE, campaign.pending_operation.operation_id);
  }
  const chapter = (content.chapters || []).find((c) => c.id === request.chapter_id);
  if (request.chapter_id && !chapter) throw new TransitionError(T_ERR.CONTENT_MISSING, request.chapter_id);

  // The strategic order that authorises the operation is validated first, so an
  // illegal order can never leave a half-created operation behind.
  let orderCost = { materiel: 0, personnel: 0 };
  if (request.order) {
    const v = validateOrder(campaign, atlas, request.order);
    if (!v.ok) throw new TransitionError(T_ERR.ORDER_REJECTED, `${v.reason}${v.detail ? ` (${v.detail})` : ''}`);
    orderCost = v.cost;
  }

  const district = content.districts?.[request.district_id];
  if (!district) throw new TransitionError(T_ERR.CONTENT_MISSING, request.district_id);

  const opId = operationId(campaign, nonce);
  const permitted = (chapter?.objectives || []).map((o) => o.id);
  const context = validateMissionContext(makeMissionContext({
    operation_id: opId,
    source_revision: campaign.revision,
    campaign_id: campaign.campaign_id,
    unit_id: request.unit_id ?? null,
    tile_id: request.tile_id,
    city_id: campaign.tiles[request.tile_id]?.city_id ?? null,
    district_id: request.district_id,
    district_content_version: district.content_version,
    chapter_id: request.chapter_id ?? null,
    date: campaign.date,
    mission_type: chapter?.mission_families?.[0] ?? request.mission_type ?? 'mission_family_recon',
    seed: hashString(`${opId}|${campaign.rng_seed}`) | 0,
    permitted_objectives: permitted.length ? permitted : ['obj_reach_extraction'],
    allowed_outcomes: chapter?.allowed_outcomes ?? ['success', 'failure', 'withdrawal'],
    outcome_bounds: boundsForChapter(chapter),
    campaign_time_cost_turns: chapter?.campaign_time_cost_turns ?? 0,
    reserved_cost: orderCost,
    loadout: request.loadout || [],
    entry_snapshot: {
      // Everything needed to put the player back exactly where they were.
      revision: campaign.revision, turn: campaign.turn, date: campaign.date,
      resources: { ...campaign.resources },
      unit: request.unit_id ? { ...campaign.units[request.unit_id] } : null,
      tile_control: campaign.tiles[request.tile_id]?.control ?? null,
    },
  }));

  reserve(campaign, orderCost);
  campaign.pending_operation = {
    operation_id: opId, state: S.READY, history: [{ state: S.READY, at: 0 }],
    context, reserved_cost: orderCost, pending_result: null, committed: false,
    district_checkpoint: null, created_at_revision: campaign.revision,
  };
  stepTo(campaign.pending_operation, S.PREPARING);
  persist?.('entry_checkpoint', campaign);          // durable BEFORE any loading starts
  return context;
}

export function markLoading(campaign, { persist } = {}) {
  const p = requirePending(campaign);
  stepTo(p, S.LOADING);
  persist?.('loading', campaign);
  return p;
}

/**
 * A mission becomes playable only when everything the player needs is ready.
 * `readiness` is reported by the loader; a missing item fails the transition
 * instead of hiding behind a permanent loading animation.
 */
export function markReady(campaign, readiness, { persist } = {}) {
  const p = requirePending(campaign);
  const need = ['player', 'collision', 'navigation', 'objectives', 'ui', 'audio'];
  const missing = need.filter((k) => !readiness?.[k]);
  if (missing.length) {
    stepTo(p, S.FAILED);
    p.failure = { code: T_ERR.NOT_PLAYABLE, missing };
    persist?.('load_failed', campaign);
    throw new TransitionError(T_ERR.NOT_PLAYABLE, missing.join(','));
  }
  stepTo(p, S.READY_MISSION);
  persist?.('mission_ready', campaign);
  return p;
}

export function markPlaying(campaign, { persist } = {}) {
  const p = requirePending(campaign);
  stepTo(p, S.PLAYING);
  persist?.('mission_playing', campaign);
  return p;
}

/** Save a district checkpoint mid-mission (focus loss, screen lock, safe boundary). */
export function saveDistrictCheckpoint(campaign, checkpoint, { persist } = {}) {
  const p = requirePending(campaign);
  if (p.state !== S.PLAYING) throw new TransitionError(T_ERR.ILLEGAL_STATE, `${p.state} cannot hold a district checkpoint`);
  p.district_checkpoint = checkpoint;
  persist?.('district_checkpoint', campaign);
  return p;
}

/**
 * Step 2: the mission hands back a result. It is validated and clamped against
 * the immutable context, then written durably BEFORE any effect is applied.
 * Returns { already_committed: true } for a repeat delivery.
 */
export function submitResult(campaign, result, { persist } = {}) {
  const p = campaign.pending_operation;
  if (!p) {
    // Repeat delivery after the commit already finished and the pending record was cleared.
    if (campaign.committed_operations.includes(result.operation_id)) return { already_committed: true, applied: null };
    throw new TransitionError(T_ERR.NO_PENDING, result.operation_id);
  }
  if (p.operation_id !== result.operation_id) {
    if (campaign.committed_operations.includes(result.operation_id)) return { already_committed: true, applied: null };
    throw new TransitionError(T_ERR.CONTEXT_MISMATCH, `${result.operation_id} vs active ${p.operation_id}`);
  }
  if (campaign.committed_operations.includes(p.operation_id)) return { already_committed: true, applied: p.applied ?? null };

  if (p.state === S.PLAYING) stepTo(p, S.RESOLVING);
  else if (p.state !== S.RESOLVING) throw new TransitionError(T_ERR.ILLEGAL_STATE, `${p.state} -> ${S.RESOLVING}`);

  // Check the raw object: makeMissionResult would silently drop an unknown
  // field, which would turn an attempted world patch into a silent no-op.
  for (const forbidden of ['world_patch', 'campaign', 'tiles', 'units', 'resources']) {
    if (forbidden in result) throw new ValidationError([`a MissionResult may not carry a world-state patch (found "${forbidden}")`]);
  }
  const { safe, clamped } = validateMissionResult(makeMissionResult(result), p.context);
  p.pending_result = safe;
  p.clamped_fields = clamped;
  persist?.('pending_result', campaign);            // durable BEFORE commit
  return { already_committed: false, pending: safe, clamped };
}

/**
 * Step 3: apply the permitted effects exactly once, then acknowledge and clear.
 * Safe to call repeatedly; the second call is a no-op that returns the same
 * applied record.
 */
export function commitResult(campaign, atlas, content, { persist } = {}) {
  const p = campaign.pending_operation;
  if (!p) throw new TransitionError(T_ERR.NO_PENDING);
  if (!p.pending_result) throw new TransitionError(T_ERR.NO_PENDING, 'no pending_result to commit');
  if (campaign.committed_operations.includes(p.operation_id)) {
    return { applied: p.applied, repeated: true };
  }

  const r = p.pending_result;
  const ctx = p.context;
  const chapter = (content.chapters || []).find((c) => c.id === ctx.chapter_id);
  const effects = chapter?.strategic_effects?.[r.outcome] || {};
  const applied = { operation_id: p.operation_id, outcome: r.outcome, changes: [] };
  const note = (what, detail) => applied.changes.push({ what, ...detail });

  // Reserved cost becomes a real spend now. A technical failure refunds it
  // instead (see failOperation), so a retry never charges twice.
  applied.spent = { ...p.reserved_cost };

  // resources, within bounds already clamped by validateMissionResult
  for (const [k, v] of Object.entries(r.declared_resources)) {
    if (!v) continue;
    campaign.resources[k] = (campaign.resources[k] ?? 0) + v;
    note('resource', { key: k, delta: v });
  }
  if (r.declared_losses.personnel) {
    campaign.resources.personnel = Math.max(0, (campaign.resources.personnel ?? 0) - r.declared_losses.personnel);
    note('resource', { key: 'personnel', delta: -r.declared_losses.personnel });
  }
  if (effects.intelligence) { campaign.resources.intelligence += effects.intelligence; note('resource', { key: 'intelligence', delta: effects.intelligence, from: 'chapter_effect' }); }
  if (effects.materiel) { campaign.resources.materiel += effects.materiel; note('resource', { key: 'materiel', delta: effects.materiel, from: 'chapter_effect' }); }
  if (effects.personnel) { campaign.resources.personnel = Math.max(0, campaign.resources.personnel + effects.personnel); note('resource', { key: 'personnel', delta: effects.personnel, from: 'chapter_effect' }); }

  // tile supply penalty
  const supplyPenalty = r.requests.supply_penalty || (effects.tile_effects || []).reduce((m, e) => Math.max(m, e.set_supply_penalty || 0), 0);
  if (supplyPenalty) {
    const t = campaign.tiles[ctx.tile_id];
    if (t) { t.supply_penalty = Math.min(4, Math.max(t.supply_penalty || 0, supplyPenalty)); note('tile_supply_penalty', { tile_id: t.tile_id, value: t.supply_penalty }); }
  }

  // enemy readiness / formation removal, only if the chapter authorised it
  if (effects.enemy_readiness_delta) {
    const side = sideOf(campaign.player_faction) === 'allied' ? 'axis' : 'allied';
    for (const u of Object.keys(campaign.units).sort().map((k) => campaign.units[k])) {
      if (sideOf(u.faction) !== side) continue;
      if (u.tile_id !== ctx.tile_id && !campaign.tiles[ctx.tile_id]?.neighbors.includes(u.tile_id)) continue;
      u.strength = Math.max(0, Math.round((u.strength + effects.enemy_readiness_delta) * 1000) / 1000);
      note('enemy_readiness', { unit_id: u.unit_id, delta: effects.enemy_readiness_delta });
    }
  }
  if (r.requests.remove_attacking_formation && ctx.outcome_bounds.may_remove_attacking_formation) {
    const side = sideOf(campaign.player_faction) === 'allied' ? 'axis' : 'allied';
    const tile = campaign.tiles[ctx.tile_id];
    // An attacking formation is one that can attack. A dug-in garrison is not
  //  the attacker, so it is only considered when nothing else qualifies.
    const candidates = Object.keys(campaign.units).sort().map((k) => campaign.units[k])
      .filter((u) => sideOf(u.faction) === side && (u.tile_id === ctx.tile_id || tile?.neighbors.includes(u.tile_id)));
    const mobile = candidates.filter((u) => (u.allowed_actions || []).includes('attack') && !u.status.includes('entrenched'));
    const target = mobile[0] || candidates[0];
    if (target) { delete campaign.units[target.unit_id]; note('formation_removed', { unit_id: target.unit_id, label_key: target.label_key }); }
    if (tile && controlSide(tile.control) !== sideOf(campaign.player_faction)) { tile.control = sideOf(campaign.player_faction); note('tile_control', { tile_id: tile.tile_id, to: tile.control }); }
  }
  if (effects.tile_control_flip_to && ctx.outcome_bounds.may_flip_tile_control) {
    const t = campaign.tiles[ctx.tile_id];
    if (t) { t.control = effects.tile_control_flip_to === 'attacker' ? (sideOf(campaign.player_faction) === 'allied' ? 'axis' : 'allied') : effects.tile_control_flip_to; note('tile_control', { tile_id: t.tile_id, to: t.control }); }
  }

  // civilians and networks
  const civDelta = r.requests.civilian_health_delta || effects.civilian_health_delta || 0;
  if (civDelta) {
    const city = campaign.cities[ctx.city_id] || Object.keys(campaign.cities).sort().map((k) => campaign.cities[k])[0];
    for (const gid of city?.civilian_group_ids || []) {
      const g = campaign.civilian_groups[gid];
      if (!g) continue;
      g.needs.medicine = Math.max(0, Math.min(1, Math.round((g.needs.medicine + civDelta * 0.1) * 1000) / 1000));
      note('civilian_needs', { group_id: gid, medicine_delta: civDelta * 0.1 });
    }
  }
  const expDelta = r.requests.network_exposure_delta || effects.network_exposure || 0;
  const accDelta = r.requests.network_access_delta || effects.network_access || 0;
  if (expDelta || accDelta) {
    const nets = Object.keys(campaign.networks).sort().map((k) => campaign.networks[k]);
    const net = nets.find((n) => n.city_id === ctx.city_id) || nets[0];
    if (net) {
      if (expDelta) { net.exposure = Math.max(0, Math.min(1, Math.round((net.exposure + expDelta) * 1000) / 1000)); note('network_exposure', { network_id: net.network_id, value: net.exposure }); }
      if (accDelta) { net.access = Math.max(0, Math.min(5, net.access + accDelta)); note('network_access', { network_id: net.network_id, value: net.access }); }
    }
  }

  // chapter progress
  if (ctx.chapter_id && ['success', 'partial_success'].includes(r.outcome)) {
    if (!campaign.completed_chapters.includes(ctx.chapter_id)) { campaign.completed_chapters.push(ctx.chapter_id); note('chapter_completed', { chapter_id: ctx.chapter_id }); }
    campaign.unlocked_chapters = campaign.unlocked_chapters.filter((c) => c !== ctx.chapter_id);
    for (const c of effects.unlock_chapters || []) if (!campaign.unlocked_chapters.includes(c) && !campaign.completed_chapters.includes(c)) { campaign.unlocked_chapters.push(c); note('chapter_unlocked', { chapter_id: c }); }
  }

  // campaign time, only if the operation declares a cost
  if (ctx.campaign_time_cost_turns > 0) {
    campaign.turn += ctx.campaign_time_cost_turns;
    campaign.date = addDays(campaign.date, (content.turn_length_days ?? 7) * ctx.campaign_time_cost_turns);
    note('campaign_time', { turns: ctx.campaign_time_cost_turns, date: campaign.date });
  }

  for (const city of Object.keys(campaign.cities).sort().map((k) => campaign.cities[k])) recomputeCityServices(city, atlas);

  // ---- the exactly-once barrier ----
  campaign.committed_operations.push(p.operation_id);
  p.committed = true;
  p.applied = applied;
  campaign.revision += 1;
  stepTo(p, S.RETURNING);
  persist?.('committed', campaign);                  // durable AFTER commit, BEFORE acknowledgement
  return { applied, repeated: false };
}

/** Step 4: acknowledge and clear. Separate from commit so a crash between the two is recoverable. */
export function acknowledgeReturn(campaign, { persist } = {}) {
  const p = campaign.pending_operation;
  if (!p) return null;
  if (!p.committed) throw new TransitionError(T_ERR.ILLEGAL_STATE, 'cannot acknowledge an uncommitted operation');
  const applied = p.applied;
  campaign.pending_operation = null;
  persist?.('return_acknowledged', campaign);
  return applied;
}

/**
 * A technical failure (missing content, failed load, cancelled entry). Refunds
 * the reservation so retrying a failure never costs the player twice.
 */
export function failOperation(campaign, code, detail, { persist } = {}) {
  const p = campaign.pending_operation;
  if (!p) return null;
  if (p.committed) throw new TransitionError(T_ERR.ILLEGAL_STATE, 'a committed operation cannot be failed');
  refund(campaign, p.reserved_cost);
  const snap = p.context.entry_snapshot;
  campaign.resources = { ...snap.resources };        // restore, not patch
  if (snap.unit && campaign.units[snap.unit.unit_id]) campaign.units[snap.unit.unit_id] = { ...snap.unit };
  if (snap.tile_control && campaign.tiles[p.context.tile_id]) campaign.tiles[p.context.tile_id].control = snap.tile_control;
  campaign.pending_operation = null;
  persist?.('operation_failed', campaign);
  return { cancelled: p.operation_id, code, detail };
}

/**
 * Called on every launch. Decides what to do about a pending operation found in
 * the save. Never infers completion from a missing scene.
 */
export function recoverOnLaunch(campaign, atlas, content, { persist } = {}) {
  const p = campaign.pending_operation;
  if (!p) return { action: 'none' };

  switch (p.state) {
    case S.READY:
    case S.PREPARING:
    case S.LOADING:
    case S.READY_MISSION:
    case S.FAILED:
      // Nothing was played. Cancel and refund; the player may re-enter freely.
      return { action: 'cancelled_entry', detail: failOperation(campaign, 'recovery.entry_incomplete', p.state, { persist }) };

    case S.PLAYING:
      // A mission was in progress. Resume it from its district checkpoint if we
      // have one, otherwise restart the mission from the entry checkpoint. In
      // both cases the operation keeps its id, so its effects stay single-use.
      return { action: p.district_checkpoint ? 'resume_mission' : 'restart_mission', operation_id: p.operation_id, context: p.context, checkpoint: p.district_checkpoint };

    case S.RESOLVING:
      // A result was written durably but the commit may not have finished.
      // commitResult is idempotent, so running it is always safe.
      if (campaign.committed_operations.includes(p.operation_id)) {
        return { action: 'already_committed', applied: acknowledgeReturn(campaign, { persist }) };
      }
      return { action: 'resumed_commit', applied: commitResult(campaign, atlas, content, { persist }).applied, acknowledged: acknowledgeReturn(campaign, { persist }) };

    case S.RETURNING:
      return { action: 'acknowledged', applied: acknowledgeReturn(campaign, { persist }) };

    default:
      return { action: 'unknown_state', state: p.state };
  }
}

function requirePending(campaign) {
  const p = campaign.pending_operation;
  if (!p) throw new TransitionError(T_ERR.NO_PENDING);
  return p;
}
