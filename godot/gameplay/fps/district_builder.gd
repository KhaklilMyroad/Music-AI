extends Node3D
class_name DistrictBuilder
## Build the 3D district from data/districts/*.json.
##
## Nothing here is hand-placed: geometry, collision, audio zones, navigation and
## patrol routes all come from the same authored data the web prototype and the
## tests read, so the layout cannot drift between the two implementations.
##
## Walls are built as solid pieces around each opening with a recessed reveal,
## so windows and doors have real thickness and a door is impassable until it
## has actually opened.

signal ready_state_changed(ready_map: Dictionary)

const STREAM_PRELOAD_M := 48.0

var data: Dictionary = {}
var cell_m: float = 8.0
var doors: Array = []            # {id, pivot, open_angle, frac, target, world, passable}
var interior_rooms: Array = []   # {id, rect, floor_y, ambience, surface}
var gameplay_lights: Array = []  # {pos: Vector2, y, radius, intensity, kind}
var ladders: Array = []
var tile_index: Dictionary = {}
var streaming_cells: Array = []
var swayables: Array = []
var _elapsed: float = 0.0
var spawn := {"pos": Vector3.ZERO, "yaw": 0.0}
var _nav_region: NavigationRegion3D = null

func build(district_data: Dictionary, quality: Dictionary) -> void:
	data = district_data
	cell_m = float((data["grid"] as Dictionary)["cell_m"])
	for t in data["tiles"]:
		tile_index["%d,%d" % [int((t as Dictionary)["c"]), int((t as Dictionary)["r"])]] = t

	_build_ground()
	_build_hedgerows()
	_build_vegetation(float(quality.get("vegetation_density", 1.0)))
	for s in data["structures"]:
		_build_structure(s, quality)
	for p in data["pois"]:
		_build_poi(p)
	_build_boundary()
	streaming_cells = data["streaming_cells"]

	# The spawn comes from the district data, where the authoring tool placed it
	# on the lane and proved by flood fill that every objective is reachable
	# from it. The fallback only exists for a district authored before that.
	var sp = data.get("spawn", null)
	if sp != null:
		var p: Array = (sp as Dictionary)["p"]
		spawn = {"pos": Vector3(float(p[0]), 0.0, float(p[1])), "yaw": deg_to_rad(float((sp as Dictionary).get("yaw_deg", 0)))}
	else:
		spawn = {"pos": Vector3(cell_m * 5.5, 0.0, float((data["grid"] as Dictionary)["rows"]) * cell_m - cell_m * 1.5), "yaw": PI}
	ready_state_changed.emit(readiness())

## Readiness for Transition.mark_ready: the mission is not playable until each
## of these is true, so a half-built district fails the transition instead of
## hiding behind a permanent loading animation.
func readiness() -> Dictionary:
	return {
		"collision": get_tree() != null and _count_static_bodies() > 0,
		"navigation": interior_rooms.size() > 0 and doors.size() > 0,
		"objectives": (data.get("pois", []) as Array).size() > 0,
	}

func _count_static_bodies() -> int:
	var n := 0
	for child in get_children():
		if child is StaticBody3D:
			n += 1
		for g in child.get_children():
			if g is StaticBody3D:
				n += 1
	return n

func _mat(id: String) -> StandardMaterial3D:
	# Production materials live in res://art/materials/<id>.tres. Until they
	# exist the builder falls back to a flat colour so the blockout is visibly
	# a blockout rather than pretending to be finished art.
	var path := "res://art/materials/%s.tres" % id
	if ResourceLoader.exists(path):
		return load(path)
	var m := StandardMaterial3D.new()
	m.albedo_color = {
		"surf_grass": Color(0.33, 0.40, 0.24), "surf_crop": Color(0.49, 0.52, 0.27),
		"surf_dirt_track": Color(0.44, 0.38, 0.28), "surf_cobble": Color(0.36, 0.36, 0.35),
		"surf_packed_earth": Color(0.42, 0.36, 0.28), "surf_board_floor": Color(0.36, 0.28, 0.19),
		"surf_stone_floor": Color(0.44, 0.44, 0.42), "surf_hedge_base": Color(0.20, 0.30, 0.16),
		"mat_limestone_render": Color(0.72, 0.70, 0.64), "mat_limestone_block": Color(0.76, 0.74, 0.69),
		"mat_rubble_stone": Color(0.55, 0.53, 0.48), "mat_plank_timber": Color(0.42, 0.31, 0.20),
		"mat_slate": Color(0.24, 0.26, 0.29), "mat_clay_tile": Color(0.50, 0.29, 0.21),
		"mat_corrugated": Color(0.44, 0.44, 0.45), "mat_hedge": Color(0.18, 0.30, 0.14),
		"mat_wood_dark": Color(0.26, 0.18, 0.11), "mat_metal_dull": Color(0.34, 0.34, 0.36),
		"mat_leaded_glass": Color(0.62, 0.70, 0.76, 0.4),
	}.get(id, Color(0.5, 0.5, 0.47))
	m.roughness = 0.9
	if id == "mat_leaded_glass":
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return m

