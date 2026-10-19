// Strategic map view. Canvas 2D, because a hex map wants crisp lines and text
// at phone DPI far more than it wants a 3D pipeline, and leaving WebGL free for
// the mission scene is the memory decision the brief asks for.
//
// Touch: tap to select, drag to pan, pinch to zoom. No long press is ever the
// only way to reach an action.

import { toPixel, fromPixel, distance } from '../sim/hex.js';
import { UNIT_CAPABILITIES } from '../sim/contracts.js';

const TERRAIN_FILL = {
  plain:   ['#54573c', '#464832'],
  farmland:['#6b6b3f', '#585835'],
  hills:   ['#5b5340', '#4a4435'],
  woods:   ['#3b4a33', '#303d2a'],
  bocage:  ['#47553a', '#3a4730'],
  mountain:['#565553', '#474644'],
  desert:  ['#8a7349', '#75613d'],
  marsh:   ['#44524c', '#384440'],
  urban:   ['#5c5a56', '#4b4945'],
  port:    ['#4e5a63', '#414b53'],
  water:   ['#223542', '#1b2a35'],
  impassable: ['#2a2a2a', '#222222'],
};
const CONTROL_TINT = { allied: 'rgba(92,127,153,.34)', axis: 'rgba(168,72,47,.34)', contested: 'rgba(201,143,54,.30)', neutral: 'rgba(107,116,126,.12)' };

export class MapView {
  constructor(canvas, svc, i18n, settings) {
    this.cv = canvas;
    this.ctx = canvas.getContext('2d', { alpha: false });
    this.svc = svc;
    this.i18n = i18n;
    this.s = settings;
    this.theater = 'theater_western_europe';
    this.size = 38;                 // hex radius in CSS px at zoom 1
    this.zoom = 1;
    this.pan = { x: 0, y: 0 };
    this.selection = null;          // { kind:'unit'|'tile'|'city', id }
    this.range = null;              // movement overlay
    this.hoverPath = null;
    this.onSelect = () => {};
    this.onTapEmpty = () => {};
    // Tapping a tile inside the selected unit's movement overlay is a move
    // target, not a new selection. The shell handles it; the view does not
    // get monkey-patched to find out.
    this.onMoveTarget = () => {};
    this.pointers = new Map();
    this.pinch = null;
    this.dragged = 0;
    this.dpr = 1;
    this.bind();
    this.resize();
  }

  get campaign() { return this.svc.c; }

  theatersOpen() {
    const c = this.campaign;
    return this.svc.atlas.theaters.filter((t) => c.history_flags[`theater_open:${t.id}`] || t.opens_on <= c.date);
  }

  setTheater(id) { this.theater = id; this.centreOnTheater(); this.draw(); }

  resize() {
    const r = this.cv.parentElement.getBoundingClientRect();
    this.dpr = Math.min(window.devicePixelRatio || 1, this.s.rendererOptions().pixelRatioCap);
    this.cv.width = Math.max(1, Math.round(r.width * this.dpr));
    this.cv.height = Math.max(1, Math.round(r.height * this.dpr));
    this.cv.style.width = `${r.width}px`;
    this.cv.style.height = `${r.height}px`;
    this.w = r.width; this.h = r.height;
    this.draw();
  }

