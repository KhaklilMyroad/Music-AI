extends Node3D
class_name MissionScene
## The mission scene: builds the district, drives the player, agents and
## objectives, and produces the MissionResult.
##
## The result is deliberately narrow — an outcome, the objectives completed,
## metrics, and bounded effect requests. It cannot write campaign state; the
## CampaignService validates and applies it.

signal resolved(result: Dictionary)
signal objective_completed(id: String, label: String)
signal player_hit(damage: float, from_dir: float)
signal subtitle(speaker: String, text: String)

const WEATHER := {
	"clear_morning": {"sun": 1.0, "sun_colour": Color(1.0, 0.91, 0.77), "sky": Color(0.56, 0.69, 0.78), "fog": Color(0.66, 0.74, 0.80), "fog_mul": 1.0, "elev": 0.55, "azim": 1.1},
	"overcast": {"sun": 0.45, "sun_colour": Color(0.85, 0.86, 0.88), "sky": Color(0.55, 0.57, 0.60), "fog": Color(0.60, 0.64, 0.67), "fog_mul": 2.2, "elev": 0.9, "azim": 1.6},
	"light_rain": {"sun": 0.30, "sun_colour": Color(0.78, 0.81, 0.83), "sky": Color(0.44, 0.47, 0.49), "fog": Color(0.50, 0.53, 0.56), "fog_mul": 3.4, "elev": 1.0, "azim": 2.0},
	"night_clear": {"sun": 0.08, "sun_colour": Color(0.50, 0.58, 0.72), "sky": Color(0.11, 0.15, 0.20), "fog": Color(0.11, 0.15, 0.19), "fog_mul": 1.6, "elev": 0.35, "azim": 4.2},
}

var context: Dictionary = {}
var chapter: Dictionary = {}
var district_data: Dictionary = {}
var rng: DetRng
var elapsed := 0.0
var mission_seconds := 0.0
var local_hour := 8.2
var paused := false
var finished: Dictionary = {}

var metrics := {"elapsed_mission_seconds": 0, "shots_fired": 0, "times_detected": 0, "alarm_raised": false, "civilians_assisted": 0, "hostiles_neutralised": 0}
var objective_state: Dictionary = {}
var poi_state: Dictionary = {}
var interact_progress := 0.0
var interact_target: Dictionary = {}
var player_exposure := 0.0
var player_cover := 0.0
var max_awareness := 0.0
var cache_revealed := false
var _was_detected := false
var _door_cooldown := 0.0
var _dialogue_cooldown := 0.0

@onready var builder: DistrictBuilder = get_node_or_null(^"District")
@onready var player: PlayerController = get_node_or_null(^"Player")
@onready var touch: TouchControls = get_node_or_null(^"UI/Touch")
@onready var hud: Node = get_node_or_null(^"UI/Hud")

var hostiles: Array = []
var civilians: Array = []
var _sun: DirectionalLight3D
var _env: WorldEnvironment

func setup(ctx: Dictionary) -> Dictionary:
	context = ctx
	chapter = ContentDB.chapter(str(ctx.get("chapter_id", "")))
	district_data = ContentDB.district(str(ctx["district_id"]))
	if district_data.is_empty():
		return {"player": false, "collision": false, "navigation": false, "objectives": false, "ui": false, "audio": false}
	rng = DetRng.new(int(ctx["seed"]))
	var quality := Settings.renderer_options()

	_apply_weather(str(district_data.get("default_weather", "clear_morning")), quality)
	builder.build(district_data, quality)
	player.bind_district(builder)
	player.global_position = (builder.spawn["pos"] as Vector3)
	player.yaw = float(builder.spawn["yaw"])
	player.noise_emitted.connect(_on_player_noise)
	player.shot_fired.connect(_on_player_shot)

	var loadout: Array = ctx.get("loadout", [])
	for id in loadout:
		var p := ContentDB.weapon(str(id))
		if not p.is_empty():
			player.equip(p, -1, 48 if p.get("ammunition") != null else 0)
	if not loadout.is_empty():
		var first := ContentDB.weapon(str(loadout[0]))
		if not first.is_empty():
			player.equip(first)
	player.inventory = {"amm_9x19": 48, "tool_medical_kit": 2}

	for spec in district_data["patrols"]:
		for i in int((spec as Dictionary)["count"]):
			var h := load("res://gameplay/ai/hostile.gd").new()
			h.setup(spec, i, builder, self)
			hostiles.append(h)
			add_child(h)
	for spec in district_data["civilians"]:
		var c := load("res://gameplay/ai/civilian.gd").new()
		c.setup(spec, builder, self)
		civilians.append(c)
		add_child(c)

	_build_objectives()
	AudioDirector.apply_options(Settings.audio_options())

	var ready_map := builder.readiness()
	ready_map["player"] = player != null
	ready_map["ui"] = hud != null
	ready_map["audio"] = AudioDirector != null
	# The cursor is captured for the duration of the mission and released by
	# the pause menu and by losing window focus (InputService handles alt-tab).
	InputService.capture_mouse(true)
	return ready_map