func _add_box(parent: Node3D, size: Vector3, pos: Vector3, mat_id: String, with_collision: bool = true, body_name: String = "") -> Node3D:
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = size
	mesh.mesh = box
	mesh.material_override = _mat(mat_id)
	mesh.position = pos
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	parent.add_child(mesh)
	if with_collision:
		var body := StaticBody3D.new()
		if body_name != "":
			body.name = body_name
		var shape := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = size
		shape.shape = bs
		body.add_child(shape)
		body.position = pos
		parent.add_child(body)
	return mesh

func _build_ground() -> void:
	# One mesh per surface type, so each keeps its own material and the footstep
	# system asks the data (not the mesh) which surface the player is on.
	var by_surface: Dictionary = {}
	for t in data["tiles"]:
		var td: Dictionary = t
		if not by_surface.has(td["surface"]):
			by_surface[td["surface"]] = []
		(by_surface[td["surface"]] as Array).append(td)
	for surface in by_surface:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		for t in by_surface[surface]:
			var td: Dictionary = t
			var x0: float = float(td["c"]) * cell_m
			var z0: float = float(td["r"]) * cell_m
			var corners := [Vector3(x0, 0, z0), Vector3(x0 + cell_m, 0, z0), Vector3(x0 + cell_m, 0, z0 + cell_m), Vector3(x0, 0, z0 + cell_m)]
			for tri in [[0, 2, 1], [0, 3, 2]]:
				for i in tri:
					st.set_normal(Vector3.UP)
					# World-space UVs so adjacent tiles do not visibly repeat per quad.
					st.set_uv(Vector2(corners[i].x / cell_m, corners[i].z / cell_m))
					st.add_vertex(corners[i])
		var mi := MeshInstance3D.new()
		mi.mesh = st.commit()
		mi.material_override = _mat(str(surface))
		mi.name = "ground_%s" % surface
		add_child(mi)
	# one floor collider for the whole district, since the ground is flat
	var body := StaticBody3D.new()
	body.name = "ground_collider"
	var shape := CollisionShape3D.new()
	var plane := BoxShape3D.new()
	var size_m: Array = (data["grid"] as Dictionary)["size_m"]
	plane.size = Vector3(float(size_m[0]) * 3.0, 0.4, float(size_m[1]) * 3.0)
	shape.shape = plane
	shape.position = Vector3(float(size_m[0]) / 2.0, -0.2, float(size_m[1]) / 2.0)
	body.add_child(shape)
	add_child(body)

func _build_hedgerows() -> void:
	for h in data["hedgerows"]:
		var hd: Dictionary = h
		var x: float = float(hd["c"]) * cell_m
		var z: float = float(hd["r"]) * cell_m
		var height: float = float(hd["height_m"])
		_add_box(self, Vector3(cell_m, height, cell_m), Vector3(x + cell_m / 2.0, height / 2.0, z + cell_m / 2.0), "mat_hedge", true, "hedge_%d_%d" % [int(hd["c"]), int(hd["r"])])
		# Break the silhouette so a hedgerow does not read as a cube wall.
		var crown := MeshInstance3D.new()
		var sphere := SphereMesh.new()
		sphere.radius = cell_m * 0.46
		sphere.height = cell_m * 0.46
		crown.mesh = sphere
		crown.material_override = _mat("mat_hedge")
		crown.position = Vector3(x + cell_m / 2.0, height, z + cell_m / 2.0)
		add_child(crown)

