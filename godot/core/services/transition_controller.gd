extends Node
## Transition state machine and exactly-once consequence commit (brief §17).
##
##   StrategicReady -> PreparingMission -> LoadingMission -> MissionReady
##                  -> PlayingMission -> ResolvingMission -> Returning -> StrategicReady
##
## Three hard rules, each with a test in tests/test_transition.gd:
##   1 a double tap cannot create two active operations
##   2 delivering the same MissionResult twice applies its effects once
##   3 an interrupted return either resumes the pending commit or loads the
##     already-committed result; completion is never inferred from a missing scene

signal state_changed(state: String, operation_id: String)
signal transition_failed(code: String, detail: String)

const ERR_OPERATION_ACTIVE := "transition.operation_already_active"
const ERR_ILLEGAL_STATE := "transition.illegal_state"
const ERR_ORDER_REJECTED := "transition.order_rejected"
const ERR_NO_PENDING := "transition.no_pending_operation"
const ERR_CONTEXT_MISMATCH := "transition.context_mismatch"
const ERR_CONTENT_MISSING := "transition.content_missing"
const ERR_NOT_PLAYABLE := "transition.not_playable"

const LEGAL := {
	Contracts.S_READY: [Contracts.S_PREPARING],
	Contracts.S_PREPARING: [Contracts.S_LOADING, Contracts.S_FAILED, Contracts.S_READY],
	Contracts.S_LOADING: [Contracts.S_MISSION_READY, Contracts.S_FAILED],
	Contracts.S_MISSION_READY: [Contracts.S_PLAYING, Contracts.S_FAILED],
	Contracts.S_PLAYING: [Contracts.S_RESOLVING, Contracts.S_FAILED],
	Contracts.S_RESOLVING: [Contracts.S_RETURNING, Contracts.S_FAILED],
	Contracts.S_RETURNING: [Contracts.S_READY],
	Contracts.S_FAILED: [Contracts.S_READY, Contracts.S_LOADING],
}

const READINESS_KEYS := ["player", "collision", "navigation", "objectives", "ui", "audio"]

var last_error: Dictionary = {}

func _step_to(pending: Dictionary, next: String) -> bool:
	var allowed: Array = LEGAL.get(pending["state"], [])
	if not allowed.has(next):
		_fail(ERR_ILLEGAL_STATE, "%s -> %s" % [pending["state"], next])
		return false
	pending["state"] = next
	(pending["history"] as Array).append({"state": next, "at": (pending["history"] as Array).size()})
	state_changed.emit(next, str(pending["operation_id"]))
	return true

func _fail(code: String, detail: String) -> void:
	last_error = {"code": code, "detail": detail}
	transition_failed.emit(code, detail)

## Deterministic operation id: the same campaign revision and nonce always give
## the same id, so a retried tap is the same operation rather than a new one.
static func operation_id(campaign: Dictionary, nonce: String) -> String:
	var h := DetRng.hash_string("%s|%d|%d|%s" % [campaign["campaign_id"], int(campaign["revision"]), int(campaign["turn"]), nonce])
	return "op_%s_%s" % [_base36(int(campaign["revision"])), _base36(h)]

static func _base36(n: int) -> String:
	if n == 0:
		return "0"
	const DIGITS := "0123456789abcdefghijklmnopqrstuvwxyz"
	var out := ""
	var v: int = abs(n)
	while v > 0:
		out = DIGITS[v % 36] + out
		v /= 36
	return out