func _apply_weather(name: String, quality: Dictionary) -> void:
	var w: Dictionary = WEATHER.get(name, WEATHER["clear_morning"])
	_env = WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var mat := ProceduralSkyMaterial.new()
	mat.sky_top_color = w["sky"]
	mat.sky_horizon_color = w["fog"]
	mat.ground_bottom_color = Color(0.18, 0.19, 0.16)
	mat.ground_horizon_color = w["fog"]
	sky.sky_material = mat
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 0.75
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 1.05

	# Forward+ features. Each one is a setting, not a constant: the floor GPU
	# has to hold 60 FPS with all of them off, and the art direction has to read
	# correctly either way (see docs/06).
	env.ssao_enabled = bool(quality.get("ssao", true))
	env.ssao_intensity = 1.6
	env.ssil_enabled = bool(quality.get("ssil", true))
	env.ssil_intensity = 0.8
	env.sdfgi_enabled = bool(quality.get("sdfgi", true))
	if env.sdfgi_enabled:
		# Bocage is a corridor world of hedgerows and small rooms, so the
		# cascades are short and dense rather than long and coarse.
		env.sdfgi_cascades = 4
		env.sdfgi_min_cell_size = 0.2
		env.sdfgi_use_occlusion = true
		env.sdfgi_bounce_feedback = 0.5
	env.ssr_enabled = str(quality.get("reflections", "screen_space")) == "screen_space"
	env.ssr_max_steps = 32

	# Distance fog always; volumetric fog only where it is affordable, because
	# it is what makes a dawn lane and a shelled street read as air rather than
	# as a flat grey curtain.
	env.fog_enabled = true
	env.fog_density = 0.004 * float(w["fog_mul"])
	env.fog_light_color = w["fog"]
	env.fog_sky_affect = 0.4
	env.volumetric_fog_enabled = bool(quality.get("volumetric_fog", true))
	if env.volumetric_fog_enabled:
		env.volumetric_fog_density = 0.012 * float(w["fog_mul"])
		env.volumetric_fog_albedo = w["fog"]
		env.volumetric_fog_gi_inject = 0.6
		env.volumetric_fog_length = minf(128.0, float(quality.get("draw_distance", 400.0)) * 0.3)

	var bloom: float = float(quality.get("bloom", 0.15))
	env.glow_enabled = bloom > 0.0
	env.glow_intensity = bloom
	env.glow_bloom = bloom * 0.5
	env.glow_hdr_threshold = 1.1

	if bool(quality.get("depth_of_field", true)):
		# Shallow, and only at close focus: the aim is to let the view model
		# read against the world, not to blur the gameplay.
		env.dof_blur_far_enabled = false
		env.dof_blur_near_enabled = true
		env.dof_blur_near_distance = 0.6
		env.dof_blur_near_transition = 0.5
		env.dof_blur_amount = 0.04

	env.adjustment_enabled = true
	env.adjustment_contrast = 1.03
	env.adjustment_saturation = 0.95

	_env.environment = env
	add_child(_env)

	_sun = DirectionalLight3D.new()
	_sun.light_color = w["sun_colour"]
	_sun.light_energy = 1.5 * float(w["sun"]) + 0.15
	_sun.rotation = Vector3(-float(w["elev"]), float(w["azim"]), 0.0)
	_sun.shadow_enabled = bool(quality.get("shadows", true))
	if _sun.shadow_enabled:
		# Four splits and a long range, because a PC district is large enough
		# that a 90 m shadow distance would pop in the middle of a field.
		_sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
		_sun.directional_shadow_max_distance = minf(300.0, float(quality.get("draw_distance", 400.0)) * 0.75)
		_sun.directional_shadow_split_1 = 0.05
		_sun.directional_shadow_split_2 = 0.15
		_sun.directional_shadow_split_3 = 0.45
		_sun.directional_shadow_blend_splits = true
		_sun.shadow_normal_bias = 0.02
		_sun.shadow_blur = 1.0
	add_child(_sun)
	if player and player.get_camera():
		player.get_camera().far = float(quality.get("draw_distance", 400.0))
		player.get_camera().fov = float(quality.get("fov", 90.0))

