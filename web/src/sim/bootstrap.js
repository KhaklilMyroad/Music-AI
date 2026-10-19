// Build an authoritative CampaignState from the content data. One place where
// the atlas becomes runtime state, so the map view and the resolver cannot
// disagree about the world.

import { makeCampaignState, makeTileState, makeUnitState, makeCityState, makeCivilianGroupState, makeUndergroundNetworkState, validateCampaign } from './contracts.js';
import { key, neighbors } from './hex.js';
import { applySupply } from './supply.js';
import { buildSources, recomputeCityServices, applyEvent } from './turn.js';
import { isOnOrAfter } from './dates.js';

const CONTROL_CHAR = { A: 'allied', X: 'axis', N: 'neutral', C: 'contested' };
const TERRAIN_CHAR = {
  '.': 'plain', f: 'farmland', h: 'hills', w: 'woods', b: 'bocage', m: 'mountain',
  d: 'desert', s: 'marsh', u: 'urban', p: 'port', '~': 'water', '#': 'impassable', ' ': 'plain',
};

export function newCampaign(atlas, content, opts = {}) {
  const c = makeCampaignState({
    campaign_id: opts.campaign_id || 'cmp_main',
    turn: 1,
    date: opts.date || content.campaign_range.start,
    mode: opts.mode || 'campaign',
    player_faction: opts.player_faction || 'french_resistance',
    resources: { materiel: 60, personnel: 30, intelligence: 2, documents: 0, ...(opts.resources || {}) },
    rng_seed: opts.seed ?? 20260101,
  });

  // tiles
  for (const th of atlas.theaters) {
    for (let r = 0; r < th.rows.length; r++) {
      const row = th.rows[r], ctrl = th.control[r], off = th.row_offset[r] ?? 0;
      for (let col = 0; col < row.length; col++) {
        const q = col + off;
        const terrain = TERRAIN_CHAR[row[col]] ?? 'plain';
        const rule = atlas.terrain_rules[terrain] || {};
        const id = `${th.id}:${q},${r}`;
        c.tiles[id] = makeTileState({
          tile_id: id, theater: th.id, q, r, terrain,
          control: CONTROL_CHAR[ctrl[col]] ?? 'neutral',
          passable: rule.passable !== false,
          naval_only: !!rule.naval_only,
          neighbors: [],
          discovered: isOnOrAfter(c.date, th.opens_on),
        });
      }
    }
  }
  // neighbour links, only within a theatre; sea links connect theatres
  for (const t of Object.values(c.tiles)) {
    t.neighbors = neighbors(t.q, t.r)
      .map(([q, r]) => `${t.theater}:${q},${r}`)
      .filter((id) => !!c.tiles[id]);
  }

  // cities
  for (const th of atlas.theaters) {
    for (const city of th.cities) {
      const tid = `${th.id}:${city.q},${city.r}`;
      const tile = c.tiles[tid];
      if (!tile) throw new Error(`city ${city.id} points at missing tile ${tid}`);
      c.cities[city.id] = makeCityState({
        city_id: city.id, label_key: city.label_key, theater: th.id, tile_id: tid,
        control: tile.control, facilities_max: city.facilities_max ?? 4, districts: city.districts || [],
      });
      tile.city_id = city.id;
    }
  }

  // communities and networks per city with a district (the places we actually play)
  const seedCommunities = opts.communities ?? true;
  if (seedCommunities) {
    for (const city of Object.values(c.cities)) {
      if (!city.districts.length) continue;
      const gid = `grp_${city.city_id}_community`;
      c.civilian_groups[gid] = makeCivilianGroupState({
        group_id: gid, label_key: `civgroup.${city.city_id}`, city_id: city.city_id, tile_id: city.tile_id,
        headcount: 240, community_id: `com_${city.city_id}`,
        household_ids: [`hh_${city.city_id}_a`, `hh_${city.city_id}_b`, `hh_${city.city_id}_c`],
        needs: { food: 0.8, water: 0.85, medicine: 0.6, shelter: 0.9 },
      });
      city.civilian_group_ids.push(gid);

      const nid = `net_${city.city_id}`;
      c.networks[nid] = makeUndergroundNetworkState({
        network_id: nid, label_key: `network.${city.city_id}`, city_id: city.city_id,
        cells: [{ cell_id: `${nid}_c1`, tile_id: city.tile_id, size: 4, compromised: false },
                { cell_id: `${nid}_c2`, tile_id: city.tile_id, size: 3, compromised: false }],
        contacts: [{ contact_id: `${nid}_k1`, role: 'printer', reliability: 0.8, compromised: false },
                   { contact_id: `${nid}_k2`, role: 'railwayman', reliability: 0.65, compromised: false }],
        area_tiles: [city.tile_id, ...c.tiles[city.tile_id].neighbors],
        access: 2, intelligence: 1, resources: { materiel: 8, personnel: 6, documents: 2 }, exposure: 0.1,
        safe_routes: [{ route_id: `${nid}_r1`, tile_ids: [city.tile_id], open: true }],
      });
      city.network_ids.push(nid);
    }
  }

  // starting formations: enough that supply, attack and defence are exercised
  for (const u of (opts.units ?? defaultUnits(atlas))) c.units[u.unit_id] = makeUnitState(u);

  // Fire every event already due on the start date, applying its effects, without
  // advancing the turn. A campaign begun in June 1944 must already have the
  // landings' supply source, the 1940 restrictions and the opened theatres.
  for (const ev of content.timeline_events.filter((e) => isOnOrAfter(c.date, e.date)).sort((a, b) => (a.date < b.date ? -1 : 1))) {
    c.fired_events.push(ev.id);
    applyEvent(c, atlas, ev, null);
  }
  for (const ch of content.chapters) {
    const dateOk = (!ch.date_window.from || isOnOrAfter(c.date, ch.date_window.from)) && (!ch.date_window.to || isOnOrAfter(ch.date_window.to, c.date));
    const evOk = ch.prerequisites.events.every((e) => c.fired_events.includes(e));
    if (dateOk && evOk && !ch.prerequisites.chapters.length) c.unlocked_chapters.push(ch.id);
  }

  applySupply(c, atlas, buildSources(c, atlas));
  for (const city of Object.values(c.cities)) { city.supply_access = c.tiles[city.tile_id].supply; recomputeCityServices(city, atlas); }
  validateCampaign(c);
  return c;
}

