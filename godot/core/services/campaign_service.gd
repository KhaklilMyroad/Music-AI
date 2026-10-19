extends Node
## CampaignService: the single authority that applies commands and mission
## outcomes (brief §16). The map view, the mission scene and the UI submit
## requests here; none of them writes campaign state directly.

signal order_queued(order_id: String, cost: Dictionary, plan: Dictionary)
signal order_rejected(order_id: String, reason: String, detail: String)
signal order_cancelled(order_id: String)
signal turn_resolved(report: Dictionary)
signal mission_resolved(applied: Variant, clamped: Array)
signal recovered(info: Dictionary)
signal campaign_changed()

const CONTROL_CHAR := {"A": "allied", "X": "axis", "N": "neutral", "C": "contested"}
const TERRAIN_CHAR := {
	".": "plain", "f": "farmland", "h": "hills", "w": "woods", "b": "bocage",
	"m": "mountain", "d": "desert", "s": "marsh", "u": "urban", "p": "port",
	"~": "water", "#": "impassable", " ": "plain",
}

var c: Dictionary = {}

# ---------------------------------------------------------------- bootstrap --

## Build an authoritative CampaignState from the content data. One place where
## the atlas becomes runtime state, so the map view and the resolver cannot
## disagree about the world.
func new_campaign(opts: Dictionary = {}) -> Dictionary:
	var campaign := Contracts.make_campaign({
		"campaign_id": opts.get("campaign_id", "cmp_main"),
		"turn": 1,
		"date": opts.get("date", (ContentDB.chapters.get("campaign_range", {}) as Dictionary).get("start", "1939-09-01")),
		"mode": opts.get("mode", "campaign"),
		"player_faction": opts.get("player_faction", "french_resistance"),
		"resources": opts.get("resources", {"materiel": 60, "personnel": 30, "intelligence": 2, "documents": 0}),
		"rng_seed": int(opts.get("seed", 20260101)),
	})

	for th in ContentDB.atlas.get("theaters", []):
		var rows: Array = th["rows"]
		var control: Array = th["control"]
		var offsets: Array = th["row_offset"]
		for r in rows.size():
			var row: String = rows[r]
			var ctrl: String = control[r]
			var off: int = int(offsets[r])
			for col in row.length():
				var q: int = col + off
				var terrain: String = TERRAIN_CHAR.get(row[col], "plain")
				var rule := ContentDB.terrain_rule(terrain)
				var id := "%s:%d,%d" % [th["id"], q, r]
				campaign["tiles"][id] = Contracts.make_tile({
					"tile_id": id, "theater": th["id"], "q": q, "r": r, "terrain": terrain,
					"control": CONTROL_CHAR.get(ctrl[col], "neutral"),
					"passable": bool(rule.get("passable", true)),
					"naval_only": bool(rule.get("naval_only", false)),
					"neighbors": [],
					"discovered": CampaignDate.is_on_or_after(str(campaign["date"]), str(th["opens_on"])),
				})
	# Neighbour links stay inside a theatre; sea links connect theatres.
	for id in campaign["tiles"]:
		var t: Dictionary = campaign["tiles"][id]
		var nb: Array = []
		for v in Hex.neighbors(int(t["q"]), int(t["r"])):
			var nid := "%s:%d,%d" % [t["theater"], v.x, v.y]
			if (campaign["tiles"] as Dictionary).has(nid):
				nb.append(nid)
		t["neighbors"] = nb

	for th in ContentDB.atlas.get("theaters", []):
		for city in th.get("cities", []):
			var tid := "%s:%d,%d" % [th["id"], int(city["q"]), int(city["r"])]
			if not (campaign["tiles"] as Dictionary).has(tid):
				push_error("city %s points at missing tile %s" % [city["id"], tid])
				continue
			var tile: Dictionary = campaign["tiles"][tid]
			campaign["cities"][city["id"]] = Contracts.make_city({
				"city_id": city["id"], "label_key": city["label_key"], "theater": th["id"], "tile_id": tid,
				"control": tile["control"], "facilities_max": int(city.get("facilities_max", 4)),
				"districts": city.get("districts", []),
			})
			tile["city_id"] = city["id"]

	# Communities and networks for the cities that have a playable district.
	for cid in campaign["cities"]:
		var city: Dictionary = campaign["cities"][cid]
		if (city["districts"] as Array).is_empty():
			continue
		var gid := "grp_%s_community" % cid
		campaign["civilian_groups"][gid] = Contracts.make_civilian_group({
			"group_id": gid, "label_key": "civgroup.%s" % cid, "city_id": cid, "tile_id": city["tile_id"],
			"headcount": 240, "community_id": "com_%s" % cid,
			"household_ids": ["hh_%s_a" % cid, "hh_%s_b" % cid, "hh_%s_c" % cid],
			"needs": {"food": 0.8, "water": 0.85, "medicine": 0.6, "shelter": 0.9},
		})
		(city["civilian_group_ids"] as Array).append(gid)
		var nid := "net_%s" % cid
		campaign["networks"][nid] = Contracts.make_network({
			"network_id": nid, "label_key": "network.%s" % cid, "city_id": cid,
			"cells": [
				{"cell_id": "%s_c1" % nid, "tile_id": city["tile_id"], "size": 4, "compromised": false},
				{"cell_id": "%s_c2" % nid, "tile_id": city["tile_id"], "size": 3, "compromised": false},
			],
			"contacts": [
				{"contact_id": "%s_k1" % nid, "role": "printer", "reliability": 0.8, "compromised": false},
				{"contact_id": "%s_k2" % nid, "role": "railwayman", "reliability": 0.65, "compromised": false},
			],
			"area_tiles": [city["tile_id"]] + (campaign["tiles"][city["tile_id"]] as Dictionary)["neighbors"],
			"access": 2, "intelligence": 1,
			"resources": {"materiel": 8, "personnel": 6, "documents": 2}, "exposure": 0.1,
			"safe_routes": [{"route_id": "%s_r1" % nid, "tile_ids": [city["tile_id"]], "open": true}],
		})
		(city["network_ids"] as Array).append(nid)

	for u in opts.get("units", _default_units()):
		campaign["units"][(u as Dictionary)["unit_id"]] = Contracts.make_unit(u)

	# Fire every event already due on the start date, applying its effects,
	# without advancing the turn: a campaign begun in June 1944 must already
	# carry the landings' supply source and the 1940 restrictions.
	var due: Array = ContentDB.timeline_events().filter(func(e): return CampaignDate.is_on_or_after(str(campaign["date"]), str(e["date"])))
	due.sort_custom(func(a, b): return str(a["date"]) < str(b["date"]))
	for ev in due:
		(campaign["fired_events"] as Array).append(ev["id"])
		TurnResolver.apply_event(campaign, ev, null)

	for ch in ContentDB.chapters.get("chapters", []):
		var w: Dictionary = ch["date_window"]
		if not CampaignDate.in_window(str(campaign["date"]), str(w.get("from", "")), str(w.get("to", ""))):
			continue
		var ok := true
		for e in (ch["prerequisites"] as Dictionary)["events"]:
			if not (campaign["fired_events"] as Array).has(e):
				ok = false
		if ok and (ch["prerequisites"] as Dictionary)["chapters"].is_empty():
			(campaign["unlocked_chapters"] as Array).append(ch["id"])

	Supply.apply(campaign, Supply.build_sources(campaign))
	for cid in campaign["cities"]:
		var city: Dictionary = campaign["cities"][cid]
		city["supply_access"] = float((campaign["tiles"][city["tile_id"]] as Dictionary)["supply"])
		TurnResolver.recompute_city_services(city)

	var issues := Contracts.validate_campaign(campaign)
	assert(issues.is_empty(), "new campaign is invalid:\n%s" % "\n".join(issues))
	return campaign

