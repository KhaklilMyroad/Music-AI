extends Node3D
class_name Civilian
## A civilian. Their priorities are their own: self-preservation, flight,
## sheltering others. This is not a combat AI with a different hat, and they
## carry no weapon and no helmet.
##
## Narrative state persists independently of whether the model is loaded, so a
## person does not reset because the player crossed a streaming boundary.

var spec: Dictionary = {}
var id: String = ""
var pos := Vector2.ZERO
var facing: float = 0.0
var state: String = "routine"
var fear: float = 0.0
var can_speak: bool = false
var narrative_flags: Array = []

var _builder: Node = null
var _moving: bool = false
var _gait: float = 0.0
var _limbs: Dictionary = {}

func setup(spec_in: Dictionary, builder: Node, _world: Node) -> void:
	spec = spec_in
	id = str(spec["id"])
	var home: Array = spec["home_m"]
	pos = Vector2(float(home[0]), float(home[1]))
	narrative_flags = (spec.get("narrative_flags", []) as Array).duplicate()
	_builder = builder
	_build_figure(0.78 if id == "civ_boy_runner" else 1.0)
	position = Vector3(pos.x, 0.0, pos.y)

func _build_figure(scale_f: float) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.42, 0.35, 0.27)
	var add_box := func(parent: Node3D, size: Vector3, p: Vector3) -> void:
		var mi := MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = size
		mi.mesh = b
		mi.material_override = mat
		mi.position = p
		parent.add_child(mi)
	add_box.call(self, Vector3(0.40, 0.54, 0.22), Vector3(0, 1.18, 0))
	add_box.call(self, Vector3(0.22, 0.25, 0.22), Vector3(0, 1.54, 0))
	for entry in [["leg_l", -0.1], ["leg_r", 0.1]]:
		var hip := Node3D.new()
		hip.position = Vector3(float(entry[1]), 0.86, 0)
		add_child(hip)
		add_box.call(hip, Vector3(0.12, 0.80, 0.12), Vector3(0, -0.40, 0))
		_limbs[str(entry[0])] = hip
	for entry in [["arm_l", -0.24], ["arm_r", 0.24]]:
		var sh := Node3D.new()
		sh.position = Vector3(float(entry[1]), 1.40, 0)
		add_child(sh)
		add_box.call(sh, Vector3(0.09, 0.56, 0.09), Vector3(0, -0.28, 0))
		_limbs[str(entry[0])] = sh
	scale = Vector3.ONE * scale_f

func scheduled_target(hour: float) -> Dictionary:
	var h: float = fposmod(hour, 24.0)
	for s in spec["schedule"]:
		var sd: Dictionary = s
		var from_h: float = float(sd["from_h"])
		var to_h: float = float(sd["to_h"])
		var inside := (h >= from_h and h < to_h) if from_h <= to_h else (h >= from_h or h < to_h)
		if inside:
			return sd
	return spec["schedule"][0]

func update(dt: float, player: Node, world: Node, threat_near: bool) -> void:
	var slot := scheduled_target(world.local_hour)
	var priority: String = str(spec["priority"])
	if threat_near and priority != "shelter_others":
		fear = minf(1.0, fear + dt * 0.6)
		state = "flee" if priority == "flee_from_danger" else "take_cover"
	else:
		fear = maxf(0.0, fear - dt * 0.12)
		if fear < 0.2:
			state = "routine"

	var home: Array = spec["home_m"]
	match state:
		"flee":
			var away := (pos - Vector2(player.global_position.x, player.global_position.z)).normalized()
			_step(pos + away * 8.0, 3.0, dt)
		"take_cover":
			_step(Vector2(float(home[0]), float(home[1])), 2.1, dt)
		_:
			var at: Array = slot["at_m"]
			if _step(Vector2(float(at[0]), float(at[1])), 0.95, dt):
				facing += dt * 0.3

	var phase: float = world.elapsed * (7.5 if state == "flee" else 3.4)
	var amp: float = ((0.55 if state == "flee" else 0.26) if _moving else 0.015)
	(_limbs["leg_l"] as Node3D).rotation.x = sin(phase) * amp
	(_limbs["leg_r"] as Node3D).rotation.x = -sin(phase) * amp
	(_limbs["arm_l"] as Node3D).rotation.x = -sin(phase) * amp * 0.8
	(_limbs["arm_r"] as Node3D).rotation.x = sin(phase) * amp * 0.8
	position = Vector3(pos.x, 0.0, pos.y)
	rotation.y = -facing + PI / 2.0
	can_speak = Vector2(player.global_position.x - pos.x, player.global_position.z - pos.y).length() < 3.2 and state == "routine"

func _step(target: Vector2, speed: float, dt: float) -> bool:
	var d := target - pos
	var dist := d.length()
	_moving = dist > 0.4
	if not _moving:
		return true
	var step := minf(dist, speed * dt)
	var next := pos + d.normalized() * step
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(Vector3(pos.x, 0.9, pos.y), Vector3(next.x, 0.9, next.y))
	if space.intersect_ray(q).is_empty():
		var moved := next.distance_to(pos)
		pos = next
		facing = atan2(d.y, d.x)
		if moved > 0.002:
			_gait += moved
			if _gait > 0.7:
				_gait = 0.0
	return false
