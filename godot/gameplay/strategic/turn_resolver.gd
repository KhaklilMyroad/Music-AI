extends RefCounted
class_name TurnResolver
## Deterministic turn resolution.
##
## Phase order is fixed and documented in docs/03-TURN-RESOLUTION-SPEC.md:
##   1 validate queued orders
##   2 reserve or spend their costs
##   3 resolve movement and encounters
##   4 resolve strategic opposition
##   5 update supply and recovery
##   6 advance construction and research
##   7 trigger dated events
##   8 present a readable turn report
##   9 commit the checkpoint
##
## Given the same (state, seed) the output is identical. Every iteration over a
## collection sorts by stable id first: Dictionary key order is not a contract.

static func _sorted_keys(d: Dictionary) -> Array:
	var k := d.keys()
	k.sort()
	return k

## Combat strength: readiness x supply x terrain x fortification. No hidden bonuses.
static func combat_power(campaign: Dictionary, unit: Dictionary, as_defender: bool) -> float:
	var tile: Dictionary = campaign["tiles"][unit["tile_id"]]
	var rule := ContentDB.terrain_rule(str(tile["terrain"]))
	var base: float = float(unit["strength"]) * (0.35 + 0.65 * float(unit["supply"]))
	if as_defender:
		base *= 1.0 + float(rule.get("cover", 0.0))
		if (unit["status"] as Array).has("entrenched"):
			base *= 1.3
		if tile.get("city_id") != null:
			var city: Dictionary = campaign["cities"][tile["city_id"]]
			for f in city["facilities"]:
				var fd: Dictionary = f
				if fd.get("facility_id") != "fac_fortification" or bool(fd.get("disabled", false)):
					continue
				var spec := ContentDB.facility("fac_fortification")
				var mult: float = float(spec["benefit"]["defence_multiplier"])
				base *= (1.0 + (mult - 1.0) * 0.5) if bool(fd.get("damaged", false)) else mult
	return maxf(0.01, base)