## The outcome bounds are the only thing that lets a mission change the
## campaign, and they come from authored content, never from the mission scene.
static func bounds_for_chapter(chapter: Dictionary) -> Dictionary:
	var effects: Dictionary = chapter.get("strategic_effects", {})
	var max_of := func(field: String) -> float:
		var m: float = 0.0
		for k in effects:
			m = maxf(m, float((effects[k] as Dictionary).get(field, 0)))
		return m
	var min_of := func(field: String) -> float:
		var m: float = 0.0
		for k in effects:
			m = minf(m, float((effects[k] as Dictionary).get(field, 0)))
		return m
	var any_true := func(field: String) -> bool:
		for k in effects:
			if bool((effects[k] as Dictionary).get(field, false)):
				return true
		return false
	var any_set := func(field: String) -> bool:
		for k in effects:
			if (effects[k] as Dictionary).get(field, null) != null:
				return true
		return false
	return {
		"max_intelligence": int(max_of.call("intelligence")),
		"max_materiel": int(max_of.call("materiel")),
		"min_materiel": int(min_of.call("materiel")),
		"max_personnel": int(max_of.call("personnel")),
		"min_personnel": int(min_of.call("personnel")),
		"may_remove_attacking_formation": any_true.call("removes_attacking_formation"),
		"may_flip_tile_control": any_set.call("tile_control_flip_to"),
		"max_civilian_health_delta": int(max_of.call("civilian_health_delta")),
		"min_civilian_health_delta": int(min_of.call("civilian_health_delta")),
		"max_network_exposure_delta": max_of.call("network_exposure"),
		"max_network_access_delta": int(max_of.call("network_access")),
	}

## Step 1: validate, create the id, reserve the cost, write a durable entry
## checkpoint BEFORE any loading starts.
func begin_operation(campaign: Dictionary, request: Dictionary, nonce: String) -> Dictionary:
	var pending = campaign.get("pending_operation")
	if pending != null and (pending as Dictionary).get("state") != Contracts.S_READY:
		_fail(ERR_OPERATION_ACTIVE, str((pending as Dictionary).get("operation_id")))
		return {}
	var chapter_id: String = str(request.get("chapter_id", ""))
	var chapter := ContentDB.chapter(chapter_id) if chapter_id != "" else {}
	if chapter_id != "" and chapter.is_empty():
		_fail(ERR_CONTENT_MISSING, chapter_id)
		return {}
	var district := ContentDB.district(str(request.get("district_id", "")))
	if district.is_empty():
		_fail(ERR_CONTENT_MISSING, str(request.get("district_id")))
		return {}

	# The strategic order that authorises the operation is validated first, so
	# an illegal order can never leave a half-created operation behind.
	var order_cost: Dictionary = {"materiel": 0, "personnel": 0}
	if request.get("order") != null:
		var v := Orders.validate(campaign, request["order"])
		if not bool(v["ok"]):
			_fail(ERR_ORDER_REJECTED, "%s (%s)" % [v["reason"], v["detail"]])
			return {}
		order_cost = v["cost"]

	var op_id := operation_id(campaign, nonce)
	var permitted: Array = []
	for o in chapter.get("objectives", []):
		permitted.append((o as Dictionary)["id"])
	if permitted.is_empty():
		permitted = ["obj_reach_extraction"]

	var unit_snapshot: Variant = null
	if request.get("unit_id") != null and (campaign["units"] as Dictionary).has(request["unit_id"]):
		unit_snapshot = (campaign["units"][request["unit_id"]] as Dictionary).duplicate(true)

	var context := Contracts.make_mission_context({
		"operation_id": op_id,
		"source_revision": int(campaign["revision"]),
		"campaign_id": campaign["campaign_id"],
		"unit_id": request.get("unit_id", null),
		"tile_id": request.get("tile_id", ""),
		"city_id": (campaign["tiles"] as Dictionary).get(request.get("tile_id", ""), {}).get("city_id", null),
		"district_id": district["id"],
		"district_content_version": district.get("content_version", "unknown"),
		"chapter_id": chapter_id if chapter_id != "" else null,
		"date": campaign["date"],
		"mission_type": (chapter.get("mission_families", ["mission_family_recon"]) as Array)[0],
		"seed": DetRng.hash_string("%s|%d" % [op_id, int(campaign["rng_seed"])]),
		"permitted_objectives": permitted,
		"allowed_outcomes": chapter.get("allowed_outcomes", ["success", "failure", "withdrawal"]),
		"outcome_bounds": bounds_for_chapter(chapter),
		"campaign_time_cost_turns": int(chapter.get("campaign_time_cost_turns", 0)),
		"reserved_cost": order_cost,
		"loadout": request.get("loadout", []),
		"entry_snapshot": {
			"revision": int(campaign["revision"]), "turn": int(campaign["turn"]), "date": campaign["date"],
			"resources": (campaign["resources"] as Dictionary).duplicate(true),
			"unit": unit_snapshot,
			"tile_control": (campaign["tiles"] as Dictionary).get(request.get("tile_id", ""), {}).get("control", null),
		},
	})
	var issues := Contracts.validate_mission_context(context)
	if not issues.is_empty():
		_fail(ERR_CONTENT_MISSING, "\n".join(issues))
		return {}

	Orders.reserve(campaign, order_cost)
	campaign["pending_operation"] = {
		"operation_id": op_id, "state": Contracts.S_READY, "history": [{"state": Contracts.S_READY, "at": 0}],
		"context": context, "reserved_cost": order_cost, "pending_result": null, "committed": false,
		"district_checkpoint": null, "created_at_revision": int(campaign["revision"]),
		"applied": null, "clamped_fields": [],
	}
	if not _step_to(campaign["pending_operation"], Contracts.S_PREPARING):
		return {}
	Saves.write("auto", campaign, null, "entry_checkpoint")
	return context

