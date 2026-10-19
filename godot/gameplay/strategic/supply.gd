extends RefCounted
class_name Supply
## Supply propagation and movement range. Supply must change what the player can
## do, so it is recomputed from sources every turn rather than stored as a
## decorative number.

static func side_of(faction: String) -> String:
	return "axis" if faction.begins_with("axis_") else "allied"

static func control_side(control: String) -> String:
	if control == "allied": return "allied"
	if control == "axis": return "axis"
	return ""   # neutral and contested carry supply for neither side

## Recompute tile supply for one side. A source emits `throughput`; each step
## costs the destination terrain's supply_draw; only a tile this side controls
## relays further. Contested tiles may receive supply but never relay it.
static func propagate(campaign: Dictionary, side: String, sources: Array) -> Dictionary:
	var best: Dictionary = {}
	var frontier: Array = []
	var tiles: Dictionary = campaign["tiles"]
	for s in sources:
		if float(s["throughput"]) <= 0.0:
			continue
		if not tiles.has(s["tile_id"]):
			continue
		var v: float = minf(10.0, float(s["throughput"]))
		if float(best.get(s["tile_id"], -1.0)) < v:
			best[s["tile_id"]] = v
			frontier.append([s["tile_id"], v])
	# Highest-value-first relaxation with the tile id as tie-break, so the
	# result is identical for a given state regardless of dictionary order.
	while not frontier.is_empty():
		frontier.sort_custom(func(a, b):
			if a[1] != b[1]: return a[1] > b[1]
			return str(a[0]) < str(b[0]))
		var head: Array = frontier.pop_front()
		var id: String = head[0]
		var val: float = head[1]
		if float(best.get(id, -1.0)) > val:
			continue
		var tile: Dictionary = tiles[id]
		if control_side(str(tile["control"])) != side:
			continue
		for nb in tile["neighbors"]:
			if not tiles.has(nb):
				continue
			var n: Dictionary = tiles[nb]
			if not bool(n["passable"]):
				continue
			var draw: float = maxf(0.5, float(ContentDB.terrain_rule(str(n["terrain"])).get("supply_draw", 1.0)))
			var nxt: float = maxf(0.0, val - draw)
			if nxt <= 0.0:
				continue
			if float(best.get(nb, -1.0)) < nxt:
				best[nb] = nxt
				frontier.append([nb, nxt])
	return best

static func apply(campaign: Dictionary, sources_by_side: Dictionary) -> void:
	var allied := propagate(campaign, "allied", sources_by_side.get("allied", []))
	var axis := propagate(campaign, "axis", sources_by_side.get("axis", []))
	for id in campaign["tiles"]:
		var t: Dictionary = campaign["tiles"][id]
		var side := control_side(str(t["control"]))
		var v: float = 0.0
		if side == "allied":
			v = float(allied.get(id, 0.0))
		elif side == "axis":
			v = float(axis.get(id, 0.0))
		else:
			v = maxf(float(allied.get(id, 0.0)), float(axis.get(id, 0.0))) * 0.5
		t["supply"] = clampf(snappedf(v - float(t.get("supply_penalty", 0.0)), 0.1), 0.0, 10.0)

	for uid in campaign["units"]:
		var u: Dictionary = campaign["units"][uid]
		var tile: Dictionary = campaign["tiles"].get(u["tile_id"], {})
		if tile.is_empty():
			continue
		var cap: Dictionary = Contracts.UNIT_CAPABILITIES[u["unit_type"]]
		if int(cap["supply_draw"]) == 0:
			# An underground cell lives off the city, not off a depot.
			u["supply"] = 1.0
			continue
		var satisfied: float = clampf(float(tile["supply"]) / float(cap["supply_draw"]), 0.0, 1.0)
		# Change is gradual: a unit does not starve or recover in one week.
		u["supply"] = snappedf(float(u["supply"]) * 0.45 + satisfied * 0.55, 0.001)
		var status: Array = u["status"]
		status = status.filter(func(s): return s != "isolated")
		if float(u["supply"]) < 0.25:
			status.append("isolated")
		u["status"] = status

## Sources that are active on the campaign's current date, including the
## overrides that dated events install (the Normandy beachhead, for instance,
## contributes nothing before the landings).
static func build_sources(campaign: Dictionary) -> Dictionary:
	var out := {"allied": [], "axis": []}
	for th in ContentDB.atlas.get("theaters", []):
		for s in th.get("supply_sources", []):
			var activates: String = str(s.get("activates_on", ""))
			if activates != "" and not CampaignDate.is_on_or_after(str(campaign["date"]), activates):
				continue
			var tile_id := "%s:%d,%d" % [th["id"], int(s["q"]), int(s["r"])]
			var overrides: Dictionary = (campaign["history_flags"] as Dictionary).get("supply_overrides", {})
			var throughput: float = float(overrides.get(tile_id, s.get("throughput", 0)))
			if throughput <= 0.0:
				continue
			(out[side_of(str(s["faction"]))] as Array).append({"tile_id": tile_id, "throughput": throughput})
	return out

## Dijkstra over move cost, honouring the unit type's movement rules.
## Returns {"dist": {tile_id: cost}, "prev": {tile_id: tile_id}}.
static func reachable(campaign: Dictionary, unit: Dictionary, budget_override: int = -1) -> Dictionary:
	var cap: Dictionary = Contracts.UNIT_CAPABILITIES[unit["unit_type"]]
	var budget: int = int(unit["move_budget"]) if budget_override < 0 else budget_override
	var side := side_of(str(unit["faction"]))
	var dist: Dictionary = {unit["tile_id"]: 0}
	var prev: Dictionary = {}
	var open: Array = [[unit["tile_id"], 0]]
	var tiles: Dictionary = campaign["tiles"]
	while not open.is_empty():
		open.sort_custom(func(a, b):
			if a[1] != b[1]: return a[1] < b[1]
			return str(a[0]) < str(b[0]))
		var head: Array = open.pop_front()
		var id: String = head[0]
		var d: int = head[1]
		if int(dist.get(id, 1 << 30)) < d:
			continue
		for nb in (tiles[id] as Dictionary)["neighbors"]:
			if not tiles.has(nb):
				continue
			var n: Dictionary = tiles[nb]
			if not bool(n["passable"]):
				continue
			var rule := ContentDB.terrain_rule(str(n["terrain"]))
			var cost: int = int(rule.get("move_cost", 1))
			if bool(cap["uses_routes"]):
				# A regular formation cannot walk into ground the other side
				# holds unless it is attacking, and pays extra for contested
				# ground and for moving off supply.
				var cs := control_side(str(n["control"]))
				if cs != "" and cs != side:
					continue
				if n["control"] == "contested":
					cost += 1
				if float(n["supply"]) < 1.0:
					cost += 1
			elif bool(cap["uses_access"]):
				# Covert movement ignores frontlines but pays for open ground.
				var conceal: float = float(rule.get("concealment", 0.1))
				cost = maxi(1, int(round(float(rule.get("move_cost", 1)) * (1.5 if conceal < 0.3 else 1.0))))
			var nd: int = d + cost
			if nd <= budget and nd < int(dist.get(nb, 1 << 30)):
				dist[nb] = nd
				prev[nb] = id
				open.append([nb, nd])
	dist.erase(unit["tile_id"])
	return {"dist": dist, "prev": prev}

static func path_to(prev: Dictionary, from_id: String, to_id: String) -> Array:
	var path: Array = [to_id]
	var cur: String = to_id
	while prev.has(cur):
		cur = str(prev[cur])
		path.insert(0, cur)
		if cur == from_id:
			break
	return path if path[0] == from_id else []
