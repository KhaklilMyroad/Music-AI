extends Node3D
class_name Hostile
## A hostile patrol member. Runs the state machine the district data declares:
## patrol -> investigate -> combat -> lost_contact -> recover.
##
## Perception goes through the shared Detection model, so what the HUD shows and
## what the AI uses are the same numbers. Aim and shots originate from the
## weapon's muzzle on the model, not from the pelvis.

var spec: Dictionary = {}
var id: String = ""
var faction: String = ""
var weapon_profile: Dictionary = {}
var route: Array = []
var leg: int = 0
var pos := Vector2.ZERO
var facing: float = 0.0
var state: String = "patrol"
var awareness: float = 0.0
var alertness: float = 0.3
var health: float = 100.0
var alive: bool = true
var sight_range: float = 58.0
var fov_rad: float = PI * 0.6
var base_acuity: float = 0.85

var _pause_left: float = 0.0
var _state_timer: float = 0.0
var _last_known = null
var _fire_cooldown: float = 0.0
var _gait: float = 0.0
var _reposition_in: float = 0.0
var _cover_target = null
var _builder: Node = null
var _world: Node = null
var _noise: Array = []
var _limbs: Dictionary = {}

func setup(spec_in: Dictionary, index: int, builder: Node, world: Node) -> void:
	spec = spec_in
	id = "%s_%d" % [spec["id"], index]
	faction = str(spec["faction"])
	weapon_profile = world.weapon_by_id(str(spec["weapon"]))
	route = spec["route_m"]
	leg = index % maxi(1, route.size())
	var start: Array = route[leg]
	pos = Vector2(float(start[0]), float(start[1]))
	alertness = float(spec["alertness"])
	_builder = builder
	_world = world
	_build_figure()
	position = Vector3(pos.x, 0.0, pos.y)

func _build_figure() -> void:
	# Blockout figure with jointed limbs: the gait drives the limbs, so feet do
	# not slide. Production characters replace this with a rigged .glb and a
	# retargeted animation set; the joint names are the same.
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.35, 0.37, 0.30)
	var add_box := func(parent: Node3D, size: Vector3, p: Vector3) -> MeshInstance3D:
		var mi := MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = size
		mi.mesh = b
		mi.material_override = mat
		mi.position = p
		parent.add_child(mi)
		return mi
	add_box.call(self, Vector3(0.42, 0.56, 0.24), Vector3(0, 1.18, 0))
	add_box.call(self, Vector3(0.36, 0.20, 0.24), Vector3(0, 0.88, 0))
	var head := add_box.call(self, Vector3(0.23, 0.26, 0.23), Vector3(0, 1.56, 0))
	for entry in [["leg_l", -0.1, 0.86, 0.42], ["leg_r", 0.1, 0.86, 0.42]]:
		var hip := Node3D.new()
		hip.position = Vector3(float(entry[1]), float(entry[2]), 0)
		add_child(hip)
		add_box.call(hip, Vector3(0.13, 0.42, 0.13), Vector3(0, -0.21, 0))
		var knee := Node3D.new()
		knee.position = Vector3(0, -0.42, 0)
		hip.add_child(knee)
		add_box.call(knee, Vector3(0.11, 0.40, 0.11), Vector3(0, -0.20, 0))
		_limbs[str(entry[0])] = {"hip": hip, "knee": knee}
	for entry in [["arm_l", -0.25], ["arm_r", 0.25]]:
		var sh := Node3D.new()
		sh.position = Vector3(float(entry[1]), 1.40, 0)
		add_child(sh)
		add_box.call(sh, Vector3(0.10, 0.30, 0.10), Vector3(0, -0.15, 0))
		var el := Node3D.new()
		el.position = Vector3(0, -0.30, 0)
		sh.add_child(el)
		add_box.call(el, Vector3(0.09, 0.28, 0.09), Vector3(0, -0.14, 0))
		_limbs[str(entry[0])] = {"hip": sh, "knee": el}
	# The weapon is a child of the forearm, so its muzzle is where the shots come from.
	var weapon := Node3D.new()
	weapon.position = Vector3(0, -0.26, -0.12)
	weapon.rotation = Vector3(1.35, 0, 0)
	(_limbs["arm_r"]["knee"] as Node3D).add_child(weapon)
	var cls: String = str(weapon_profile.get("class", "bolt_action_rifle"))
	var mi := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = Vector3(0.05, 0.08, 0.18 if cls == "pistol" else 0.9)
	mi.mesh = b
	mi.material_override = mat
	weapon.add_child(mi)

