extends Node
## Audio routing rules (brief §14). This node holds the decisions that must be
## testable without a listening test: the voice budget, source priority, reverb
## and obstruction per source, distance behaviour and the mono fallback.
##
## It does NOT replace human listening. Audio acceptance in the matrix requires
## a person on a phone speaker, ordinary headphones and Bluetooth.

signal caption(id: String, direction: String, distance: float)

const BUSES := ["Master", "Effects", "Ambience", "Dialogue", "Music"]

## Priority classes. A prop must never cut off a reload cue or a spoken line.
const PRIORITY := {
	"dialogue": 100, "weapon_mechanism": 90, "weapon_shot": 85,
	"player_feedback": 80, "threat": 70, "interaction": 60,
	"character_foley": 50, "ambience_zone": 30, "prop": 10,
}

const REVERB := {
	"rv_open": {"decay": 0.6, "wet": 0.08, "hf_damp": 0.2},
	"rv_open_hedged": {"decay": 0.9, "wet": 0.14, "hf_damp": 0.35},
	"rv_dense_foliage": {"decay": 0.5, "wet": 0.10, "hf_damp": 0.6},
	"rv_room_small": {"decay": 0.7, "wet": 0.22, "hf_damp": 0.3},
	"rv_room_stone": {"decay": 1.8, "wet": 0.34, "hf_damp": 0.15},
	"rv_barn": {"decay": 1.4, "wet": 0.28, "hf_damp": 0.25},
	"rv_chapel": {"decay": 3.2, "wet": 0.42, "hf_damp": 0.1},
	"rv_bunker": {"decay": 1.1, "wet": 0.38, "hf_damp": 0.45},
	"rv_attic": {"decay": 0.55, "wet": 0.18, "hf_damp": 0.5},
}

## Distance behaviour per family. A rifle shot has a tail; a footstep does not.
const DISTANCE_MODEL := {
	"weapon_shot": {"max_m": 900.0, "rolloff": 1.1, "tail_from_m": 60.0, "distant_layer": true},
	"weapon_mechanism": {"max_m": 22.0, "rolloff": 1.6, "tail_from_m": -1.0, "distant_layer": false},
	"explosion": {"max_m": 1600.0, "rolloff": 1.0, "tail_from_m": 80.0, "distant_layer": true},
	"character_foley": {"max_m": 28.0, "rolloff": 1.8, "tail_from_m": -1.0, "distant_layer": false},
	"dialogue": {"max_m": 35.0, "rolloff": 1.3, "tail_from_m": -1.0, "distant_layer": false},
	"prop": {"max_m": 18.0, "rolloff": 2.0, "tail_from_m": -1.0, "distant_layer": false},
	"ambience_zone": {"max_m": 0.0, "rolloff": 0.0, "tail_from_m": -1.0, "distant_layer": false},
}

const ROOM_REVERB := {
	"amb_interior_kitchen": "rv_room_small", "amb_interior_quiet": "rv_room_small",
	"amb_interior_attic": "rv_attic", "amb_interior_barn": "rv_barn",
	"amb_interior_chapel": "rv_chapel", "amb_bocage_field": "rv_open",
	"amb_bocage_lane": "rv_open_hedged", "amb_bocage_hedge": "rv_dense_foliage",
	"amb_bunker": "rv_bunker",
}

var max_voices: int = 24
var mono: bool = false
var sound_captions: bool = false
var bus_volumes: Dictionary = {"Master": 1.0, "Effects": 1.0, "Ambience": 1.0, "Dialogue": 1.0, "Music": 1.0}
var active: Array = []
var rejected: Array = []
var captions: Array = []

var _last_played: Dictionary = {}

func _ready() -> void:
	apply_options(Settings.audio_options())
	Settings.changed.connect(func(id, _v):
		if id == "mono" or id == "sound_captions" or str(id).begins_with("vol_") or id == "quality":
			apply_options(Settings.audio_options()))

func apply_options(o: Dictionary) -> void:
	max_voices = int(o.get("max_voices", 24))
	mono = bool(o.get("mono", false))
	sound_captions = bool(o.get("sound_captions", false))
	bus_volumes = o.get("bus_volumes", bus_volumes)
	for i in BUSES.size():
		var idx := AudioServer.get_bus_index(BUSES[i])
		if idx >= 0:
			AudioServer.set_bus_volume_db(idx, linear_to_db(maxf(0.0001, float(bus_volumes.get(BUSES[i], 1.0)))))
			AudioServer.set_bus_mute(idx, float(bus_volumes.get(BUSES[i], 1.0)) <= 0.0)

static func reverb_for_room(ambience: String) -> String:
	return ROOM_REVERB.get(ambience, "rv_open")

