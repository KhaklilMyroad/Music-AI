extends RefCounted
class_name WeaponRuntime
## Weapon runtime: a state machine over the data-driven profile in
## data/weapons.json. The brief's rules that this enforces:
##  * ammunition changes only at the profile's declared insert point
##  * single-round, partial and empty reloads follow the weapon's own rules
##  * interruption (death, mission resolution, weapon switch) follows the
##    declared cancel_policy and never leaves duplicated rounds
##  * availability is checked against date and faction

const IDLE := "idle"
const FIRING := "firing"
const CYCLING := "cycling"
const RELOADING := "reloading"
const EMPTY := "empty"

var profile: Dictionary
var capacity: int = 0
var chamber_extra: bool = false
var loaded: int = 0
var reserve: int = 0
var state: String = IDLE
var t: float = 0.0
var reload_info: Dictionary = {}
var events: Array = []
var recoil := Vector2.ZERO    # x = yaw, y = pitch
var ads: float = 0.0

static func is_available(p: Dictionary, date: String, faction: String) -> bool:
	var from_s: String = str(p.get("available_from", ""))
	var until = p.get("available_until", null)
	var until_s: String = "" if until == null else str(until)
	if not CampaignDate.in_window(date, from_s, until_s):
		return false
	return (p.get("factions", []) as Array).has(faction)

func _init(p: Dictionary, loaded_in: int = -1, reserve_in: int = 0) -> void:
	profile = p
	var mag = p.get("magazine", null)
	capacity = int((mag as Dictionary).get("capacity", 0)) if mag != null else 0
	chamber_extra = bool((mag as Dictionary).get("chamber_extra", false)) if mag != null else false
	loaded = capacity if loaded_in < 0 else mini(max_loaded(), loaded_in)
	reserve = reserve_in
	state = IDLE if loaded > 0 else EMPTY

func max_loaded() -> int:
	return capacity + (1 if chamber_extra else 0)

func can_fire() -> bool:
	return (state == IDLE or state == FIRING) and loaded > 0

func emit_event(id: String, data: Dictionary = {}) -> void:
	var e := {"id": id}
	e.merge(data)
	events.append(e)

func drain_events() -> Array:
	var e := events
	events = []
	return e

func try_fire(rng_next: float) -> Dictionary:
	if state == RELOADING:
		# Firing during a reload cancels it first, per the profile's policy.
		cancel_reload("fire_input")
	if loaded <= 0:
		state = EMPTY
		emit_event("dry")    # a trigger pull on an empty weapon always clicks
		return {"fired": false, "reason": "empty"}
	if state == CYCLING:
		return {"fired": false, "reason": "cycling"}

	loaded -= 1
	emit_event("fire", {"remaining": loaded})
	var h: Dictionary = profile["handling"]
	var spread: float = 1.0 - (0.6 if float(h.get("rpm_cyclic", 0)) > 0.0 else 0.75) * ads
	recoil.y += float(h["recoil_vertical"]) * (0.85 + 0.3 * rng_next)
	recoil.x += float(h["recoil_horizontal"]) * (rng_next * 2.0 - 1.0)
	state = CYCLING
	if float(h.get("rpm_cyclic", 0)) > 0.0:
		t = 60.0 / float(h["rpm_cyclic"])
	else:
		t = float(h["cycle_seconds"])
		emit_event("bolt_open" if profile["class"] == "bolt_action_rifle" else "slide_cycle")
	if loaded == 0:
		emit_event("last_round")
	return {"fired": true, "spread": spread, "remaining": loaded}

## kind: "auto" picks charger vs single from what the profile supports and how
## empty the weapon is.
func start_reload(kind: String = "auto") -> Dictionary:
	if state == RELOADING:
		return {"started": false, "reason": "already_reloading"}
	if profile.get("reload") == null:
		return {"started": false, "reason": "no_reload"}
	if reserve <= 0:
		return {"started": false, "reason": "no_reserve"}
	if loaded >= max_loaded():
		return {"started": false, "reason": "full"}
	var r: Dictionary = profile["reload"]
	var was_empty := loaded == 0
	if not bool(r.get("supports_partial", false)) and not was_empty and kind != "force":
		return {"started": false, "reason": "partial_not_supported"}

	var chosen := kind
	if kind == "auto":
		chosen = "single" if (bool(r.get("supports_single_round", false)) and loaded > 0) else "charger"
	var total: float = float(r["single_round_seconds"]) if chosen == "single" else float(r["charger_seconds"]) + (float(r["empty_penalty_seconds"]) if was_empty else 0.0)

	reload_info = {"kind": chosen, "total": total, "elapsed": 0.0, "inserted": false, "pre_count": loaded, "was_empty": was_empty}
	state = RELOADING
	var feed: String = str((profile.get("magazine", {}) as Dictionary).get("feed", ""))
	emit_event("single_insert_start" if chosen == "single" else ("mag_release" if feed == "detachable_box" else "bolt_open"))
	return {"started": true, "kind": chosen, "total": total}

