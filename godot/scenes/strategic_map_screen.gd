extends Control
## Strategic map screen: the map view plus the mobile sheets.
##
## A unit or city selection opens a focused sheet with the primary action
## immediately visible (brief §5), and every order goes through an explicit
## confirmation that shows its cost before it is committed.

@onready var _map: StrategicMapView = $Map
@onready var _date: Label = $TopBar/Date
@onready var _theaters: HBoxContainer = $TopBar/Theaters
@onready var _resources: HBoxContainer = $TopBar/Resources
@onready var _bottom: HBoxContainer = $BottomBar
@onready var _sheet: PanelContainer = $Sheet
@onready var _sheet_body: VBoxContainer = $Sheet/Body

func _ready() -> void:
	_map.selected.connect(_on_selected)
	Campaign.turn_resolved.connect(_show_turn_report)
	Campaign.order_rejected.connect(func(_id, reason, detail): _toast("%s %s" % [Loc.t(reason), detail]))
	Campaign.campaign_changed.connect(_refresh_chrome)
	_refresh_chrome()

func _refresh_chrome() -> void:
	_date.text = "%s  ·  %s %d" % [Loc.date(str(Campaign.c["date"])), Loc.t("map.turn"), int(Campaign.c["turn"])]
	for child in _theaters.get_children():
		child.queue_free()
	for th in _map.theaters_open():
		var b := Button.new()
		b.text = Loc.t(str(th["label_key"]))
		b.toggle_mode = true
		b.button_pressed = th["id"] == _map.theater
		b.custom_minimum_size = Vector2(0, 48)
		b.pressed.connect(func(): _map.set_theater(str(th["id"])); _refresh_chrome())
		_theaters.add_child(b)
	for child in _resources.get_children():
		child.queue_free()
	for pair in [["materiel", "map.materiel"], ["personnel", "map.personnel"], ["intelligence", "map.intelligence"]]:
		var l := Label.new()
		l.text = "%s %s" % [Loc.t(str(pair[1])), Loc.num(float(Campaign.c["resources"][pair[0]]))]
		_resources.add_child(l)
	for child in _bottom.get_children():
		child.queue_free()
	var ops := Button.new()
	var playable := 0
	for ch in Campaign.available_chapters():
		if (ch as Dictionary)["status"] == "authored" and ContentDB.districts.has((ch as Dictionary)["district"]):
			playable += 1
	ops.text = "%s (%d)" % [Loc.t("mission.briefing"), playable]
	ops.disabled = playable == 0
	ops.custom_minimum_size = Vector2(0, 48)
	ops.pressed.connect(_open_operations)
	_bottom.add_child(ops)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_bottom.add_child(spacer)
	if not (Campaign.c["order_queue"] as Array).is_empty():
		var q := Button.new()
		q.text = "%s (%d)" % [Loc.t("map.no_orders"), (Campaign.c["order_queue"] as Array).size()]
		q.custom_minimum_size = Vector2(0, 48)
		q.pressed.connect(_open_queue)
		_bottom.add_child(q)
	var end := Button.new()
	end.text = Loc.t("map.end_turn")
	end.custom_minimum_size = Vector2(0, 48)
	end.pressed.connect(func():
		var out := Campaign.end_turn()
		if not bool(out["ok"]):
			_toast(Loc.t(str(out["reason"]))))
	_bottom.add_child(end)

func _clear_sheet(kicker: String, title: String) -> void:
	for child in _sheet_body.get_children():
		child.queue_free()
	_sheet.visible = true
	var k := Label.new()
	k.text = kicker
	k.modulate = Color(0.79, 0.56, 0.21)
	var t := Label.new()
	t.text = title
	_sheet_body.add_child(k)
	_sheet_body.add_child(t)

func _row(text: String, fn: Variant = null) -> void:
	if fn is Callable:
		var b := Button.new()
		b.text = text
		b.custom_minimum_size = Vector2(0, 48)
		b.pressed.connect(fn)
		_sheet_body.add_child(b)
	else:
		var l := Label.new()
		l.text = text
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_sheet_body.add_child(l)

func _on_selected(kind: String, id: String) -> void:
	match kind:
		"unit": _open_unit(id)
		"city": _open_city(id)
		"tile": _open_tile(id)
		"move_target": _confirm_order({"kind": "move", "unit_id": str(_map.selection["id"]), "tile_id": id})
		_: _sheet.visible = false