func _default_units() -> Array:
	var t := func(th: String, q: int, r: int) -> String: return "%s:%d,%d" % [th, q, r]
	return [
		{"unit_id": "u_res_cell_nor", "unit_type": "underground_cell", "faction": "french_resistance", "label_key": "unit.cell_normandy", "tile_id": t.call("theater_western_europe", 3, 0), "strength": 0.9, "supply": 1.0},
		{"unit_id": "u_partisan_nor", "unit_type": "partisan_squad", "faction": "french_resistance", "label_key": "unit.partisans_bocage", "tile_id": t.call("theater_western_europe", 2, 1), "strength": 0.75, "supply": 0.7},
		{"unit_id": "u_res_cell_wsw", "unit_type": "underground_cell", "faction": "french_resistance", "label_key": "unit.cell_warsaw", "tile_id": t.call("theater_eastern_europe", 3, 0), "strength": 0.85, "supply": 1.0},
		{"unit_id": "u_axis_inf_nor", "unit_type": "infantry_division", "faction": "axis_army", "label_key": "unit.axis_infantry", "tile_id": t.call("theater_western_europe", 2, 2), "strength": 0.9, "supply": 0.85},
		{"unit_id": "u_axis_gar_nor", "unit_type": "garrison", "faction": "axis_army", "label_key": "unit.axis_garrison", "tile_id": t.call("theater_western_europe", 3, 0), "strength": 0.7, "supply": 0.8, "status": ["entrenched"]},
		{"unit_id": "u_axis_gar_wsw", "unit_type": "garrison", "faction": "axis_army", "label_key": "unit.axis_garrison_warsaw", "tile_id": t.call("theater_eastern_europe", 3, 0), "strength": 0.8, "supply": 0.9, "status": ["entrenched"]},
		{"unit_id": "u_axis_arm_east", "unit_type": "armoured_division", "faction": "axis_army", "label_key": "unit.axis_armour", "tile_id": t.call("theater_eastern_europe", 2, 3), "strength": 0.95, "supply": 0.9},
		{"unit_id": "u_cd_london", "unit_type": "civil_defence_team", "faction": "uk_civil_defence", "label_key": "unit.warden_team", "tile_id": t.call("theater_home_front", 2, 0), "strength": 1.0, "supply": 1.0},
	]