func mark_loading(campaign: Dictionary) -> bool:
	var p = campaign.get("pending_operation")
	if p == null:
		_fail(ERR_NO_PENDING, "")
		return false
	if not _step_to(p, Contracts.S_LOADING):
		return false
	Saves.write("auto", campaign, null, "loading")
	return true

## A mission becomes playable only when everything the player needs is ready. A
## missing item fails the transition instead of hiding behind a permanent
## loading animation.
func mark_ready(campaign: Dictionary, readiness: Dictionary) -> bool:
	var p = campaign.get("pending_operation")
	if p == null:
		_fail(ERR_NO_PENDING, "")
		return false
	var missing: Array = []
	for k in READINESS_KEYS:
		if not bool(readiness.get(k, false)):
			missing.append(k)
	if not missing.is_empty():
		_step_to(p, Contracts.S_FAILED)
		(p as Dictionary)["failure"] = {"code": ERR_NOT_PLAYABLE, "missing": missing}
		Saves.write("auto", campaign, null, "load_failed")
		_fail(ERR_NOT_PLAYABLE, ", ".join(missing))
		return false
	if not _step_to(p, Contracts.S_MISSION_READY):
		return false
	Saves.write("auto", campaign, null, "mission_ready")
	return true

func mark_playing(campaign: Dictionary) -> bool:
	var p = campaign.get("pending_operation")
	if p == null:
		_fail(ERR_NO_PENDING, "")
		return false
	if not _step_to(p, Contracts.S_PLAYING):
		return false
	Saves.write("auto", campaign, null, "mission_playing")
	return true

## Save a district checkpoint mid-mission (focus loss, screen lock, safe boundary).
func save_district_checkpoint(campaign: Dictionary, checkpoint: Dictionary) -> bool:
	var p = campaign.get("pending_operation")
	if p == null:
		_fail(ERR_NO_PENDING, "")
		return false
	if (p as Dictionary)["state"] != Contracts.S_PLAYING:
		_fail(ERR_ILLEGAL_STATE, "%s cannot hold a district checkpoint" % (p as Dictionary)["state"])
		return false
	(p as Dictionary)["district_checkpoint"] = checkpoint
	Saves.write("auto", campaign, checkpoint, "district_checkpoint")
	return true