func _open_unit(unit_id: String) -> void:
	var u: Dictionary = (Campaign.c["units"] as Dictionary).get(unit_id, {})
	if u.is_empty():
		return
	_clear_sheet(Loc.t("unit.%s" % u["unit_type"]), Loc.t(str(u["label_key"])))
	var explain := Campaign.explain_unit(unit_id)
	_row("%s %d%%   %s %d%%   %s %d/%d" % [
		Loc.t("hud.health"), int(float(u["strength"]) * 100.0),
		Loc.t("map.supply"), int(float(u["supply"]) * 100.0),
		Loc.t("map.route"), int(u["move_budget"]), int(u["move_budget_max"])])
	for r in explain["reasons"]:
		_row("· %s" % Loc.t(str((r as Dictionary)["key"])))
	if u["faction"] != Campaign.c["player_faction"]:
		_row(Loc.t("reject.wrong_faction"))
		return
	# Only the actions this kind of group can actually perform are offered.
	for verb in u["allowed_actions"]:
		var label: String = {
			"entrench": "explain.entrenched", "defend": "mf.defence", "hide": "mf.concealment",
			"reconnoitre": "mf.recon", "sabotage": "mf.sabotage", "courier": "mf.courier",
			"relieve": "mf.medical", "evacuate": "mf.evacuation",
		}.get(str(verb), "")
		if label == "":
			continue
		_row(Loc.t(label), func(): _confirm_order({"kind": str(verb), "unit_id": unit_id, "tile_id": u["tile_id"], "city_id": (Campaign.c["tiles"][u["tile_id"]] as Dictionary).get("city_id", "")}))
	if not _map.range_tiles.is_empty():
		_row("%s — %d %s" % [Loc.t("map.move_here"), _map.range_tiles.size(), Loc.t("map.route")])

func _open_city(city_id: String) -> void:
	var city: Dictionary = (Campaign.c["cities"] as Dictionary).get(city_id, {})
	if city.is_empty():
		return
	_clear_sheet(Loc.t(str(city["theater"]).replace("theater_", "theater.")), Loc.t(str(city["label_key"])))
	_row("%s %s   ·   %s %d/%d" % [Loc.t("map.supply"), Loc.num(float(city["supply_access"]), 1), Loc.t("map.build"), (city["facilities"] as Array).size(), int(city["facilities_max"])])
	if int(city["restriction_level"]) > 0:
		_row("%s %d/5" % [Loc.t("content.intensity"), int(city["restriction_level"])])
	for gid in city["civilian_group_ids"]:
		var g: Dictionary = Campaign.c["civilian_groups"][gid]
		_row("%s — %d %s" % [Loc.t(str(g["label_key"])), int(g["headcount"]), g["displacement"]])
		var needs: Dictionary = g["needs"]
		_row("  food %d%%  water %d%%  medicine %d%%  shelter %d%%" % [
			int(float(needs["food"]) * 100.0), int(float(needs["water"]) * 100.0),
			int(float(needs["medicine"]) * 100.0), int(float(needs["shelter"]) * 100.0)])
	for nid in city["network_ids"]:
		var n: Dictionary = Campaign.c["networks"][nid]
		var intact := 0
		for c in n["cells"]:
			if not bool((c as Dictionary).get("compromised", false)):
				intact += 1
		_row("%s — access %d/5, exposure %d%%, cells %d/%d" % [Loc.t(str(n["label_key"])), int(n["access"]), int(float(n["exposure"]) * 100.0), intact, (n["cells"] as Array).size()])
	for spec in ContentDB.atlas.get("facility_catalog", []):
		var probe := Campaign.preview_order({"order_id": "probe_%s" % spec["id"], "kind": "construct", "city_id": city_id, "facility_id": spec["id"]})
		var label := "%s — %s" % [Loc.t(str(spec["label_key"])), (("%d %s" % [int(spec["build_turns"]), Loc.t("map.turn")]) if bool(probe["ok"]) else Loc.t(str(probe["reason"])))]
		if bool(probe["ok"]):
			_row(label, func(): _confirm_order({"kind": "construct", "city_id": city_id, "facility_id": spec["id"]}))
		else:
			_row(label)

func _open_tile(tile_id: String) -> void:
	var t: Dictionary = (Campaign.c["tiles"] as Dictionary).get(tile_id, {})
	if t.is_empty():
		return
	_clear_sheet(str(t["terrain"]), "%d, %d" % [int(t["q"]), int(t["r"])])
	var rule := ContentDB.terrain_rule(str(t["terrain"]))
	_row("%s %s   ·   %s %s" % [Loc.t("map.supply"), Loc.num(float(t["supply"]), 1), str(t["control"]), ("" if bool(t["passable"]) else Loc.t("map.impassable_border"))])
	_row("move cost %d   ·   cover %d%%" % [int(rule.get("move_cost", 1)), int(float(rule.get("cover", 0.0)) * 100.0)])