func adopt(campaign: Dictionary) -> void:
	c = campaign
	campaign_changed.emit()

# ------------------------------------------------------------------ queries --

## Cost and route preview for the confirmation sheet. Never mutates.
func preview_order(order: Dictionary) -> Dictionary:
	var v := Orders.validate(c, order)
	if not bool(v["ok"]):
		return v
	var after: Dictionary = {}
	for k in c["resources"]:
		after[k] = int(c["resources"][k]) - int((v["cost"] as Dictionary).get(k, 0))
	v["resources_after"] = after
	return v

func movement_range(unit_id: String) -> Dictionary:
	var u: Dictionary = (c["units"] as Dictionary).get(unit_id, {})
	if u.is_empty():
		return {"tiles": [], "blocked": []}
	var reach := Supply.reachable(c, u)
	var tiles: Array = []
	for tid in (reach["dist"] as Dictionary).keys():
		tiles.append({"tile_id": tid, "cost": int(reach["dist"][tid]), "path": Supply.path_to(reach["prev"], str(u["tile_id"]), str(tid))})
	tiles.sort_custom(func(a, b): return str(a["tile_id"]) < str(b["tile_id"]))
	var blocked: Array = []
	for nb in (c["tiles"][u["tile_id"]] as Dictionary)["neighbors"]:
		if not (reach["dist"] as Dictionary).has(nb):
			blocked.append({"tile_id": nb, "reason": why_blocked(u, str(nb))})
	return {"tiles": tiles, "blocked": blocked}

func why_blocked(unit: Dictionary, tile_id: String) -> String:
	var t: Dictionary = (c["tiles"] as Dictionary).get(tile_id, {})
	if t.is_empty():
		return Orders.NO_TARGET
	if not bool(t["passable"]):
		return Orders.IMPASSABLE
	var far := Supply.reachable(c, unit, 99)
	if not (far["dist"] as Dictionary).has(tile_id):
		return Orders.UNREACHABLE
	return Orders.NO_MOVE_BUDGET

## Why a unit is weakened, in words the player can read.
func explain_unit(unit_id: String) -> Dictionary:
	var u: Dictionary = (c["units"] as Dictionary).get(unit_id, {})
	if u.is_empty():
		return {}
	var reasons: Array = []
	var tile: Dictionary = c["tiles"][u["tile_id"]]
	if float(u["supply"]) < 0.25:
		reasons.append({"key": "explain.isolated", "detail": {"tile_supply": tile["supply"]}})
	elif float(u["supply"]) < 0.6:
		reasons.append({"key": "explain.short_supply", "detail": {"tile_supply": tile["supply"]}})
	if float(u["strength"]) < 0.4:
		reasons.append({"key": "explain.weakened", "detail": {"strength": u["strength"]}})
	if (u["status"] as Array).has("routed"):
		reasons.append({"key": "explain.routed", "detail": {}})
	if (u["status"] as Array).has("entrenched"):
		reasons.append({"key": "explain.entrenched", "detail": {}})
	if (u["status"] as Array).has("in_transit"):
		reasons.append({"key": "explain.in_transit", "detail": u.get("transit", {})})
	if reasons.is_empty():
		reasons.append({"key": "explain.ready", "detail": {}})
	return {"unit_id": unit_id, "reasons": reasons, "move_budget": u["move_budget"], "move_budget_max": u["move_budget_max"], "allowed_actions": u["allowed_actions"]}