func _build_vegetation(density: float) -> void:
	var i := 0
	for v in data["vegetation"]:
		i += 1
		if density < 1.0 and fmod(float(i), 1.0 / maxf(0.01, density)) >= 1.0:
			continue
		var vd: Dictionary = v
		var p: Array = vd["p"]
		var scale_f: float = float(vd["scale"])
		var trunk_h: float = 2.4 * scale_f
		# The trunk collides; the crown does not. Wind moves the crown only, so
		# a trunk can never appear to slide.
		var trunk := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.16 * scale_f
		cyl.bottom_radius = 0.22 * scale_f
		cyl.height = trunk_h
		trunk.mesh = cyl
		trunk.material_override = _mat("mat_wood_dark")
		trunk.position = Vector3(float(p[0]), trunk_h / 2.0, float(p[1]))
		add_child(trunk)
		var body := StaticBody3D.new()
		var shape := CollisionShape3D.new()
		var cs := CylinderShape3D.new()
		cs.radius = 0.25
		cs.height = trunk_h
		shape.shape = cs
		body.add_child(shape)
		body.position = trunk.position
		add_child(body)
		var crown := MeshInstance3D.new()
		var sp := SphereMesh.new()
		sp.radius = 1.9 * scale_f
		sp.height = 3.1 * scale_f
		crown.mesh = sp
		crown.material_override = _mat("mat_hedge")
		crown.position = Vector3(float(p[0]), trunk_h + 1.1 * scale_f, float(p[1]))
		add_child(crown)
		crown.set_meta("sway", float(vd.get("sway", 0.3)))
		swayables.append(crown)