## Step 2: the mission hands back a result. It is validated and clamped against
## the immutable context, then written durably BEFORE any effect is applied.
## Returns {"already_committed": bool, "pending": Dictionary, "clamped": Array, "ok": bool}.
func submit_result(campaign: Dictionary, raw_result: Dictionary) -> Dictionary:
	var p = campaign.get("pending_operation")
	var op_id: String = str(raw_result.get("operation_id", ""))
	if p == null:
		# Repeat delivery after the commit finished and the record was cleared.
		if (campaign["committed_operations"] as Array).has(op_id):
			return {"ok": true, "already_committed": true, "pending": {}, "clamped": []}
		_fail(ERR_NO_PENDING, op_id)
		return {"ok": false, "already_committed": false, "pending": {}, "clamped": []}
	var pending: Dictionary = p
	if str(pending["operation_id"]) != op_id:
		if (campaign["committed_operations"] as Array).has(op_id):
			return {"ok": true, "already_committed": true, "pending": {}, "clamped": []}
		_fail(ERR_CONTEXT_MISMATCH, "%s vs active %s" % [op_id, pending["operation_id"]])
		return {"ok": false, "already_committed": false, "pending": {}, "clamped": []}
	if (campaign["committed_operations"] as Array).has(op_id):
		return {"ok": true, "already_committed": true, "pending": {}, "clamped": []}

	if pending["state"] == Contracts.S_PLAYING:
		if not _step_to(pending, Contracts.S_RESOLVING):
			return {"ok": false, "already_committed": false, "pending": {}, "clamped": []}
	elif pending["state"] != Contracts.S_RESOLVING:
		_fail(ERR_ILLEGAL_STATE, "%s -> %s" % [pending["state"], Contracts.S_RESOLVING])
		return {"ok": false, "already_committed": false, "pending": {}, "clamped": []}

	var v := Contracts.validate_mission_result(raw_result, pending["context"])
	if not bool(v["ok"]):
		_fail(ERR_CONTEXT_MISMATCH, "\n".join(v["issues"]))
		return {"ok": false, "already_committed": false, "pending": {}, "clamped": [], "issues": v["issues"]}
	pending["pending_result"] = v["safe"]
	pending["clamped_fields"] = v["clamped"]
	Saves.write("auto", campaign, pending.get("district_checkpoint"), "pending_result")
	return {"ok": true, "already_committed": false, "pending": v["safe"], "clamped": v["clamped"]}

