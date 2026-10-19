extends Control
class_name StrategicMapView
## Strategic map (brief §5, §10). Drawn with the 2D canvas, because a hex map
## wants crisp lines and text at phone DPI far more than a 3D pipeline, and
## leaving the 3D renderer free is the memory decision the brief asks for:
## the full map and the full first-person world are never both resident.
##
## Touch: tap to select, drag to pan, pinch to zoom. No long press is ever the
## only way to reach an action.

signal selected(kind: String, id: String)

const TERRAIN_FILL := {
	"plain": Color(0.33, 0.34, 0.24), "farmland": Color(0.42, 0.42, 0.25),
	"hills": Color(0.36, 0.33, 0.25), "woods": Color(0.23, 0.29, 0.20),
	"bocage": Color(0.28, 0.33, 0.23), "mountain": Color(0.34, 0.33, 0.33),
	"desert": Color(0.54, 0.45, 0.29), "marsh": Color(0.27, 0.32, 0.30),
	"urban": Color(0.36, 0.35, 0.34), "port": Color(0.31, 0.35, 0.39),
	"water": Color(0.13, 0.21, 0.26), "impassable": Color(0.16, 0.16, 0.16),
}
const CONTROL_TINT := {
	"allied": Color(0.36, 0.50, 0.60, 0.34), "axis": Color(0.66, 0.28, 0.18, 0.34),
	"contested": Color(0.79, 0.56, 0.21, 0.30), "neutral": Color(0.42, 0.45, 0.49, 0.12),
}

var theater: String = "theater_western_europe"
var hex_size: float = 38.0
var zoom: float = 1.0
var pan := Vector2.ZERO
var selection: Dictionary = {}
var range_tiles: Dictionary = {}     # tile_id -> cost
var preview_path: Array = []

var _pointers: Dictionary = {}
var _pinch_start_dist: float = 0.0
var _pinch_start_zoom: float = 1.0
var _dragged: float = 0.0
var _font: Font

func _ready() -> void:
	_font = ThemeDB.fallback_font
	set_process_unhandled_input(true)
	Campaign.campaign_changed.connect(queue_redraw)
	centre_on_theater()

func theaters_open() -> Array:
	var out: Array = []
	for th in ContentDB.atlas.get("theaters", []):
		if (Campaign.c["history_flags"] as Dictionary).has("theater_open:%s" % th["id"]) or CampaignDate.is_on_or_after(str(Campaign.c["date"]), str(th["opens_on"])):
			out.append(th)
	return out

func set_theater(id: String) -> void:
	theater = id
	centre_on_theater()
	queue_redraw()

func tiles_of(th: String) -> Array:
	var out: Array = []
	for id in Campaign.c["tiles"]:
		var t: Dictionary = Campaign.c["tiles"][id]
		if t["theater"] == th:
			out.append(t)
	return out

func centre_on_theater() -> void:
	var tiles := tiles_of(theater)
	if tiles.is_empty():
		return
	var mn := Vector2(INF, INF)
	var mx := Vector2(-INF, -INF)
	for t in tiles:
		var p := Hex.to_pixel(int((t as Dictionary)["q"]), int((t as Dictionary)["r"]), hex_size)
		mn = Vector2(minf(mn.x, p.x), minf(mn.y, p.y))
		mx = Vector2(maxf(mx.x, p.x), maxf(mx.y, p.y))
	var span := mx - mn + Vector2(hex_size * 3.0, hex_size * 3.0)
	zoom = clampf(minf((size.x - 24.0) / span.x, (size.y - 150.0) / span.y), 0.55, 1.6)
	pan = Vector2(size.x / 2.0, (size.y - 60.0) / 2.0 + 20.0) - (mn + mx) * 0.5 * zoom

func to_screen(q: int, r: int) -> Vector2:
	return Hex.to_pixel(q, r, hex_size) * zoom + pan