func sun_intensity() -> float:
	return float((WEATHER.get(str(district_data.get("default_weather", "clear_morning")), WEATHER["clear_morning"]) as Dictionary)["sun"])

func _build_objectives() -> void:
	for o in chapter.get("objectives", []):
		var od: Dictionary = o
		objective_state[od["id"]] = {
			"spec": od, "done": false, "failed": false, "progress": 0.0,
			"label": Loc.t(str(od["label_key"])), "required": bool(od["required"]),
		}
	for p in district_data["pois"]:
		poi_state[(p as Dictionary)["id"]] = {"complete": false, "observed": 0.0, "held": 0.0, "last_stage": -1}

func complete_objective(id: Variant, how: String) -> void:
	if id == null or not objective_state.has(id):
		return
	var o: Dictionary = objective_state[id]
	if bool(o["done"]):
		return
	o["done"] = true
	o["how"] = how
	objective_completed.emit(str(id), str(o["label"]))

func weapon_by_id(id: String) -> Dictionary:
	return ContentDB.weapon(id)

func _on_player_noise(noise: Dictionary) -> void:
	for h in hostiles:
		if h.alive:
			h.hear([noise])
	if str(noise.get("source", "")) == "gunshot":
		metrics["alarm_raised"] = true

func _on_player_shot(shot: Dictionary) -> void:
	metrics["shots_fired"] = int(metrics["shots_fired"]) + 1
	AudioDirector.play({"id": "shot_%d" % metrics["shots_fired"], "family": "weapon_shot", "dist": 0.0, "essential": true,
		"reverb": AudioDirector.reverb_for_room(str(builder.room_at(player.global_position).get("ambience", district_data["ambience_default"])))}, elapsed)
	# Hit resolution against hostiles, respecting geometry.
	var origin: Vector3 = shot["origin"]
	var dir: Vector3 = (shot["dir"] as Vector3).normalized()
	var spread: float = deg_to_rad(0.3 + float(shot["spread"]) * 1.6)
	dir = (dir + Vector3(rng.float_range(-spread, spread), rng.float_range(-spread, spread), 0.0)).normalized()
	var space := get_world_3d().direct_space_state
	var best: Dictionary = {}
	var best_t := 1e9
	for h in hostiles:
		if not h.alive:
			continue
		var torso := Vector3(h.pos.x, 1.2, h.pos.y)
		var head := Vector3(h.pos.x, 1.56, h.pos.y)
		var rel := torso - origin
		var t: float = rel.dot(dir)
		if t < 0.4 or t > 180.0:
			continue
		var closest := origin + dir * t
		var miss: float = closest.distance_to(torso)
		var head_miss: float = closest.distance_to(head)
		var zone := ""
		if head_miss < 0.16: zone = "head"
		elif miss < 0.2: zone = "torso"
		elif miss < 0.55: zone = "limb"
		if zone == "":
			continue
		var q := PhysicsRayQueryParameters3D.create(origin, torso)
		if not space.intersect_ray(q).is_empty():
			continue
		if t < best_t:
			best_t = t
			best = {"h": h, "zone": zone, "dist": t}
	if not best.is_empty():
		var dmg := WeaponRuntime.damage_at((shot["profile"] as Dictionary), float(best["dist"]), str(best["zone"]))
		(best["h"] as Node).call("take_hit", float(dmg), self)