static func resolve(campaign: Dictionary) -> Dictionary:
	var rng := DetRng.new(int(campaign["rng_seed"]) ^ (int(campaign["turn"]) * 0x9e3779b1))
	var report := {
		"turn": int(campaign["turn"]), "date": str(campaign["date"]),
		"rejected_orders": [], "movements": [], "engagements": [], "opposition": [],
		"supply_changes": [], "construction": [], "events": [], "civilian": [], "network": [],
	}

	# -- phase 1: re-validate everything still queued ------------------------
	# A queued order whose preconditions expired is refunded, never silently
	# applied.
	var accepted: Array = []
	var queue: Array = (campaign["order_queue"] as Array).duplicate()
	for q in queue:
		var rest: Array = []
		for other in queue:
			if other != q:
				rest.append(other)
		campaign["order_queue"] = rest
		var v := Orders.validate(campaign, (q as Dictionary)["order"])
		campaign["order_queue"] = queue
		if not bool(v["ok"]):
			Orders.refund(campaign, (q as Dictionary)["cost"])
			(report["rejected_orders"] as Array).append({
				"order_id": (q as Dictionary)["order_id"], "reason": v["reason"],
				"detail": v["detail"], "refunded": (q as Dictionary)["cost"],
			})
		else:
			var a: Dictionary = (q as Dictionary).duplicate()
			a["plan"] = v["plan"]
			accepted.append(a)
	campaign["order_queue"] = []

	# -- phase 2: costs were reserved at submission; the refunds above are the
	#             only resource movement in this phase.

	# -- phase 3: movement, then encounters ----------------------------------
	var moves: Array = accepted.filter(func(a): return (a["plan"] as Dictionary)["kind"] in ["move", "move_covert"])
	moves.sort_custom(func(a, b): return str(a["plan"]["unit_id"]) < str(b["plan"]["unit_id"]))
	for m in moves:
		var plan: Dictionary = m["plan"]
		var unit: Dictionary = (campaign["units"] as Dictionary).get(plan["unit_id"], {})
		if unit.is_empty():
			continue
		var from_id: String = str(unit["tile_id"])
		var path: Array = plan["path"]
		unit["tile_id"] = path[path.size() - 1]
		unit["move_budget"] = maxi(0, int(unit["move_budget"]) - int(plan["move_cost"]))
		unit["status"] = (unit["status"] as Array).filter(func(s): return s != "entrenched")
		var dest: Dictionary = campaign["tiles"][unit["tile_id"]]
		var cap: Dictionary = Contracts.UNIT_CAPABILITIES[unit["unit_type"]]
		if bool(cap["can_occupy"]) and Supply.control_side(str(dest["control"])) == "":
			dest["control"] = Supply.side_of(str(unit["faction"]))
		(report["movements"] as Array).append({"unit_id": unit["unit_id"], "from": from_id, "to": unit["tile_id"], "cost": plan["move_cost"]})

	for tid in _sorted_keys(campaign["tiles"]):
		var t: Dictionary = campaign["tiles"][tid]
		var sides: Dictionary = {}
		var occupants: Array = []
		for uid in _sorted_keys(campaign["units"]):
			var u: Dictionary = campaign["units"][uid]
			if u["tile_id"] == tid:
				occupants.append(uid)
				sides[Supply.side_of(str(u["faction"]))] = true
		if sides.size() > 1:
			if t["control"] != "contested":
				t["control"] = "contested"
				t["contested_since_turn"] = int(campaign["turn"])
			(report["engagements"] as Array).append({"tile_id": tid, "kind": "contact", "unit_ids": occupants})

	# attacks
	var attacks: Array = accepted.filter(func(a): return (a["plan"] as Dictionary)["kind"] == "attack")
	attacks.sort_custom(func(a, b): return str(a["plan"]["unit_id"]) < str(b["plan"]["unit_id"]))
	for a in attacks:
		var plan: Dictionary = a["plan"]
		var attacker: Dictionary = (campaign["units"] as Dictionary).get(plan["unit_id"], {})
		if attacker.is_empty():
			continue
		var tile: Dictionary = campaign["tiles"][plan["tile_id"]]
		var defenders: Array = []
		for did in plan["defender_ids"]:
			if (campaign["units"] as Dictionary).has(did):
				defenders.append(campaign["units"][did])
		var ap := combat_power(campaign, attacker, false)
		var dp: float = 0.0
		for d in defenders:
			dp += combat_power(campaign, d, true)
		var roll := rng.fork("attack:%s:%d" % [plan["unit_id"], int(campaign["turn"])]).float_range(0.85, 1.15)
		var ratio: float = (ap * roll) / maxf(0.01, dp if dp > 0.0 else 0.2)
		var outcome: String
		if ratio >= 1.6: outcome = "attacker_takes_tile"
		elif ratio >= 1.05: outcome = "defender_pushed"
		elif ratio >= 0.7: outcome = "stalemate"
		else: outcome = "attack_repulsed"

		var loss_a: float = {"attack_repulsed": 0.18, "stalemate": 0.11}.get(outcome, 0.07)
		var loss_d: float = {"attacker_takes_tile": 0.26, "defender_pushed": 0.16, "stalemate": 0.10}.get(outcome, 0.04)
		attacker["strength"] = maxf(0.0, snappedf(float(attacker["strength"]) - loss_a, 0.001))
		var all_broken := true
		for d in defenders:
			d["strength"] = maxf(0.0, snappedf(float(d["strength"]) - loss_d, 0.001))
			if float(d["strength"]) <= 0.12:
				if not (d["status"] as Array).has("routed"):
					(d["status"] as Array).append("routed")
			else:
				all_broken = false
		if outcome == "attacker_takes_tile" and all_broken:
			for d in defenders:
				(campaign["units"] as Dictionary).erase(d["unit_id"])
			attacker["tile_id"] = tile["tile_id"]
			tile["control"] = Supply.side_of(str(attacker["faction"]))
		elif outcome == "defender_pushed":
			tile["control"] = "contested"
			tile["contested_since_turn"] = int(campaign["turn"])
		if float(attacker["strength"]) <= 0.12 and not (attacker["status"] as Array).has("routed"):
			(attacker["status"] as Array).append("routed")
		(report["engagements"] as Array).append({"tile_id": tile["tile_id"], "kind": outcome, "attacker": attacker["unit_id"], "ratio": snappedf(ratio, 0.01)})

	# covert actions
	for a in accepted.filter(func(x): return (x["plan"] as Dictionary)["kind"] in ["sabotage", "reconnoitre", "courier"]):
		var plan: Dictionary = a["plan"]
		var unit: Dictionary = (campaign["units"] as Dictionary).get(plan["unit_id"], {})
		if unit.is_empty():
			continue
		var net: Dictionary = {}
		for nid in _sorted_keys(campaign["networks"]):
			var n: Dictionary = campaign["networks"][nid]
			for c in n["cells"]:
				if (c as Dictionary).get("tile_id") == unit["tile_id"]:
					net = n
			if net.is_empty():
				net = n
		var sub := rng.fork("covert:%s:%s:%d" % [plan["kind"], plan["unit_id"], int(campaign["turn"])])
		var base: float = 0.55 if plan["kind"] == "sabotage" else 0.75
		var access: int = int(net.get("access", 0))
		var exposure: float = float(net.get("exposure", 0.0))
		var ok: bool = sub.chance(minf(0.95, base + 0.08 * float(access) - 0.4 * exposure))
		match plan["kind"]:
			"sabotage":
				if ok:
					var t: Dictionary = campaign["tiles"][plan["tile_id"]]
					t["supply_penalty"] = minf(4.0, float(t.get("supply_penalty", 0.0)) + 1.0)
				if not net.is_empty():
					net["exposure"] = minf(1.0, snappedf(exposure + (0.05 if ok else 0.14), 0.001))
			"reconnoitre":
				if ok:
					campaign["resources"]["intelligence"] = int(campaign["resources"]["intelligence"]) + 1
					(campaign["tiles"][plan["tile_id"]] as Dictionary)["discovered"] = true
				if not net.is_empty():
					net["exposure"] = minf(1.0, snappedf(exposure + (0.01 if ok else 0.07), 0.001))
			"courier":
				if ok and not net.is_empty() and access < 3:
					net["access"] = mini(5, access + 1)
				elif not net.is_empty() and not ok:
					net["exposure"] = minf(1.0, snappedf(exposure + 0.1, 0.001))
		(report["network"] as Array).append({"unit_id": unit["unit_id"], "action": plan["kind"], "succeeded": ok, "exposure": net.get("exposure", null)})

	for a in accepted.filter(func(x): return (x["plan"] as Dictionary)["kind"] in ["defend", "entrench", "hide"]):
		var plan: Dictionary = a["plan"]
		var unit: Dictionary = (campaign["units"] as Dictionary).get(plan["unit_id"], {})
		if unit.is_empty():
			continue
		if plan["kind"] == "entrench" and not (unit["status"] as Array).has("entrenched"):
			(unit["status"] as Array).append("entrenched")
		if plan["kind"] == "hide" and not (unit["status"] as Array).has("hidden"):
			(unit["status"] as Array).append("hidden")

	for a in accepted.filter(func(x): return (x["plan"] as Dictionary)["kind"] in ["relieve", "evacuate"]):
		var plan: Dictionary = a["plan"]
		var city: Dictionary = (campaign["cities"] as Dictionary).get(plan["city_id"], {})
		if city.is_empty():
			continue
		for gid in city["civilian_group_ids"]:
			var g: Dictionary = (campaign["civilian_groups"] as Dictionary).get(gid, {})
			if g.is_empty():
				continue
			if plan["kind"] == "relieve":
				g["needs"]["food"] = minf(1.0, snappedf(float(g["needs"]["food"]) + 0.3, 0.001))
				g["needs"]["medicine"] = minf(1.0, snappedf(float(g["needs"]["medicine"]) + 0.2, 0.001))
			elif g["displacement"] in ["restricted", "displaced"]:
				for f in city["facilities"]:
					if (f as Dictionary).get("facility_id") == "fac_escape_route" and not bool((f as Dictionary).get("disabled", false)):
						g["displacement"] = "evacuated"
						(report["civilian"] as Array).append({"group_id": gid, "change": "evacuated"})
						break

	# -- phase 4: strategic opposition ---------------------------------------
	# The opponent is bound by the same movement, supply and adjacency rules.
	var opp_side := "axis" if Supply.side_of(str(campaign["player_faction"])) == "allied" else "allied"
	for uid in _sorted_keys(campaign["units"]):
		var u: Dictionary = (campaign["units"] as Dictionary).get(uid, {})
		if u.is_empty() or Supply.side_of(str(u["faction"])) != opp_side:
			continue
		if (u["status"] as Array).has("in_transit") or (u["status"] as Array).has("routed"):
			continue
		var cap: Dictionary = Contracts.UNIT_CAPABILITIES[u["unit_type"]]
		if not (cap["actions"] as Array).has("attack") or float(u["supply"]) < 0.25 or int(u["move_budget"]) <= 0:
			continue
		var home: Dictionary = campaign["tiles"][u["tile_id"]]
		var targets: Array = []
		for nb in home["neighbors"]:
			var n: Dictionary = (campaign["tiles"] as Dictionary).get(nb, {})
			if n.is_empty() or not bool(n["passable"]):
				continue
			for oid in _sorted_keys(campaign["units"]):
				var o: Dictionary = campaign["units"][oid]
				if o["tile_id"] == nb and Supply.side_of(str(o["faction"])) != opp_side:
					targets.append(nb)
					break
		if targets.is_empty():
			continue
		targets.sort()
		var target: Dictionary = campaign["tiles"][targets[0]]
		var defenders: Array = []
		for oid in _sorted_keys(campaign["units"]):
			var o: Dictionary = campaign["units"][oid]
			if o["tile_id"] == target["tile_id"] and Supply.side_of(str(o["faction"])) != opp_side:
				defenders.append(o)
		var ap := combat_power(campaign, u, false)
		var dp: float = 0.0
		for d in defenders:
			dp += combat_power(campaign, d, true)
		if ap < dp * 0.8:
			(report["opposition"] as Array).append({"unit_id": uid, "decision": "held", "reason": "unfavourable"})
			continue
		var roll := rng.fork("opp:%s:%d" % [uid, int(campaign["turn"])]).float_range(0.85, 1.15)
		var ratio: float = (ap * roll) / maxf(0.01, dp)
		for d in defenders:
			d["strength"] = maxf(0.0, snappedf(float(d["strength"]) - (0.2 if ratio > 1.2 else 0.11), 0.001))
			if float(d["strength"]) <= 0.12 and not (d["status"] as Array).has("routed"):
				(d["status"] as Array).append("routed")
		u["strength"] = maxf(0.0, snappedf(float(u["strength"]) - (0.06 if ratio > 1.2 else 0.13), 0.001))
		u["move_budget"] = 0
		if target["control"] != "contested":
			target["control"] = "contested"
			target["contested_since_turn"] = int(campaign["turn"])
		(report["opposition"] as Array).append({"unit_id": uid, "decision": "attacked", "tile_id": target["tile_id"], "ratio": snappedf(ratio, 0.01)})

	# -- phase 5: supply and recovery ----------------------------------------
	var before: Dictionary = {}
	for tid in _sorted_keys(campaign["tiles"]):
		before[tid] = float((campaign["tiles"][tid] as Dictionary)["supply"])
	Supply.apply(campaign, Supply.build_sources(campaign))
	for tid in _sorted_keys(campaign["tiles"]):
		var t: Dictionary = campaign["tiles"][tid]
		if absf(float(before[tid]) - float(t["supply"])) >= 0.5:
			(report["supply_changes"] as Array).append({"tile_id": tid, "from": before[tid], "to": t["supply"]})

	for uid in _sorted_keys(campaign["units"]):
		var u: Dictionary = campaign["units"][uid]
		var cap: Dictionary = Contracts.UNIT_CAPABILITIES[u["unit_type"]]
		u["move_budget"] = 0 if (u["status"] as Array).has("in_transit") else maxi(0, int(round(float(cap["move_budget"]) * (0.4 + 0.6 * float(u["supply"])))))
		if float(u["supply"]) > 0.6 and float(u["strength"]) < 1.0:
			var bonus: float = 0.0
			var tile: Dictionary = campaign["tiles"][u["tile_id"]]
			if tile.get("city_id") != null:
				for f in (campaign["cities"][tile["city_id"]] as Dictionary)["facilities"]:
					if (f as Dictionary).get("facility_id") == "fac_medical_depot" and not bool((f as Dictionary).get("disabled", false)):
						bonus = 0.09 if bool((f as Dictionary).get("damaged", false)) else 0.18
			u["strength"] = minf(1.0, snappedf(float(u["strength"]) + 0.05 + bonus, 0.001))
			if float(u["strength"]) > 0.3:
				u["status"] = (u["status"] as Array).filter(func(s): return s != "routed")

	for gid in _sorted_keys(campaign["civilian_groups"]):
		var g: Dictionary = campaign["civilian_groups"][gid]
		var city: Dictionary = (campaign["cities"] as Dictionary).get(g["city_id"], {})
		var kitchen: Dictionary = _facility(city, "fac_relief_kitchen")
		var depot: Dictionary = _facility(city, "fac_medical_depot")
		var restriction: float = float(city.get("restriction_level", 0)) / 5.0
		var decay: float = 0.06 + 0.10 * restriction
		g["needs"]["food"] = _c01(float(g["needs"]["food"]) - decay + (0.0 if kitchen.is_empty() else (0.05 if bool(kitchen.get("damaged", false)) else 0.12)))
		g["needs"]["water"] = _c01(float(g["needs"]["water"]) - decay * 0.7 + (0.08 if float(city.get("supply_access", 0.0)) > 2.0 else 0.0))
		g["needs"]["medicine"] = _c01(float(g["needs"]["medicine"]) - decay * 0.6 + (0.0 if depot.is_empty() else (0.04 if bool(depot.get("damaged", false)) else 0.11)))
		g["needs"]["shelter"] = _c01(float(g["needs"]["shelter"]) - (0.1 if city.get("control") == "contested" else 0.02))
		if float(g["needs"]["food"]) < 0.25 and g["displacement"] == "in_place":
			g["displacement"] = "restricted"
			(report["civilian"] as Array).append({"group_id": gid, "change": "restricted", "cause": "food"})

	for nid in _sorted_keys(campaign["networks"]):
		var n: Dictionary = campaign["networks"][nid]
		var city: Dictionary = (campaign["cities"] as Dictionary).get(n["city_id"], {})
		var radio: Dictionary = _facility(city, "fac_underground_radio")
		if not radio.is_empty() and not bool(radio.get("damaged", false)):
			var spec := ContentDB.facility("fac_underground_radio")
			campaign["resources"]["intelligence"] = int(campaign["resources"]["intelligence"]) + int(spec["benefit"]["intelligence_per_turn"])
			n["exposure"] = minf(1.0, snappedf(float(n["exposure"]) + float(spec["risk"]["exposure_per_turn"]), 0.001))
		n["exposure"] = maxf(0.0, snappedf(float(n["exposure"]) - 0.03, 0.001))
		if float(n["exposure"]) >= 0.8:
			var sub := rng.fork("search:%s:%d" % [nid, int(campaign["turn"])])
			var cells: Array = (n["cells"] as Array).filter(func(c): return not bool((c as Dictionary).get("compromised", false)))
			cells.sort_custom(func(a, b): return str(a["cell_id"]) < str(b["cell_id"]))
			if not cells.is_empty() and sub.chance(0.5):
				(cells[0] as Dictionary)["compromised"] = true
				n["access"] = maxi(0, int(n["access"]) - 1)
				n["exposure"] = maxf(0.0, float(n["exposure"]) - 0.25)
				(report["network"] as Array).append({"network_id": nid, "event": "cell_compromised", "cell_id": (cells[0] as Dictionary)["cell_id"]})

	# -- phase 6: construction and research ---------------------------------
	for a in accepted.filter(func(x): return (x["plan"] as Dictionary)["kind"] == "construct"):
		var plan: Dictionary = a["plan"]
		var city: Dictionary = campaign["cities"][plan["city_id"]]
		(city["construction_queue"] as Array).append({"facility_id": plan["facility_id"], "turns_remaining": int(plan["turns"]), "reserved_cost": a["cost"]})
		(report["construction"] as Array).append({"city_id": plan["city_id"], "facility_id": plan["facility_id"], "started": true, "turns": plan["turns"]})
	for a in accepted.filter(func(x): return (x["plan"] as Dictionary)["kind"] == "repair"):
		var plan: Dictionary = a["plan"]
		var city: Dictionary = campaign["cities"][plan["city_id"]]
		var f := _facility(city, str(plan["facility_id"]))
		if not f.is_empty():
			f["damaged"] = false
			f["disabled"] = false
			(report["construction"] as Array).append({"city_id": plan["city_id"], "facility_id": plan["facility_id"], "repaired": true})

	for cid in _sorted_keys(campaign["cities"]):
		var city: Dictionary = campaign["cities"][cid]
		var still: Array = []
		for q in city["construction_queue"]:
			var qd: Dictionary = q
			qd["turns_remaining"] = int(qd["turns_remaining"]) - 1
			if int(qd["turns_remaining"]) <= 0:
				(city["facilities"] as Array).append({"facility_id": qd["facility_id"], "built_turn": int(campaign["turn"]), "damaged": false, "disabled": false})
				(report["construction"] as Array).append({"city_id": cid, "facility_id": qd["facility_id"], "completed": true})
			else:
				still.append(qd)
		city["construction_queue"] = still
		recompute_city_services(city)
		var tile: Dictionary = campaign["tiles"][city["tile_id"]]
		city["supply_access"] = float(tile["supply"])
		var tile_side := Supply.control_side(str(tile["control"]))
		if tile_side != "" and Supply.control_side(str(city["control"])) != tile_side:
			city["control"] = tile["control"]
			apply_control_change(city, report)

	# -- phase 7: dated events ----------------------------------------------
	campaign["turn"] = int(campaign["turn"]) + 1
	campaign["date"] = CampaignDate.add_days(str(campaign["date"]), ContentDB.turn_length_days())
	var events: Array = ContentDB.timeline_events().duplicate()
	events.sort_custom(func(a, b): return str(a["date"]) < str(b["date"]))
	for ev in events:
		if (campaign["fired_events"] as Array).has(ev["id"]):
			continue
		if not CampaignDate.is_on_or_after(str(campaign["date"]), str(ev["date"])):
			continue
		(campaign["fired_events"] as Array).append(ev["id"])
		apply_event(campaign, ev, report)
		(report["events"] as Array).append({"id": ev["id"], "date": ev["date"], "label_key": ev["label_key"], "sensitivity": ev.get("sensitivity", null)})

	# chapter availability follows date and prerequisites, never a hidden unlock
	for ch in ContentDB.chapters.get("chapters", []):
		if (campaign["unlocked_chapters"] as Array).has(ch["id"]) or (campaign["completed_chapters"] as Array).has(ch["id"]):
			continue
		var w: Dictionary = ch["date_window"]
		if not CampaignDate.in_window(str(campaign["date"]), str(w.get("from", "")), str(w.get("to", ""))):
			continue
		var ok := true
		for e in (ch["prerequisites"] as Dictionary)["events"]:
			if not (campaign["fired_events"] as Array).has(e):
				ok = false
		for c in (ch["prerequisites"] as Dictionary)["chapters"]:
			if not (campaign["completed_chapters"] as Array).has(c):
				ok = false
		if int(campaign["resources"]["intelligence"]) < int((ch["prerequisites"] as Dictionary).get("min_intelligence", 0)):
			ok = false
		if ok:
			(campaign["unlocked_chapters"] as Array).append(ch["id"])
			(report["events"] as Array).append({"id": ch["id"], "label_key": ch["label_key"], "kind": "chapter_available"})

	# -- phase 8 + 9: report, then commit -----------------------------------
	campaign["revision"] = int(campaign["revision"]) + 1
	campaign["last_turn_report"] = report
	return report

