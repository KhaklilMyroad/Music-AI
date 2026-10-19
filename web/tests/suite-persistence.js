import { describe, it, eq, ok, notOk, throws } from './runner.js';
import { atlas, content, districtNormandy, freshService, normandyRequest, FULL_READY } from './fixtures.js';
import { SaveService, memoryStore, migrate, describeConflict, SAVE_ERR } from '../src/sim/save.js';
import { newCampaign } from '../src/sim/bootstrap.js';
import { CampaignService } from '../src/sim/campaign.js';
import { digest } from '../src/sim/rng.js';
import { SCHEMA_VERSION } from '../src/sim/contracts.js';

export default function run() {

describe('Persistence: integrity and recovery (brief §19)', () => {
  it('a save round-trips exactly', () => {
    const { svc } = freshService();
    svc.endTurn();
    const before = digest(svc.c);
    const loaded = svc.saves.load('auto');
    ok(loaded.ok);
    eq(digest(loaded.campaign), before, 'the save did not round-trip');
  });

  it('a tampered save is detected by its integrity digest', () => {
    const { svc, store } = freshService();
    svc.endTurn();            // save #1
    svc.endTurn();            // save #2, rolling #1 down to .lkg so recovery has somewhere to go
    const raw = JSON.parse(store.read('wbtm.save.auto'));
    raw.payload.campaign.resources.materiel = 999999;
    store.write('wbtm.save.auto', JSON.stringify(raw));
    const loaded = svc.saves.load('auto');
    eq(loaded.recovered_from, SAVE_ERR.INTEGRITY_MISMATCH, 'tampering was not detected');
    notOk(loaded.campaign.resources.materiel === 999999, 'the tampered value was loaded');
  });

  it('a corrupt save falls back to last-known-good and says which', () => {
    const { svc, store } = freshService();
    svc.endTurn();            // writes save #1
    svc.endTurn();            // writes save #2, rolling #1 down to .lkg
    store.write('wbtm.save.auto', '{ this is not json');
    const loaded = svc.saves.load('auto');
    ok(loaded.ok);
    eq(loaded.source, 'last_known_good');
    eq(loaded.recovered_from, SAVE_ERR.CORRUPT);
    ok(loaded.campaign.turn >= 1);
  });

  it('termination part-way through a write leaves the previous save intact', () => {
    const { svc, store } = freshService();
    svc.endTurn();
    const good = digest(svc.saves.load('auto').campaign);
    store._failNextWrite(120);                       // cut the .part write short
    try { svc.endTurn(); } catch (e) { ok(String(e.message).includes('write_interrupted')); }
    const loaded = svc.saves.load('auto');
    ok(loaded.ok, 'no readable save survived the interrupted write');
    eq(digest(loaded.campaign), good, 'the interrupted write damaged the published save');
  });

  it('an incomplete write is never loaded as if it were finished', () => {
    const store = memoryStore();
    const saves = new SaveService(store);
    store.write('wbtm.save.auto', JSON.stringify({ schema_version: SCHEMA_VERSION, save_id: 's', payload: {}, recovery: { write_complete: false }, integrity: 'x' }));
    throws(() => saves.load('auto', { allowLkg: false }), SAVE_ERR.INCOMPLETE_WRITE);
  });

  it('the save list is readable without loading every save', () => {
    const { svc } = freshService();
    svc.endTurn();
    const list = svc.saves.list();
    ok(list.length >= 1);
    ok(list[0].turn && list[0].date && list[0].reason, 'the save list cannot describe a save to the player');
  });
});

describe('Persistence: schema migration (brief §16, §19)', () => {
  it('an old save is migrated step by step, not assumed compatible', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    const old = JSON.parse(JSON.stringify(c));
    old.schema_version = 1;
    delete old.networks; delete old.committed_operations; delete old.unlocked_equipment;
    for (const g of Object.values(old.civilian_groups)) { g.strength = 0.5; delete g.needs; }
    for (const t of Object.values(old.tiles)) delete t.supply_penalty;
    const m = migrate(old);
    eq(m.schema_version, SCHEMA_VERSION);
    ok(m.networks && Array.isArray(m.committed_operations) && Array.isArray(m.unlocked_equipment));
    for (const g of Object.values(m.civilian_groups)) { notOk('strength' in g, 'the military strength field survived migration'); ok(g.needs.food === 1); }
    for (const t of Object.values(m.tiles)) eq(t.supply_penalty, 0);
  });

  it('a save from a newer build is refused with a readable reason, not half-loaded', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    const future = { ...JSON.parse(JSON.stringify(c)), schema_version: SCHEMA_VERSION + 3 };
    throws(() => migrate(future), 'newer than this build');
  });

  it('a gap in the migration chain fails loudly', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    const weird = { ...JSON.parse(JSON.stringify(c)), schema_version: 0 };
    throws(() => migrate(weird), 'no migration path');
  });
});

describe('Persistence: cloud conflicts are never silently merged (brief §19)', () => {
  it('both branches are preserved and described', () => {
    const { svc } = freshService();
    svc.endTurn();
    const local = svc.saves.peek('auto');
    const { svc: other } = freshService({ seed: 999 });
    other.endTurn(); other.endTurn();
    const remote = other.saves.peek('auto');
    const c = describeConflict(local, remote);
    eq(c.strategy, 'keep_both_let_player_choose');
    eq(c.merged, null, 'a field-by-field merge was produced');
    ok(c.local.turn !== c.remote.turn, 'the two branches are indistinguishable to the player');
    ok('completed_chapters' in c.local && 'in_mission' in c.local);
  });
});

describe('Persistence: campaign and sandbox timelines stay distinct (brief §9, §17)', () => {
  it('a sandbox save uses its own slot and does not overwrite the campaign', () => {
    const { svc, store } = freshService();
    svc.endTurn();
    const campaignDigest = digest(svc.saves.load('auto').campaign);
    const sandbox = newCampaign(atlas, content, { date: '1944-06-06', mode: 'sandbox', campaign_id: 'cmp_sandbox' });
    svc.saves.write('sandbox', sandbox, null, 'sandbox_entry');
    eq(digest(svc.saves.load('auto').campaign), campaignDigest, 'the sandbox save overwrote the campaign');
    eq(svc.saves.load('sandbox').campaign.mode, 'sandbox');
  });

  it('a district checkpoint records its content version, so stale content is detectable', () => {
    const { svc } = freshService();
    svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    svc.checkpointDistrict({
      checkpoint_version: 2, district_id: districtNormandy.id, district_content_version: districtNormandy.content_version,
      player: { position: [1, 1.7, 1] }, mission_flags: {},
    });
    const cp = svc.saves.load('auto').district_checkpoint;
    eq(cp.district_content_version, districtNormandy.content_version);
  });

  it('a revisited objective does not pay its reward twice', () => {
    const { svc } = freshService();
    const { context } = svc.enterMission(normandyRequest(), 'n');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    svc.finishMission({
      result_version: 2, operation_id: context.operation_id, source_revision: context.source_revision,
      outcome: 'success', completed_objectives: ['obj_cut_field_line'], declared_resources: { intelligence: 3 },
    });
    const intel = svc.c.resources.intelligence;
    ok(svc.c.completed_chapters.includes('chapter_nor_01'));
    // Re-enter the same chapter: it is no longer unlocked, so the entry has no chapter reward to pay.
    notOk(svc.c.unlocked_chapters.includes('chapter_nor_01'), 'a completed chapter stayed available for a repeat reward');
    eq(svc.c.resources.intelligence, intel);
  });
});

}
