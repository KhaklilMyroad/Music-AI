// CampaignService: the single authority that applies commands and mission
// outcomes (brief §16). The map view, the mission scene and the UI submit
// requests here; none of them writes campaign state directly.

import { validateCampaign } from './contracts.js';
import { validateOrder, reserve, refund } from './orders.js';
import { resolveTurn, buildSources } from './turn.js';
import { applySupply, reachable, pathTo } from './supply.js';
import * as T from './transition.js';
import { SaveService } from './save.js';

export class CampaignService {
  /**
   * @param {object} campaign  CampaignState (owned by this service from now on)
   * @param {object} atlas     theaters.json
   * @param {object} content   { chapters, timeline_events, mission_families, districts, turn_length_days, campaign_range }
   * @param {SaveService} saves
   */
  constructor(campaign, atlas, content, saves) {
    this.c = campaign;
    this.atlas = atlas;
    this.content = content;
    this.saves = saves;
    this.listeners = new Set();
    this.persist = (reason) => { this.saves?.write('auto', this.c, this.c.pending_operation?.district_checkpoint ?? null, reason); };
  }

  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit(kind, data) { for (const fn of this.listeners) fn(kind, data, this.c); }

  // ------------------------------------------------------------- read-only --
  /** Cost and route preview for the confirmation sheet. Never mutates. */
  previewOrder(order) {
    const v = validateOrder(this.c, this.atlas, order);
    if (!v.ok) return { ok: false, reason: v.reason, detail: v.detail };
    return { ok: true, cost: v.cost, plan: v.plan, resources_after: Object.fromEntries(Object.entries(this.c.resources).map(([k, n]) => [k, n - (v.cost[k] ?? 0)])) };
  }

  /** Movement range for the selected unit, for the map overlay. */
  movementRange(unit_id) {
    const u = this.c.units[unit_id];
    if (!u) return { tiles: [], blocked: [] };
    const { dist, prev } = reachable(this.c, this.atlas, u);
    return {
      tiles: [...dist.entries()].map(([tile_id, cost]) => ({ tile_id, cost, path: pathTo(prev, u.tile_id, tile_id) })).sort((a, b) => (a.tile_id < b.tile_id ? -1 : 1)),
      blocked: this.c.tiles[u.tile_id].neighbors.filter((id) => !dist.has(id)).map((id) => ({ tile_id: id, reason: this.whyBlocked(u, id) })),
    };
  }

  whyBlocked(unit, tile_id) {
    const t = this.c.tiles[tile_id];
    if (!t) return 'reject.no_target';
    if (!t.passable) return 'reject.impassable';
    const { dist } = reachable(this.c, this.atlas, unit, 99);
    if (!dist.has(tile_id)) return 'reject.unreachable';
    return 'reject.no_move_budget';
  }

  explainUnit(unit_id) {
    const u = this.c.units[unit_id];
    if (!u) return null;
    const t = this.c.tiles[u.tile_id];
    const reasons = [];
    if (u.supply < 0.25) reasons.push({ key: 'explain.isolated', detail: { tile_supply: t.supply } });
    else if (u.supply < 0.6) reasons.push({ key: 'explain.short_supply', detail: { tile_supply: t.supply } });
    if (u.strength < 0.4) reasons.push({ key: 'explain.weakened', detail: { strength: u.strength } });
    if (u.status.includes('routed')) reasons.push({ key: 'explain.routed' });
    if (u.status.includes('entrenched')) reasons.push({ key: 'explain.entrenched' });
    if (u.status.includes('in_transit')) reasons.push({ key: 'explain.in_transit', detail: u.transit });
    if (!reasons.length) reasons.push({ key: 'explain.ready' });
    return { unit_id, reasons, move_budget: u.move_budget, move_budget_max: u.move_budget_max, allowed_actions: u.allowed_actions };
  }

  availableChapters() {
    return this.c.unlocked_chapters
      .map((id) => this.content.chapters.find((ch) => ch.id === id))
      .filter(Boolean)
      .filter((ch) => !this.content.chapters_gated_out?.includes(ch.id));
  }