static func _c01(v: float) -> float:
	return clampf(snappedf(v, 0.001), 0.0, 1.0)

static func _facility(city: Dictionary, id: String) -> Dictionary:
	if city.is_empty():
		return {}
	for f in city.get("facilities", []):
		if (f as Dictionary).get("facility_id") == id and not bool((f as Dictionary).get("disabled", false)):
			return f
	return {}

static func recompute_city_services(city: Dictionary) -> Dictionary:
	var health: float = 0.0
	var food: float = 0.0
	var evac: float = 0.0
	for f in city["facilities"]:
		var fd: Dictionary = f
		if bool(fd.get("disabled", false)):
			continue
		var spec := ContentDB.facility(str(fd["facility_id"]))
		if spec.is_empty():
			continue
		var scale: float = 0.5 if bool(fd.get("damaged", false)) else 1.0
		var b: Dictionary = spec["benefit"]
		health += float(b.get("civilian_health_capacity", 0)) * scale
		food += float(b.get("civilian_food_capacity", 0)) * scale
		evac += float(b.get("civilian_evacuation_per_turn", 0)) * scale
	city["service_capacity"] = {
		"civilian_health": snappedf(health, 0.1),
		"civilian_food": snappedf(food, 0.1),
		"evacuation": snappedf(evac, 0.1),
	}
	return city["service_capacity"]