  centreOnTheater() {
    const tiles = this.tilesOf(this.theater);
    if (!tiles.length) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const t of tiles) {
      const p = toPixel(t.q, t.r, this.size);
      minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
    }
    const spanX = maxX - minX + this.size * 3, spanY = maxY - minY + this.size * 3;
    this.zoom = Math.max(0.55, Math.min(1.6, Math.min((this.w - 24) / spanX, (this.h - 150) / spanY)));
    this.pan = { x: this.w / 2 - ((minX + maxX) / 2) * this.zoom, y: (this.h - 60) / 2 - ((minY + maxY) / 2) * this.zoom + 20 };
  }

  tilesOf(theater) { return Object.values(this.campaign.tiles).filter((t) => t.theater === theater); }

  toScreen(q, r) { const p = toPixel(q, r, this.size); return { x: p.x * this.zoom + this.pan.x, y: p.y * this.zoom + this.pan.y }; }
  fromScreen(x, y) { return fromPixel((x - this.pan.x) / this.zoom, (y - this.pan.y) / this.zoom, this.size); }

  bind() {
    const el = this.cv;
    el.addEventListener('pointerdown', (e) => {
      el.setPointerCapture(e.pointerId);
      this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY });
      this.dragged = 0;
      if (this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()];
        this.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), zoom: this.zoom, cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 };
      }
    });
    el.addEventListener('pointermove', (e) => {
      const p = this.pointers.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;
      this.dragged += Math.hypot(dx, dy);
      if (this.pointers.size === 2 && this.pinch) {
        const [a, b] = [...this.pointers.values()];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        const next = Math.max(0.45, Math.min(2.6, this.pinch.zoom * (d / this.pinch.d)));
        const rect = el.getBoundingClientRect();
        const cx = this.pinch.cx - rect.left, cy = this.pinch.cy - rect.top;
        const wx = (cx - this.pan.x) / this.zoom, wy = (cy - this.pan.y) / this.zoom;
        this.zoom = next;
        this.pan.x = cx - wx * this.zoom; this.pan.y = cy - wy * this.zoom;
      } else if (this.pointers.size === 1) {
        this.pan.x += dx; this.pan.y += dy;
      }
      this.draw();
    });
    const up = (e) => {
      const p = this.pointers.get(e.pointerId);
      this.pointers.delete(e.pointerId);
      if (this.pointers.size < 2) this.pinch = null;
      if (!p) return;
      if (this.dragged < 12 && this.pointers.size === 0) {
        const rect = el.getBoundingClientRect();
        this.handleTap(e.clientX - rect.left, e.clientY - rect.top);
      }
    };
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', (e) => { this.pointers.delete(e.pointerId); this.pinch = null; });
    el.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left, cy = e.clientY - rect.top;
      const wx = (cx - this.pan.x) / this.zoom, wy = (cy - this.pan.y) / this.zoom;
      this.zoom = Math.max(0.45, Math.min(2.6, this.zoom * (e.deltaY < 0 ? 1.12 : 0.89)));
      this.pan.x = cx - wx * this.zoom; this.pan.y = cy - wy * this.zoom;
      this.draw();
    }, { passive: false });
    addEventListener('resize', () => this.resize());
  }

  handleTap(x, y) {
    const [q, r] = this.fromScreen(x, y);
    const id = `${this.theater}:${q},${r}`;
    const tile = this.campaign.tiles[id];
    if (!tile) { this.onTapEmpty(); return; }

    if (this.selection?.kind === 'unit' && (this.range?.tiles || []).some((t) => t.tile_id === id)) {
      this.previewPath(id);
      this.onMoveTarget(this.selection.id, id);
      return;
    }

    // Prefer a unit on the tile the player can order, then the city, then the tile.
    const mine = Object.values(this.campaign.units)
      .filter((u) => u.tile_id === id && u.faction === this.campaign.player_faction)
      .sort((a, b) => (a.unit_id < b.unit_id ? -1 : 1));
    if (mine.length) { this.select({ kind: 'unit', id: mine[0].unit_id }); return; }
    const others = Object.values(this.campaign.units).filter((u) => u.tile_id === id && UNIT_CAPABILITIES[u.unit_type].visible_on_map);
    if (tile.city_id) { this.select({ kind: 'city', id: tile.city_id }); return; }
    if (others.length) { this.select({ kind: 'unit', id: others[0].unit_id }); return; }
    this.select({ kind: 'tile', id });
  }

  select(sel) {
    this.selection = sel;
    this.range = null;
    if (sel?.kind === 'unit') {
      const u = this.campaign.units[sel.id];
      if (u && u.faction === this.campaign.player_faction && u.move_budget > 0) this.range = this.svc.movementRange(sel.id);
    }
    this.onSelect(sel);
    this.draw();
  }

  clearSelection() { this.selection = null; this.range = null; this.draw(); }

  hexPath(ctx, x, y, s) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 180 * (60 * i - 30);
      const px = x + s * Math.cos(a), py = y + s * Math.sin(a);
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath();
  }

  draw() {
    const ctx = this.ctx;
    const hc = document.documentElement.getAttribute('data-contrast') === 'high';
    ctx.save();
    ctx.scale(this.dpr, this.dpr);
    ctx.fillStyle = hc ? '#000' : '#0d1013';
    ctx.fillRect(0, 0, this.w, this.h);

    const s = this.size * this.zoom;
    const tiles = this.tilesOf(this.theater);
    const rangeMap = new Map((this.range?.tiles || []).map((t) => [t.tile_id, t.cost]));
    const sel = this.selection;
    const selTileId = sel?.kind === 'unit' ? this.campaign.units[sel.id]?.tile_id
                    : sel?.kind === 'city' ? this.campaign.cities[sel.id]?.tile_id
                    : sel?.kind === 'tile' ? sel.id : null;

    // pass 1: terrain + control
    for (const t of tiles) {
      const p = this.toScreen(t.q, t.r);
      if (p.x < -s * 2 || p.x > this.w + s * 2 || p.y < -s * 2 || p.y > this.h + s * 2) continue;
      const [a, b] = TERRAIN_FILL[t.terrain] || TERRAIN_FILL.plain;
      const g = ctx.createLinearGradient(p.x, p.y - s, p.x, p.y + s);
      g.addColorStop(0, a); g.addColorStop(1, b);
      this.hexPath(ctx, p.x, p.y, s * 0.98);
      ctx.fillStyle = g; ctx.fill();

      if (!t.discovered) { ctx.fillStyle = 'rgba(8,10,12,.72)'; ctx.fill(); }
      else {
        ctx.fillStyle = CONTROL_TINT[t.control] || 'transparent'; ctx.fill();
        // supply as a readable shading, with a number at close zoom
        if (t.passable && t.supply < 3) { ctx.fillStyle = `rgba(10,12,14,${0.1 + (3 - t.supply) * 0.09})`; ctx.fill(); }
      }
      ctx.lineWidth = 1; ctx.strokeStyle = hc ? 'rgba(216,210,196,.35)' : 'rgba(0,0,0,.45)'; ctx.stroke();
      if (!t.passable) {
        // impassable is drawn, not merely refused
        ctx.save(); this.hexPath(ctx, p.x, p.y, s * 0.98); ctx.clip();
        ctx.strokeStyle = 'rgba(0,0,0,.5)'; ctx.lineWidth = 2;
        for (let i = -2; i <= 2; i++) { ctx.beginPath(); ctx.moveTo(p.x - s + i * s * 0.5, p.y + s); ctx.lineTo(p.x + s + i * s * 0.5, p.y - s); ctx.stroke(); }
        ctx.restore();
      }
    }

    // pass 2: movement overlay
    if (rangeMap.size && s > 16) {
      for (const [id, cost] of rangeMap) {
        const t = this.campaign.tiles[id];
        if (!t || t.theater !== this.theater) continue;
        const p = this.toScreen(t.q, t.r);
        this.hexPath(ctx, p.x, p.y, s * 0.9);
        ctx.fillStyle = 'rgba(201,143,54,.18)'; ctx.fill();
        ctx.strokeStyle = 'rgba(201,143,54,.75)'; ctx.lineWidth = 1.5; ctx.stroke();
        if (s > 26) {
          ctx.fillStyle = 'rgba(242,238,227,.92)';
          ctx.font = `600 ${Math.round(s * 0.34)}px ${getComputedStyle(document.body).fontFamily}`;
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          ctx.fillText(String(cost), p.x, p.y + s * 0.42);
        }
      }
    }

    // pass 3: path preview
    if (this.hoverPath?.length > 1) {
      ctx.beginPath();
      this.hoverPath.forEach((id, i) => {
        const t = this.campaign.tiles[id]; if (!t) return;
        const p = this.toScreen(t.q, t.r);
        i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y);
      });
      ctx.strokeStyle = 'rgba(201,143,54,.95)'; ctx.lineWidth = Math.max(2, s * 0.09);
      ctx.setLineDash([s * 0.22, s * 0.16]); ctx.stroke(); ctx.setLineDash([]);
    }

    // pass 4: cities, facilities, units
    for (const t of tiles) {
      const p = this.toScreen(t.q, t.r);
      if (p.x < -s * 2 || p.x > this.w + s * 2 || p.y < -s * 2 || p.y > this.h + s * 2) continue;
      if (t.city_id && t.discovered) this.drawCity(ctx, p, s, this.campaign.cities[t.city_id]);
      const units = Object.values(this.campaign.units)
        .filter((u) => u.tile_id === t.tile_id)
        .filter((u) => u.faction === this.campaign.player_faction || UNIT_CAPABILITIES[u.unit_type].visible_on_map)
        .sort((a, b) => (a.unit_id < b.unit_id ? -1 : 1));
      units.forEach((u, i) => this.drawUnit(ctx, p, s, u, i, units.length));
    }

    // pass 5: selection ring
    if (selTileId) {
      const t = this.campaign.tiles[selTileId];
      if (t && t.theater === this.theater) {
        const p = this.toScreen(t.q, t.r);
        this.hexPath(ctx, p.x, p.y, s * 0.99);
        ctx.strokeStyle = '#f2eee3'; ctx.lineWidth = 2.5; ctx.stroke();
        this.hexPath(ctx, p.x, p.y, s * 0.88);
        ctx.strokeStyle = 'rgba(201,143,54,.9)'; ctx.lineWidth = 1.5; ctx.stroke();
      }
    }
    ctx.restore();
  }

  drawCity(ctx, p, s, city) {
    if (!city) return;
    const r = s * 0.3;
    ctx.save();
    ctx.translate(p.x, p.y - s * 0.12);
    ctx.fillStyle = 'rgba(14,16,18,.82)';
    ctx.strokeStyle = city.control === 'allied' ? '#5c7f99' : city.control === 'axis' ? '#a8482f' : '#c98f36';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(-r, -r * 0.8, r * 2, r * 1.6, r * 0.26);
    ctx.fill(); ctx.stroke();
    // facility pips: what is built is visible on the map
    const built = city.facilities.filter((f) => !f.disabled).length;
    const queued = city.construction_queue.length;
    for (let i = 0; i < Math.min(5, built + queued); i++) {
      ctx.beginPath();
      ctx.arc(-r + r * 0.4 + i * (r * 0.38), r * 1.1, Math.max(1.4, r * 0.11), 0, Math.PI * 2);
      ctx.fillStyle = i < built ? '#c98f36' : 'rgba(201,143,54,.4)';
      ctx.fill();
    }
    if (s > 28) {
      ctx.fillStyle = '#ded8c9';
      ctx.font = `600 ${Math.round(s * 0.26)}px ${getComputedStyle(document.body).fontFamily}`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      ctx.fillText(this.i18n.t(city.label_key), 0, r * 1.5);
    }
    ctx.restore();
  }

  drawUnit(ctx, p, s, u, i, n) {
    const cap = UNIT_CAPABILITIES[u.unit_type];
    const spread = n > 1 ? (i - (n - 1) / 2) * s * 0.46 : 0;
    const x = p.x + spread, y = p.y + s * 0.42;
    const r = s * 0.2;
    const allied = !u.faction.startsWith('axis_');
    ctx.save();
    ctx.translate(x, y);
    ctx.beginPath();
    if (cap.visible_on_map) {
      ctx.rect(-r, -r * 0.7, r * 2, r * 1.4);                   // formation: block
    } else {
      ctx.moveTo(0, -r); ctx.lineTo(r, 0); ctx.lineTo(0, r); ctx.lineTo(-r, 0); ctx.closePath();  // covert: diamond
    }
    ctx.fillStyle = allied ? 'rgba(92,127,153,.92)' : 'rgba(168,72,47,.92)';
    ctx.fill();
    ctx.lineWidth = u.faction === this.campaign.player_faction ? 2 : 1;
    ctx.strokeStyle = u.faction === this.campaign.player_faction ? '#f2eee3' : 'rgba(0,0,0,.6)';
    ctx.stroke();
    // strength bar; colour-independent because the bar length carries the value
    const bw = r * 2, bh = Math.max(2, r * 0.22);
    ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.fillRect(-bw / 2, r * 0.95, bw, bh);
    ctx.fillStyle = u.strength > 0.6 ? '#7a9a5e' : u.strength > 0.3 ? '#c98f36' : '#a8482f';
    ctx.fillRect(-bw / 2, r * 0.95, bw * u.strength, bh);
    if (u.status.includes('isolated')) { ctx.fillStyle = '#f2eee3'; ctx.font = `700 ${Math.round(r * 1.1)}px serif`; ctx.textAlign = 'center'; ctx.fillText('!', 0, -r * 1.1); }
    if (u.status.includes('entrenched')) { ctx.strokeStyle = 'rgba(242,238,227,.8)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(-r * 1.2, r * 0.6); ctx.lineTo(r * 1.2, r * 0.6); ctx.stroke(); }
    ctx.restore();
  }

  previewPath(tile_id) {
    const entry = (this.range?.tiles || []).find((t) => t.tile_id === tile_id);
    this.hoverPath = entry?.path ?? null;
    this.draw();
  }
}