func observer_record() -> Dictionary:
	return {
		"pos": pos, "facing": facing, "fov_rad": fov_rad, "sight_range": sight_range,
		"alertness": minf(1.0, alertness + (0.0 if state == "patrol" else 0.4)),
		"base_acuity": base_acuity,
	}

func hear(noise_events: Array) -> void:
	for n in noise_events:
		var nd: Dictionary = n
		var heard := Detection.noise_heard(nd, {"pos": pos, "alertness": alertness}, Callable(_builder, "acoustic_occlusion"))
		if not bool(heard["heard"]):
			continue
		_last_known = nd["pos"]
		awareness = minf(1.0, awareness + (0.9 if str(nd.get("source", "")) == "gunshot" else 0.3))
		if state == "patrol":
			_enter("investigate")

func _enter(next: String) -> void:
	state = next
	_state_timer = 0.0
	if next == "combat":
		_reposition_in = _rand((spec["states"]["combat"] as Dictionary)["reposition_s"])

func _rand(range_v: Variant) -> float:
	if range_v is Array:
		var a: Array = range_v
		return randf_range(float(a[0]), float(a[1]))
	return float(range_v)

func _move_toward_point(target: Vector2, speed: float, dt: float) -> bool:
	var d := target - pos
	var dist := d.length()
	if dist < 0.25:
		return true
	var step := minf(dist, speed * dt)
	var next := pos + d.normalized() * step
	# Slide along blockers rather than stopping dead.
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(Vector3(pos.x, 0.9, pos.y), Vector3(next.x, 0.9, next.y))
	if not space.intersect_ray(q).is_empty():
		next = pos + Vector2(-d.y, d.x).normalized() * step * 0.6
	var moved := next.distance_to(pos)
	pos = next
	facing = atan2(d.y, d.x)
	if moved > 0.002:
		_gait += moved
		if _gait > 0.78:
			_gait = 0.0
			var n := Detection.movement_noise({
				"grounded": true, "displacement": moved, "speed": speed, "posture": "stand",
				"surface": _builder.call("surface_at", Vector3(pos.x, 0, pos.y)), "load_kg": 18.0,
			})
			if float(n["loudness"]) > 0.0:
				n["pos"] = pos
				_noise.append(n)
	return false