## The cancel policy from the profile. Default reverts to the pre-reload count.
func cancel_reload(cause: String) -> Dictionary:
	if state != RELOADING or reload_info.is_empty():
		return {"cancelled": false}
	var policy: String = str((profile["reload"] as Dictionary).get("cancel_policy", "revert_to_pre_reload_count"))
	if not bool(reload_info["inserted"]) and policy == "revert_to_pre_reload_count":
		loaded = int(reload_info["pre_count"])   # nothing entered the weapon yet
	# If ammunition was already inserted it stays inserted and the reserve was
	# already debited: cancelling can neither duplicate nor lose a round.
	reload_info = {}
	state = IDLE if loaded > 0 else EMPTY
	emit_event("reload_cancelled", {"cause": cause, "policy": policy, "loaded": loaded})
	return {"cancelled": true, "cause": cause, "loaded": loaded}

## Called when the mission ends or the player dies mid-action.
func interrupt(cause: String) -> Dictionary:
	var out := {"cause": cause, "cancelled_reload": false}
	if state == RELOADING:
		cancel_reload(cause)
		out["cancelled_reload"] = true
	state = IDLE if loaded > 0 else EMPTY
	t = 0.0
	# Any mechanism sound still in flight is stopped: an interrupted action must
	# not keep producing unrelated mechanism audio.
	emit_event("mechanism_audio_stop", {"cause": cause})
	return out

func step(dt: float, aiming: bool = false) -> Dictionary:
	var h: Dictionary = profile["handling"]
	var ads_time: float = maxf(0.01, float(h.get("ads_time", 0.3)))
	ads = clampf(ads + (dt / ads_time if aiming else -dt / ads_time), 0.0, 1.0)
	var recovery: float = maxf(0.01, float(h.get("recoil_recovery", 0.2)))
	recoil *= maxf(0.0, 1.0 - dt / recovery)

	if state == CYCLING:
		t -= dt
		if t <= 0.0:
			t = 0.0
			if profile["class"] == "bolt_action_rifle":
				emit_event("bolt_close")
			state = IDLE if loaded > 0 else EMPTY
		return {}

	if state == RELOADING and not reload_info.is_empty():
		reload_info["elapsed"] = float(reload_info["elapsed"]) + dt
		var frac: float = float(reload_info["elapsed"]) / float(reload_info["total"])
		var insert_point: float = float((profile["reload"] as Dictionary).get("insert_point_fraction", 0.5))
		# The ammunition count changes exactly at the insert point, never before.
		if not bool(reload_info["inserted"]) and frac >= insert_point:
			reload_info["inserted"] = true
			var feed: String = str((profile.get("magazine", {}) as Dictionary).get("feed", ""))
			if reload_info["kind"] == "single":
				var take: int = mini(mini(1, reserve), max_loaded() - loaded)
				loaded += take
				reserve -= take
				emit_event("single_insert", {"loaded": loaded, "reserve": reserve})
			else:
				var take: int = mini(maxi(0, max_loaded() - loaded), reserve)
				loaded += take
				reserve -= take
				emit_event("mag_insert" if feed == "detachable_box" else "charger_strip", {"loaded": loaded, "reserve": reserve})
		if float(reload_info["elapsed"]) >= float(reload_info["total"]):
			var was_single: bool = reload_info["kind"] == "single"
			reload_info = {}
			state = IDLE if loaded > 0 else EMPTY
			emit_event("reload_complete", {"loaded": loaded, "reserve": reserve})
			# A single-round weapon keeps topping up while reload is held.
			if was_single and loaded < max_loaded() and reserve > 0:
				return {"chain_single": true}
	return {}

## Damage with distance falloff. Returns an integer so results are reproducible.
static func damage_at(p: Dictionary, distance_m: float, hit_zone: String = "torso") -> int:
	var d = p.get("damage", null)
	if d == null:
		return 0
	var dd: Dictionary = d
	var f: float = 1.0
	var start: float = float(dd["falloff_start_m"])
	if distance_m > start:
		var span: float = maxf(1.0, float(dd["falloff_end_m"]) - start)
		var tt: float = minf(1.0, (distance_m - start) / span)
		f = 1.0 - tt * (1.0 - float(dd["falloff_min_factor"]))
	var zone: float = {"head": 2.6, "torso": 1.0, "limb": 0.6}.get(hit_zone, 1.0)
	return int(round(float(dd["base"]) * f * zone))