func on_hostile_down(h: Node) -> void:
	metrics["hostiles_neutralised"] = int(metrics["hostiles_neutralised"]) + 1

func hostile_fire(h: Node, target: Vector3, dist: float) -> void:
	AudioDirector.play({"id": "hostile_fire_%s" % h.get("id"), "family": "weapon_shot", "dist": dist, "essential": true}, elapsed)
	var space := get_world_3d().direct_space_state
	var from := Vector3(h.pos.x, 1.42, h.pos.y)
	var q := PhysicsRayQueryParameters3D.create(from, target)
	var blocked := not space.intersect_ray(q).is_empty()
	if blocked or not rng.chance(maxf(0.05, 0.55 - dist * 0.006)):
		return
	var dmg: float = maxf(4.0, round(float(WeaponRuntime.damage_at(h.weapon_profile, dist, "torso")) * 0.42))
	player.health = maxf(0.0, player.health - dmg)
	player_hit.emit(dmg, atan2(h.pos.y - player.global_position.z, h.pos.x - player.global_position.x))
	# Gamepad rumble, not handheld vibration: there is no phone to buzz, and a
	# player on keyboard and mouse gets nothing from this at all.
	var rumble: float = float(Settings.get_value("rumble"))
	if rumble > 0.0 and Input.get_connected_joypads().size() > 0:
		Input.start_joy_vibration(int(Input.get_connected_joypads()[0]), 0.35 * rumble, 0.7 * rumble, 0.18)
	if player.health <= 0.0:
		resolve("failure", "player_down")

func say(speaker: String, text: String) -> void:
	if not bool(Settings.get_value("subtitles")):
		return
	subtitle.emit(speaker if bool(Settings.get_value("speaker_names")) else "", text)

func _process(dt: float) -> void:
	if not finished.is_empty() or paused or builder == null or player == null:
		return
	elapsed += dt
	mission_seconds += dt
	local_hour += dt / 3600.0 * 6.0     # a mission hour passes in ten minutes
	_door_cooldown = maxf(0.0, _door_cooldown - dt)
	_dialogue_cooldown = maxf(0.0, _dialogue_cooldown - dt)

	var input := InputService.sample()
	player.update(dt, input, {"elapsed": elapsed})

	var pressed: Dictionary = input.get("pressed", {})
	if pressed.has("pause"):
		on_interrupted("pause")
		return
	if pressed.has("quick_save"):
		Campaign.checkpoint_district(checkpoint())
	if pressed.has("weapon_next") or pressed.has("weapon_prev"):
		_cycle_weapon(1 if pressed.has("weapon_next") else -1)

	# Stealth inputs, shared with the AI: the HUD and the patrols read the same
	# numbers, so what the player is told matches what is being decided.
	player_exposure = player.exposure(sun_intensity())
	player_cover = _cover_at(player.global_position)

	interact_target = _nearest_interaction()
	var held := bool(input.get("interact_held", false))
	var tapped := pressed.has("interact")
	if not interact_target.is_empty() and str(interact_target["kind"]) == "poi":
		_interact(interact_target, dt, held or tapped)
	elif tapped:
		_interact(interact_target, dt, true)
	else:
		interact_progress = 0.0

	if pressed.has("reload"):
		player.reload()
	if bool(input.get("fire", false)):
		player.try_fire(rng)

	_update_observation(dt)
	_update_zones(dt)

	var in_combat := 0
	for h in hostiles:
		if h.alive:
			h.update(dt, player, self)
			if h.state == "combat":
				in_combat += 1
	for c in civilians:
		c.update(dt, player, self, in_combat > 0 or int(metrics["shots_fired"]) > 0)

	max_awareness = 0.0
	for h in hostiles:
		if h.alive:
			max_awareness = maxf(max_awareness, h.awareness)
	var band := Detection.awareness_band(max_awareness)
	if band == "detected" and not _was_detected:
		metrics["times_detected"] = int(metrics["times_detected"]) + 1
		_was_detected = true
	elif band != "detected":
		_was_detected = false

	for id in objective_state:
		var o: Dictionary = objective_state[id]
		if (o["spec"] as Dictionary).get("type") != "constraint" or bool(o["failed"]):
			continue
		var constraint: String = str((o["spec"] as Dictionary).get("constraint", ""))
		if constraint == "alarm_never_raised" and bool(metrics["alarm_raised"]):
			o["failed"] = true
		if constraint == "never_detected" and int(metrics["times_detected"]) > 0:
			o["failed"] = true

	metrics["elapsed_mission_seconds"] = int(round(mission_seconds))