func update(dt: float, player: Node, world: Node) -> void:
	if not alive:
		return
	_state_timer += dt
	_fire_cooldown = maxf(0.0, _fire_cooldown - dt)

	var det := Detection.detection_rate(observer_record(), {
		"pos": Vector2(player.global_position.x, player.global_position.z),
		"posture": player.posture, "light_exposure": world.player_exposure,
		"cover": world.player_cover, "speed": 1.5,
	}, Callable(_builder, "has_line_of_sight"))
	awareness = Detection.step_awareness(awareness, float(det["rate"]), dt, 0.03 if state == "combat" else 0.22)
	if float(det["rate"]) > 0.0:
		_last_known = Vector2(player.global_position.x, player.global_position.z)
	var band := Detection.awareness_band(awareness)

	match state:
		"patrol":
			if band == "detected":
				_enter("combat")
			elif band == "suspicious":
				_enter("investigate")
			elif _pause_left > 0.0:
				_pause_left -= dt
				facing += dt * 0.5
			else:
				var leg_pos: Array = route[leg]
				if _move_toward_point(Vector2(float(leg_pos[0]), float(leg_pos[1])), 1.25, dt):
					leg = (leg + 1) % route.size()
					_pause_left = _rand(spec["pause_s"])
		"investigate":
			var cfg: Dictionary = spec["states"]["investigate"]
			if band == "detected":
				_enter("combat")
			else:
				var target: Vector2 = _last_known if _last_known != null else Vector2(float((route[leg] as Array)[0]), float((route[leg] as Array)[1]))
				if _move_toward_point(target, 2.6 if bool(cfg["sprint_to_last_known"]) else 1.4, dt):
					facing += dt * 1.6      # sweep the area
				if _state_timer > float(cfg["search_seconds"]):
					_enter("lost_contact")
		"combat":
			var cfg: Dictionary = spec["states"]["combat"]
			if band != "detected" and _state_timer > 3.0:
				_enter("lost_contact")
			else:
				var target: Vector2 = _last_known if _last_known != null else Vector2(player.global_position.x, player.global_position.z)
				var dist := target.distance_to(pos)
				facing = atan2(target.y - pos.y, target.x - pos.x)
				_reposition_in -= dt
				if bool(cfg["use_cover"]) and _reposition_in <= 0.0:
					_reposition_in = _rand(cfg["reposition_s"])
					_cover_target = _find_cover(target)
				if _cover_target != null:
					if _move_toward_point(_cover_target, 2.2, dt):
						_cover_target = null
				elif dist > 22.0:
					_move_toward_point(target, 1.9, dt)
				if _fire_cooldown <= 0.0 and float(det["rate"]) > 0.0 and dist < 70.0:
					_fire_cooldown = 0.55 if float((weapon_profile.get("handling", {}) as Dictionary).get("rpm_cyclic", 0)) > 0.0 else 1.7
					world.hostile_fire(self, player.global_position + Vector3(0, 1.2, 0), dist)
		"lost_contact":
			var cfg: Dictionary = spec["states"]["lost_contact"]
			if band == "detected":
				_enter("combat")
			else:
				facing += dt * 0.9
				if _state_timer > float(cfg["hold_seconds"]):
					_enter("investigate" if cfg["then"] == "sweep" else "recover")
		"recover":
			var cfg: Dictionary = spec["states"]["recover"]
			if band == "detected":
				_enter("combat")
			else:
				var leg_pos: Array = route[leg]
				if _move_toward_point(Vector2(float(leg_pos[0]), float(leg_pos[1])), 1.2, dt) or _state_timer > float(cfg["decay_seconds"]):
					awareness = minf(awareness, 0.2)
					_enter("patrol")

	# Pose: the gait drives the limbs, so feet do not slide and the aiming pose
	# agrees with where the shots come from.
	var walking := state != "patrol" or _pause_left <= 0.0
	var phase: float = world.elapsed * (7.0 if state == "combat" else 4.4)
	var amp: float = (0.5 if state == "combat" else 0.34) if walking else 0.02
	(_limbs["leg_l"]["hip"] as Node3D).rotation.x = sin(phase) * amp
	(_limbs["leg_r"]["hip"] as Node3D).rotation.x = -sin(phase) * amp
	(_limbs["leg_l"]["knee"] as Node3D).rotation.x = maxf(0.0, -sin(phase) * amp * 1.2)
	(_limbs["leg_r"]["knee"] as Node3D).rotation.x = maxf(0.0, sin(phase) * amp * 1.2)
	var aiming := state == "combat"
	(_limbs["arm_r"]["hip"] as Node3D).rotation.x = -1.25 if aiming else -0.3 + sin(phase) * amp * 0.5
	(_limbs["arm_r"]["knee"] as Node3D).rotation.x = -0.45 if aiming else -0.35
	(_limbs["arm_l"]["hip"] as Node3D).rotation.x = -1.1 if aiming else -0.3 - sin(phase) * amp * 0.5
	(_limbs["arm_l"]["knee"] as Node3D).rotation.x = -0.9 if aiming else -0.3
	(_limbs["arm_l"]["hip"] as Node3D).rotation.z = 0.35 if aiming else 0.0
	position = Vector3(pos.x, 0.0, pos.y)
	rotation.y = -facing + PI / 2.0

	for n in _noise:
		for other in world.hostiles:
			if other != self and other.alive:
				other.hear([n])
	_noise.clear()

func _find_cover(threat: Vector2) -> Variant:
	var space := get_world_3d().direct_space_state
	var best = null
	var best_score := -1e9
	for angle in range(0, 360, 30):
		var dir := Vector2(cos(deg_to_rad(float(angle))), sin(deg_to_rad(float(angle))))
		var spot := pos + dir * 6.0
		var q := PhysicsRayQueryParameters3D.create(Vector3(spot.x, 1.2, spot.y), Vector3(threat.x, 1.2, threat.y))
		if space.intersect_ray(q).is_empty():
			continue       # no cover from the threat here
		var d_self := spot.distance_to(pos)
		var d_threat := spot.distance_to(threat)
		if d_threat < 6.0:
			continue
		var score := -d_self * 0.35 + minf(d_threat, 30.0) * 0.1 + 6.0
		if score > best_score:
			best_score = score
			best = spot
	return best

func take_hit(damage: float, world: Node) -> void:
	health -= damage
	if health <= 0.0 and alive:
		alive = false
		rotation.z = PI / 2.1
		position.y = 0.26
		world.on_hostile_down(self)
	else:
		awareness = 1.0
		_last_known = Vector2(world.player.global_position.x, world.player.global_position.z)
		if state != "combat":
			_enter("combat")
