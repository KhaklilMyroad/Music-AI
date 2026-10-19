extends RefCounted
class_name Contracts
## Data contracts (brief §16), mirroring web/src/sim/contracts.js.
##
## These are the save contract and the interchange format. Scene nodes are views
## and controllers: none of them owns any of this. Every contract is a plain
## Dictionary of serialisable values, so a save never holds a node reference, a
## live Resource or an unvalidated dictionary.
##
## The JavaScript reference implementation in web/src/sim is covered by 156
## acceptance tests. Any change to a rule here must be mirrored there, and the
## shared normative spec is docs/02-DATA-CONTRACTS.md.

const SCHEMA_VERSION: int = 4
const RESULT_VERSION: int = 2
const CHECKPOINT_VERSION: int = 2

const FACTIONS := [
	"allied_us_army", "allied_uk_army", "allied_soviet", "polish_home_army",
	"french_resistance", "resistance_cell", "jewish_fighting_organisations",
	"uk_civil_defence", "us_home_front_organisations", "civilian",
	"axis_army", "axis_police", "axis_air_force", "axis_occupation_authority",
]
const UNIT_TYPES := [
	"infantry_division", "armoured_division", "garrison", "partisan_squad",
	"underground_cell", "civil_defence_team", "relief_column", "supply_column",
]
const CONTROL := ["allied", "axis", "neutral", "contested"]
const OUTCOMES := ["success", "partial_success", "failure", "withdrawal"]

const S_READY := "StrategicReady"
const S_PREPARING := "PreparingMission"
const S_LOADING := "LoadingMission"
const S_MISSION_READY := "MissionReady"
const S_PLAYING := "PlayingMission"
const S_RESOLVING := "ResolvingMission"
const S_RETURNING := "Returning"
const S_FAILED := "TransitionFailed"
const TRANSITION_STATES := [S_READY, S_PREPARING, S_LOADING, S_MISSION_READY, S_PLAYING, S_RESOLVING, S_RETURNING, S_FAILED]

## Capabilities per unit type. A civilian group can never inherit a division's
## verbs merely because both are drawn as an icon.
const UNIT_CAPABILITIES := {
	"infantry_division":  {"actions": ["move", "attack", "defend", "reconnoitre", "entrench"], "move_budget": 3, "supply_draw": 4, "can_occupy": true,  "visible_on_map": true,  "uses_routes": true,  "uses_access": false},
	"armoured_division":  {"actions": ["move", "attack", "defend", "reconnoitre"],             "move_budget": 5, "supply_draw": 7, "can_occupy": true,  "visible_on_map": true,  "uses_routes": true,  "uses_access": false},
	"garrison":           {"actions": ["defend", "entrench"],                                  "move_budget": 0, "supply_draw": 2, "can_occupy": true,  "visible_on_map": true,  "uses_routes": false, "uses_access": false},
	"partisan_squad":     {"actions": ["move", "sabotage", "reconnoitre", "ambush", "hide"],    "move_budget": 2, "supply_draw": 1, "can_occupy": false, "visible_on_map": false, "uses_routes": false, "uses_access": true},
	"underground_cell":   {"actions": ["move_covert", "sabotage", "courier", "shelter", "recruit", "hide"], "move_budget": 1, "supply_draw": 0, "can_occupy": false, "visible_on_map": false, "uses_routes": false, "uses_access": true},
	"civil_defence_team": {"actions": ["relieve", "evacuate", "treat", "move"],                "move_budget": 2, "supply_draw": 1, "can_occupy": false, "visible_on_map": true,  "uses_routes": true,  "uses_access": false},
	"relief_column":      {"actions": ["move", "relieve", "deliver"],                          "move_budget": 2, "supply_draw": 1, "can_occupy": false, "visible_on_map": true,  "uses_routes": true,  "uses_access": false},
	"supply_column":      {"actions": ["move", "deliver"],                                     "move_budget": 3, "supply_draw": 1, "can_occupy": false, "visible_on_map": true,  "uses_routes": true,  "uses_access": false},
}

# ------------------------------------------------------------- constructors --