func available_chapters() -> Array:
	var out: Array = []
	for id in c["unlocked_chapters"]:
		var ch := ContentDB.chapter(str(id))
		if not ch.is_empty():
			out.append(ch)
	return out

# ----------------------------------------------------------------- commands --

## Queue an order. Rejection leaves resources and state unchanged.
func submit_order(order: Dictionary) -> Dictionary:
	var before: int = int(c["revision"])
	var v := Orders.validate(c, order)
	if not bool(v["ok"]):
		order_rejected.emit(str(order.get("order_id", "")), str(v["reason"]), str(v["detail"]))
		return v
	Orders.reserve(c, v["cost"])
	(c["order_queue"] as Array).append({
		"order_id": order.get("order_id"), "unit_id": order.get("unit_id", null),
		"city_id": order.get("city_id", null), "order": order, "cost": v["cost"],
	})
	order_queued.emit(str(order.get("order_id", "")), v["cost"], v["plan"])
	campaign_changed.emit()
	assert(int(c["revision"]) == before, "submit_order must not change revision; only end_turn and commit_result may")
	return v

func cancel_order(order_id: String) -> Dictionary:
	var queue: Array = c["order_queue"]
	for i in queue.size():
		if str((queue[i] as Dictionary)["order_id"]) == order_id:
			var q: Dictionary = queue[i]
			queue.remove_at(i)
			Orders.refund(c, q["cost"])
			order_cancelled.emit(order_id)
			campaign_changed.emit()
			return {"ok": true, "refunded": q["cost"]}
	return {"ok": false, "reason": Orders.NO_TARGET}

func end_turn() -> Dictionary:
	var pending = c.get("pending_operation")
	if pending != null and (pending as Dictionary).get("state") != Contracts.S_READY:
		return {"ok": false, "reason": Orders.MISSION_ACTIVE}
	var report := TurnResolver.resolve(c)
	var issues := Contracts.validate_campaign(c)
	if not issues.is_empty():
		push_error("campaign invalid after turn resolution:\n%s" % "\n".join(issues))
	Saves.write("auto", c, null, "turn_committed")
	turn_resolved.emit(report)
	campaign_changed.emit()
	return {"ok": true, "report": report}

# ----------------------------------------------------- mission transitions --

func enter_mission(request: Dictionary, nonce: String) -> Dictionary:
	var ctx := Transition.begin_operation(c, request, nonce)
	if ctx.is_empty():
		return {"ok": false, "code": Transition.last_error.get("code", ""), "detail": Transition.last_error.get("detail", "")}
	return {"ok": true, "context": ctx}

func mark_loading() -> bool: return Transition.mark_loading(c)
func mark_ready(readiness: Dictionary) -> bool: return Transition.mark_ready(c, readiness)
func mark_playing() -> bool: return Transition.mark_playing(c)
func checkpoint_district(cp: Dictionary) -> bool: return Transition.save_district_checkpoint(c, cp)

## Submit, commit and acknowledge. Idempotent end to end.
func finish_mission(result: Dictionary) -> Dictionary:
	var sub := Transition.submit_result(c, result)
	if not bool(sub.get("ok", false)):
		return {"ok": false, "code": Transition.last_error.get("code", ""), "detail": Transition.last_error.get("detail", "")}
	if bool(sub["already_committed"]):
		mission_resolved.emit(null, [])
		return {"ok": true, "duplicate": true, "applied": null}
	var com := Transition.commit_result(c)
	var ack = Transition.acknowledge_return(c)
	Supply.apply(c, Supply.build_sources(c))
	var issues := Contracts.validate_campaign(c)
	if not issues.is_empty():
		push_error("campaign invalid after mission commit:\n%s" % "\n".join(issues))
	Saves.write("auto", c, null, "mission_result_final")
	mission_resolved.emit(ack, sub["clamped"])
	campaign_changed.emit()
	return {"ok": true, "duplicate": false, "applied": ack, "clamped": sub["clamped"], "repeated": bool(com.get("repeated", false))}

func abort_mission(code: String, detail: String) -> Dictionary:
	var out := Transition.fail_operation(c, code, detail)
	campaign_changed.emit()
	return out

func recover() -> Dictionary:
	var out := Transition.recover_on_launch(c)
	recovered.emit(out)
	campaign_changed.emit()
	return out