func _build_structure(s_in: Variant, quality: Dictionary) -> void:
	var s: Dictionary = s_in
	var origin: Array = s["origin"]
	var ox: float = float(origin[0])
	var oz: float = float(origin[1])
	var fp: Array = s["footprint"]
	var fx: float = float(fp[0])
	var fz: float = float(fp[1])
	var th: float = float(s["wall_thickness"])
	var wall_h: float = float(s["wall_h"])
	var grp := Node3D.new()
	grp.name = str(s["id"])
	grp.position = Vector3(ox, 0.0, oz)
	add_child(grp)

	var faces := [
		{"name": "south", "axis": "x", "len": fx, "a": Vector2(0, fz - th), "b": Vector2(fx, fz)},
		{"name": "north", "axis": "x", "len": fx, "a": Vector2(0, 0), "b": Vector2(fx, th)},
		{"name": "west", "axis": "z", "len": fz, "a": Vector2(0, 0), "b": Vector2(th, fz)},
		{"name": "east", "axis": "z", "len": fz, "a": Vector2(fx - th, 0), "b": Vector2(fx, fz)},
	]
	for f in faces:
		var openings: Array = (s["openings"] as Array).filter(func(o): return (o as Dictionary)["face"] == f["name"])
		for seg in _punch_wall(f, openings, wall_h):
			var w: float = float(seg["x1"]) - float(seg["x0"])
			var h: float = float(seg["y1"]) - float(seg["y0"])
			if w <= 0.001 or h <= 0.001:
				continue
			var size := Vector3(w, h, th) if f["axis"] == "x" else Vector3(th, h, w)
			var cx: float = float(seg["x0"]) + w / 2.0 if f["axis"] == "x" else ((f["a"] as Vector2).x + (f["b"] as Vector2).x) / 2.0
			var cz: float = ((f["a"] as Vector2).y + (f["b"] as Vector2).y) / 2.0 if f["axis"] == "x" else float(seg["x0"]) + w / 2.0
			_add_box(grp, size, Vector3(cx, float(seg["y0"]) + h / 2.0, cz), str(s["material"]), true, "%s_wall_%s" % [s["id"], f["name"]])
		# window glass sits in its recess, so walls read as thick
		for o in openings.filter(func(x): return (x as Dictionary)["kind"] == "window"):
			var od: Dictionary = o
			var u: float = float(od["u"]) * float(f["len"])
			var y_base: float = float(od["sill"]) + (wall_h * 0.52 if od.has("floor") else 0.0)
			var gsize := Vector3(float(od["w"]), float(od["h"]), 0.04) if f["axis"] == "x" else Vector3(0.04, float(od["h"]), float(od["w"]))
			var gx: float = u if f["axis"] == "x" else ((f["a"] as Vector2).x + (f["b"] as Vector2).x) / 2.0
			var gz: float = ((f["a"] as Vector2).y + (f["b"] as Vector2).y) / 2.0 if f["axis"] == "x" else u
			_add_box(grp, gsize, Vector3(gx, y_base + float(od["h"]) / 2.0, gz), str(od.get("glass", "mat_leaded_glass")), false)
		# doors as hinged leaves with their own blocking volume
		for o in openings.filter(func(x): return (x as Dictionary)["kind"] == "door"):
			_build_door(grp, s, f, o, ox, oz)

	var floors: int = int(s.get("floors", 1))
	var floor_h: float = wall_h / float(maxi(1, floors))
	for room in (s["interior"] as Dictionary)["rooms"]:
		var rd: Dictionary = room
		var rect: Array = rd["rect"]
		var y: float = float(rd.get("floor", 0)) * floor_h
		var mi := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(float(rect[2]) - float(rect[0]), float(rect[3]) - float(rect[1]))
		mi.mesh = pm
		mi.material_override = _mat(str(rd["surface"]))
		mi.position = Vector3((float(rect[0]) + float(rect[2])) / 2.0, y + 0.01, (float(rect[1]) + float(rect[3])) / 2.0)
		grp.add_child(mi)
		if float(rd.get("floor", 0)) > 0.0:
			# the underside of an upper floor is the room below's ceiling, and
			# the slab is solid so the player cannot fall through it
			_add_box(grp, Vector3(pm.size.x, 0.12, pm.size.y), Vector3(mi.position.x, y - 0.06, mi.position.z), "surf_board_floor", true)
		interior_rooms.append({
			"id": "%s:%s" % [s["id"], rd["id"]], "structure": s["id"], "label_key": rd["label_key"],
			"rect": [ox + float(rect[0]), oz + float(rect[1]), ox + float(rect[2]), oz + float(rect[3])],
			"floor_y": y, "ambience": rd["ambience"], "surface": rd["surface"],
		})
		for p in rd.get("props", []):
			_build_prop(grp, s, p, y, ox, oz, quality)

	for st in (s["interior"] as Dictionary).get("stairs", []):
		var sd: Dictionary = st
		var rect: Array = sd["rect"]
		for i in int(sd["steps"]):
			_add_box(grp, Vector3(float(rect[2]) - float(rect[0]), float(sd["rise"]), float(sd["run"])),
				Vector3((float(rect[0]) + float(rect[2])) / 2.0, float(sd["rise"]) * (float(i) + 0.5), float(rect[1]) + float(sd["run"]) * (float(i) + 0.5)),
				str(sd["surface"]), true)

	var mezz = (s["interior"] as Dictionary).get("mezzanine", null)
	if mezz != null:
		var md: Dictionary = mezz
		var rect: Array = md["rect"]
		_add_box(grp, Vector3(float(rect[2]) - float(rect[0]), 0.18, float(rect[3]) - float(rect[1])),
			Vector3((float(rect[0]) + float(rect[2])) / 2.0, float(md["height"]), (float(rect[1]) + float(rect[3])) / 2.0),
			str(md["surface"]), true)
		var lp: Array = md["ladder_p"]
		ladders.append({"id": "%s_ladder" % s["id"], "pos": Vector2(ox + float(lp[0]), oz + float(lp[1])), "top": float(md["height"]), "label_key": "hud.interact"})

	for d in (s["interior"] as Dictionary).get("internal_doors", []):
		var dd: Dictionary = d
		var p: Array = dd["p"]
		var pivot := Node3D.new()
		pivot.position = Vector3(float(p[0]), 0.0, float(p[1]))
		grp.add_child(pivot)
		_add_box(pivot, Vector3(0.07, float(dd["h"]), float(dd["w"])), Vector3(0, float(dd["h"]) / 2.0, float(dd["w"]) / 2.0), "mat_plank_timber", true)
		var frac: float = 1.0 if dd.get("state") == "open" else 0.0
		pivot.rotation.y = -PI / 2.0 * frac
		doors.append({
			"id": "%s_int_%s" % [s["id"], "_".join(PackedStringArray(dd["between"]))],
			"pivot": pivot, "open_angle": -PI / 2.0, "frac": frac, "target": frac,
			"world": Vector2(ox + float(p[0]), oz + float(p[1])), "w": float(dd["w"]), "h": float(dd["h"]),
		})

	_build_roof(grp, s, fx, fz, wall_h)

