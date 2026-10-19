// Saving, integrity, last-known-good and schema migration (brief §19).
//
// The store is injected so the same logic runs over localStorage in the browser,
// a file in Node tests, and Godot's user:// directory.
//
// Write protocol (survives process termination mid-write):
//   1 write <slot>.part with write_complete=false
//   2 compute and attach the integrity digest, rewrite <slot>.part complete
//   3 copy the current <slot> to <slot>.lkg
//   4 rename <slot>.part -> <slot>
// A crash at any step leaves either the old save or the .lkg intact.

import { digest } from './rng.js';
import { makeSaveEnvelope, validateSaveEnvelope, validateCampaign, SCHEMA_VERSION, ValidationError } from './contracts.js';

export class SaveError extends Error {
  constructor(code, detail) { super(`${code}${detail ? `: ${detail}` : ''}`); this.name = 'SaveError'; this.code = code; this.detail = detail; }
}
export const SAVE_ERR = {
  NOT_FOUND: 'save.not_found',
  CORRUPT: 'save.corrupt',
  INCOMPLETE_WRITE: 'save.incomplete_write',
  INTEGRITY_MISMATCH: 'save.integrity_mismatch',
  UNSUPPORTED_SCHEMA: 'save.unsupported_schema',
  NO_SPACE: 'save.no_space',
};

/** In-memory store used by tests; mirrors the three operations a real store needs. */
export function memoryStore() {
  const m = new Map();
  let failNextWriteAfterBytes = null;
  return {
    _map: m,
    /** Simulate OS termination part-way through a write. */
    _failNextWrite(after) { failNextWriteAfterBytes = after; },
    read: (k) => (m.has(k) ? m.get(k) : null),
    write: (k, v) => {
      if (failNextWriteAfterBytes !== null) {
        const truncated = v.slice(0, failNextWriteAfterBytes);
        failNextWriteAfterBytes = null;
        m.set(k, truncated);
        throw new SaveError('save.write_interrupted', k);
      }
      m.set(k, v);
    },
    remove: (k) => m.delete(k),
    keys: () => [...m.keys()].sort(),
  };
}

export class SaveService {
  constructor(store, { engine_build = 'dev', contentVersions = {} } = {}) {
    this.store = store;
    this.engine_build = engine_build;
    this.contentVersions = contentVersions;
  }

  slotKey(slot) { return `wbtm.save.${slot}`; }
  lkgKey(slot) { return `wbtm.save.${slot}.lkg`; }
  partKey(slot) { return `wbtm.save.${slot}.part`; }

  /** Durable write. `reason` is recorded so a QA log shows which boundary saved. */
  write(slot, campaign, districtCheckpoint, reason = 'manual') {
    const env = makeSaveEnvelope({
      save_id: `${campaign.campaign_id}:${slot}:${campaign.revision}`,
      slot, mode: campaign.mode, revision: campaign.revision,
      saved_at: new Date().toISOString(),
      engine_build: this.engine_build,
      content_versions: this.contentVersions,
      previous_save_id: this.peek(slot)?.save_id ?? null,
      payload: { campaign, district_checkpoint: districtCheckpoint ?? null, reason },
    });
    // step 1: incomplete marker
    env.recovery.write_complete = false;
    this.store.write(this.partKey(slot), JSON.stringify(env));
    // step 2: digest over the payload only, so recovery metadata can change without invalidating it
    env.integrity = digest(env.payload);
    env.recovery.write_complete = true;
    this.store.write(this.partKey(slot), JSON.stringify(env));
    // step 3: roll the current save down to last-known-good
    const current = this.store.read(this.slotKey(slot));
    if (current) this.store.write(this.lkgKey(slot), current);
    // step 4: publish
    this.store.write(this.slotKey(slot), this.store.read(this.partKey(slot)));
    this.store.remove(this.partKey(slot));
    return env;
  }

  peek(slot) {
    const raw = this.store.read(this.slotKey(slot));
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }

