extends RefCounted
class_name Detection
## Stealth: visibility and noise (brief §8).
##
## Deliberate design choices, each one a line in the acceptance matrix:
##  * The model reads ONLY gameplay inputs. Render scale, shadow quality and
##    post-processing are not parameters, so a lower quality tier cannot change
##    whether the player is concealed or illuminated.
##  * Light exposure is a calibrated gameplay number in 0..1. It is not a
##    photometric measurement and the HUD never claims it is one.
##  * A footstep requires ground contact AND horizontal displacement, so
##    pushing into a wall or moving through the air is silent by construction.

const POSTURE := {
	"stand":  {"profile": 1.00, "noise_scale": 1.00, "speed": 1.00},
	"crouch": {"profile": 0.58, "noise_scale": 0.45, "speed": 0.55},
	"prone":  {"profile": 0.30, "noise_scale": 0.18, "speed": 0.22},
}

const SURFACE_NOISE := {
	"surf_grass": 0.55, "surf_crop": 0.70, "surf_dirt_track": 0.75, "surf_cobble": 1.00,
	"surf_packed_earth": 0.80, "surf_board_floor": 0.95, "surf_stone_floor": 1.00,
	"surf_hedge_base": 0.85, "surf_gravel": 1.15, "surf_water_shallow": 1.25, "surf_rubble": 1.20,
}

## Equipment adds a floor to movement noise: a loaded pack cannot be silent.
static func carried_noise(load_kg: float) -> float:
	return minf(0.5, load_kg * 0.012)

## Light exposure at a point, 0 (dark) to 1 (fully lit). Inputs are the gameplay
## light list, not the renderer's.
static func light_exposure(point: Vector2, sun_intensity: float, indoors: bool, lights: Array) -> float:
	var e: float = sun_intensity * (0.25 if indoors else 1.0)
	for l in lights:
		var ld: Dictionary = l
		if bool(ld.get("occluded", false)):
			continue
		var d: float = point.distance_to(ld["pos"] as Vector2)
		var radius: float = float(ld["radius"])
		if d >= radius:
			continue
		var falloff: float = 1.0 - d / radius
		e += float(ld["intensity"]) * falloff * falloff
	return clampf(e, 0.0, 1.0)

## Chance-per-second that an observer notices the player, before accumulation.
## Returns the rate and the breakdown, so the HUD indicator and the debug view
## can both explain WHY risk is high rather than showing a bare bar.
##
## observer: {pos: Vector2, facing: float, fov_rad: float, sight_range: float,
##            alertness: float, base_acuity: float}
## player:   {pos: Vector2, posture: String, light_exposure: float,
##            cover: float, speed: float}
## los:      a Callable(from: Vector2, to: Vector2, posture: String) -> bool, or null
static func detection_rate(observer: Dictionary, player: Dictionary, los: Variant) -> Dictionary:
	var delta_v: Vector2 = (player["pos"] as Vector2) - (observer["pos"] as Vector2)
	var dist: float = delta_v.length()
	var post: Dictionary = POSTURE.get(str(player.get("posture", "stand")), POSTURE["stand"])

	if dist > float(observer["sight_range"]):
		return {"rate": 0.0, "blocked_by": "range", "dist": dist, "factors": {}}
	if los is Callable and not bool((los as Callable).call(observer["pos"], player["pos"], player.get("posture", "stand"))):
		return {"rate": 0.0, "blocked_by": "occlusion", "dist": dist, "factors": {}}

	# Attention falls off outside the cone instead of snapping to zero, so
	# peripheral movement still matters.
	var to_player: float = atan2(delta_v.y, delta_v.x)
	var off: float = absf(wrapf(to_player - float(observer["facing"]), -PI, PI))
	var half: float = float(observer["fov_rad"]) / 2.0
	var angle_factor: float = 1.0 if off <= half else maxf(0.0, 1.0 - (off - half) / (PI - half)) * 0.35
	if angle_factor <= 0.0:
		return {"rate": 0.0, "blocked_by": "facing", "dist": dist, "factors": {}}

	var distance_factor: float = maxf(0.05, 1.0 - pow(dist / float(observer["sight_range"]), 1.4))
	var light_factor: float = 0.18 + 0.82 * float(player["light_exposure"])   # never invisible in the open
	var cover_factor: float = 1.0 - minf(0.9, float(player["cover"]))
	var motion_factor: float = 0.45 + 0.55 * minf(1.0, float(player["speed"]) / 3.2)
	var alert: float = 0.6 + 1.4 * float(observer["alertness"])

	var rate: float = float(observer["base_acuity"]) * alert * angle_factor * distance_factor * light_factor * cover_factor * motion_factor * float(post["profile"])
	return {
		"rate": maxf(0.0, rate), "blocked_by": null, "dist": dist,
		"factors": {
			"angle": angle_factor, "distance": distance_factor, "light": light_factor,
			"cover": cover_factor, "motion": motion_factor, "profile": post["profile"], "alert": alert,
		},
	}