func _cover_at(p: Vector3) -> float:
	# Cover is sampled by short rays in the cardinal directions: the number the
	# stealth model uses comes from real geometry, not an authored hint.
	var space := get_world_3d().direct_space_state
	var hits := 0
	for d in [Vector3(1, 0, 0), Vector3(-1, 0, 0), Vector3(0, 0, 1), Vector3(0, 0, -1)]:
		var q := PhysicsRayQueryParameters3D.create(p + Vector3(0, 0.8, 0), p + Vector3(0, 0.8, 0) + d * 1.1)
		if not space.intersect_ray(q).is_empty():
			hits += 1
	return minf(0.9, float(hits) * 0.26)

func _nearest_interaction() -> Dictionary:
	var p := player.global_position
	var best: Dictionary = {}
	var bd := 2.4
	for poi in district_data["pois"]:
		var pd: Dictionary = poi
		if str(pd["kind"]) in ["observation_target", "zone", "landmark"]:
			continue
		if pd.get("hidden_until_intel") != null and not cache_revealed:
			continue
		if bool((poi_state[pd["id"]] as Dictionary)["complete"]):
			continue
		var pos: Array = pd["p"]
		var d: float = Vector2(float(pos[0]) - p.x, float(pos[1]) - p.z).length()
		if d < bd:
			bd = d
			best = {"kind": "poi", "id": pd["id"], "poi": pd, "label_key": pd["label_key"]}
	if best.is_empty():
		var door := builder.nearest_door(p, 1.9)
		if not door.is_empty():
			best = {"kind": "door", "id": door["id"], "door": door, "label_key": "hud.interact"}
	for c in civilians:
		if not c.can_speak:
			continue
		var d: float = Vector2(c.pos.x - p.x, c.pos.y - p.z).length()
		if d < bd:
			bd = d
			best = {"kind": "civilian", "id": c.id, "civ": c, "label_key": c.spec["label_key"]}
	for l in builder.ladders:
		if (l["pos"] as Vector2).distance_to(Vector2(p.x, p.z)) < 1.6 and best.is_empty():
			best = {"kind": "ladder", "id": l["id"], "ladder": l, "label_key": "hud.interact"}
	return best