## Step 3: apply the permitted effects exactly once, then step to Returning.
## Safe to call repeatedly; a second call is a no-op returning the same record.
func commit_result(campaign: Dictionary) -> Dictionary:
	var p = campaign.get("pending_operation")
	if p == null:
		_fail(ERR_NO_PENDING, "")
		return {}
	var pending: Dictionary = p
	if pending.get("pending_result") == null:
		_fail(ERR_NO_PENDING, "no pending_result to commit")
		return {}
	if (campaign["committed_operations"] as Array).has(pending["operation_id"]):
		return {"applied": pending.get("applied"), "repeated": true}

	var r: Dictionary = pending["pending_result"]
	var ctx: Dictionary = pending["context"]
	var chapter := ContentDB.chapter(str(ctx.get("chapter_id", ""))) if ctx.get("chapter_id") != null else {}
	var effects: Dictionary = (chapter.get("strategic_effects", {}) as Dictionary).get(str(r["outcome"]), {})
	var applied := {"operation_id": pending["operation_id"], "outcome": r["outcome"], "changes": [], "spent": (pending["reserved_cost"] as Dictionary).duplicate()}
	var note := func(what: String, detail: Dictionary) -> void:
		var row := {"what": what}
		row.merge(detail)
		(applied["changes"] as Array).append(row)

	for k in r["declared_resources"]:
		var v: int = int(r["declared_resources"][k])
		if v == 0:
			continue
		campaign["resources"][k] = int(campaign["resources"].get(k, 0)) + v
		note.call("resource", {"key": k, "delta": v})
	var lost: int = int(r["declared_losses"].get("personnel", 0))
	if lost != 0:
		campaign["resources"]["personnel"] = maxi(0, int(campaign["resources"]["personnel"]) - lost)
		note.call("resource", {"key": "personnel", "delta": -lost})
	for k in ["intelligence", "materiel", "personnel"]:
		var v: int = int(effects.get(k, 0))
		if v == 0:
			continue
		campaign["resources"][k] = maxi(0, int(campaign["resources"][k]) + v) if k == "personnel" else int(campaign["resources"][k]) + v
		note.call("resource", {"key": k, "delta": v, "from": "chapter_effect"})

	var supply_penalty: int = int((r["requests"] as Dictionary).get("supply_penalty", 0))
	for te in effects.get("tile_effects", []):
		supply_penalty = maxi(supply_penalty, int((te as Dictionary).get("set_supply_penalty", 0)))
	if supply_penalty > 0 and (campaign["tiles"] as Dictionary).has(ctx["tile_id"]):
		var t: Dictionary = campaign["tiles"][ctx["tile_id"]]
		t["supply_penalty"] = minf(4.0, maxf(float(t.get("supply_penalty", 0.0)), float(supply_penalty)))
		note.call("tile_supply_penalty", {"tile_id": t["tile_id"], "value": t["supply_penalty"]})

	var opp_side := "axis" if Supply.side_of(str(campaign["player_faction"])) == "allied" else "allied"
	var readiness_delta: float = float(effects.get("enemy_readiness_delta", 0.0))
	if readiness_delta != 0.0:
		var home: Dictionary = (campaign["tiles"] as Dictionary).get(ctx["tile_id"], {})
		var keys := (campaign["units"] as Dictionary).keys()
		keys.sort()
		for uid in keys:
			var u: Dictionary = campaign["units"][uid]
			if Supply.side_of(str(u["faction"])) != opp_side:
				continue
			if u["tile_id"] != ctx["tile_id"] and not (home.get("neighbors", []) as Array).has(u["tile_id"]):
				continue
			u["strength"] = maxf(0.0, snappedf(float(u["strength"]) + readiness_delta, 0.001))
			note.call("enemy_readiness", {"unit_id": uid, "delta": readiness_delta})

	if bool((r["requests"] as Dictionary).get("remove_attacking_formation", false)):
		var home: Dictionary = (campaign["tiles"] as Dictionary).get(ctx["tile_id"], {})
		var keys := (campaign["units"] as Dictionary).keys()
		keys.sort()
		var candidates: Array = []
		for uid in keys:
			var u: Dictionary = campaign["units"][uid]
			if Supply.side_of(str(u["faction"])) != opp_side:
				continue
			if u["tile_id"] == ctx["tile_id"] or (home.get("neighbors", []) as Array).has(u["tile_id"]):
				candidates.append(u)
		# An attacking formation is one that can attack. A dug-in garrison is
		# only considered when nothing else qualifies.
		var mobile: Array = candidates.filter(func(u): return (u["allowed_actions"] as Array).has("attack") and not (u["status"] as Array).has("entrenched"))
		var target: Dictionary = (mobile[0] if not mobile.is_empty() else (candidates[0] if not candidates.is_empty() else {}))
		if not target.is_empty():
			(campaign["units"] as Dictionary).erase(target["unit_id"])
			note.call("formation_removed", {"unit_id": target["unit_id"], "label_key": target["label_key"]})
		if not home.is_empty() and Supply.control_side(str(home["control"])) != Supply.side_of(str(campaign["player_faction"])):
			home["control"] = Supply.side_of(str(campaign["player_faction"]))
			note.call("tile_control", {"tile_id": home["tile_id"], "to": home["control"]})

	if effects.get("tile_control_flip_to") != null and bool((ctx["outcome_bounds"] as Dictionary)["may_flip_tile_control"]):
		var t: Dictionary = (campaign["tiles"] as Dictionary).get(ctx["tile_id"], {})
		if not t.is_empty():
			var to: String = str(effects["tile_control_flip_to"])
			t["control"] = opp_side if to == "attacker" else to
			note.call("tile_control", {"tile_id": t["tile_id"], "to": t["control"]})

	var civ_delta: float = float((r["requests"] as Dictionary).get("civilian_health_delta", 0.0))
	if civ_delta == 0.0:
		civ_delta = float(effects.get("civilian_health_delta", 0.0))
	if civ_delta != 0.0:
		var city: Dictionary = (campaign["cities"] as Dictionary).get(ctx.get("city_id", ""), {})
		if city.is_empty():
			var ck := (campaign["cities"] as Dictionary).keys()
			ck.sort()
			if not ck.is_empty():
				city = campaign["cities"][ck[0]]
		for gid in city.get("civilian_group_ids", []):
			var g: Dictionary = (campaign["civilian_groups"] as Dictionary).get(gid, {})
			if g.is_empty():
				continue
			g["needs"]["medicine"] = clampf(snappedf(float(g["needs"]["medicine"]) + civ_delta * 0.1, 0.001), 0.0, 1.0)
			note.call("civilian_needs", {"group_id": gid, "medicine_delta": civ_delta * 0.1})

	var exp_delta: float = maxf(float((r["requests"] as Dictionary).get("network_exposure_delta", 0.0)), float(effects.get("network_exposure", 0.0)))
	var acc_delta: int = maxi(int((r["requests"] as Dictionary).get("network_access_delta", 0)), int(effects.get("network_access", 0)))
	if exp_delta != 0.0 or acc_delta != 0:
		var nk := (campaign["networks"] as Dictionary).keys()
		nk.sort()
		var net: Dictionary = {}
		for nid in nk:
			var n: Dictionary = campaign["networks"][nid]
			if n["city_id"] == ctx.get("city_id"):
				net = n
				break
		if net.is_empty() and not nk.is_empty():
			net = campaign["networks"][nk[0]]
		if not net.is_empty():
			if exp_delta != 0.0:
				net["exposure"] = clampf(snappedf(float(net["exposure"]) + exp_delta, 0.001), 0.0, 1.0)
				note.call("network_exposure", {"network_id": net["network_id"], "value": net["exposure"]})
			if acc_delta != 0:
				net["access"] = clampi(int(net["access"]) + acc_delta, 0, 5)
				note.call("network_access", {"network_id": net["network_id"], "value": net["access"]})

	if ctx.get("chapter_id") != null and str(r["outcome"]) in ["success", "partial_success"]:
		var cid: String = str(ctx["chapter_id"])
		if not (campaign["completed_chapters"] as Array).has(cid):
			(campaign["completed_chapters"] as Array).append(cid)
			note.call("chapter_completed", {"chapter_id": cid})
		campaign["unlocked_chapters"] = (campaign["unlocked_chapters"] as Array).filter(func(c): return c != cid)
		for c in effects.get("unlock_chapters", []):
			if not (campaign["unlocked_chapters"] as Array).has(c) and not (campaign["completed_chapters"] as Array).has(c):
				(campaign["unlocked_chapters"] as Array).append(c)
				note.call("chapter_unlocked", {"chapter_id": c})

	var time_cost: int = int(ctx.get("campaign_time_cost_turns", 0))
	if time_cost > 0:
		campaign["turn"] = int(campaign["turn"]) + time_cost
		campaign["date"] = CampaignDate.add_days(str(campaign["date"]), ContentDB.turn_length_days() * time_cost)
		note.call("campaign_time", {"turns": time_cost, "date": campaign["date"]})

	var cityk := (campaign["cities"] as Dictionary).keys()
	cityk.sort()
	for cid in cityk:
		TurnResolver.recompute_city_services(campaign["cities"][cid])

	# ---- the exactly-once barrier ----
	(campaign["committed_operations"] as Array).append(pending["operation_id"])
	pending["committed"] = true
	pending["applied"] = applied
	campaign["revision"] = int(campaign["revision"]) + 1
	_step_to(pending, Contracts.S_RETURNING)
	Saves.write("auto", campaign, null, "committed")
	return {"applied": applied, "repeated": false}