func _build_door(grp: Node3D, s: Dictionary, f: Dictionary, o_in: Variant, ox: float, oz: float) -> void:
	var o: Dictionary = o_in
	var u: float = float(o["u"]) * float(f["len"])
	var leaves: int = 2 if o.get("hinge") == "double" else 1
	var leaf_w: float = float(o["w"]) / float(leaves)
	for i in leaves:
		var sign_f: float = (-1.0 if i == 0 else 1.0) if leaves == 2 else (1.0 if o.get("hinge") == "right" else -1.0)
		var px: float = (u + sign_f * float(o["w"]) / 2.0) if f["axis"] == "x" else ((f["a"] as Vector2).x + (f["b"] as Vector2).x) / 2.0
		var pz: float = ((f["a"] as Vector2).y + (f["b"] as Vector2).y) / 2.0 if f["axis"] == "x" else (u + sign_f * float(o["w"]) / 2.0)
		var pivot := Node3D.new()
		pivot.position = Vector3(px, 0.0, pz)
		grp.add_child(pivot)
		var leaf_pos := Vector3(-sign_f * leaf_w / 2.0, float(o["h"]) / 2.0, 0.0) if f["axis"] == "x" else Vector3(0.0, float(o["h"]) / 2.0, -sign_f * leaf_w / 2.0)
		var leaf_size := Vector3(leaf_w, float(o["h"]), 0.07) if f["axis"] == "x" else Vector3(0.07, float(o["h"]), leaf_w)
		_add_box(pivot, leaf_size, leaf_pos, "mat_plank_timber", true)
		var open_angle: float = (1.0 if o.get("swing") == "outward" else -1.0) * sign_f * PI * 0.52
		var start_frac: float = 1.0 if o.get("state") == "open" else (float(o.get("ajar_deg", 20)) / 94.0 if o.get("state") == "ajar" else 0.0)
		pivot.rotation.y = open_angle * start_frac
		doors.append({
			"id": "%s_door_%s_%d" % [s["id"], f["name"], i],
			"pivot": pivot, "open_angle": open_angle, "frac": start_frac, "target": start_frac,
			"world": Vector2(ox + px, oz + pz), "w": float(o["w"]), "h": float(o["h"]),
		})

## Split a wall face into solid rectangles around its openings.
func _punch_wall(f: Dictionary, openings: Array, wall_h: float) -> Array:
	var length: float = float(f["len"])
	if openings.is_empty():
		return [{"x0": 0.0, "x1": length, "y0": 0.0, "y1": wall_h}]
	var holes: Array = []
	for o in openings:
		var od: Dictionary = o
		var u: float = float(od["u"]) * length
		var lift: float = wall_h * 0.52 if od.has("floor") else 0.0
		holes.append({"u0": u - float(od["w"]) / 2.0, "u1": u + float(od["w"]) / 2.0, "y0": float(od["sill"]) + lift, "y1": float(od["sill"]) + float(od["h"]) + lift})
	var us: Array = [0.0, length]
	for h in holes:
		us.append(clampf(float((h as Dictionary)["u0"]), 0.0, length))
		us.append(clampf(float((h as Dictionary)["u1"]), 0.0, length))
	us.sort()
	var out: Array = []
	for i in us.size() - 1:
		var u0: float = float(us[i])
		var u1: float = float(us[i + 1])
		if u1 - u0 < 0.01:
			continue
		var mid: float = (u0 + u1) / 2.0
		var spanning: Array = holes.filter(func(h): return mid > float((h as Dictionary)["u0"]) and mid < float((h as Dictionary)["u1"]))
		spanning.sort_custom(func(a, b): return float(a["y0"]) < float(b["y0"]))
		if spanning.is_empty():
			out.append({"x0": u0, "x1": u1, "y0": 0.0, "y1": wall_h})
			continue
		var y: float = 0.0
		for h in spanning:
			var hd: Dictionary = h
			if float(hd["y0"]) > y:
				out.append({"x0": u0, "x1": u1, "y0": y, "y1": minf(float(hd["y0"]), wall_h)})
			y = maxf(y, float(hd["y1"]))
		if y < wall_h:
			out.append({"x0": u0, "x1": u1, "y0": y, "y1": wall_h})
	return out