static func make_tile(o: Dictionary) -> Dictionary:
	return {
		"tile_id": o.get("tile_id", ""),
		"theater": o.get("theater", ""),
		"q": int(o.get("q", 0)), "r": int(o.get("r", 0)),
		"terrain": o.get("terrain", "plain"),
		"control": o.get("control", "neutral"),
		"passable": bool(o.get("passable", true)),
		"naval_only": bool(o.get("naval_only", false)),
		"neighbors": o.get("neighbors", []),
		"city_id": o.get("city_id", null),
		"poi_refs": o.get("poi_refs", []),
		"supply": float(o.get("supply", 0.0)),
		"supply_penalty": float(o.get("supply_penalty", 0.0)),
		"discovered": bool(o.get("discovered", false)),
		"contested_since_turn": o.get("contested_since_turn", null),
	}

static func make_unit(o: Dictionary) -> Dictionary:
	var ut: String = o.get("unit_type", "")
	assert(UNIT_CAPABILITIES.has(ut), "unknown unit_type %s" % ut)
	var cap: Dictionary = UNIT_CAPABILITIES[ut]
	return {
		"unit_id": o.get("unit_id", ""),
		"unit_type": ut,
		"faction": o.get("faction", ""),
		"label_key": o.get("label_key", "unit.%s" % ut),
		"tile_id": o.get("tile_id", ""),
		"strength": float(o.get("strength", 1.0)),
		"supply": float(o.get("supply", 1.0)),
		"move_budget": int(o.get("move_budget", cap["move_budget"])),
		"move_budget_max": int(cap["move_budget"]),
		"allowed_actions": o.get("allowed_actions", (cap["actions"] as Array).duplicate()),
		"equipment": o.get("equipment", []),
		"status": o.get("status", []),
		"transit": o.get("transit", null),
	}

static func make_city(o: Dictionary) -> Dictionary:
	return {
		"city_id": o.get("city_id", ""),
		"label_key": o.get("label_key", ""),
		"theater": o.get("theater", ""),
		"tile_id": o.get("tile_id", ""),
		"place_date_context": o.get("place_date_context", null),
		"control": o.get("control", "neutral"),
		"facilities": o.get("facilities", []),
		"construction_queue": o.get("construction_queue", []),
		"facilities_max": int(o.get("facilities_max", 4)),
		"supply_access": float(o.get("supply_access", 0.0)),
		"service_capacity": o.get("service_capacity", {"civilian_health": 0.0, "civilian_food": 0.0, "evacuation": 0.0}),
		"civilian_group_ids": o.get("civilian_group_ids", []),
		"network_ids": o.get("network_ids", []),
		"districts": o.get("districts", []),
		"restriction_level": int(o.get("restriction_level", 0)),
	}

static func make_civilian_group(o: Dictionary) -> Dictionary:
	var needs: Dictionary = {"food": 1.0, "water": 1.0, "medicine": 1.0, "shelter": 1.0}
	for k in o.get("needs", {}):
		needs[k] = float(o["needs"][k])
	# NOTE: needs are satisfaction levels, never a suffering score. See the
	# editorial rule in docs/08: persecution is never a measured percentage.
	return {
		"group_id": o.get("group_id", ""),
		"label_key": o.get("label_key", ""),
		"is_fictional": bool(o.get("is_fictional", true)),
		"community_id": o.get("community_id", null),
		"household_ids": o.get("household_ids", []),
		"headcount": int(o.get("headcount", 1)),
		"city_id": o.get("city_id", ""),
		"tile_id": o.get("tile_id", ""),
		"needs": needs,
		"access_restrictions": o.get("access_restrictions", []),
		"displacement": o.get("displacement", "in_place"),
		"narrative_flags": o.get("narrative_flags", []),
		"relationships": o.get("relationships", []),
	}

