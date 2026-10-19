extends RefCounted
class_name Orders
## Order validation and cost reservation.
##
## Contract tested by the acceptance matrix: a REJECTED order leaves resources
## and state unchanged. Validation therefore runs entirely on a read-only view
## before anything is written, and reservation is one atomic step at the end.

const KINDS := ["move", "attack", "defend", "entrench", "reconnoitre", "sabotage", "move_covert", "courier", "construct", "repair", "relieve", "evacuate", "transit", "hide"]

## Reason codes. The UI maps these to localised strings; it never invents its own.
const UNKNOWN_UNIT := "reject.unknown_unit"
const WRONG_FACTION := "reject.wrong_faction"
const ACTION_NOT_ALLOWED := "reject.action_not_allowed"
const NO_MOVE_BUDGET := "reject.no_move_budget"
const UNREACHABLE := "reject.unreachable"
const IMPASSABLE := "reject.impassable"
const OUT_OF_SUPPLY := "reject.out_of_supply"
const IN_TRANSIT := "reject.in_transit"
const ROUTED := "reject.routed"
const NOT_ADJACENT := "reject.not_adjacent"
const NO_TARGET := "reject.no_target"
const INSUFFICIENT := "reject.insufficient_resources"
const CITY_NOT_CONTROLLED := "reject.city_not_controlled"
const SLOTS_FULL := "reject.facility_slots_full"
const FACILITY_EXISTS := "reject.facility_exists"
const PREREQ_SUPPLY := "reject.facility_prereq_supply"
const PREREQ_ACCESS := "reject.facility_prereq_access"
const DUPLICATE := "reject.duplicate_order"
const MISSION_ACTIVE := "reject.mission_active"
const UNKNOWN_KIND := "reject.unknown_kind"

static func _cost(d: Dictionary = {}) -> Dictionary:
	var out := {"materiel": 0, "personnel": 0, "intelligence": 0, "documents": 0}
	for k in d:
		out[k] = int(d[k])
	return out

static func _can_afford(res: Dictionary, cost: Dictionary) -> bool:
	for k in cost:
		if int(cost[k]) > int(res.get(k, 0)):
			return false
	return true