  /** Load with full validation. Falls back to last-known-good and says so. */
  load(slot, { allowLkg = true } = {}) {
    const attempt = (key, source) => {
      const raw = this.store.read(key);
      if (!raw) return { ok: false, error: new SaveError(SAVE_ERR.NOT_FOUND, key) };
      let env;
      try { env = JSON.parse(raw); } catch (e) { return { ok: false, error: new SaveError(SAVE_ERR.CORRUPT, `${key}: unparseable`) }; }
      try { validateSaveEnvelope(env); } catch (e) {
        const code = env?.recovery?.write_complete === false ? SAVE_ERR.INCOMPLETE_WRITE : SAVE_ERR.CORRUPT;
        return { ok: false, error: new SaveError(code, e.message) };
      }
      if (digest(env.payload) !== env.integrity) return { ok: false, error: new SaveError(SAVE_ERR.INTEGRITY_MISMATCH, key) };
      let campaign;
      try { campaign = migrate(env.payload.campaign); } catch (e) { return { ok: false, error: new SaveError(SAVE_ERR.UNSUPPORTED_SCHEMA, e.message) }; }
      try { validateCampaign(campaign); } catch (e) { return { ok: false, error: new SaveError(SAVE_ERR.CORRUPT, e.message) }; }
      return { ok: true, envelope: env, campaign, district_checkpoint: env.payload.district_checkpoint ?? null, source };
    };

    const primary = attempt(this.slotKey(slot), 'primary');
    if (primary.ok) return primary;
    if (!allowLkg) throw primary.error;
    const lkg = attempt(this.lkgKey(slot), 'last_known_good');
    if (lkg.ok) return { ...lkg, recovered_from: primary.error.code };
    // Also inspect an orphaned .part: it may be the only thing left after a crash.
    const part = attempt(this.partKey(slot), 'interrupted_part');
    if (part.ok) return { ...part, recovered_from: primary.error.code };
    throw primary.error;
  }

  list() {
    return this.store.keys()
      .filter((k) => k.startsWith('wbtm.save.') && !k.endsWith('.lkg') && !k.endsWith('.part'))
      .map((k) => { try { const e = JSON.parse(this.store.read(k)); return { slot: e.slot, save_id: e.save_id, revision: e.revision, mode: e.mode, saved_at: e.saved_at, turn: e.payload?.campaign?.turn, date: e.payload?.campaign?.date, reason: e.payload?.reason }; } catch { return { slot: k, corrupt: true }; } });
  }
}

// ------------------------------------------------------------- migrations ----
// A migration is explicit and ordered. Sharing JSON syntax is not compatibility:
// a save from a schema we have no migration for is refused, loudly.
const MIGRATIONS = [
  { from: 1, to: 2, apply: (c) => { c.networks = c.networks || {}; c.committed_operations = c.committed_operations || []; return c; } },
  { from: 2, to: 3, apply: (c) => { for (const g of Object.values(c.civilian_groups || {})) { delete g.strength; g.needs = { food: 1, water: 1, medicine: 1, shelter: 1, ...(g.needs || {}) }; } return c; } },
  { from: 3, to: 4, apply: (c) => { for (const t of Object.values(c.tiles || {})) t.supply_penalty = t.supply_penalty ?? 0; c.unlocked_equipment = c.unlocked_equipment || []; return c; } },
];

export function migrate(campaign) {
  let c = JSON.parse(JSON.stringify(campaign));
  let v = c.schema_version ?? 1;
  if (v > SCHEMA_VERSION) throw new Error(`save schema ${v} is newer than this build (${SCHEMA_VERSION}); update the game to load it`);
  while (v < SCHEMA_VERSION) {
    const step = MIGRATIONS.find((m) => m.from === v);
    if (!step) throw new Error(`no migration path from schema ${v} to ${SCHEMA_VERSION}`);
    c = step.apply(c);
    v = step.to;
    c.schema_version = v;
  }
  return c;
}

/**
 * Cloud conflict handling: never merge field by field. Both branches are kept
 * and described so the player chooses a continuation.
 */
export function describeConflict(localEnv, remoteEnv) {
  const d = (e) => ({
    save_id: e.save_id, revision: e.revision, turn: e.payload.campaign.turn,
    date: e.payload.campaign.date, mode: e.mode, saved_at: e.saved_at,
    completed_chapters: e.payload.campaign.completed_chapters.length,
    in_mission: !!e.payload.district_checkpoint,
  });
  return { strategy: 'keep_both_let_player_choose', local: d(localEnv), remote: d(remoteEnv), merged: null };
}