func _build_roof(grp: Node3D, s: Dictionary, fx: float, fz: float, wall_h: float) -> void:
	var r: Dictionary = s["roof"]
	var over: float = float(r["overhang"])
	var pitch: float = deg_to_rad(float(r["pitch"]))
	if r["type"] == "gable":
		var half_span: float = fz / 2.0 + over
		var rise: float = tan(pitch) * half_span
		var slope: float = sqrt(half_span * half_span + rise * rise)
		for sign_f in [-1.0, 1.0]:
			var mesh := MeshInstance3D.new()
			var box := BoxMesh.new()
			box.size = Vector3(fx + over * 2.0, 0.12, slope)
			mesh.mesh = box
			mesh.material_override = _mat(str(r["material"]))
			mesh.position = Vector3(fx / 2.0, wall_h + rise / 2.0, fz / 2.0 + sign_f * half_span / 2.0)
			mesh.rotation.x = -sign_f * pitch
			grp.add_child(mesh)
		# gable ends close the attic so daylight does not leak in
		for z in [0.0, fz]:
			_add_box(grp, Vector3(fx, rise, 0.2), Vector3(fx / 2.0, wall_h + rise / 2.0, z), str(s["material"]), true)
	else:
		var rise: float = tan(pitch) * fz
		var mesh := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = Vector3(fx + over * 2.0, 0.1, sqrt(fz * fz + rise * rise) + over)
		mesh.mesh = box
		mesh.material_override = _mat(str(r["material"]))
		mesh.position = Vector3(fx / 2.0, wall_h + rise / 2.0, fz / 2.0)
		mesh.rotation.x = -pitch
		grp.add_child(mesh)

func _build_prop(grp: Node3D, s: Dictionary, p_in: Variant, y: float, ox: float, oz: float, quality: Dictionary) -> void:
	var p: Dictionary = p_in
	var pos: Array = p["p"]
	var spec: Dictionary = PROP_SIZES.get(str(p["t"]), {"size": Vector3(0.6, 0.5, 0.6), "mat": "mat_plank_timber"})
	var size: Vector3 = spec["size"]
	var node := _add_box(grp, size, Vector3(float(pos[0]), y + size.y / 2.0, float(pos[1])), str(spec["mat"]), size.y > 0.3)
	node.rotation.y = deg_to_rad(float(p.get("rot", 0)))
	if p.get("light") != null:
		var ld: Dictionary = p["light"]
		var light := OmniLight3D.new()
		light.light_color = _kelvin(float(ld["warm"]))
		light.light_energy = float(ld["intensity"]) * 1.6
		light.omni_range = float(ld["radius"])
		light.position = Vector3(float(pos[0]), y + 1.3, float(pos[1]))
		if bool(quality.get("shadows", true)) and ld["kind"] == "fire":
			light.shadow_enabled = true
		grp.add_child(light)
		gameplay_lights.append({
			"pos": Vector2(ox + float(pos[0]), oz + float(pos[1])), "y": y + 1.3,
			"radius": float(ld["radius"]), "intensity": minf(1.0, float(ld["intensity"]) / 2.6), "kind": ld["kind"],
		})

const PROP_SIZES := {
	"prop_hearth": {"size": Vector3(1.6, 1.3, 0.8), "mat": "mat_rubble_stone"},
	"prop_table_long": {"size": Vector3(2.2, 0.78, 0.9), "mat": "mat_plank_timber"},
	"prop_bench": {"size": Vector3(1.9, 0.45, 0.34), "mat": "mat_plank_timber"},
	"prop_chair": {"size": Vector3(0.46, 0.92, 0.46), "mat": "mat_plank_timber"},
	"prop_dresser": {"size": Vector3(1.1, 1.7, 0.45), "mat": "mat_wood_dark"},
	"prop_bed_iron": {"size": Vector3(1.0, 0.6, 1.95), "mat": "mat_metal_dull"},
	"prop_trunk": {"size": Vector3(0.9, 0.5, 0.5), "mat": "mat_wood_dark"},
	"prop_washstand": {"size": Vector3(0.6, 0.9, 0.4), "mat": "mat_plank_timber"},
	"prop_crate": {"size": Vector3(0.6, 0.5, 0.6), "mat": "mat_plank_timber"},
	"prop_barrel": {"size": Vector3(0.6, 0.86, 0.6), "mat": "mat_wood_dark"},
	"prop_sack_flour": {"size": Vector3(0.55, 0.5, 0.4), "mat": "mat_plank_timber"},
	"prop_pail": {"size": Vector3(0.3, 0.32, 0.3), "mat": "mat_metal_dull"},
	"prop_jerrycan": {"size": Vector3(0.18, 0.46, 0.36), "mat": "mat_metal_dull"},
	"prop_hay_pile": {"size": Vector3(2.4, 1.5, 2.0), "mat": "surf_crop"},
	"prop_cart": {"size": Vector3(2.6, 1.3, 1.5), "mat": "mat_plank_timber"},
	"prop_plough": {"size": Vector3(1.4, 0.9, 0.7), "mat": "mat_metal_dull"},
	"prop_toolrack": {"size": Vector3(0.25, 1.8, 1.6), "mat": "mat_plank_timber"},
	"prop_lantern": {"size": Vector3(0.16, 0.24, 0.16), "mat": "mat_metal_dull"},
	"prop_shelf": {"size": Vector3(0.3, 1.6, 1.4), "mat": "mat_plank_timber"},
	"prop_pew": {"size": Vector3(3.2, 0.95, 0.5), "mat": "mat_wood_dark"},
	"prop_candle_stand": {"size": Vector3(0.3, 1.1, 0.3), "mat": "mat_metal_dull"},
}