## The confirmation step with the cost preview the brief requires.
func _confirm_order(order: Dictionary) -> void:
	var full := order.duplicate()
	full["order_id"] = "ord_%d_%d" % [int(Campaign.c["revision"]), randi()]
	var preview := Campaign.preview_order(full)
	_clear_sheet(Loc.t("map.confirm_order"), Loc.t("map.cost"))
	if not bool(preview["ok"]):
		_row("%s %s" % [Loc.t(str(preview["reason"])), str(preview["detail"])])
		_row(Loc.t("map.cancel"), func(): _sheet.visible = false)
		return
	var costs: Array = []
	for k in preview["cost"]:
		if int(preview["cost"][k]) != 0:
			costs.append("%s −%d" % [Loc.t("map.%s" % k), int(preview["cost"][k])])
	_row(", ".join(costs) if not costs.is_empty() else "no resource cost")
	var plan: Dictionary = preview["plan"]
	if plan.has("path"):
		_row("%s: %d steps · move cost %d" % [Loc.t("map.route"), (plan["path"] as Array).size() - 1, int(plan["move_cost"])])
	_row(Loc.t("map.confirm_order"), func():
		var out := Campaign.submit_order(full)
		if bool(out["ok"]):
			_sheet.visible = false
			_map.select({}))
	_row(Loc.t("map.cancel"), func(): _sheet.visible = false)

func _open_queue() -> void:
	_clear_sheet(Loc.t("map.turn"), Loc.t("map.no_orders"))
	for q in Campaign.c["order_queue"]:
		var qd: Dictionary = q
		_row("%s — %s" % [str((qd["order"] as Dictionary)["kind"]), Loc.t("map.cancel")], func():
			Campaign.cancel_order(str(qd["order_id"]))
			_open_queue())

func _open_operations() -> void:
	_clear_sheet(Loc.t("mission.briefing"), Loc.t("mission.objectives"))
	for ch in Campaign.available_chapters():
		var cd: Dictionary = ch
		var installed := ContentDB.districts.has(cd["district"])
		var playable: bool = cd["status"] == "authored" and installed
		var label := "%s — %s" % [Loc.t(str(cd["label_key"])), (Loc.t("mission.begin") if playable else (Loc.t("error.content_missing") if not installed else str(cd["status"])))]
		if playable:
			_row(label, func(): _begin(cd))
		else:
			_row(label)

func _begin(chapter: Dictionary) -> void:
	var unit_id := ""
	for uid in (Campaign.c["units"] as Dictionary).keys():
		var u: Dictionary = Campaign.c["units"][uid]
		if u["faction"] == Campaign.c["player_faction"]:
			unit_id = uid
			if (Campaign.c["tiles"][u["tile_id"]] as Dictionary).get("city_id") == chapter["location"]:
				break
	var tile_id: String = str(((Campaign.c["cities"] as Dictionary).get(chapter["location"], {}) as Dictionary).get("tile_id", ""))
	if tile_id == "" and unit_id != "":
		tile_id = str((Campaign.c["units"][unit_id] as Dictionary)["tile_id"])
	var loadout: Array = ["tool_wire_cutters", "wpn_pistol_civ"] if (chapter["mission_families"] as Array).has("mission_family_sabotage") else ["wpn_pistol_civ", "tool_medical_kit"]
	var out := Campaign.enter_mission({
		"chapter_id": chapter["id"], "district_id": chapter["district"],
		"tile_id": tile_id, "unit_id": unit_id, "loadout": loadout,
	}, str(Time.get_ticks_msec()))
	if not bool(out["ok"]):
		_toast("%s (%s)" % [Loc.t("error.transition_failed"), out["code"]])
		return
	get_tree().change_scene_to_file("res://scenes/mission.tscn")

func _show_turn_report(report: Dictionary) -> void:
	_clear_sheet(Loc.t("map.turn_report"), "%s %d → %d" % [Loc.t("map.turn"), int(report["turn"]), int(report["turn"]) + 1])
	for r in report["rejected_orders"]:
		_row("✗ %s" % Loc.t(str((r as Dictionary)["reason"])))
	for m in report["movements"]:
		_row("→ %s" % str((m as Dictionary)["to"]).split(":")[1])
	for e in report["engagements"]:
		_row("⚔ %s %s" % [str((e as Dictionary)["tile_id"]).split(":")[1], str((e as Dictionary)["kind"])])
	for o in report["opposition"]:
		_row("◼ %s %s" % [str((o as Dictionary)["unit_id"]), str((o as Dictionary)["decision"])])
	for c in report["construction"]:
		_row("⚒ %s" % JSON.stringify(c))
	for ev in report["events"]:
		var label: String = Loc.t(str((ev as Dictionary)["label_key"]))
		_row("● %s%s" % [label, " ⚑" if (ev as Dictionary).get("sensitivity") == "high" else ""])
	for ev in report["events"]:
		if (ev as Dictionary).get("sensitivity") == "high":
			_row("⚑ %s" % Loc.t("content.sensitive_notice"))
			break

func _toast(text: String) -> void:
	var l := Label.new()
	l.text = text
	l.position = Vector2(size.x / 2.0 - 160.0, 70.0)
	l.custom_minimum_size = Vector2(320, 40)
	add_child(l)
	await get_tree().create_timer(3.4).timeout
	if is_instance_valid(l):
		l.queue_free()