static func make_network(o: Dictionary) -> Dictionary:
	var res: Dictionary = {"materiel": 0, "personnel": 0, "documents": 0}
	for k in o.get("resources", {}):
		res[k] = int(o["resources"][k])
	return {
		"network_id": o.get("network_id", ""),
		"label_key": o.get("label_key", ""),
		"city_id": o.get("city_id", ""),
		"cells": o.get("cells", []),
		"contacts": o.get("contacts", []),
		"area_tiles": o.get("area_tiles", []),
		"access": int(o.get("access", 0)),
		"intelligence": int(o.get("intelligence", 0)),
		"resources": res,
		"exposure": float(o.get("exposure", 0.0)),
		"safe_routes": o.get("safe_routes", []),
		"compromised_links": o.get("compromised_links", []),
	}

static func make_campaign(o: Dictionary) -> Dictionary:
	var res: Dictionary = {"materiel": 0, "personnel": 0, "intelligence": 0, "documents": 0}
	for k in o.get("resources", {}):
		res[k] = int(o["resources"][k])
	return {
		"schema_version": SCHEMA_VERSION,
		"campaign_id": o.get("campaign_id", "cmp_main"),
		"revision": int(o.get("revision", 0)),
		"turn": int(o.get("turn", 1)),
		"date": o.get("date", "1939-09-01"),
		"mode": o.get("mode", "campaign"),
		"player_faction": o.get("player_faction", "french_resistance"),
		"resources": res,
		"tiles": o.get("tiles", {}),
		"units": o.get("units", {}),
		"cities": o.get("cities", {}),
		"civilian_groups": o.get("civilian_groups", {}),
		"networks": o.get("networks", {}),
		"fired_events": o.get("fired_events", []),
		"completed_chapters": o.get("completed_chapters", []),
		"unlocked_chapters": o.get("unlocked_chapters", []),
		"unlocked_equipment": o.get("unlocked_equipment", []),
		"history_flags": o.get("history_flags", {}),
		"pending_operation": o.get("pending_operation", null),
		"committed_operations": o.get("committed_operations", []),
		"order_queue": o.get("order_queue", []),
		"last_turn_report": o.get("last_turn_report", null),
		"rng_seed": int(o.get("rng_seed", 1)),
	}

static func make_mission_context(o: Dictionary) -> Dictionary:
	var bounds: Dictionary = {
		"max_intelligence": 0, "max_materiel": 0, "max_personnel": 0,
		"min_materiel": -999, "min_personnel": -999,
		"may_remove_attacking_formation": false, "may_flip_tile_control": false,
		"max_civilian_health_delta": 0, "min_civilian_health_delta": -999,
		"max_network_exposure_delta": 1.0, "max_network_access_delta": 0,
	}
	for k in o.get("outcome_bounds", {}):
		bounds[k] = o["outcome_bounds"][k]
	return {
		"operation_id": o.get("operation_id", ""),
		"source_revision": int(o.get("source_revision", 0)),
		"campaign_id": o.get("campaign_id", ""),
		"unit_id": o.get("unit_id", null),
		"tile_id": o.get("tile_id", ""),
		"city_id": o.get("city_id", null),
		"district_id": o.get("district_id", ""),
		"district_content_version": o.get("district_content_version", ""),
		"chapter_id": o.get("chapter_id", null),
		"date": o.get("date", ""),
		"mission_type": o.get("mission_type", "mission_family_recon"),
		"seed": int(o.get("seed", 1)),
		"permitted_objectives": o.get("permitted_objectives", []),
		"allowed_outcomes": o.get("allowed_outcomes", OUTCOMES.duplicate()),
		"outcome_bounds": bounds,
		"entry_snapshot": o.get("entry_snapshot", {}),
		"reserved_cost": o.get("reserved_cost", {}),
		"campaign_time_cost_turns": int(o.get("campaign_time_cost_turns", 0)),
		"loadout": o.get("loadout", []),
	}

static func make_mission_result(o: Dictionary) -> Dictionary:
	var metrics: Dictionary = {
		"elapsed_mission_seconds": 0, "shots_fired": 0, "times_detected": 0,
		"alarm_raised": false, "civilians_assisted": 0, "hostiles_neutralised": 0,
	}
	for k in o.get("metrics", {}):
		metrics[k] = o["metrics"][k]
	var losses: Dictionary = {"personnel": 0}
	for k in o.get("declared_losses", {}):
		losses[k] = o["declared_losses"][k]
	var gains: Dictionary = {"materiel": 0, "intelligence": 0, "documents": 0}
	for k in o.get("declared_resources", {}):
		gains[k] = o["declared_resources"][k]
	return {
		"result_version": RESULT_VERSION,
		"operation_id": o.get("operation_id", ""),
		"source_revision": int(o.get("source_revision", 0)),
		"outcome": o.get("outcome", "failure"),
		"completed_objectives": o.get("completed_objectives", []),
		"failed_objectives": o.get("failed_objectives", []),
		"metrics": metrics,
		"declared_losses": losses,
		"declared_resources": gains,
		"requests": o.get("requests", {}),
	}

