import { describe, it, eq, ok, notOk, throws } from './runner.js';
import { atlas, content, districtNormandy, freshService, normandyRequest, FULL_READY } from './fixtures.js';
import * as T from '../src/sim/transition.js';
import { RESULT_VERSION } from '../src/sim/contracts.js';
import { digest } from '../src/sim/rng.js';
import { SaveService, memoryStore } from '../src/sim/save.js';
import { CampaignService } from '../src/sim/campaign.js';
import { migrate } from '../src/sim/save.js';

const okResult = (ctx, over = {}) => ({
  result_version: RESULT_VERSION, operation_id: ctx.operation_id, source_revision: ctx.source_revision,
  outcome: 'success', completed_objectives: ['obj_cut_field_line', 'obj_mark_battery', 'obj_reach_barn'],
  metrics: { elapsed_mission_seconds: 412, shots_fired: 0, times_detected: 0, alarm_raised: false },
  declared_resources: { intelligence: 3 }, ...over,
});

export default function run() {

describe('Transition: a double tap cannot create two operations (brief §17)', () => {
  it('the second entry attempt is refused while one is active', () => {
    const { svc } = freshService();
    const a = svc.enterMission(normandyRequest(), 'tap1');
    ok(a.ok);
    const b = svc.enterMission(normandyRequest(), 'tap2');
    notOk(b.ok, 'a second operation was created');
    eq(b.code, T.T_ERR.OPERATION_ACTIVE);
  });

  it('the refused attempt does not reserve a second cost', () => {
    const { svc } = freshService();
    svc.enterMission(normandyRequest(), 'tap1');
    const after1 = digest(svc.c.resources);
    svc.enterMission(normandyRequest(), 'tap2');
    eq(digest(svc.c.resources), after1, 'the refused tap still charged the player');
  });

  it('the same nonce yields the same operation id, so a retried tap is the same operation', () => {
    const { svc: a } = freshService();
    const { svc: b } = freshService();
    const ra = a.enterMission(normandyRequest(), 'same');
    const rb = b.enterMission(normandyRequest(), 'same');
    eq(ra.context.operation_id, rb.context.operation_id);
  });
});

describe('Transition: delivering a result twice applies it once (brief §17, §20)', () => {
  it('a repeated delivery of the same result is a no-op', () => {
    const { svc } = freshService();
    const { context } = svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    const first = svc.finishMission(okResult(context));
    ok(first.ok); notOk(first.duplicate);
    const intel1 = svc.c.resources.intelligence;
    const rev1 = svc.c.revision;

    const second = svc.finishMission(okResult(context));
    ok(second.duplicate, 'the duplicate was applied instead of ignored');
    eq(svc.c.resources.intelligence, intel1, 'a duplicate result paid the reward twice');
    eq(svc.c.revision, rev1, 'a duplicate result bumped the revision');
  });

  it('a result delivered after the pending record was cleared is still recognised', () => {
    const { svc } = freshService();
    const { context } = svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    svc.finishMission(okResult(context));
    eq(svc.c.pending_operation, null, 'pending record was not cleared');
    const again = svc.finishMission(okResult(context));
    ok(again.duplicate);
  });

  it('commitResult is itself idempotent', () => {
    const { svc } = freshService();
    const { context } = svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    T.submitResult(svc.c, okResult(context));
    const one = T.commitResult(svc.c, atlas, content);
    notOk(one.repeated);
    const two = T.commitResult(svc.c, atlas, content);
    ok(two.repeated, 'a second commit re-applied the effects');
    eq(digest(one.applied), digest(two.applied));
  });
});

describe('Transition: a failed load costs the player nothing (brief §17)', () => {
  it('a missing content pack refuses entry and reserves nothing', () => {
    const { svc } = freshService();
    const before = digest(svc.c);
    const out = svc.enterMission(normandyRequest({ district_id: 'district_not_installed' }), 'n');
    notOk(out.ok);
    eq(out.code, T.T_ERR.CONTENT_MISSING);
    eq(digest(svc.c), before, 'a refused entry changed state');
  });

  it('a mission is not playable until player, collision, navigation, objectives, UI and audio are ready', () => {
    const { svc } = freshService();
    svc.enterMission(normandyRequest(), 'n');
    svc.markLoading();
    const partial = svc.markReady({ ...FULL_READY, navigation: false, audio: false });
    notOk(partial.ok, 'the mission went playable with navigation and audio missing');
    eq(partial.code, T.T_ERR.NOT_PLAYABLE);
    ok(partial.detail.includes('navigation') && partial.detail.includes('audio'));
  });

  it('retrying after a technical failure does not charge twice', () => {
    const { svc } = freshService();
    const r0 = { ...svc.c.resources };
    svc.enterMission(normandyRequest({ order: { order_id: 'sab', kind: 'sabotage', unit_id: 'u_res_cell_nor', tile_id: 'theater_western_europe:3,0' } }), 'n1');
    svc.markLoading();
    svc.markReady({ ...FULL_READY, collision: false });
    svc.abortMission('load_failed', 'collision');
    eq(svc.c.resources, r0, 'the failed attempt kept the player\'s materiel');
    const retry = svc.enterMission(normandyRequest({ order: { order_id: 'sab2', kind: 'sabotage', unit_id: 'u_res_cell_nor', tile_id: 'theater_western_europe:3,0' } }), 'n2');
    ok(retry.ok, 'retry was refused');
    eq(svc.c.resources.materiel, r0.materiel - 4, 'the retry charged more than one sabotage');
  });

  it('an illegal strategic order refuses entry before any operation exists', () => {
    const { svc } = freshService();
    const out = svc.enterMission(normandyRequest({ order: { order_id: 'bad', kind: 'attack', unit_id: 'u_res_cell_nor', tile_id: 'theater_western_europe:4,0' } }), 'n');
    notOk(out.ok);
    eq(out.code, T.T_ERR.ORDER_REJECTED);
    eq(svc.c.pending_operation, null);
  });

  it('an illegal state transition throws rather than being silently allowed', () => {
    const { svc } = freshService();
    svc.enterMission(normandyRequest(), 'n');
    throws(() => svc.markPlaying(), 'illegal_state');
  });
});

describe('Transition: recovery at every boundary (brief §17, §20)', () => {
  const boundaries = ['PreparingMission', 'LoadingMission', 'MissionReady', 'PlayingMission', 'ResolvingMission', 'Returning'];

  const drive = (svc, upto, ctxOut) => {
    const { context } = svc.enterMission(normandyRequest(), 'n');
    if (ctxOut) ctxOut.ctx = context;
    if (upto === 'PreparingMission') return;
    svc.markLoading(); if (upto === 'LoadingMission') return;
    svc.markReady(FULL_READY); if (upto === 'MissionReady') return;
    svc.markPlaying(); if (upto === 'PlayingMission') return;
    const persist = { persist: (r) => svc.persist(r) };
    T.submitResult(svc.c, okResult(context), persist); if (upto === 'ResolvingMission') return;
    T.commitResult(svc.c, atlas, content, persist); if (upto === 'Returning') return;
  };

  for (const b of boundaries) {
    it(`terminating at ${b} recovers to a usable state with no duplicate outcome`, () => {
      const { svc, store } = freshService();
      const holder = {};
      drive(svc, b, holder);
      // Simulate process termination: reload from the auto save only.
      const loaded = svc.saves.load('auto');
      ok(loaded.ok, 'the auto save was unreadable');
      const svc2 = new CampaignService(loaded.campaign, atlas, content, svc.saves);
      const rec = svc2.recover();
      ok(rec.action !== 'unknown_state', `recovery did not understand ${b}`);

      if (['PreparingMission', 'LoadingMission', 'MissionReady'].includes(b)) {
        eq(rec.action, 'cancelled_entry', `${b} should cancel a never-played entry`);
        eq(svc2.c.pending_operation, null);
        // and re-entry is possible
        ok(svc2.enterMission(normandyRequest(), 'n2').ok, 're-entry after recovery was refused');
      } else if (b === 'PlayingMission') {
        ok(['resume_mission', 'restart_mission'].includes(rec.action), rec.action);
        eq(rec.operation_id, holder.ctx.operation_id, 'the operation id changed across recovery');
        notOk(svc2.c.committed_operations.includes(holder.ctx.operation_id), 'an unfinished mission was counted as committed');
      } else if (b === 'ResolvingMission') {
        eq(rec.action, 'resumed_commit', rec.action);
        ok(svc2.c.committed_operations.includes(holder.ctx.operation_id));
        // the reward landed exactly once
        const again = svc2.finishMission(okResult(holder.ctx));
        ok(again.duplicate, 'the resumed commit allowed a second application');
      } else if (b === 'Returning') {
        eq(rec.action, 'acknowledged', rec.action);
        ok(svc2.c.committed_operations.includes(holder.ctx.operation_id));
        eq(svc2.c.pending_operation, null);
      }
    });
  }

  it('completion is never inferred from a missing scene', () => {
    const { svc } = freshService();
    const { context } = svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    // No district checkpoint, no result: the mission simply vanished.
    const rec = svc.recover();
    eq(rec.action, 'restart_mission', 'a vanished mission was treated as finished');
    notOk(svc.c.committed_operations.includes(context.operation_id));
    eq(svc.c.completed_chapters.length, 0, 'a chapter was marked complete without a result');
  });

  it('a mid-mission checkpoint resumes the same operation rather than restarting it', () => {
    const { svc } = freshService();
    const { context } = svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    svc.checkpointDistrict({
      checkpoint_version: 2, district_id: districtNormandy.id, district_content_version: districtNormandy.content_version,
      player: { position: [40, 1.7, 60], yaw: 1.2, pitch: 0, posture: 'crouch', health: 86 },
      inventory: { amm_9x19: 24 }, mission_flags: { obj_cut_field_line: true },
      weapon_states: { wpn_pistol_civ: { loaded: 6, reserve: 18, chambered: true } },
      local_time_hours: 9.5, weather: 'overcast',
    });
    const loaded = svc.saves.load('auto');
    const svc2 = new CampaignService(loaded.campaign, atlas, content, svc.saves);
    const rec = svc2.recover();
    eq(rec.action, 'resume_mission');
    eq(rec.checkpoint.player.posture, 'crouch');
    eq(rec.checkpoint.mission_flags.obj_cut_field_line, true);
    eq(rec.operation_id, context.operation_id);
  });

  it('an interrupted reload resumes or reverts per the checkpoint, never duplicating rounds', () => {
    const { svc } = freshService();
    svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    svc.checkpointDistrict({
      checkpoint_version: 2, district_id: districtNormandy.id, district_content_version: districtNormandy.content_version,
      player: { position: [10, 1.7, 10], yaw: 0, pitch: 0, posture: 'stand', health: 100 },
      weapon_states: { wpn_pistol_civ: { loaded: 3, reserve: 15, chambered: true } },
      inventory: { amm_9x19: 15 },
      interrupted_action: { kind: 'reload', progress: 0.4, revert_to: { loaded: 3, reserve: 15 } },
    });
    const loaded = svc.saves.load('auto');
    const cp = loaded.district_checkpoint;
    const total = cp.weapon_states.wpn_pistol_civ.loaded + cp.weapon_states.wpn_pistol_civ.reserve;
    eq(total, 18, 'rounds were duplicated or lost across the interruption');
    eq(cp.interrupted_action.revert_to.loaded + cp.interrupted_action.revert_to.reserve, 18);
  });
});

describe('Transition: the authorised consequence actually lands (brief §7, §20)', () => {
  it('a successful defence can remove the attacking formation, because the chapter says so', () => {
    const { svc } = freshService();
    svc.c.completed_chapters.push('chapter_nor_01');
    svc.c.resources.intelligence = 5;
    svc.c.unlocked_chapters.push('chapter_nor_02');
    const attacker = 'u_axis_inf_nor';
    svc.c.units[attacker].tile_id = 'theater_western_europe:3,0';
    delete svc.c.units.u_axis_gar_nor;          // leave exactly one candidate, so the test is unambiguous
    const { context } = svc.enterMission(normandyRequest({ chapter_id: 'chapter_nor_02' }), 'd1');
    ok(context.outcome_bounds.may_remove_attacking_formation, 'the chapter did not authorise formation removal');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    const out = svc.finishMission({
      result_version: RESULT_VERSION, operation_id: context.operation_id, source_revision: context.source_revision,
      outcome: 'success', completed_objectives: ['obj_hold_crossroad', 'obj_treat_wounded'],
      requests: { remove_attacking_formation: true },
    });
    ok(out.ok);
    notOk(svc.c.units[attacker], 'the attacking formation survived an authorised rout');
    ok(out.applied.changes.some((c) => c.what === 'formation_removed'));
  });

  it('a mission whose chapter does not authorise it cannot remove a formation', () => {
    const { svc } = freshService();
    const { context } = svc.enterMission(normandyRequest(), 'n');   // chapter_nor_01: sabotage, no rout
    notOk(context.outcome_bounds.may_remove_attacking_formation);
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    const unitsBefore = Object.keys(svc.c.units).length;
    const out = svc.finishMission(okResult(context, { requests: { remove_attacking_formation: true } }));
    eq(Object.keys(svc.c.units).length, unitsBefore, 'a sabotage mission destroyed a division');
    ok(out.clamped.includes('remove_attacking_formation'));
  });

  it('the result report says exactly what changed and why', () => {
    const { svc } = freshService();
    const { context } = svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    const out = svc.finishMission(okResult(context));
    ok(out.applied.changes.length >= 2, 'the player was told nothing about the consequences');
    ok(out.applied.changes.some((c) => c.what === 'chapter_completed'));
    ok(out.applied.changes.some((c) => c.what === 'resource' && c.key === 'intelligence'));
  });

  it('campaign time only advances when the operation declares a cost', () => {
    const { svc } = freshService();
    const t0 = svc.c.turn, d0 = svc.c.date;
    const { context } = svc.enterMission(normandyRequest(), 'n');   // nor_01 costs 0 turns
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    svc.finishMission(okResult(context));
    eq(svc.c.turn, t0, 'a zero-cost operation advanced the war');
    eq(svc.c.date, d0);
  });

  it('a strategic order is refused while a mission is active', () => {
    const { svc } = freshService();
    svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    const out = svc.submitOrder({ order_id: 'x', kind: 'hide', unit_id: 'u_res_cell_nor' });
    notOk(out.ok, 'the campaign accepted an order during a mission');
    const turn = svc.endTurn();
    notOk(turn.ok, 'the war advanced while a mission was being played');
  });
});

}
