// Build the 3D district from shared-data/districts/*.json.
//
// Nothing here is hand-placed: the geometry, the collision volumes, the audio
// zones, the navigation blockers and the patrol routes all come from the same
// authored data the Godot project reads, so the layout cannot drift between the
// two implementations.
//
// Walls are built as four solid pieces per opening (below, above, and the two
// sides) with a recessed reveal, so windows and doors have real thickness and a
// door is impassable until it has actually opened.

import { material } from './materials.js';

let THREE;
export function initBuilder(three) { THREE = three; }

const FACE_DIR = { south: [0, 1], north: [0, -1], east: [1, 0], west: [-1, 0] };

export class District {
  constructor(data, opts = {}) {
    this.data = data;
    this.opts = opts;
    this.group = new THREE.Group();
    this.colliders = [];        // { min:[x,z], max:[x,z], y0, y1, kind, id }
    this.occluders = [];        // same shape, used for line of sight and audio
    this.doors = [];            // { id, pivot, mesh, open, target, collider, w }
    this.ladders = [];
    this.interiorRooms = [];    // { id, rect, floorY, ambience, surface, structure }
    this.surfaceAt = this.surfaceAt.bind(this);
    this.lights = [];           // gameplay lights for the stealth model
    this.props = [];
    this.spawn = null;
    this.build();
  }

  // ----------------------------------------------------------------- ground --
  build() {
    const d = this.data;
    const [W, H] = d.grid.size_m;
    const cell = d.grid.cell_m;
    this.size = [W, H];

    // Ground is drawn as one mesh per surface type, so each keeps its own
    // material and the footstep system can ask the data (not the mesh) which
    // surface the player is on.
    const bySurface = new Map();
    for (const t of d.tiles) {
      const list = bySurface.get(t.surface) || [];
      list.push(t);
      bySurface.set(t.surface, list);
    }
    this.tileIndex = new Map(d.tiles.map((t) => [`${t.c},${t.r}`, t]));

    for (const [surface, tiles] of bySurface) {
      const geos = [];
      for (const t of tiles) {
        const g = new THREE.PlaneGeometry(cell, cell);
        g.rotateX(-Math.PI / 2);
        g.translate(t.c * cell + cell / 2, 0, t.r * cell + cell / 2);
        geos.push(g);
      }
      const merged = mergeGeometries(geos);
      const mesh = new THREE.Mesh(merged, material(surface));
      mesh.receiveShadow = true;
      mesh.name = `ground:${surface}`;
      this.group.add(mesh);
    }

    // a dark skirt so the world does not end in a visible void
    const skirt = new THREE.Mesh(
      new THREE.PlaneGeometry(W * 4, H * 4),
      material('surf_grass', { color: 0x3f4a34 }),
    );
    skirt.rotation.x = -Math.PI / 2;
    skirt.position.set(W / 2, -0.05, H / 2);
    this.group.add(skirt);

    for (const h of d.hedgerows) this.buildHedge(h, cell);
    for (const v of d.vegetation) this.buildTree(v);
    for (const s of d.structures) this.buildStructure(s);
    for (const p of d.pois) this.buildPoi(p);

    // boundary colliders so the player cannot walk off the authored area
    const t = 2;
    this.colliders.push({ min: [-t, -t], max: [W + t, 0], y0: 0, y1: 8, kind: 'boundary', id: 'bound_n' });
    this.colliders.push({ min: [-t, H], max: [W + t, H + t], y0: 0, y1: 8, kind: 'boundary', id: 'bound_s' });
    this.colliders.push({ min: [-t, -t], max: [0, H + t], y0: 0, y1: 8, kind: 'boundary', id: 'bound_w' });
    this.colliders.push({ min: [W, -t], max: [W + t, H + t], y0: 0, y1: 8, kind: 'boundary', id: 'bound_e' });

    // The spawn is the lane at the south edge: the player arrives by the track.
    this.spawn = { pos: [cell * 5.5, 0, H - cell * 1.5], yaw: Math.PI };
  }

  buildHedge(h, cell) {
    const x = h.c * cell, z = h.r * cell;
    const g = new THREE.BoxGeometry(cell, h.height_m, cell);
    const mesh = new THREE.Mesh(g, material('mat_hedge'));
    mesh.position.set(x + cell / 2, h.height_m / 2, z + cell / 2);
    mesh.castShadow = true; mesh.receiveShadow = true;
    // Break the silhouette so a hedgerow does not read as a cube wall.
    const crown = new THREE.Mesh(new THREE.SphereGeometry(cell * 0.46, 7, 5), material('mat_hedge'));
    crown.position.set(x + cell / 2, h.height_m, z + cell / 2);
    crown.scale.set(1, 0.45, 1);
    crown.castShadow = true;
    this.group.add(mesh, crown);
    const c = { min: [x + 0.3, z + 0.3], max: [x + cell - 0.3, z + cell - 0.3], y0: 0, y1: h.height_m, kind: 'hedge', id: `hedge_${h.c}_${h.r}`, cover: 0.55, concealment: 0.65 };
    this.colliders.push(c); this.occluders.push(c);
  }