func _interact(target: Dictionary, dt: float, held: bool) -> void:
	if target.is_empty():
		interact_progress = 0.0
		return
	match str(target["kind"]):
		"door":
			if _door_cooldown <= 0.0:
				builder.open_door(str(target["id"]), float((target["door"] as Dictionary)["target"]) < 0.5)
				_door_cooldown = 0.45
				player.noise_emitted.emit({"loudness": 0.5, "radius_m": 13.0, "source": "door", "pos": Vector2(player.global_position.x, player.global_position.z)})
		"ladder":
			player.global_position.y = float((target["ladder"] as Dictionary)["top"]) + 0.02
		"civilian":
			if _dialogue_cooldown <= 0.0:
				_dialogue_cooldown = 4.0
				var c = target["civ"]
				var line := ""
				match str(c.id):
					"civ_farm_woman":
						if c.narrative_flags.has("knows_cache_location") and not cache_revealed:
							cache_revealed = true
							line = "מתחת לקש, מאחורי האסם. אל תדליק אור." if Loc.locale == "he" else "Under the straw, behind the barn. Do not strike a light."
						else:
							line = "הם עוברים בדרך כל חצי שעה. חכה." if Loc.locale == "he" else "They pass on the lane every half hour. Wait."
					"civ_boy_runner":
						line = "ראיתי תותח בשדה המזרחי." if Loc.locale == "he" else "There is a gun in the east field. I saw it."
					"civ_priest":
						line = "הדלת פתוחה. אל תביא אותם לכאן." if Loc.locale == "he" else "The door is open. Do not bring them here."
					_:
						line = "…"
				say(Loc.t(str(c.spec["label_key"])), line)
				AudioDirector.play({"id": "dialogue_line", "family": "dialogue", "dist": 1.5, "essential": true}, elapsed)
		"poi":
			var pd: Dictionary = target["poi"]
			if not held:
				interact_progress = 0.0
				return
			var tool = pd.get("tool", null)
			if tool != null and (player.equipped.is_empty() or str((player.equipped["profile"] as Dictionary)["id"]) != str(tool)):
				var p := ContentDB.weapon(str(tool))
				if not p.is_empty():
					player.equip(p)
				else:
					say("", Loc.t("hud.no_weapon"))
					return
			var total: float = float(pd.get("stages", 1)) * float(pd.get("stage_seconds", 1.2))
			interact_progress = minf(1.0, interact_progress + dt / total)
			var stage: int = int(interact_progress * float(pd.get("stages", 1)))
			var st: Dictionary = poi_state[pd["id"]]
			if stage != int(st["last_stage"]):
				st["last_stage"] = stage
				if AudioDirector.allow_clip("cut_stage_%d" % stage, elapsed):
					AudioDirector.play({"id": "cut_stage_%d" % stage, "family": "interaction", "dist": 0.6}, elapsed)
					player.noise_emitted.emit({"loudness": 0.35, "radius_m": float(pd.get("noise_radius_m", 8.0)), "source": "tool", "pos": Vector2(player.global_position.x, player.global_position.z)})
			if interact_progress >= 1.0:
				st["complete"] = true
				interact_progress = 0.0
				for item in pd.get("contents", []):
					var it: Dictionary = item
					player.inventory[it["item"]] = int(player.inventory.get(it["item"], 0)) + int(it["count"])
				complete_objective(pd.get("objective"), "interaction")
				AudioDirector.play({"id": "objective_complete", "family": "player_feedback", "dist": 0.0, "essential": true}, elapsed)

func _update_observation(dt: float) -> void:
	for poi in district_data["pois"]:
		var pd: Dictionary = poi
		if str(pd["kind"]) != "observation_target":
			continue
		var obj = pd.get("objective")
		if obj == null or (objective_state.has(obj) and bool((objective_state[obj] as Dictionary)["done"])):
			continue
		var st: Dictionary = poi_state[pd["id"]]
		var pos: Array = pd["p"]
		var target := Vector3(float(pos[0]), 1.4, float(pos[1]))
		var p := player.global_position
		var d: float = Vector2(target.x - p.x, target.z - p.z).length()
		var cam := player.get_camera()
		var aligned := false
		if cam:
			aligned = (-cam.global_transform.basis.z).normalized().dot((target - cam.global_position).normalized()) > 0.985
		var space := get_world_3d().direct_space_state
		var sight := space.intersect_ray(PhysicsRayQueryParameters3D.create(p + Vector3(0, 1.5, 0), target)).is_empty()
		var far := d <= float(pd.get("required_distance_m", 60.0)) and d > 6.0
		var ads: float = 0.0
		if not player.equipped.is_empty():
			ads = (player.equipped["runtime"] as WeaponRuntime).ads
		if aligned and sight and far and ads > 0.6:
			st["observed"] = float(st["observed"]) + dt
			if float(st["observed"]) >= float(pd.get("required_seconds", 3.0)):
				complete_objective(obj, "observation")
		else:
			st["observed"] = maxf(0.0, float(st["observed"]) - dt * 0.6)