function defaultUnits(atlas) {
  const t = (th, q, r) => `${th}:${q},${r}`;
  return [
    { unit_id: 'u_res_cell_nor', unit_type: 'underground_cell', faction: 'french_resistance', label_key: 'unit.cell_normandy', tile_id: t('theater_western_europe', 3, 0), strength: 0.9, supply: 1 },
    { unit_id: 'u_partisan_nor', unit_type: 'partisan_squad',   faction: 'french_resistance', label_key: 'unit.partisans_bocage', tile_id: t('theater_western_europe', 2, 1), strength: 0.75, supply: 0.7 },
    { unit_id: 'u_res_cell_wsw', unit_type: 'underground_cell', faction: 'french_resistance', label_key: 'unit.cell_warsaw', tile_id: t('theater_eastern_europe', 3, 0), strength: 0.85, supply: 1 },
    { unit_id: 'u_axis_inf_nor', unit_type: 'infantry_division', faction: 'axis_army', label_key: 'unit.axis_infantry', tile_id: t('theater_western_europe', 2, 2), strength: 0.9, supply: 0.85 },
    { unit_id: 'u_axis_gar_nor', unit_type: 'garrison',          faction: 'axis_army', label_key: 'unit.axis_garrison', tile_id: t('theater_western_europe', 3, 0), strength: 0.7, supply: 0.8, status: ['entrenched'] },
    { unit_id: 'u_axis_gar_wsw', unit_type: 'garrison',          faction: 'axis_army', label_key: 'unit.axis_garrison_warsaw', tile_id: t('theater_eastern_europe', 3, 0), strength: 0.8, supply: 0.9, status: ['entrenched'] },
    { unit_id: 'u_axis_arm_east', unit_type: 'armoured_division', faction: 'axis_army', label_key: 'unit.axis_armour', tile_id: t('theater_eastern_europe', 2, 3), strength: 0.95, supply: 0.9 },
    { unit_id: 'u_cd_london',    unit_type: 'civil_defence_team', faction: 'uk_civil_defence', label_key: 'unit.warden_team', tile_id: t('theater_home_front', 2, 0), strength: 1, supply: 1 },
  ];
}

export { defaultUnits };