func from_screen(p: Vector2) -> Vector2i:
	return Hex.from_pixel((p - pan) / zoom, hex_size)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var e := event as InputEventScreenTouch
		if e.pressed:
			_pointers[e.index] = e.position
			_dragged = 0.0
			if _pointers.size() == 2:
				var ps: Array = _pointers.values()
				_pinch_start_dist = (ps[0] as Vector2).distance_to(ps[1] as Vector2)
				_pinch_start_zoom = zoom
		else:
			_pointers.erase(e.index)
			if _dragged < 12.0 and _pointers.is_empty():
				_handle_tap(e.position)
	elif event is InputEventScreenDrag:
		var e := event as InputEventScreenDrag
		if not _pointers.has(e.index):
			return
		_dragged += e.relative.length()
		_pointers[e.index] = e.position
		if _pointers.size() == 2 and _pinch_start_dist > 0.0:
			var ps: Array = _pointers.values()
			var d: float = (ps[0] as Vector2).distance_to(ps[1] as Vector2)
			var centre: Vector2 = ((ps[0] as Vector2) + (ps[1] as Vector2)) * 0.5
			var world := (centre - pan) / zoom
			zoom = clampf(_pinch_start_zoom * (d / _pinch_start_dist), 0.45, 2.6)
			pan = centre - world * zoom
		else:
			pan += e.relative
		queue_redraw()

func _handle_tap(p: Vector2) -> void:
	var axial := from_screen(p)
	var id := "%s:%d,%d" % [theater, axial.x, axial.y]
	if not (Campaign.c["tiles"] as Dictionary).has(id):
		selection = {}
		queue_redraw()
		return
	var tile: Dictionary = Campaign.c["tiles"][id]
	# While a unit with a movement overlay is selected, tapping a highlighted
	# tile previews the move; the order still needs explicit confirmation.
	if selection.get("kind") == "unit" and range_tiles.has(id):
		preview_path = []
		var r := Campaign.movement_range(str(selection["id"]))
		for t in r["tiles"]:
			if (t as Dictionary)["tile_id"] == id:
				preview_path = (t as Dictionary)["path"]
		selected.emit("move_target", id)
		queue_redraw()
		return
	# Prefer a unit the player can order, then the city, then the tile.
	var mine: Array = []
	for uid in (Campaign.c["units"] as Dictionary).keys():
		var u: Dictionary = Campaign.c["units"][uid]
		if u["tile_id"] == id and u["faction"] == Campaign.c["player_faction"]:
			mine.append(uid)
	mine.sort()
	if not mine.is_empty():
		select({"kind": "unit", "id": mine[0]})
	elif tile.get("city_id") != null:
		select({"kind": "city", "id": tile["city_id"]})
	else:
		select({"kind": "tile", "id": id})

func select(sel: Dictionary) -> void:
	selection = sel
	range_tiles.clear()
	preview_path.clear()
	if sel.get("kind") == "unit":
		var u: Dictionary = (Campaign.c["units"] as Dictionary).get(sel["id"], {})
		if not u.is_empty() and u["faction"] == Campaign.c["player_faction"] and int(u["move_budget"]) > 0:
			for t in (Campaign.movement_range(str(sel["id"]))["tiles"] as Array):
				range_tiles[(t as Dictionary)["tile_id"]] = int((t as Dictionary)["cost"])
	selected.emit(str(sel.get("kind", "")), str(sel.get("id", "")))
	queue_redraw()