func _update_zones(dt: float) -> void:
	for poi in district_data["pois"]:
		var pd: Dictionary = poi
		if str(pd["kind"]) != "zone" or pd.get("objective") == null:
			continue
		var obj: String = str(pd["objective"])
		if not objective_state.has(obj) or bool((objective_state[obj] as Dictionary)["done"]):
			continue
		var pos: Array = pd["p"]
		var p := player.global_position
		var d: float = Vector2(float(pos[0]) - p.x, float(pos[1]) - p.z).length()
		var st: Dictionary = poi_state[pd["id"]]
		if str(pd["interaction"]) == "reach" and d < float(pd.get("radius_m", 5.0)):
			# The extraction zone only counts once the required objectives are met.
			var all_done := true
			for id in objective_state:
				var o: Dictionary = objective_state[id]
				if bool(o["required"]) and id != obj and not bool(o["done"]):
					all_done = false
			if all_done:
				complete_objective(obj, "reached")
				resolve(_derive_outcome(), "extracted")
		elif str(pd["interaction"]) == "hold":
			if d < float(pd.get("radius_m", 8.0)):
				st["held"] = float(st["held"]) + dt
				(objective_state[obj] as Dictionary)["progress"] = minf(1.0, float(st["held"]) / 180.0)
			if float(st["held"]) >= 180.0:
				complete_objective(obj, "held")

func _derive_outcome() -> String:
	var required := 0
	var done := 0
	for id in objective_state:
		var o: Dictionary = objective_state[id]
		if not bool(o["required"]):
			continue
		required += 1
		if bool(o["done"]):
			done += 1
	if done == required:
		return "success"
	return "partial_success" if done > 0 else "failure"

## Build the MissionResult. Bounded: an outcome, objectives, metrics, requests.
func resolve(outcome: String, reason: String) -> Dictionary:
	if not finished.is_empty():
		return finished
	var allowed: Array = context["allowed_outcomes"]
	var final := outcome
	if not allowed.has(final):
		final = "partial_success" if allowed.has("partial_success") else str(allowed[0])
	var completed: Array = []
	var failed: Array = []
	for id in objective_state:
		var o: Dictionary = objective_state[id]
		if bool(o["done"]) and not bool(o["failed"]):
			completed.append(id)
		elif bool(o["failed"]) or (not bool(o["done"]) and bool(o["required"])):
			failed.append(id)
	var eff: Dictionary = (chapter.get("strategic_effects", {}) as Dictionary).get(final, {})
	var supply_penalty := 0
	for te in eff.get("tile_effects", []):
		supply_penalty = maxi(supply_penalty, int((te as Dictionary).get("set_supply_penalty", 0)))
	finished = {
		"result_version": Contracts.RESULT_VERSION,
		"operation_id": context["operation_id"],
		"source_revision": context["source_revision"],
		"outcome": final,
		"completed_objectives": completed,
		"failed_objectives": failed,
		"metrics": metrics.duplicate(),
		"declared_losses": {"personnel": abs(int(eff.get("personnel", 0))) if final == "failure" else 0},
		"declared_resources": {"intelligence": int(eff.get("intelligence", 0)), "materiel": int(eff.get("materiel", 0)), "documents": 0},
		"requests": {
			"remove_attacking_formation": bool(eff.get("removes_attacking_formation", false)),
			"supply_penalty": supply_penalty,
			"network_exposure_delta": float(eff.get("network_exposure", 0.0)),
			"network_access_delta": int(eff.get("network_access", 0)),
			"civilian_health_delta": int(eff.get("civilian_health_delta", 0)),
		},
		"reason": reason,
	}
	resolved.emit(finished)
	return finished

func withdraw() -> Dictionary:
	return resolve("withdrawal", "player_withdrew")