func _build_poi(p_in: Variant) -> void:
	var p: Dictionary = p_in
	var pos: Array = p["p"]
	var grp := Node3D.new()
	grp.name = str(p["id"])
	grp.position = Vector3(float(pos[0]), 0.0, float(pos[1]))
	add_child(grp)
	match str(p["id"]):
		"poi_field_telephone_junction":
			_add_box(grp, Vector3(0.24, 5.2, 0.24), Vector3(0, 2.6, 0), "mat_wood_dark", true)
			_add_box(grp, Vector3(1.5, 0.08, 0.08), Vector3(0, 4.7, 0), "mat_wood_dark", false)
			_add_box(grp, Vector3(0.34, 0.46, 0.2), Vector3(0, 1.35, 0.18), "mat_metal_dull", false)
		"poi_gun_position":
			_add_box(grp, Vector3(2.2, 1.5, 2.2), Vector3(0, 0.75, 0), "surf_packed_earth", true)
			_add_box(grp, Vector3(4.4, 0.32, 0.32), Vector3(0, 1.5, 0), "mat_metal_dull", false)
			_add_box(grp, Vector3(2.4, 1.2, 0.12), Vector3(0, 1.4, 0.7), "mat_metal_dull", true)
		"poi_arms_cache":
			_add_box(grp, Vector3(1.1, 0.5, 0.6), Vector3(0, 0.25, 0), "mat_plank_timber", true)
			_add_box(grp, Vector3(1.5, 0.22, 1.0), Vector3(0, 0.6, 0), "surf_crop", false)
		"poi_crossroad":
			_add_box(grp, Vector3(0.14, 2.3, 0.14), Vector3(0, 1.15, 0), "mat_wood_dark", false)
			_add_box(grp, Vector3(1.1, 0.22, 0.05), Vector3(0.4, 2.0, 0), "mat_plank_timber", false)

func _build_boundary() -> void:
	var size_m: Array = (data["grid"] as Dictionary)["size_m"]
	var w: float = float(size_m[0])
	var h: float = float(size_m[1])
	for spec in [
		{"size": Vector3(w + 4.0, 8.0, 2.0), "pos": Vector3(w / 2.0, 4.0, -1.0)},
		{"size": Vector3(w + 4.0, 8.0, 2.0), "pos": Vector3(w / 2.0, 4.0, h + 1.0)},
		{"size": Vector3(2.0, 8.0, h + 4.0), "pos": Vector3(-1.0, 4.0, h / 2.0)},
		{"size": Vector3(2.0, 8.0, h + 4.0), "pos": Vector3(w + 1.0, 4.0, h / 2.0)},
	]:
		var body := StaticBody3D.new()
		body.name = "boundary"
		var shape := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = (spec["size"] as Vector3)
		shape.shape = bs
		body.add_child(shape)
		body.position = (spec["pos"] as Vector3)
		add_child(body)

func _kelvin(k: float) -> Color:
	var t: float = k / 100.0
	var r: float = 255.0 if t <= 66.0 else 329.7 * pow(t - 60.0, -0.1332)
	var g: float = (99.47 * log(t) - 161.12) if t <= 66.0 else 288.12 * pow(t - 60.0, -0.0755)
	var b: float = 255.0 if t >= 66.0 else (0.0 if t <= 19.0 else 138.52 * log(t - 10.0) - 305.04)
	return Color(clampf(r / 255.0, 0, 1), clampf(g / 255.0, 0, 1), clampf(b / 255.0, 0, 1))

# ------------------------------------------------------------------ queries --