func gain_for(family: String, bus: String, dist: float, occlusion: float = 0.0) -> float:
	var m: Dictionary = DISTANCE_MODEL.get(family, DISTANCE_MODEL["prop"])
	var g: float = 1.0
	if float(m["max_m"]) > 0.0:
		if dist >= float(m["max_m"]):
			g = 0.0
		else:
			g = pow(1.0 - dist / float(m["max_m"]), float(m["rolloff"]))
	g *= 1.0 - minf(0.92, occlusion * 0.85)
	g *= float(bus_volumes.get(bus, 1.0)) * float(bus_volumes.get("Master", 1.0))
	return clampf(g, 0.0, 1.0)

## Request a voice. Within budget it plays; over budget it only plays if it can
## displace a strictly lower-priority voice. The result says what happened and
## why, so a QA log can show which cue lost and to what.
func play(req: Dictionary, now: float = 0.0) -> Dictionary:
	var family: String = str(req.get("family", "prop"))
	var priority: int = int(req.get("priority", PRIORITY.get(family, PRIORITY["prop"])))
	var bus: String = str(req.get("bus", "Dialogue" if family == "dialogue" else ("Ambience" if family == "ambience_zone" else "Effects")))
	var dist: float = float(req.get("dist", 0.0))
	var gain := gain_for(family, bus, dist, float(req.get("occlusion", 0.0)))
	if gain <= 0.001 and family != "ambience_zone":
		rejected.append({"id": req.get("id"), "reason": "inaudible"})
		return {"played": false, "reason": "inaudible"}

	if active.size() >= max_voices:
		var sorted := active.duplicate()
		sorted.sort_custom(func(a, b):
			if int(a["priority"]) != int(b["priority"]): return int(a["priority"]) < int(b["priority"])
			if float(a["gain"]) != float(b["gain"]): return float(a["gain"]) < float(b["gain"])
			return float(a["started_at"]) < float(b["started_at"]))
		var victim: Dictionary = sorted[0]
		if int(victim["priority"]) >= priority:
			rejected.append({"id": req.get("id"), "reason": "voice_budget", "blocked_by": victim.get("id")})
			return {"played": false, "reason": "voice_budget", "blocked_by": victim.get("id")}
		active.erase(victim)
		rejected.append({"id": victim.get("id"), "reason": "evicted_by", "by": req.get("id")})

	var m: Dictionary = DISTANCE_MODEL.get(family, DISTANCE_MODEL["prop"])
	var tail: float = float(m["tail_from_m"])
	var voice := {
		"id": req.get("id"), "family": family, "priority": priority, "bus": bus,
		"gain": gain, "started_at": now, "dist": dist,
		"reverb": REVERB.get(str(req.get("reverb", "rv_open")), REVERB["rv_open"]),
		"pan": 0.0 if mono else float(req.get("pan", 0.0)),
		"distant_layer": bool(m["distant_layer"]) and tail >= 0.0 and dist >= tail,
	}
	active.append(voice)

	# In mono, direction is gone, so an essential cue is captioned rather than lost.
	if bool(req.get("essential", false)) and (mono or sound_captions):
		var dir := direction_word(float(req.get("pan", 0.0)))
		captions.append({"id": req.get("id"), "direction": dir, "dist": dist, "forced_by": "mono" if mono else ""})
		caption.emit(str(req.get("id")), dir, dist)
	return {"played": true, "voice": voice}

func stop(id: String) -> void:
	active = active.filter(func(v): return str(v["id"]) != id)

## Interrupt handling: a phone call or focus loss must leave no orphan voices.
func on_interruption(kind: String) -> Dictionary:
	var stopped: Array = []
	for v in active:
		stopped.append(v["id"])
	active.clear()
	return {
		"kind": kind, "stopped": stopped,
		"resume_policy": "resume_ambience_and_music_only" if kind == "phone_call" else "resume_all_positional",
	}

## Repetition guard: the same clip must not fire twice inside its window.
func allow_clip(clip_id: String, now: float, window: float = 0.18) -> bool:
	var last: float = float(_last_played.get(clip_id, -999.0))
	if now - last < window:
		return false
	_last_played[clip_id] = now
	return true

static func direction_word(pan: float) -> String:
	if pan <= -0.6: return "left"
	if pan >= 0.6: return "right"
	if pan <= -0.2: return "front_left"
	if pan >= 0.2: return "front_right"
	return "ahead"

## Measurable peak so a dense-mix test can fail on clipping before a listening pass.
func mix_peak() -> float:
	var s: float = 0.0
	for v in active:
		s += float(v["gain"]) * float(v["gain"])
	return sqrt(s)