  buildTree(v) {
    const trunkH = 2.4 * v.scale, crownR = 1.9 * v.scale;
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * v.scale, 0.22 * v.scale, trunkH, 7), material('mat_wood_dark'));
    trunk.position.set(v.p[0], trunkH / 2, v.p[1]);
    trunk.castShadow = true;
    const crown = new THREE.Mesh(new THREE.SphereGeometry(crownR, 9, 7), material('mat_hedge'));
    crown.position.set(v.p[0], trunkH + crownR * 0.6, v.p[1]);
    crown.scale.set(1, 0.82, 1);
    crown.castShadow = true;
    crown.userData.sway = v.sway;
    this.group.add(trunk, crown);
    // The trunk collides; the crown does not. Wind moves the crown only, so a
    // trunk can never appear to slide.
    this.colliders.push({ min: [v.p[0] - 0.25, v.p[1] - 0.25], max: [v.p[0] + 0.25, v.p[1] + 0.25], y0: 0, y1: trunkH, kind: 'trunk', id: `tree_${v.p.join('_')}` });
    this.swayables = this.swayables || [];
    this.swayables.push(crown);
  }

  // ------------------------------------------------------------- structures --
  buildStructure(s) {
    const [ox, oz] = s.origin;
    const [fx, fz] = s.footprint;
    const th = s.wall_thickness;
    const grp = new THREE.Group();
    grp.name = s.id;
    const wallMat = material(s.material);
    const floors = s.floors ?? 1;
    const floorH = s.wall_h / floors;

    // Four walls, each punched by its own openings.
    const faces = [
      { name: 'south', a: [0, fz - th], b: [fx, fz], axis: 'x', len: fx },
      { name: 'north', a: [0, 0], b: [fx, th], axis: 'x', len: fx },
      { name: 'west',  a: [0, 0], b: [th, fz], axis: 'z', len: fz },
      { name: 'east',  a: [fx - th, 0], b: [fx, fz], axis: 'z', len: fz },
    ];

    for (const f of faces) {
      const openings = s.openings.filter((o) => o.face === f.name);
      const segments = this.punchWall(f, openings, s.wall_h, th);
      for (const seg of segments) {
        const w = seg.x1 - seg.x0, h = seg.y1 - seg.y0;
        if (w <= 0.001 || h <= 0.001) continue;
        const geo = new THREE.BoxGeometry(f.axis === 'x' ? w : th, h, f.axis === 'x' ? th : w);
        const mesh = new THREE.Mesh(geo, wallMat);
        const cx = f.axis === 'x' ? seg.x0 + w / 2 : (f.a[0] + f.b[0]) / 2;
        const cz = f.axis === 'x' ? (f.a[1] + f.b[1]) / 2 : seg.x0 + w / 2;
        mesh.position.set(cx, seg.y0 + h / 2, cz);
        mesh.castShadow = true; mesh.receiveShadow = true;
        grp.add(mesh);
        const wmin = [ox + (f.axis === 'x' ? seg.x0 : f.a[0]), oz + (f.axis === 'x' ? f.a[1] : seg.x0)];
        const wmax = [ox + (f.axis === 'x' ? seg.x1 : f.b[0]), oz + (f.axis === 'x' ? f.b[1] : seg.x1)];
        const col = { min: wmin, max: wmax, y0: seg.y0, y1: seg.y1, kind: 'wall', id: `${s.id}_wall_${f.name}_${segments.indexOf(seg)}`, cover: 0.85 };
        this.colliders.push(col);
        this.occluders.push(col);
      }
      // window glass and reveals
      for (const o of openings.filter((x) => x.kind === 'window')) {
        const u = o.u * f.len, w = o.w;
        const yBase = (o.floor ?? 0) * floorH + o.sill;
        const glass = new THREE.Mesh(
          new THREE.BoxGeometry(f.axis === 'x' ? w : 0.04, o.h, f.axis === 'x' ? 0.04 : w),
          material(o.glass || 'mat_leaded_glass'),
        );
        const gx = f.axis === 'x' ? u : (f.a[0] + f.b[0]) / 2;
        const gz = f.axis === 'x' ? (f.a[1] + f.b[1]) / 2 : u;
        glass.position.set(gx, yBase + o.h / 2, gz);
        grp.add(glass);
      }
      // doors as hinged leaves
      for (const o of openings.filter((x) => x.kind === 'door')) {
        const u = o.u * f.len;
        const leaves = o.hinge === 'double' ? 2 : 1;
        const leafW = o.w / leaves;
        for (let i = 0; i < leaves; i++) {
          const pivot = new THREE.Group();
          const sign = leaves === 2 ? (i === 0 ? -1 : 1) : (o.hinge === 'right' ? 1 : -1);
          const px = f.axis === 'x' ? u + sign * o.w / 2 : (f.a[0] + f.b[0]) / 2;
          const pz = f.axis === 'x' ? (f.a[1] + f.b[1]) / 2 : u + sign * o.w / 2;
          pivot.position.set(px, 0, pz);
          const leaf = new THREE.Mesh(
            new THREE.BoxGeometry(f.axis === 'x' ? leafW : 0.07, o.h, f.axis === 'x' ? 0.07 : leafW),
            material('mat_plank_timber'),
          );
          leaf.position.set(f.axis === 'x' ? -sign * leafW / 2 : 0, o.h / 2, f.axis === 'x' ? 0 : -sign * leafW / 2);
          leaf.castShadow = true;
          pivot.add(leaf);
          grp.add(pivot);
          const openAngle = (o.swing === 'outward' ? 1 : -1) * sign * Math.PI * 0.52;
          const startFrac = o.state === 'open' ? 1 : o.state === 'ajar' ? (o.ajar_deg ?? 20) / 94 : 0;
          pivot.rotation.y = openAngle * startFrac;
          const doorRec = {
            id: `${s.id}_door_${f.name}_${i}`, structure: s.id, pivot, openAngle,
            frac: startFrac, target: startFrac, w: o.w, h: o.h,
            world: [ox + px, oz + pz],
            // A door is passable only once it is sufficiently open.
            get passable() { return this.frac > 0.55; },
          };
          this.doors.push(doorRec);
        }
        // The doorway's own blocking volume, removed from colliders while open.
        const dw = o.w, dmin = [ox + (f.axis === 'x' ? u - dw / 2 : f.a[0]), oz + (f.axis === 'x' ? f.a[1] : u - dw / 2)];
        const dmax = [ox + (f.axis === 'x' ? u + dw / 2 : f.b[0]), oz + (f.axis === 'x' ? f.b[1] : u + dw / 2)];
        const doorCol = { min: dmin, max: dmax, y0: 0, y1: o.h, kind: 'door', id: `${s.id}_doorway_${f.name}_${o.u}`, doorId: `${s.id}_door_${f.name}_0`, cover: 0.2 };
        this.colliders.push(doorCol);
      }
    }

    // floors, ceilings, rooms, stairs, interior doors, props
    for (const room of s.interior.rooms) {
      const [rx0, rz0, rx1, rz1] = room.rect;
      const y = (room.floor ?? 0) * floorH;
      const fl = new THREE.Mesh(new THREE.PlaneGeometry(rx1 - rx0, rz1 - rz0), material(room.surface));
      fl.rotation.x = -Math.PI / 2;
      fl.position.set((rx0 + rx1) / 2, y + 0.01, (rz0 + rz1) / 2);
      fl.receiveShadow = true;
      grp.add(fl);
      if ((room.floor ?? 0) > 0) {
        // the underside of an upper floor is the room below's ceiling
        const ce = new THREE.Mesh(new THREE.PlaneGeometry(rx1 - rx0, rz1 - rz0), material('surf_board_floor'));
        ce.rotation.x = Math.PI / 2;
        ce.position.set((rx0 + rx1) / 2, y - 0.02, (rz0 + rz1) / 2);
        grp.add(ce);
        this.colliders.push({ min: [ox + rx0, oz + rz0], max: [ox + rx1, oz + rz1], y0: y - 0.1, y1: y, kind: 'floor', id: `${s.id}_${room.id}_slab` });
      }
      this.interiorRooms.push({
        id: `${s.id}:${room.id}`, structure: s.id, label_key: room.label_key,
        rect: [ox + rx0, oz + rz0, ox + rx1, oz + rz1],
        floorY: y, ambience: room.ambience, surface: room.surface,
      });
      for (const p of room.props) this.buildProp(grp, s, p, y, ox, oz);
    }

    // roof: a real gable or shed plane, not a flat cap
    this.buildRoof(grp, s, fx, fz);

    for (const st of s.interior.stairs || []) {
      const [sx0, sz0, sx1, sz1] = st.rect;
      for (let i = 0; i < st.steps; i++) {
        const stepG = new THREE.BoxGeometry(sx1 - sx0, st.rise, st.run);
        const step = new THREE.Mesh(stepG, material(st.surface));
        step.position.set((sx0 + sx1) / 2, st.rise * (i + 0.5), sz0 + st.run * (i + 0.5));
        step.castShadow = true;
        grp.add(step);
      }
      this.stairs = this.stairs || [];
      this.stairs.push({
        min: [ox + sx0, oz + sz0], max: [ox + sx1, oz + sz0 + st.run * st.steps],
        y0: 0, y1: st.rise * st.steps, rise: st.rise, run: st.run, dir: [0, 1],
        id: `${s.id}_stairs`,
      });
    }

    if (s.interior.mezzanine) {
      const mz = s.interior.mezzanine;
      const [mx0, mz0, mx1, mz1] = mz.rect;
      const deck = new THREE.Mesh(new THREE.BoxGeometry(mx1 - mx0, 0.18, mz1 - mz0), material(mz.surface));
      deck.position.set((mx0 + mx1) / 2, mz.height, (mz0 + mz1) / 2);
      deck.castShadow = true; deck.receiveShadow = true;
      grp.add(deck);
      this.platforms = this.platforms || [];
      this.platforms.push({ min: [ox + mx0, oz + mz0], max: [ox + mx1, oz + mz1], y: mz.height, id: `${s.id}_mezz` });
      const lad = new THREE.Group();
      for (let i = 0; i < Math.floor(mz.height / 0.32); i++) {
        const rung = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.05, 0.05), material('mat_wood_dark'));
        rung.position.set(0, 0.32 * (i + 1), 0);
        lad.add(rung);
      }
      lad.position.set(mz.ladder_p[0], 0, mz.ladder_p[1]);
      grp.add(lad);
      this.ladders.push({ id: `${s.id}_ladder`, pos: [ox + mz.ladder_p[0], oz + mz.ladder_p[1]], top: mz.height, label_key: 'hud.interact' });
    }

    for (const d of s.interior.internal_doors || []) {
      const pivot = new THREE.Group();
      pivot.position.set(d.p[0], 0, d.p[1]);
      const leaf = new THREE.Mesh(new THREE.BoxGeometry(0.07, d.h, d.w), material('mat_plank_timber'));
      leaf.position.set(0, d.h / 2, d.w / 2);
      pivot.add(leaf);
      pivot.rotation.y = d.state === 'open' ? -Math.PI / 2 : 0;
      grp.add(pivot);
      this.doors.push({
        id: `${s.id}_int_${d.between.join('_')}`, structure: s.id, pivot, openAngle: -Math.PI / 2,
        frac: d.state === 'open' ? 1 : 0, target: d.state === 'open' ? 1 : 0, w: d.w, h: d.h,
        world: [ox + d.p[0], oz + d.p[1]],
        get passable() { return this.frac > 0.55; },
      });
    }

    grp.position.set(ox, 0, oz);
    grp.rotation.y = (s.rot_deg || 0) * Math.PI / 180;
    this.group.add(grp);
  }

  /** Split a wall face into solid rectangles around its openings. */
  punchWall(face, openings, wallH, th) {
    // Build a 2D occupancy of (u, y) holes, then emit column strips.
    const holes = openings.map((o) => {
      const u = o.u * face.len;
      const floors = o.floor ?? 0;
      const yBase = floors * (wallH / Math.max(1, (o.floor != null ? 2 : 1))) + o.sill;
      return { u0: u - o.w / 2, u1: u + o.w / 2, y0: o.sill + (o.floor ? wallH * 0.52 : 0), y1: o.sill + o.h + (o.floor ? wallH * 0.52 : 0) };
    });
    if (!holes.length) return [{ x0: face.axis === 'x' ? 0 : face.a[1], x1: face.axis === 'x' ? face.len : face.b[1], y0: 0, y1: wallH }];

    const edges = [0, face.len];
    for (const h of holes) { edges.push(h.u0, h.u1); }
    const us = [...new Set(edges.map((v) => Math.max(0, Math.min(face.len, Math.round(v * 1000) / 1000))))].sort((a, b) => a - b);

    const out = [];
    for (let i = 0; i < us.length - 1; i++) {
      const u0 = us[i], u1 = us[i + 1];
      if (u1 - u0 < 0.01) continue;
      const mid = (u0 + u1) / 2;
      const spanning = holes.filter((h) => mid > h.u0 && mid < h.u1).sort((a, b) => a.y0 - b.y0);
      if (!spanning.length) { out.push({ x0: u0, x1: u1, y0: 0, y1: wallH }); continue; }
      let y = 0;
      for (const h of spanning) {
        if (h.y0 > y) out.push({ x0: u0, x1: u1, y0: y, y1: Math.min(h.y0, wallH) });
        y = Math.max(y, h.y1);
      }
      if (y < wallH) out.push({ x0: u0, x1: u1, y0: y, y1: wallH });
    }
    return out;
  }

  buildRoof(grp, s, fx, fz) {
    const r = s.roof;
    const over = r.overhang;
    const mat = material(r.material);
    if (r.type === 'gable') {
      const pitch = r.pitch * Math.PI / 180;
      const halfSpan = fz / 2 + over;
      const rise = Math.tan(pitch) * halfSpan;
      const slope = Math.hypot(halfSpan, rise);
      for (const sign of [-1, 1]) {
        const plane = new THREE.Mesh(new THREE.BoxGeometry(fx + over * 2, 0.12, slope), mat);
        plane.position.set(fx / 2, s.wall_h + rise / 2, fz / 2 + sign * halfSpan / 2);
        plane.rotation.x = sign * (Math.PI / 2 - Math.atan2(halfSpan, rise) + Math.PI / 2) * 0 + sign * -pitch;
        plane.castShadow = true; plane.receiveShadow = true;
        grp.add(plane);
      }
      // gable ends close the attic
      for (const z of [0, fz]) {
        const tri = new THREE.Shape();
        tri.moveTo(-fx / 2, 0); tri.lineTo(fx / 2, 0); tri.lineTo(0, rise); tri.closePath();
        const geo = new THREE.ExtrudeGeometry(tri, { depth: 0.2, bevelEnabled: false });
        const m = new THREE.Mesh(geo, material(s.material));
        m.position.set(fx / 2, s.wall_h, z);
        grp.add(m);
      }
      this.colliders.push({
        min: [s.origin[0] - over, s.origin[1] - over], max: [s.origin[0] + fx + over, s.origin[1] + fz + over],
        y0: s.wall_h, y1: s.wall_h + rise + 0.2, kind: 'roof', id: `${s.id}_roof`,
      });
    } else {
      const pitch = r.pitch * Math.PI / 180;
      const rise = Math.tan(pitch) * fz;
      const plane = new THREE.Mesh(new THREE.BoxGeometry(fx + over * 2, 0.1, Math.hypot(fz, rise) + over), mat);
      plane.position.set(fx / 2, s.wall_h + rise / 2, fz / 2);
      plane.rotation.x = -pitch;
      plane.castShadow = true;
      grp.add(plane);
      this.colliders.push({
        min: [s.origin[0] - over, s.origin[1] - over], max: [s.origin[0] + fx + over, s.origin[1] + fz + over],
        y0: s.wall_h, y1: s.wall_h + rise + 0.2, kind: 'roof', id: `${s.id}_roof`,
      });
    }
  }

  buildProp(grp, s, p, y, ox, oz) {
    const spec = PROPS[p.t] || PROPS.prop_crate;
    const mesh = spec.build(THREE, material);
    mesh.position.set(p.p[0], y + (spec.yOff ?? 0), p.p[1]);
    mesh.rotation.y = (p.rot || 0) * Math.PI / 180;
    mesh.traverse?.((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    grp.add(mesh);
    if (spec.size) {
      this.colliders.push({
        min: [ox + p.p[0] - spec.size[0] / 2, oz + p.p[1] - spec.size[2] / 2],
        max: [ox + p.p[0] + spec.size[0] / 2, oz + p.p[1] + spec.size[2] / 2],
        y0: y, y1: y + spec.size[1], kind: 'prop', id: `${s.id}_${p.t}_${p.p.join('_')}`,
        cover: Math.min(0.7, spec.size[1] / 2),
      });
    }
    if (p.light) {
      const l = new THREE.PointLight(kelvinToHex(p.light.warm), p.light.intensity * 1.6, p.light.radius, 2);
      l.position.set(p.p[0], y + 1.3, p.p[1]);
      if (this.opts.shadows && p.light.kind === 'fire') { l.castShadow = true; l.shadow.mapSize.set(256, 256); }
      grp.add(l);
      this.lights.push({ pos: [ox + p.p[0], oz + p.p[1]], y: y + 1.3, radius: p.light.radius, intensity: Math.min(1, p.light.intensity / 2.6), kind: p.light.kind, three: l });
    }
    this.props.push({ id: `${s.id}_${p.t}`, type: p.t, pos: [ox + p.p[0], oz + p.p[1]] });
  }

  buildPoi(p) {
    const grp = new THREE.Group();
    grp.position.set(p.p[0], 0, p.p[1]);
    if (p.id === 'poi_field_telephone_junction') {
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.14, 5.2, 8), material('mat_wood_dark'));
      pole.position.y = 2.6; pole.castShadow = true;
      const arm = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.08, 0.08), material('mat_wood_dark'));
      arm.position.y = 4.7;
      const box = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.46, 0.2), material('mat_metal_dull'));
      box.position.set(0, 1.35, 0.18);
      grp.add(pole, arm, box);
      this.colliders.push({ min: [p.p[0] - 0.2, p.p[1] - 0.2], max: [p.p[0] + 0.2, p.p[1] + 0.2], y0: 0, y1: 5.2, kind: 'prop', id: p.id });
    } else if (p.id === 'poi_gun_position') {
      const berm = new THREE.Mesh(new THREE.CylinderGeometry(4.6, 5.4, 1.5, 14, 1, true), material('surf_packed_earth'));
      berm.position.y = 0.75; berm.receiveShadow = true;
      const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.2, 4.4, 10), material('mat_metal_dull'));
      barrel.rotation.z = Math.PI / 2; barrel.rotation.y = -0.4;
      barrel.position.set(0, 1.5, 0);
      const shield = new THREE.Mesh(new THREE.BoxGeometry(2.4, 1.2, 0.12), material('mat_metal_dull'));
      shield.position.set(0, 1.4, 0.7);
      const carriage = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.7, 1.9), material('mat_metal_dull'));
      carriage.position.y = 0.75;
      grp.add(berm, barrel, shield, carriage);
      this.colliders.push({ min: [p.p[0] - 1.1, p.p[1] - 1.1], max: [p.p[0] + 1.1, p.p[1] + 1.1], y0: 0, y1: 1.6, kind: 'prop', id: p.id, cover: 0.8 });
    } else if (p.id === 'poi_arms_cache') {
      const crate = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.5, 0.6), material('mat_plank_timber'));
      crate.position.y = 0.25; crate.castShadow = true;
      const straw = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.22, 1.0), material('surf_crop'));
      straw.position.y = 0.5;
      grp.add(crate, straw);
    } else if (p.id === 'poi_crossroad') {
      const sign = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 2.3, 7), material('mat_wood_dark'));
      sign.position.y = 1.15;
      const board = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.22, 0.05), material('mat_plank_timber'));
      board.position.set(0.4, 2.0, 0);
      grp.add(sign, board);
    }
    grp.name = p.id;
    this.group.add(grp);
  }

  // ------------------------------------------------------------- queries ----
  /** Which authored surface is under a world position. Drives footstep audio. */
  surfaceAt(x, z, y = 0) {
    for (const r of this.interiorRooms) {
      if (x >= r.rect[0] && x <= r.rect[2] && z >= r.rect[1] && z <= r.rect[3] && Math.abs(y - r.floorY) < 1.6) return r.surface;
    }
    const cell = this.data.grid.cell_m;
    const t = this.tileIndex.get(`${Math.floor(x / cell)},${Math.floor(z / cell)}`);
    return t?.surface ?? 'surf_grass';
  }

  roomAt(x, z, y = 0) {
    for (const r of this.interiorRooms) {
      if (x >= r.rect[0] && x <= r.rect[2] && z >= r.rect[1] && z <= r.rect[3] && Math.abs(y - r.floorY) < 1.6) return r;
    }
    return null;
  }

  isIndoors(x, z, y = 0) { return !!this.roomAt(x, z, y); }

  /** Cover value from the nearest blocking volume, for the stealth model. */
  coverAt(x, z, y) {
    let best = 0;
    for (const c of this.colliders) {
      if (c.cover == null) continue;
      if (y > c.y1 + 0.1) continue;
      const dx = Math.max(c.min[0] - x, 0, x - c.max[0]);
      const dz = Math.max(c.min[1] - z, 0, z - c.max[1]);
      const d = Math.hypot(dx, dz);
      if (d < 1.1) best = Math.max(best, c.cover * (1 - d / 1.1));
    }
    return Math.min(0.9, best);
  }

  /** Segment-vs-AABB line of sight over the occluder list, at eye height. */
  hasLineOfSight(aPos, bPos, posture = 'stand') {
    const eyeA = 1.62, eyeB = posture === 'prone' ? 0.42 : posture === 'crouch' ? 1.05 : 1.62;
    return !this.segmentBlocked(aPos[0], eyeA, aPos[1], bPos[0], eyeB, bPos[1], true);
  }

  segmentBlocked(x0, y0, z0, x1, y1, z1, forSight = false) {
    const list = forSight ? this.occluders : this.colliders;
    const dx = x1 - x0, dy = y1 - y0, dz = z1 - z0;
    for (const c of list) {
      if (forSight && c.kind === 'door') continue;
      let t0 = 0, t1 = 1, hit = true;
      const slab = (p, d, lo, hi) => {
        if (Math.abs(d) < 1e-9) return p >= lo && p <= hi;
        let a = (lo - p) / d, b = (hi - p) / d;
        if (a > b) [a, b] = [b, a];
        t0 = Math.max(t0, a); t1 = Math.min(t1, b);
        return t0 <= t1;
      };
      hit = slab(x0, dx, c.min[0], c.max[0]) && slab(z0, dz, c.min[1], c.max[1]) && slab(y0, dy, c.y0, c.y1);
      if (hit && t1 > 0.001 && t0 < 0.999) return { id: c.id, kind: c.kind, t: t0 };
    }
    return null;
  }

  /** How much a wall between two points dampens sound, 0..1. */
  acousticOcclusion(aPos, bPos) {
    const hit = this.segmentBlocked(aPos[0], 1.3, aPos[1], bPos[0], 1.3, bPos[1], false);
    if (!hit) return 0;
    // An open doorway transmits; a stone wall does not.
    if (hit.kind === 'door') {
      const d = this.doors.find((x) => x.id.startsWith(hit.id.replace('_doorway_', '_door_').split('_0.')[0]));
      return d?.passable ? 0.15 : 0.6;
    }
    return { wall: 0.85, hedge: 0.35, roof: 0.9, floor: 0.8, prop: 0.3, trunk: 0.2, boundary: 1 }[hit.kind] ?? 0.5;
  }

  openDoor(id, open = true) {
    const d = this.doors.find((x) => x.id === id);
    if (d) d.target = open ? 1 : 0;
    return d;
  }

  nearestDoor(x, z, maxDist = 1.9) {
    let best = null, bd = maxDist;
    for (const d of this.doors) {
      const dist = Math.hypot(d.world[0] - x, d.world[1] - z);
      if (dist < bd) { bd = dist; best = d; }
    }
    return best;
  }

  step(dt, elapsed) {
    for (const d of this.doors) {
      if (Math.abs(d.frac - d.target) > 0.001) {
        const dir = Math.sign(d.target - d.frac);
        d.frac = Math.max(0, Math.min(1, d.frac + dir * dt * 1.6));
        d.pivot.rotation.y = d.openAngle * d.frac;
      }
    }
    // Wind moves crowns only; trunks and collision never move.
    if (this.swayables && this.opts.ambientMotion !== false) {
      for (let i = 0; i < this.swayables.length; i++) {
        const c = this.swayables[i];
        const s = c.userData.sway ?? 0.3;
        c.rotation.z = Math.sin(elapsed * 0.9 + i * 1.7) * 0.035 * s;
        c.rotation.x = Math.cos(elapsed * 0.7 + i * 2.3) * 0.028 * s;
      }
    }
  }

  dispose() {
    this.group.traverse((o) => { if (o.isMesh) { o.geometry?.dispose?.(); } });
  }
}