func _hex_points(centre: Vector2, s: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in 6:
		var a := deg_to_rad(60.0 * float(i) - 30.0)
		pts.append(centre + Vector2(cos(a), sin(a)) * s)
	return pts

func _draw() -> void:
	var high_contrast := bool(Settings.get_value("high_contrast"))
	draw_rect(Rect2(Vector2.ZERO, size), Color.BLACK if high_contrast else Color(0.051, 0.063, 0.075))
	var s := hex_size * zoom
	var tiles := tiles_of(theater)

	for t in tiles:
		var td: Dictionary = t
		var p := to_screen(int(td["q"]), int(td["r"]))
		if p.x < -s * 2.0 or p.x > size.x + s * 2.0 or p.y < -s * 2.0 or p.y > size.y + s * 2.0:
			continue
		var pts := _hex_points(p, s * 0.98)
		draw_colored_polygon(pts, TERRAIN_FILL.get(str(td["terrain"]), TERRAIN_FILL["plain"]))
		if not bool(td["discovered"]):
			draw_colored_polygon(pts, Color(0.03, 0.04, 0.05, 0.72))
		else:
			draw_colored_polygon(pts, CONTROL_TINT.get(str(td["control"]), Color.TRANSPARENT))
			# Supply is shaded, and a number is added once the map is zoomed in.
			if bool(td["passable"]) and float(td["supply"]) < 3.0:
				draw_colored_polygon(pts, Color(0.04, 0.05, 0.055, 0.1 + (3.0 - float(td["supply"])) * 0.09))
		draw_polyline(pts + PackedVector2Array([pts[0]]), Color(0.85, 0.82, 0.77, 0.35) if high_contrast else Color(0, 0, 0, 0.45), 1.0)
		if not bool(td["passable"]):
			# Impassable ground is drawn, not merely refused when tapped.
			for i in range(-2, 3):
				draw_line(p + Vector2(-s + float(i) * s * 0.5, s), p + Vector2(s + float(i) * s * 0.5, -s), Color(0, 0, 0, 0.5), 2.0)

	for id in range_tiles:
		var t: Dictionary = (Campaign.c["tiles"] as Dictionary).get(id, {})
		if t.is_empty() or t["theater"] != theater:
			continue
		var p := to_screen(int(t["q"]), int(t["r"]))
		var pts := _hex_points(p, s * 0.9)
		draw_colored_polygon(pts, Color(0.79, 0.56, 0.21, 0.18))
		draw_polyline(pts + PackedVector2Array([pts[0]]), Color(0.79, 0.56, 0.21, 0.75), 1.5)
		if s > 26.0 and _font:
			draw_string(_font, p + Vector2(-6, s * 0.5), str(range_tiles[id]), HORIZONTAL_ALIGNMENT_LEFT, -1, int(s * 0.34), Color(0.95, 0.93, 0.89))

	if preview_path.size() > 1:
		var pts := PackedVector2Array()
		for id in preview_path:
			var t: Dictionary = (Campaign.c["tiles"] as Dictionary).get(id, {})
			if not t.is_empty():
				pts.append(to_screen(int(t["q"]), int(t["r"])))
		if pts.size() > 1:
			draw_polyline(pts, Color(0.79, 0.56, 0.21, 0.95), maxf(2.0, s * 0.09))

	for t in tiles:
		var td: Dictionary = t
		var p := to_screen(int(td["q"]), int(td["r"]))
		if td.get("city_id") != null and bool(td["discovered"]):
			_draw_city(p, s, (Campaign.c["cities"] as Dictionary)[td["city_id"]])
		var occupants: Array = []
		for uid in (Campaign.c["units"] as Dictionary).keys():
			var u: Dictionary = Campaign.c["units"][uid]
			if u["tile_id"] != td["tile_id"]:
				continue
			var cap: Dictionary = Contracts.UNIT_CAPABILITIES[u["unit_type"]]
			# A covert unit is only drawn if it is the player's own.
			if u["faction"] == Campaign.c["player_faction"] or bool(cap["visible_on_map"]):
				occupants.append(u)
		occupants.sort_custom(func(a, b): return str(a["unit_id"]) < str(b["unit_id"]))
		for i in occupants.size():
			_draw_unit(p, s, occupants[i], i, occupants.size())

	if not selection.is_empty():
		var tile_id := ""
		match str(selection.get("kind", "")):
			"unit": tile_id = str(((Campaign.c["units"] as Dictionary).get(selection["id"], {}) as Dictionary).get("tile_id", ""))
			"city": tile_id = str(((Campaign.c["cities"] as Dictionary).get(selection["id"], {}) as Dictionary).get("tile_id", ""))
			"tile": tile_id = str(selection["id"])
		var t: Dictionary = (Campaign.c["tiles"] as Dictionary).get(tile_id, {})
		if not t.is_empty() and t["theater"] == theater:
			var p := to_screen(int(t["q"]), int(t["r"]))
			draw_polyline(_hex_points(p, s * 0.99) + PackedVector2Array([_hex_points(p, s * 0.99)[0]]), Color(0.95, 0.93, 0.89), 2.5)

func _draw_city(p: Vector2, s: float, city: Dictionary) -> void:
	var r := s * 0.3
	var centre := p - Vector2(0, s * 0.12)
	var colour: Color = {"allied": Color(0.36, 0.50, 0.60), "axis": Color(0.66, 0.28, 0.18)}.get(str(city["control"]), Color(0.79, 0.56, 0.21))
	draw_rect(Rect2(centre - Vector2(r, r * 0.8), Vector2(r * 2.0, r * 1.6)), Color(0.055, 0.063, 0.071, 0.82), true)
	draw_rect(Rect2(centre - Vector2(r, r * 0.8), Vector2(r * 2.0, r * 1.6)), colour, false, 2.0)
	# Facility pips: what is built is visible on the map without opening a panel.
	var built := 0
	for f in city["facilities"]:
		if not bool((f as Dictionary).get("disabled", false)):
			built += 1
	var queued: int = (city["construction_queue"] as Array).size()
	for i in mini(5, built + queued):
		draw_circle(centre + Vector2(-r + r * 0.4 + float(i) * r * 0.38, r * 1.1), maxf(1.4, r * 0.11),
			Color(0.79, 0.56, 0.21) if i < built else Color(0.79, 0.56, 0.21, 0.4))
	if s > 28.0 and _font:
		draw_string(_font, centre + Vector2(-r * 2.0, r * 2.2), Loc.t(str(city["label_key"])), HORIZONTAL_ALIGNMENT_CENTER, r * 4.0, int(s * 0.26), Color(0.87, 0.85, 0.79))

func _draw_unit(p: Vector2, s: float, u: Dictionary, index: int, total: int) -> void:
	var cap: Dictionary = Contracts.UNIT_CAPABILITIES[u["unit_type"]]
	var spread: float = (float(index) - float(total - 1) / 2.0) * s * 0.46 if total > 1 else 0.0
	var centre := p + Vector2(spread, s * 0.42)
	var r := s * 0.2
	var allied := not str(u["faction"]).begins_with("axis_")
	var fill := Color(0.36, 0.50, 0.60, 0.92) if allied else Color(0.66, 0.28, 0.18, 0.92)
	if bool(cap["visible_on_map"]):
		draw_rect(Rect2(centre - Vector2(r, r * 0.7), Vector2(r * 2.0, r * 1.4)), fill, true)   # formation: block
	else:
		draw_colored_polygon(PackedVector2Array([centre + Vector2(0, -r), centre + Vector2(r, 0), centre + Vector2(0, r), centre + Vector2(-r, 0)]), fill)  # covert: diamond
	# Strength bar: colour-independent, because the bar length carries the value.
	var bw := r * 2.0
	draw_rect(Rect2(centre - Vector2(bw / 2.0, -r * 0.95), Vector2(bw, maxf(2.0, r * 0.22))), Color(0, 0, 0, 0.55), true)
	draw_rect(Rect2(centre - Vector2(bw / 2.0, -r * 0.95), Vector2(bw * float(u["strength"]), maxf(2.0, r * 0.22))),
		Color(0.48, 0.60, 0.37) if float(u["strength"]) > 0.6 else (Color(0.79, 0.56, 0.21) if float(u["strength"]) > 0.3 else Color(0.66, 0.28, 0.18)), true)
	if (u["status"] as Array).has("isolated") and _font:
		draw_string(_font, centre + Vector2(-r * 0.2, -r * 1.1), "!", HORIZONTAL_ALIGNMENT_LEFT, -1, int(r * 1.3), Color(0.95, 0.93, 0.89))
	if (u["status"] as Array).has("entrenched"):
		draw_line(centre + Vector2(-r * 1.2, r * 0.6), centre + Vector2(r * 1.2, r * 0.6), Color(0.95, 0.93, 0.89, 0.8), 1.0)