  // ------------------------------------------------------------- commands ---
  /** Queue an order. Rejection leaves resources and state unchanged. */
  submitOrder(order) {
    const before = this.c.revision;
    const v = validateOrder(this.c, this.atlas, order);
    if (!v.ok) {
      this.emit('order_rejected', { order_id: order.order_id, reason: v.reason, detail: v.detail });
      return { ok: false, reason: v.reason, detail: v.detail };
    }
    reserve(this.c, v.cost);
    this.c.order_queue.push({ order_id: order.order_id, unit_id: order.unit_id ?? null, city_id: order.city_id ?? null, order, cost: v.cost });
    this.emit('order_queued', { order_id: order.order_id, cost: v.cost, plan: v.plan });
    if (this.c.revision !== before) throw new Error('submitOrder must not change revision; only resolveTurn and commitResult may');
    return { ok: true, cost: v.cost, plan: v.plan };
  }

  cancelOrder(order_id) {
    const i = this.c.order_queue.findIndex((q) => q.order_id === order_id);
    if (i < 0) return { ok: false, reason: 'reject.no_target' };
    const [q] = this.c.order_queue.splice(i, 1);
    refund(this.c, q.cost);
    this.emit('order_cancelled', { order_id });
    return { ok: true, refunded: q.cost };
  }

  endTurn() {
    if (this.c.pending_operation && this.c.pending_operation.state !== T.S.READY) {
      return { ok: false, reason: 'reject.mission_active' };
    }
    const report = resolveTurn(this.c, this.atlas, this.content);
    validateCampaign(this.c);
    this.persist('turn_committed');
    this.emit('turn_resolved', report);
    return { ok: true, report };
  }

  // ------------------------------------------------- mission transitions ----
  enterMission(request, nonce) {
    try {
      const ctx = T.beginOperation(this.c, this.atlas, this.content, request, { nonce, persist: (r) => this.persist(r) });
      this.emit('mission_preparing', ctx);
      return { ok: true, context: ctx };
    } catch (e) {
      if (e instanceof T.TransitionError) { this.emit('mission_entry_rejected', { code: e.code, detail: e.detail }); return { ok: false, code: e.code, detail: e.detail }; }
      throw e;
    }
  }

  markLoading() { T.markLoading(this.c, { persist: (r) => this.persist(r) }); this.emit('mission_loading', this.c.pending_operation.context); }
  markReady(readiness) {
    try { T.markReady(this.c, readiness, { persist: (r) => this.persist(r) }); this.emit('mission_ready', this.c.pending_operation.context); return { ok: true }; }
    catch (e) { this.emit('mission_load_failed', { code: e.code, detail: e.detail }); return { ok: false, code: e.code, detail: e.detail }; }
  }
  markPlaying() { T.markPlaying(this.c, { persist: (r) => this.persist(r) }); this.emit('mission_playing', this.c.pending_operation.context); }
  checkpointDistrict(cp) { T.saveDistrictCheckpoint(this.c, cp, { persist: (r) => this.persist(r) }); }

  /** Submit + commit + acknowledge. Idempotent end to end. */
  finishMission(result) {
    const sub = T.submitResult(this.c, result, { persist: (r) => this.persist(r) });
    if (sub.already_committed) { this.emit('mission_result_duplicate', { operation_id: result.operation_id }); return { ok: true, duplicate: true, applied: sub.applied }; }
    const com = T.commitResult(this.c, this.atlas, this.content, { persist: (r) => this.persist(r) });
    const ack = T.acknowledgeReturn(this.c, { persist: (r) => this.persist(r) });
    applySupply(this.c, this.atlas, buildSources(this.c, this.atlas));
    validateCampaign(this.c);
    this.persist('mission_result_final');
    this.emit('mission_resolved', { applied: ack, clamped: sub.clamped });
    return { ok: true, duplicate: false, applied: ack, clamped: sub.clamped, repeated: com.repeated };
  }

  abortMission(code, detail) {
    const out = T.failOperation(this.c, code, detail, { persist: (r) => this.persist(r) });
    this.emit('mission_aborted', out);
    return out;
  }

  recover() {
    const out = T.recoverOnLaunch(this.c, this.atlas, this.content, { persist: (r) => this.persist(r) });
    this.emit('recovered', out);
    return out;
  }
}