## Pure validation; NEVER mutates. Returns
## {"ok": bool, "reason": String, "detail": String, "cost": Dictionary, "plan": Dictionary}.
static func validate(campaign: Dictionary, order: Dictionary) -> Dictionary:
	var fail := func(reason: String, detail: String = "") -> Dictionary:
		return {"ok": false, "reason": reason, "detail": detail, "cost": {}, "plan": {}}
	var kind: String = str(order.get("kind", ""))
	if not KINDS.has(kind):
		return fail.call(UNKNOWN_KIND, kind)
	var pending = campaign.get("pending_operation")
	if pending != null and (pending as Dictionary).get("state") != Contracts.S_READY:
		return fail.call(MISSION_ACTIVE, str((pending as Dictionary).get("operation_id", "")))
	for q in campaign["order_queue"]:
		if (q as Dictionary).get("order_id") == order.get("order_id"):
			return fail.call(DUPLICATE, str(order.get("order_id")))

	if kind == "construct" or kind == "repair":
		var city: Dictionary = (campaign["cities"] as Dictionary).get(order.get("city_id", ""), {})
		if city.is_empty():
			return fail.call(NO_TARGET, str(order.get("city_id")))
		var spec := ContentDB.facility(str(order.get("facility_id", "")))
		if spec.is_empty():
			return fail.call(NO_TARGET, str(order.get("facility_id")))
		var tile: Dictionary = campaign["tiles"][city["tile_id"]]
		var player_side := Supply.side_of(str(campaign["player_faction"]))
		if kind == "construct":
			for f in city["facilities"]:
				if (f as Dictionary).get("facility_id") == spec["id"]:
					return fail.call(FACILITY_EXISTS, str(spec["id"]))
			for q in city["construction_queue"]:
				if (q as Dictionary).get("facility_id") == spec["id"]:
					return fail.call(DUPLICATE, str(spec["id"]))
			if (city["facilities"] as Array).size() + (city["construction_queue"] as Array).size() >= int(city["facilities_max"]):
				return fail.call(SLOTS_FULL, str(city["facilities_max"]))
			var pre: Dictionary = spec["prerequisites"]
			if pre.get("requires_control") == "owner" and Supply.control_side(str(city["control"])) != player_side:
				return fail.call(CITY_NOT_CONTROLLED, str(city["city_id"]))
			if float(tile["supply"]) < float(pre.get("min_supply", 0)):
				return fail.call(PREREQ_SUPPLY, "%s < %s" % [tile["supply"], pre.get("min_supply")])
			if pre.get("requires_network_access") != null:
				var access: int = 0
				for nid in city["network_ids"]:
					access = maxi(access, int((campaign["networks"][nid] as Dictionary)["access"]))
				if access < int(pre["requires_network_access"]):
					return fail.call(PREREQ_ACCESS, "%d < %d" % [access, int(pre["requires_network_access"])])
			var cost := _cost(spec["cost"])
			if not _can_afford(campaign["resources"], cost):
				return fail.call(INSUFFICIENT, JSON.stringify(cost))
			return {"ok": true, "reason": "", "detail": "", "cost": cost,
				"plan": {"kind": "construct", "city_id": city["city_id"], "facility_id": spec["id"], "turns": int(spec["build_turns"])}}
		# repair
		var built: Dictionary = {}
		for f in city["facilities"]:
			if (f as Dictionary).get("facility_id") == spec["id"]:
				built = f
		if built.is_empty():
			return fail.call(NO_TARGET, str(spec["id"]))
		if not bool(built.get("damaged", false)) and not bool(built.get("disabled", false)):
			return fail.call(NO_TARGET, "facility.undamaged")
		var rcost := _cost(spec.get("repair_cost", {}))
		if not _can_afford(campaign["resources"], rcost):
			return fail.call(INSUFFICIENT, JSON.stringify(rcost))
		return {"ok": true, "reason": "", "detail": "", "cost": rcost,
			"plan": {"kind": "repair", "city_id": city["city_id"], "facility_id": spec["id"], "turns": 1}}

	# ---- every other kind is a unit order ----
	var unit: Dictionary = (campaign["units"] as Dictionary).get(order.get("unit_id", ""), {})
	if unit.is_empty():
		return fail.call(UNKNOWN_UNIT, str(order.get("unit_id")))
	if unit["faction"] != campaign["player_faction"]:
		return fail.call(WRONG_FACTION, str(unit["faction"]))
	if (unit["status"] as Array).has("in_transit"):
		return fail.call(IN_TRANSIT, "")
	if (unit["status"] as Array).has("routed"):
		return fail.call(ROUTED, str(unit["unit_id"]))
	var cap: Dictionary = Contracts.UNIT_CAPABILITIES[unit["unit_type"]]
	var verb: String = kind
	if kind == "move" and (cap["actions"] as Array).has("move_covert") and not (cap["actions"] as Array).has("move"):
		verb = "move_covert"
	if not (unit["allowed_actions"] as Array).has(verb):
		return fail.call(ACTION_NOT_ALLOWED, "%s:%s" % [unit["unit_type"], verb])
	for q in campaign["order_queue"]:
		if (q as Dictionary).get("unit_id") == unit["unit_id"]:
			return fail.call(DUPLICATE, str(unit["unit_id"]))

	if verb == "move" or verb == "move_covert":
		var dest: Dictionary = (campaign["tiles"] as Dictionary).get(order.get("tile_id", ""), {})
		if dest.is_empty():
			return fail.call(NO_TARGET, str(order.get("tile_id")))
		if not bool(dest["passable"]):
			return fail.call(IMPASSABLE, str(dest["tile_id"]))
		if int(unit["move_budget"]) <= 0:
			return fail.call(NO_MOVE_BUDGET, "0")
		var reach := Supply.reachable(campaign, unit)
		if not (reach["dist"] as Dictionary).has(dest["tile_id"]):
			return fail.call(UNREACHABLE, "%s beyond budget %d" % [dest["tile_id"], int(unit["move_budget"])])
		var path := Supply.path_to(reach["prev"], str(unit["tile_id"]), str(dest["tile_id"]))
		if path.is_empty():
			return fail.call(UNREACHABLE, str(dest["tile_id"]))
		return {"ok": true, "reason": "", "detail": "", "cost": _cost(),
			"plan": {"kind": verb, "unit_id": unit["unit_id"], "path": path, "move_cost": int((reach["dist"] as Dictionary)[dest["tile_id"]])}}

	if verb == "attack":
		var dest: Dictionary = (campaign["tiles"] as Dictionary).get(order.get("tile_id", ""), {})
		if dest.is_empty():
			return fail.call(NO_TARGET, str(order.get("tile_id")))
		if not ((campaign["tiles"][unit["tile_id"]] as Dictionary)["neighbors"] as Array).has(dest["tile_id"]):
			return fail.call(NOT_ADJACENT, str(dest["tile_id"]))
		var defenders: Array = []
		for uid in campaign["units"]:
			var o: Dictionary = campaign["units"][uid]
			if o["tile_id"] == dest["tile_id"] and Supply.side_of(str(o["faction"])) != Supply.side_of(str(unit["faction"])):
				defenders.append(uid)
		var hostile_ground := Supply.control_side(str(dest["control"])) != "" and Supply.control_side(str(dest["control"])) != Supply.side_of(str(unit["faction"]))
		if defenders.is_empty() and not hostile_ground:
			return fail.call(NO_TARGET, str(dest["tile_id"]))
		if float(unit["supply"]) < 0.25:
			return fail.call(OUT_OF_SUPPLY, str(unit["supply"]))
		var cost := _cost({"materiel": 6})
		if not _can_afford(campaign["resources"], cost):
			return fail.call(INSUFFICIENT, JSON.stringify(cost))
		return {"ok": true, "reason": "", "detail": "", "cost": cost,
			"plan": {"kind": "attack", "unit_id": unit["unit_id"], "tile_id": dest["tile_id"], "defender_ids": defenders}}

	if verb in ["sabotage", "reconnoitre", "courier"]:
		var target_id: String = str(order.get("tile_id", unit["tile_id"]))
		var dest: Dictionary = (campaign["tiles"] as Dictionary).get(target_id, {})
		if dest.is_empty():
			return fail.call(NO_TARGET, target_id)
		var home: Dictionary = campaign["tiles"][unit["tile_id"]]
		var d: int = abs(int(dest["q"]) - int(home["q"])) + abs(int(dest["r"]) - int(home["r"]))
		if d > 2:
			return fail.call(UNREACHABLE, "%d tiles from the cell's area of operation" % d)
		var cost := _cost({"materiel": 4}) if verb == "sabotage" else _cost()
		if not _can_afford(campaign["resources"], cost):
			return fail.call(INSUFFICIENT, JSON.stringify(cost))
		return {"ok": true, "reason": "", "detail": "", "cost": cost,
			"plan": {"kind": verb, "unit_id": unit["unit_id"], "tile_id": target_id}}

	if verb in ["defend", "entrench", "hide"]:
		return {"ok": true, "reason": "", "detail": "", "cost": _cost(), "plan": {"kind": verb, "unit_id": unit["unit_id"]}}

	if verb in ["relieve", "evacuate"]:
		var city: Dictionary = (campaign["cities"] as Dictionary).get(order.get("city_id", ""), {})
		if city.is_empty():
			return fail.call(NO_TARGET, str(order.get("city_id")))
		var cost := _cost({"materiel": 5 if verb == "relieve" else 2, "personnel": 1})
		if not _can_afford(campaign["resources"], cost):
			return fail.call(INSUFFICIENT, JSON.stringify(cost))
		return {"ok": true, "reason": "", "detail": "", "cost": cost,
			"plan": {"kind": verb, "unit_id": unit["unit_id"], "city_id": city["city_id"]}}

	return fail.call(UNKNOWN_KIND, verb)

## Atomic reservation. Only called after validate() returned ok.
static func reserve(campaign: Dictionary, cost: Dictionary) -> void:
	for k in cost:
		if int(cost[k]) != 0:
			campaign["resources"][k] = int(campaign["resources"].get(k, 0)) - int(cost[k])

static func refund(campaign: Dictionary, cost: Dictionary) -> void:
	for k in cost:
		if int(cost[k]) != 0:
			campaign["resources"][k] = int(campaign["resources"].get(k, 0)) + int(cost[k])