static func make_district_checkpoint(o: Dictionary) -> Dictionary:
	var p: Dictionary = o.get("player", {})
	return {
		"checkpoint_version": CHECKPOINT_VERSION,
		"district_id": o.get("district_id", ""),
		"district_content_version": o.get("district_content_version", ""),
		"saved_at_boundary": o.get("saved_at_boundary", "safe_action_boundary"),
		"player": {
			"position": p.get("position", [0.0, 0.0, 0.0]),
			"yaw": float(p.get("yaw", 0.0)), "pitch": float(p.get("pitch", 0.0)),
			"posture": p.get("posture", "stand"),
			"health": float(p.get("health", 100.0)),
			"condition": p.get("condition", {"fatigue": 0.0, "warmth": 1.0, "hunger": 0.0, "thirst": 0.0}),
			"equipped": p.get("equipped", null),
		},
		"inventory": o.get("inventory", {}),
		"weapon_states": o.get("weapon_states", {}),
		"mission_flags": o.get("mission_flags", {}),
		"poi_states": o.get("poi_states", {}),
		"door_states": o.get("door_states", {}),
		"container_states": o.get("container_states", {}),
		"local_entities": o.get("local_entities", []),
		"local_time_hours": float(o.get("local_time_hours", 8.0)),
		"weather": o.get("weather", "clear_morning"),
		"interrupted_action": o.get("interrupted_action", null),
	}

# ---------------------------------------------------------------- validators --

static func validate_tile(t: Dictionary, issues: Array, path: String = "tile") -> Array:
	if not (t.get("tile_id", "") is String and t["tile_id"] != ""):
		issues.append("%s.tile_id must be a non-empty string" % path)
	if not (t.get("q") is int and t.get("r") is int):
		issues.append("%s.q/r must be integers" % path)
	if not CONTROL.has(t.get("control")):
		issues.append("%s.control must be one of %s" % [path, CONTROL])
	var s: float = float(t.get("supply", -1.0))
	if s < 0.0 or s > 10.0:
		issues.append("%s.supply must be 0..10 (got %s)" % [path, s])
	return issues

static func validate_unit(u: Dictionary, issues: Array, path: String = "unit") -> Array:
	if not UNIT_TYPES.has(u.get("unit_type")):
		issues.append("%s.unit_type invalid: %s" % [path, u.get("unit_type")])
		return issues
	if not FACTIONS.has(u.get("faction")):
		issues.append("%s.faction invalid: %s" % [path, u.get("faction")])
	var st: float = float(u.get("strength", -1.0))
	if st < 0.0 or st > 1.0:
		issues.append("%s.strength must be 0..1" % path)
	var sp: float = float(u.get("supply", -1.0))
	if sp < 0.0 or sp > 1.0:
		issues.append("%s.supply must be 0..1" % path)
	var cap: Dictionary = UNIT_CAPABILITIES[u["unit_type"]]
	if int(u.get("move_budget", 0)) > int(cap["move_budget"]):
		issues.append("%s.move_budget %s exceeds %s max %s" % [path, u["move_budget"], u["unit_type"], cap["move_budget"]])
	for a in u.get("allowed_actions", []):
		if not (cap["actions"] as Array).has(a):
			issues.append("%s.allowed_actions contains actions %s cannot perform: %s" % [path, u["unit_type"], a])
	return issues