func checkpoint() -> Dictionary:
	var p := player.checkpoint()
	var flags: Dictionary = {}
	for id in objective_state:
		if bool((objective_state[id] as Dictionary)["done"]):
			flags[id] = true
	var doors: Dictionary = {}
	for d in builder.doors:
		doors[d["id"]] = float(d["frac"]) > 0.5
	var ents: Array = []
	for h in hostiles:
		ents.append({"id": h.id, "alive": h.alive, "pos": [h.pos.x, h.pos.y], "state": h.state})
	return Contracts.make_district_checkpoint({
		"district_id": district_data["id"],
		"district_content_version": district_data["content_version"],
		"player": p, "inventory": p["inventory"], "weapon_states": p["weapon_states"],
		"mission_flags": flags, "poi_states": poi_state.duplicate(true),
		"door_states": doors, "local_entities": ents,
		"local_time_hours": local_hour, "weather": district_data["default_weather"],
		"interrupted_action": p["interrupted_action"],
	})

func restore(cp: Dictionary) -> void:
	if cp.is_empty():
		return
	player.restore(cp)
	for id in cp.get("mission_flags", {}):
		if objective_state.has(id):
			(objective_state[id] as Dictionary)["done"] = true
	for id in cp.get("poi_states", {}):
		if poi_state.has(id):
			poi_state[id] = (cp["poi_states"][id] as Dictionary).duplicate()
	for id in cp.get("door_states", {}):
		builder.open_door(str(id), bool(cp["door_states"][id]))
	for e in cp.get("local_entities", []):
		var ed: Dictionary = e
		for h in hostiles:
			if h.id == ed["id"]:
				h.alive = bool(ed["alive"])
				h.pos = Vector2(float((ed["pos"] as Array)[0]), float((ed["pos"] as Array)[1]))
				h.state = str(ed["state"])
	local_hour = float(cp.get("local_time_hours", local_hour))

## Pause safely. On PC the interruptions are alt-tab, the pause key, sleep and
## a crash; the durable-write order in docs/04 is what makes any of them safe.
func on_interrupted(kind: String) -> void:
	paused = true
	InputService.capture_mouse(false)
	AudioDirector.on_interruption("focus_lost" if kind == "focus_lost" else "paused")
	if finished.is_empty():
		Campaign.checkpoint_district(checkpoint())

func resume() -> void:
	paused = false
	InputService.capture_mouse(true)

func _cycle_weapon(dir: int) -> void:
	var loadout: Array = context.get("loadout", [])
	if loadout.size() < 2 or player.equipped.is_empty():
		return
	var current: String = str((player.equipped["profile"] as Dictionary)["id"])
	var i: int = loadout.find(current)
	var next: String = str(loadout[posmod(i + dir, loadout.size())])
	var p := ContentDB.weapon(next)
	if not p.is_empty():
		player.equip(p)

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_WINDOW_FOCUS_OUT and not paused and finished.is_empty():
		on_interrupted("focus_lost")

func hud_state() -> Dictionary:
	var w = null
	if not player.equipped.is_empty():
		var rt: WeaponRuntime = player.equipped["runtime"]
		var prof: Dictionary = player.equipped["profile"]
		w = {
			"label_key": prof["label_key"], "loaded": rt.loaded, "reserve": rt.reserve,
			"is_tool": prof["class"] == "tool", "reloading": not rt.reload_info.is_empty(),
			"reload_progress": (float(rt.reload_info["elapsed"]) / float(rt.reload_info["total"])) if not rt.reload_info.is_empty() else 0.0,
			"ads": rt.ads,
		}
	var objs: Array = []
	for id in objective_state:
		var o: Dictionary = objective_state[id]
		objs.append({"id": id, "label": o["label"], "done": o["done"], "failed": o["failed"], "required": o["required"], "progress": o["progress"]})
	return {
		"health": player.health, "stamina": player.stamina, "weapon": w,
		"stealth": Detection.stealth_readout(player_exposure, player_cover, 0.0, max_awareness),
		"objectives": objs,
		"interact": {"label_key": interact_target.get("label_key", ""), "progress": interact_progress} if not interact_target.is_empty() else null,
		"posture": player.posture, "hour": local_hour,
		"captions": AudioDirector.captions.slice(maxi(0, AudioDirector.captions.size() - 3)),
	}