## Accumulating awareness. Detection is never instant and never omniscient:
## awareness rises while the player is observable and decays when not.
static func step_awareness(current: float, rate: float, dt: float, decay_per_second: float = 0.22) -> float:
	var next: float = (current + rate * dt) if rate > 0.0 else (current - decay_per_second * dt)
	return clampf(next, 0.0, 1.0)

static func awareness_band(a: float) -> String:
	if a >= 0.75: return "detected"
	if a >= 0.4: return "suspicious"
	return "unaware"

## Noise emitted by a movement step. `grounded` and `displacement` come from the
## character controller, which is why wall-pushing and airborne movement are
## silent by construction rather than by a special case.
static func movement_noise(p: Dictionary) -> Dictionary:
	if p.get("interaction") != null:
		var it: Dictionary = p["interaction"]
		return {"loudness": float(it["loudness"]), "radius_m": float(it["loudness"]) * 26.0, "source": str(it["id"])}
	if not bool(p.get("grounded", false)):
		return {"loudness": 0.0, "radius_m": 0.0, "source": "airborne"}
	if float(p.get("displacement", 0.0)) < 0.06:
		return {"loudness": 0.0, "radius_m": 0.0, "source": "no_displacement"}
	var post: Dictionary = POSTURE.get(str(p.get("posture", "stand")), POSTURE["stand"])
	var surf: float = float(SURFACE_NOISE.get(str(p.get("surface", "")), 0.8))
	var speed_term: float = minf(1.25, 0.35 + float(p.get("speed", 0.0)) / 3.6)
	var loudness: float = clampf(surf * float(post["noise_scale"]) * speed_term + carried_noise(float(p.get("load_kg", 0.0))), 0.0, 1.5)
	return {"loudness": snappedf(loudness, 0.001), "radius_m": snappedf(loudness * 26.0, 0.1), "source": "footstep"}

## Does a noise reach an observer? Walls dampen; a doorway transmits.
## occlusion: a Callable(from: Vector2, to: Vector2) -> float, or null.
static func noise_heard(noise: Dictionary, listener: Dictionary, occlusion: Variant) -> Dictionary:
	if float(noise["loudness"]) <= 0.0:
		return {"heard": false, "attenuated": 0.0}
	var d: float = (listener["pos"] as Vector2).distance_to(noise["pos"] as Vector2)
	if d > float(noise["radius_m"]):
		return {"heard": false, "attenuated": 0.0}
	var occl: float = float((occlusion as Callable).call(noise["pos"], listener["pos"])) if occlusion is Callable else 0.0
	var level: float = float(noise["loudness"]) * (1.0 - d / float(noise["radius_m"])) * (1.0 - occl * 0.75)
	var threshold: float = 0.08 + 0.12 * (1.0 - float(listener.get("alertness", 0.5)))
	return {"heard": level >= threshold, "attenuated": snappedf(level, 0.001), "occlusion": occl}

## Player-facing stealth readout. Colour-independent: bands carry a word and a
## bar length, and the disclaimer says this is a model, not a measurement.
static func stealth_readout(light_exposure_value: float, cover: float, noise: float, awareness: float) -> Dictionary:
	var vis: float = clampf(light_exposure_value * (1.0 - minf(0.9, cover)), 0.0, 1.0)
	var band := func(v: float) -> String:
		if v < 0.25: return "low"
		if v < 0.6: return "medium"
		return "high"
	var nv: float = minf(1.0, noise / 1.2)
	return {
		"visibility": {"value": snappedf(vis, 0.01), "band": band.call(vis), "label_key": "stealth.visibility.%s" % band.call(vis)},
		"noise": {"value": snappedf(nv, 0.01), "band": band.call(nv), "label_key": "stealth.noise.%s" % band.call(nv)},
		"awareness": {"value": snappedf(awareness, 0.01), "band": awareness_band(awareness), "label_key": "stealth.awareness.%s" % awareness_band(awareness)},
		"disclaimer_key": "stealth.model_is_gameplay",
	}
