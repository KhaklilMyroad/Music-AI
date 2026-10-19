import fs from 'node:fs';
import { newCampaign } from '../src/sim/bootstrap.js';
import { CampaignService } from '../src/sim/campaign.js';
import { SaveService, memoryStore } from '../src/sim/save.js';

const R = new URL('../../shared-data/', import.meta.url).pathname;
const read = (p) => JSON.parse(fs.readFileSync(R + p, 'utf8'));

export const atlas = read('theaters.json');
export const chapters = read('chapters.json');
export const weapons = read('weapons.json');
export const history = read('historical-records.json');
export const districtNormandy = read('districts/district_normandy_bocage.json');
export const provenance = read('asset-provenance.json');
export const locales = { en: read('locales/en.json'), he: read('locales/he.json') };

export const content = {
  ...chapters,
  districts: { [districtNormandy.id]: districtNormandy },
};

export function freshService(opts = {}) {
  const c = newCampaign(atlas, content, { date: '1944-06-06', seed: 7, ...opts });
  const store = memoryStore();
  const saves = new SaveService(store, { engine_build: 'test', contentVersions: { [districtNormandy.id]: districtNormandy.content_version } });
  return { svc: new CampaignService(c, atlas, content, saves), store, saves, campaign: c };
}

export function normandyRequest(overrides = {}) {
  return {
    chapter_id: 'chapter_nor_01',
    district_id: 'district_normandy_bocage',
    tile_id: 'theater_western_europe:3,0',
    unit_id: 'u_res_cell_nor',
    loadout: ['tool_wire_cutters', 'wpn_pistol_civ'],
    ...overrides,
  };
}

export const FULL_READY = { player: true, collision: true, navigation: true, objectives: true, ui: true, audio: true };