## Step 4: acknowledge and clear. Separate from commit so a crash between the
## two is recoverable.
func acknowledge_return(campaign: Dictionary) -> Variant:
	var p = campaign.get("pending_operation")
	if p == null:
		return null
	var pending: Dictionary = p
	if not bool(pending.get("committed", false)):
		_fail(ERR_ILLEGAL_STATE, "cannot acknowledge an uncommitted operation")
		return null
	var applied = pending.get("applied")
	campaign["pending_operation"] = null
	Saves.write("auto", campaign, null, "return_acknowledged")
	return applied

## A technical failure (missing content, failed load, cancelled entry). Refunds
## the reservation and restores the entry snapshot, so retrying a failure never
## costs the player twice.
func fail_operation(campaign: Dictionary, code: String, detail: String) -> Dictionary:
	var p = campaign.get("pending_operation")
	if p == null:
		return {}
	var pending: Dictionary = p
	if bool(pending.get("committed", false)):
		_fail(ERR_ILLEGAL_STATE, "a committed operation cannot be failed")
		return {}
	Orders.refund(campaign, pending["reserved_cost"])
	var snap: Dictionary = (pending["context"] as Dictionary)["entry_snapshot"]
	campaign["resources"] = (snap["resources"] as Dictionary).duplicate(true)
	if snap.get("unit") != null and (campaign["units"] as Dictionary).has((snap["unit"] as Dictionary)["unit_id"]):
		campaign["units"][(snap["unit"] as Dictionary)["unit_id"]] = (snap["unit"] as Dictionary).duplicate(true)
	if snap.get("tile_control") != null and (campaign["tiles"] as Dictionary).has((pending["context"] as Dictionary)["tile_id"]):
		(campaign["tiles"][(pending["context"] as Dictionary)["tile_id"]] as Dictionary)["control"] = snap["tile_control"]
	campaign["pending_operation"] = null
	Saves.write("auto", campaign, null, "operation_failed")
	return {"cancelled": pending["operation_id"], "code": code, "detail": detail}