static func apply_control_change(city: Dictionary, report: Variant = null) -> void:
	for f in city["facilities"]:
		var fd: Dictionary = f
		var spec := ContentDB.facility(str(fd["facility_id"]))
		if spec.is_empty():
			continue
		match str(spec.get("on_control_change", "")):
			"captured_disabled": fd["disabled"] = true
			"captured_intact": pass
			"survives_hidden": pass
			_: fd["disabled"] = true
		if report != null:
			((report as Dictionary)["construction"] as Array).append({"city_id": city["city_id"], "facility_id": fd["facility_id"], "control_change": spec.get("on_control_change")})
	recompute_city_services(city)

static func apply_event(campaign: Dictionary, ev: Dictionary, report: Variant = null) -> void:
	var e: Dictionary = ev.get("effects", {})
	for th in e.get("opens_theaters", []):
		(campaign["history_flags"] as Dictionary)["theater_open:%s" % th] = true
	for city_id in e.get("city_state", {}):
		var c: Dictionary = (campaign["cities"] as Dictionary).get(city_id, {})
		if not c.is_empty():
			c["place_date_context"] = e["city_state"][city_id]
	for city_id in e.get("civilian_restriction_level", {}):
		var c: Dictionary = (campaign["cities"] as Dictionary).get(city_id, {})
		if c.is_empty():
			continue
		var lvl: int = int(e["civilian_restriction_level"][city_id])
		c["restriction_level"] = lvl
		for gid in c["civilian_group_ids"]:
			var g: Dictionary = (campaign["civilian_groups"] as Dictionary).get(gid, {})
			if g.is_empty():
				continue
			if lvl >= 3 and g["displacement"] == "in_place":
				g["displacement"] = "restricted"
			var flag := "restriction_level_%d" % lvl
			if not (g["access_restrictions"] as Array).has(flag):
				(g["access_restrictions"] as Array).append(flag)
	for district_id in e.get("district_state", {}):
		(campaign["history_flags"] as Dictionary)["district_state:%s" % district_id] = e["district_state"][district_id]
	for s in e.get("supply_source_activate", []):
		var hf: Dictionary = campaign["history_flags"]
		if not hf.has("supply_overrides"):
			hf["supply_overrides"] = {}
		(hf["supply_overrides"] as Dictionary)["%s:%d,%d" % [s["theater"], int(s["q"]), int(s["r"])]] = float(s["throughput"])
	for eq in e.get("unlock_equipment", []):
		if not (campaign["unlocked_equipment"] as Array).has(eq):
			(campaign["unlocked_equipment"] as Array).append(eq)
	for th in e.get("theater_control", {}):
		var side: String = str(e["theater_control"][th])
		for tid in _sorted_keys(campaign["tiles"]):
			var t: Dictionary = campaign["tiles"][tid]
			if t["theater"] == th and bool(t["passable"]):
				t["control"] = side
		if report != null:
			((report as Dictionary)["events"] as Array).append({"id": ev["id"], "kind": "theater_control", "theater": th, "to": side})
	if e.has("campaign_phase"):
		(campaign["history_flags"] as Dictionary)["campaign_phase"] = e["campaign_phase"]