static func validate_civilian_group(g: Dictionary, issues: Array, path: String = "civilian_group") -> Array:
	if not (g.get("group_id", "") is String and g["group_id"] != ""):
		issues.append("%s.group_id required" % path)
	if int(g.get("headcount", -1)) < 0:
		issues.append("%s.headcount must be a non-negative integer" % path)
	for k in ["food", "water", "medicine", "shelter"]:
		var v: float = float((g.get("needs", {}) as Dictionary).get(k, -1.0))
		if v < 0.0 or v > 1.0:
			issues.append("%s.needs.%s must be 0..1" % [path, k])
	if not ["in_place", "restricted", "displaced", "evacuated", "unaccounted"].has(g.get("displacement")):
		issues.append("%s.displacement invalid: %s" % [path, g.get("displacement")])
	# Guard against the exact bug the brief names: a civilian's condition is
	# never inferred from a military strength value.
	if g.has("strength"):
		issues.append("%s must not carry a military 'strength' field; civilian condition is never inferred from unit strength" % path)
	return issues

static func validate_campaign(c: Dictionary) -> Array:
	var issues: Array = []
	if int(c.get("schema_version", -1)) != SCHEMA_VERSION:
		issues.append("schema_version must be %d, got %s" % [SCHEMA_VERSION, c.get("schema_version")])
	if int(c.get("revision", -1)) < 0:
		issues.append("revision must be a non-negative integer")
	if int(c.get("turn", 0)) < 1:
		issues.append("turn must be >= 1")
	var re := RegEx.new()
	re.compile("^\\d{4}-\\d{2}-\\d{2}$")
	if re.search(str(c.get("date", ""))) == null:
		issues.append("date must be ISO yyyy-mm-dd, got %s" % c.get("date"))
	if not ["campaign", "sandbox"].has(c.get("mode")):
		issues.append("mode invalid: %s" % c.get("mode"))
	if not FACTIONS.has(c.get("player_faction")):
		issues.append("player_faction invalid: %s" % c.get("player_faction"))

	var tiles: Dictionary = c.get("tiles", {})
	for id in tiles:
		var t: Dictionary = tiles[id]
		if id != t.get("tile_id"):
			issues.append("tiles key \"%s\" does not match tile_id \"%s\"" % [id, t.get("tile_id")])
		validate_tile(t, issues, "tiles[%s]" % id)
		for nb in t.get("neighbors", []):
			if not tiles.has(nb):
				issues.append("tiles[%s].neighbors references missing tile \"%s\"" % [id, nb])
		if t.get("city_id") != null and not (c.get("cities", {}) as Dictionary).has(t["city_id"]):
			issues.append("tiles[%s].city_id references missing city \"%s\"" % [id, t["city_id"]])
	var units: Dictionary = c.get("units", {})
	for id in units:
		var u: Dictionary = units[id]
		if id != u.get("unit_id"):
			issues.append("units key \"%s\" does not match unit_id" % id)
		validate_unit(u, issues, "units[%s]" % id)
		if not tiles.has(u.get("tile_id")):
			issues.append("units[%s].tile_id references missing tile \"%s\"" % [id, u.get("tile_id")])
	var groups: Dictionary = c.get("civilian_groups", {})
	for id in groups:
		validate_civilian_group(groups[id], issues, "civilian_groups[%s]" % id)
	var cities: Dictionary = c.get("cities", {})
	for id in cities:
		var city: Dictionary = cities[id]
		if not tiles.has(city.get("tile_id")):
			issues.append("cities[%s].tile_id references missing tile" % id)
		if (city.get("facilities", []) as Array).size() > int(city.get("facilities_max", 0)):
			issues.append("cities[%s] has more facilities than its maximum" % id)
	var pending = c.get("pending_operation")
	if pending != null and not TRANSITION_STATES.has((pending as Dictionary).get("state")):
		issues.append("pending_operation.state invalid: %s" % (pending as Dictionary).get("state"))
	return issues

static func validate_mission_context(m: Dictionary) -> Array:
	var issues: Array = []
	if str(m.get("operation_id", "")) == "":
		issues.append("operation_id required")
	if str(m.get("district_id", "")) == "":
		issues.append("district_id required")
	if str(m.get("district_content_version", "")) == "":
		issues.append("district_content_version required (a mission must know which content it was built for)")
	if (m.get("permitted_objectives", []) as Array).is_empty():
		issues.append("permitted_objectives must be non-empty")
	for o in m.get("allowed_outcomes", []):
		if not OUTCOMES.has(o):
			issues.append("allowed_outcomes must be a subset of %s" % [OUTCOMES])
	if not (m.get("entry_snapshot") is Dictionary):
		issues.append("entry_snapshot required for safe return")
	return issues