## Called on every launch. Decides what to do about a pending operation found in
## the save. NEVER infers completion from a missing scene.
func recover_on_launch(campaign: Dictionary) -> Dictionary:
	var p = campaign.get("pending_operation")
	if p == null:
		return {"action": "none"}
	var pending: Dictionary = p
	match str(pending["state"]):
		Contracts.S_READY, Contracts.S_PREPARING, Contracts.S_LOADING, Contracts.S_MISSION_READY, Contracts.S_FAILED:
			# Nothing was played. Cancel and refund; the player may re-enter.
			return {"action": "cancelled_entry", "detail": fail_operation(campaign, "recovery.entry_incomplete", str(pending["state"]))}
		Contracts.S_PLAYING:
			# A mission was in progress. Resume from its district checkpoint if
			# there is one, else restart it. Either way the operation keeps its
			# id, so its effects stay single-use.
			return {
				"action": "resume_mission" if pending.get("district_checkpoint") != null else "restart_mission",
				"operation_id": pending["operation_id"], "context": pending["context"],
				"checkpoint": pending.get("district_checkpoint"),
			}
		Contracts.S_RESOLVING:
			# A result was written durably but the commit may not have
			# finished. commit_result is idempotent, so running it is safe.
			if (campaign["committed_operations"] as Array).has(pending["operation_id"]):
				return {"action": "already_committed", "applied": acknowledge_return(campaign)}
			var out := commit_result(campaign)
			return {"action": "resumed_commit", "applied": out.get("applied"), "acknowledged": acknowledge_return(campaign)}
		Contracts.S_RETURNING:
			return {"action": "acknowledged", "applied": acknowledge_return(campaign)}
	return {"action": "unknown_state", "state": pending["state"]}