function kelvinToHex(k) {
  // crude blackbody for lamp/fire/candle warmth
  const t = k / 100;
  let r, g, b;
  if (t <= 66) { r = 255; g = 99.47 * Math.log(t) - 161.12; } else { r = 329.7 * Math.pow(t - 60, -0.1332); g = 288.12 * Math.pow(t - 60, -0.0755); }
  b = t >= 66 ? 255 : t <= 19 ? 0 : 138.52 * Math.log(t - 10) - 305.04;
  const cl = (v) => Math.max(0, Math.min(255, Math.round(v)));
  return (cl(r) << 16) | (cl(g) << 8) | cl(b);
}

function mergeGeometries(geos) {
  // Minimal position/normal/uv merge: avoids pulling in an addon for one job.
  let vCount = 0;
  for (const g of geos) vCount += g.attributes.position.count;
  const pos = new Float32Array(vCount * 3), nor = new Float32Array(vCount * 3), uv = new Float32Array(vCount * 2);
  const idx = [];
  let vo = 0;
  for (const g of geos) {
    const p = g.attributes.position, n = g.attributes.normal, u = g.attributes.uv;
    pos.set(p.array, vo * 3); nor.set(n.array, vo * 3);
    // world-space UVs so adjacent tiles do not visibly tile per quad
    for (let i = 0; i < p.count; i++) { uv[(vo + i) * 2] = p.getX(i) / 8; uv[(vo + i) * 2 + 1] = p.getZ(i) / 8; }
    const gi = g.index ? g.index.array : null;
    if (gi) for (let i = 0; i < gi.length; i++) idx.push(gi[i] + vo);
    else for (let i = 0; i < p.count; i++) idx.push(i + vo);
    vo += p.count;
    g.dispose();
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  out.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  out.setIndex(idx);
  out.computeBoundingSphere();
  return out;
}

// -------------------------------------------------------------------- props --
const box = (THREE, mat, w, h, d, m) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(m));
export const PROPS = {
  prop_hearth:     { size: [1.6, 1.3, 0.8], yOff: 0.65, build: (T, m) => box(T, m, 1.6, 1.3, 0.8, 'mat_rubble_stone') },
  prop_table_long: { size: [2.2, 0.78, 0.9], yOff: 0.39, build: (T, m) => { const g = new T.Group(); const top = box(T, m, 2.2, 0.07, 0.9, 'mat_plank_timber'); top.position.y = 0.36; g.add(top); for (const [x, z] of [[-1, -0.38], [1, -0.38], [-1, 0.38], [1, 0.38]]) { const l = box(T, m, 0.08, 0.72, 0.08, 'mat_wood_dark'); l.position.set(x, 0, z); g.add(l); } return g; } },
  prop_bench:      { size: [1.9, 0.45, 0.34], yOff: 0.22, build: (T, m) => box(T, m, 1.9, 0.06, 0.34, 'mat_plank_timber') },
  prop_chair:      { size: [0.46, 0.92, 0.46], yOff: 0.46, build: (T, m) => { const g = new T.Group(); const s = box(T, m, 0.44, 0.05, 0.44, 'mat_plank_timber'); s.position.y = 0; const b = box(T, m, 0.44, 0.5, 0.05, 'mat_plank_timber'); b.position.set(0, 0.26, -0.2); g.add(s, b); return g; } },
  prop_dresser:    { size: [1.1, 1.7, 0.45], yOff: 0.85, build: (T, m) => box(T, m, 1.1, 1.7, 0.45, 'mat_wood_dark') },
  prop_bed_iron:   { size: [1.0, 0.6, 1.95], yOff: 0.3, build: (T, m) => { const g = new T.Group(); g.add(box(T, m, 1.0, 0.22, 1.95, 'mat_cloth')); const h = box(T, m, 1.0, 0.7, 0.06, 'mat_metal_dull'); h.position.set(0, 0.3, -0.95); g.add(h); return g; } },
  prop_trunk:      { size: [0.9, 0.5, 0.5], yOff: 0.25, build: (T, m) => box(T, m, 0.9, 0.5, 0.5, 'mat_wood_dark') },
  prop_washstand:  { size: [0.6, 0.9, 0.4], yOff: 0.45, build: (T, m) => box(T, m, 0.6, 0.9, 0.4, 'mat_plank_timber') },
  prop_crate:      { size: [0.6, 0.5, 0.6], yOff: 0.25, build: (T, m) => box(T, m, 0.6, 0.5, 0.6, 'mat_plank_timber') },
  prop_barrel:     { size: [0.6, 0.86, 0.6], yOff: 0.43, build: (T, m) => new T.Mesh(new T.CylinderGeometry(0.3, 0.27, 0.86, 12), m('mat_wood_dark')) },
  prop_sack_flour: { size: [0.55, 0.5, 0.4], yOff: 0.25, build: (T, m) => new T.Mesh(new T.SphereGeometry(0.3, 8, 6), m('mat_cloth')) },
  prop_pail:       { size: [0.3, 0.32, 0.3], yOff: 0.16, build: (T, m) => new T.Mesh(new T.CylinderGeometry(0.15, 0.12, 0.32, 10), m('mat_metal_dull')) },
  prop_jerrycan:   { size: [0.18, 0.46, 0.36], yOff: 0.23, build: (T, m) => box(T, m, 0.18, 0.46, 0.36, 'mat_metal_dull') },
  prop_hay_pile:   { size: [2.4, 1.5, 2.0], yOff: 0.75, build: (T, m) => { const s = new T.Mesh(new T.SphereGeometry(1.2, 9, 6), m('surf_crop')); s.scale.set(1, 0.62, 0.85); return s; } },
  prop_cart:       { size: [2.6, 1.3, 1.5], yOff: 0.5, build: (T, m) => { const g = new T.Group(); const bed = box(T, m, 2.4, 0.14, 1.3, 'mat_plank_timber'); bed.position.y = 0.3; g.add(bed); for (const x of [-0.8, 0.8]) for (const z of [-0.65, 0.65]) { const w = new T.Mesh(new T.CylinderGeometry(0.44, 0.44, 0.09, 12), m('mat_wood_dark')); w.rotation.x = Math.PI / 2; w.position.set(x, -0.06, z); g.add(w); } return g; } },
  prop_plough:     { size: [1.4, 0.9, 0.7], yOff: 0.3, build: (T, m) => { const g = new T.Group(); g.add(box(T, m, 1.3, 0.08, 0.1, 'mat_metal_dull')); const b = box(T, m, 0.4, 0.5, 0.08, 'mat_metal_dull'); b.position.set(0.5, -0.2, 0); g.add(b); return g; } },
  prop_toolrack:   { size: [0.25, 1.8, 1.6], yOff: 0.9, build: (T, m) => box(T, m, 0.2, 1.8, 1.6, 'mat_plank_timber') },
  prop_lantern:    { size: null, yOff: 1.3, build: (T, m) => new T.Mesh(new T.BoxGeometry(0.16, 0.24, 0.16), m('mat_metal_dull')) },
  prop_shelf:      { size: [0.3, 1.6, 1.4], yOff: 0.8, build: (T, m) => box(T, m, 0.3, 1.6, 1.4, 'mat_plank_timber') },
  prop_pew:        { size: [3.2, 0.95, 0.5], yOff: 0.45, build: (T, m) => { const g = new T.Group(); const s = box(T, m, 3.2, 0.07, 0.42, 'mat_wood_dark'); g.add(s); const b = box(T, m, 3.2, 0.5, 0.06, 'mat_wood_dark'); b.position.set(0, 0.28, -0.2); g.add(b); return g; } },
  prop_candle_stand: { size: [0.3, 1.1, 0.3], yOff: 0.55, build: (T, m) => new T.Mesh(new T.CylinderGeometry(0.1, 0.18, 1.1, 8), m('mat_metal_dull')) },
};