## Which authored surface is under a world position. Drives footstep audio.
func surface_at(p: Vector3) -> String:
	for r in interior_rooms:
		var rd: Dictionary = r
		var rect: Array = rd["rect"]
		if p.x >= float(rect[0]) and p.x <= float(rect[2]) and p.z >= float(rect[1]) and p.z <= float(rect[3]) and absf(p.y - float(rd["floor_y"])) < 1.6:
			return str(rd["surface"])
	var t = tile_index.get("%d,%d" % [int(floor(p.x / cell_m)), int(floor(p.z / cell_m))])
	return str((t as Dictionary)["surface"]) if t != null else "surf_grass"

func room_at(p: Vector3) -> Dictionary:
	for r in interior_rooms:
		var rd: Dictionary = r
		var rect: Array = rd["rect"]
		if p.x >= float(rect[0]) and p.x <= float(rect[2]) and p.z >= float(rect[1]) and p.z <= float(rect[3]) and absf(p.y - float(rd["floor_y"])) < 1.6:
			return rd
	return {}

func is_indoors(p: Vector3) -> bool:
	return not room_at(p).is_empty()

## Gameplay lights, with occlusion resolved against real geometry.
func gameplay_lights(from: Vector3) -> Array:
	var out: Array = []
	var space := get_world_3d().direct_space_state
	for l in gameplay_lights:
		var ld: Dictionary = l
		var pos: Vector2 = ld["pos"]
		var q := PhysicsRayQueryParameters3D.create(Vector3(pos.x, float(ld["y"]), pos.y), from + Vector3(0, 1.2, 0))
		var hit := space.intersect_ray(q)
		out.append({"pos": pos, "radius": ld["radius"], "intensity": ld["intensity"], "occluded": not hit.is_empty()})
	return out

func has_line_of_sight(from: Vector2, to: Vector2, posture: String) -> bool:
	var eye_a := 1.62
	var eye_b: float = {"prone": 0.42, "crouch": 1.05}.get(posture, 1.62)
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(Vector3(from.x, eye_a, from.y), Vector3(to.x, eye_b, to.y))
	return space.intersect_ray(q).is_empty()

## How much a wall between two points dampens sound, 0..1.
func acoustic_occlusion(from: Vector2, to: Vector2) -> float:
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(Vector3(from.x, 1.3, from.y), Vector3(to.x, 1.3, to.y))
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return 0.0
	var n: String = str((hit["collider"] as Node).name)
	if n.contains("door"):
		return 0.15 if _door_passable_near(Vector2(hit["position"].x, hit["position"].z)) else 0.6
	if n.begins_with("hedge"):
		return 0.35
	if n.contains("wall"):
		return 0.85
	return 0.5

func _door_passable_near(p: Vector2) -> bool:
	for d in doors:
		if (d["world"] as Vector2).distance_to(p) < 1.6 and float(d["frac"]) > 0.55:
			return true
	return false

func open_door(id: String, open: bool = true) -> void:
	for d in doors:
		if str(d["id"]) == id:
			d["target"] = 1.0 if open else 0.0

func nearest_door(p: Vector3, max_dist: float = 1.9) -> Dictionary:
	var best: Dictionary = {}
	var bd := max_dist
	for d in doors:
		var dist: float = (d["world"] as Vector2).distance_to(Vector2(p.x, p.z))
		if dist < bd:
			bd = dist
			best = d
	return best

func _process(dt: float) -> void:
	_elapsed += dt
	for d in doors:
		if absf(float(d["frac"]) - float(d["target"])) > 0.001:
			var dir: float = signf(float(d["target"]) - float(d["frac"]))
			d["frac"] = clampf(float(d["frac"]) + dir * dt * 1.6, 0.0, 1.0)
			(d["pivot"] as Node3D).rotation.y = float(d["open_angle"]) * float(d["frac"])
			# A door's collision travels with its leaf, so it is impassable
			# until it has actually opened far enough.
	# Wind moves crowns only; trunks and collision never move.
	if not bool(Settings.get_value("motion_reduction")):
		for i in swayables.size():
			var c: Node3D = swayables[i]
			var s: float = float(c.get_meta("sway", 0.3))
			c.rotation.z = sin(_elapsed * 0.9 + float(i) * 1.7) * 0.035 * s
			c.rotation.x = cos(_elapsed * 0.7 + float(i) * 2.3) * 0.028 * s