## Validate a MissionResult against the context that produced it, and clamp it.
## This is the gate that stops a mission scene writing arbitrary campaign state.
## Returns {"ok": bool, "issues": Array, "safe": Dictionary, "clamped": Array}.
static func validate_mission_result(raw: Dictionary, context: Dictionary) -> Dictionary:
	var issues: Array = []
	# Check the RAW dictionary: make_mission_result would drop an unknown field,
	# turning an attempted world patch into a silent no-op.
	for forbidden in ["world_patch", "campaign", "tiles", "units", "resources"]:
		if raw.has(forbidden):
			issues.append("a MissionResult may not carry a world-state patch (found \"%s\")" % forbidden)
	var result := make_mission_result(raw)
	if int(result["result_version"]) != RESULT_VERSION:
		issues.append("result_version must be %d" % RESULT_VERSION)
	if result["operation_id"] != context["operation_id"]:
		issues.append("result.operation_id \"%s\" does not match context \"%s\"" % [result["operation_id"], context["operation_id"]])
	if int(result["source_revision"]) != int(context["source_revision"]):
		issues.append("result.source_revision %s does not match context %s" % [result["source_revision"], context["source_revision"]])
	if not (context["allowed_outcomes"] as Array).has(result["outcome"]):
		issues.append("outcome \"%s\" is not permitted by this mission" % result["outcome"])
	for o in result["completed_objectives"]:
		if not (context["permitted_objectives"] as Array).has(o):
			issues.append("result claims an objective this mission does not define: %s" % o)
	if not issues.is_empty():
		return {"ok": false, "issues": issues, "safe": {}, "clamped": []}

	var b: Dictionary = context["outcome_bounds"]
	var clamped: Array = []
	var safe := result.duplicate(true)
	var gains: Dictionary = safe["declared_resources"]
	var new_intel: int = clampi(int(gains.get("intelligence", 0)), 0, int(b["max_intelligence"]))
	var new_mat: int = clampi(int(gains.get("materiel", 0)), int(b["min_materiel"]), int(b["max_materiel"]))
	if new_intel != int(gains.get("intelligence", 0)):
		clamped.append("intelligence")
	if new_mat != int(gains.get("materiel", 0)):
		clamped.append("materiel")
	gains["intelligence"] = new_intel
	gains["materiel"] = new_mat
	gains["documents"] = clampi(int(gains.get("documents", 0)), 0, int(b["max_intelligence"]))
	safe["declared_losses"]["personnel"] = clampi(int(safe["declared_losses"].get("personnel", 0)), 0, abs(int(b["min_personnel"])))

	var rq: Dictionary = result.get("requests", {})
	var remove_ok: bool = bool(rq.get("remove_attacking_formation", false)) and bool(b["may_remove_attacking_formation"])
	if bool(rq.get("remove_attacking_formation", false)) and not remove_ok:
		clamped.append("remove_attacking_formation")
	safe["requests"] = {
		"remove_attacking_formation": remove_ok,
		"flip_tile_control_to": (rq.get("flip_tile_control_to", null) if bool(b["may_flip_tile_control"]) else null),
		"civilian_health_delta": clampf(float(rq.get("civilian_health_delta", 0.0)), float(b["min_civilian_health_delta"]), float(b["max_civilian_health_delta"])),
		"network_exposure_delta": clampf(float(rq.get("network_exposure_delta", 0.0)), 0.0, float(b["max_network_exposure_delta"])),
		"network_access_delta": clampi(int(rq.get("network_access_delta", 0)), 0, int(b["max_network_access_delta"])),
		"supply_penalty": clampi(int(rq.get("supply_penalty", 0)), 0, 4),
	}
	return {"ok": true, "issues": [], "safe": safe, "clamped": clamped}
