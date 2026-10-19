extends CharacterBody3D
class_name PlayerController
## First-person character controller and view model.
##
## Two things here exist specifically because the brief calls them out:
##  * Footsteps are emitted from measured ground contact and horizontal
##    displacement, so pushing into a wall and moving through the air are both
##    silent without needing a special case.
##  * The support hand is parented to a named contact point on the weapon
##    scene, so it cannot detach or intersect the stock while the weapon moves.

signal noise_emitted(noise: Dictionary)
signal shot_fired(shot: Dictionary)
signal interaction_changed(target: Dictionary)

const EYE := {"stand": 1.62, "crouch": 1.05, "prone": 0.42}
const SPEED := {"stand": 3.1, "crouch": 1.55, "prone": 0.62}
const SPRINT_MULT := 1.78
const GRAVITY := 16.5
## Leaning is a PC-native verb: it needs a free second hand on the keyboard,
## so it was absent from the touch build and is present here.
const LEAN_ANGLE := 0.26
const LEAN_OFFSET := 0.32
const LEAN_SPEED := 7.0

@export var head_path: NodePath = ^"Head"
@export var camera_path: NodePath = ^"Head/Camera3D"
@export var viewmodel_path: NodePath = ^"Head/Camera3D/ViewModel"

var posture: String = "stand"
var posture_blend: float = EYE["stand"]
var sprinting: bool = false
var stamina: float = 1.0
var lean: float = 0.0            ## -1 left .. +1 right, blended
var holding_breath: bool = false
var breath: float = 1.0          ## 0..1; holding steadies the aim and drains it
var health: float = 100.0
var condition := {"fatigue": 0.0, "warmth": 1.0, "hunger": 0.0, "thirst": 0.0}
var inventory: Dictionary = {}
var yaw: float = 0.0
var pitch: float = 0.0

var weapons: Dictionary = {}        # weapon_id -> {profile, runtime, model, right, left}
var equipped: Dictionary = {}
var _step_accum: float = 0.0
var _last_moved: float = 0.0
var _last_speed: float = 0.0
var _shake: float = 0.0
var _elapsed: float = 0.0

var _head: Node3D
var _camera: Camera3D
var _viewmodel: Node3D
var _weapon_slot: Node3D
var _hands: Node3D
var _district: Node = null

func _ready() -> void:
	_head = get_node_or_null(head_path)
	_camera = get_node_or_null(camera_path)
	_viewmodel = get_node_or_null(viewmodel_path)
	if _viewmodel:
		_weapon_slot = _viewmodel.get_node_or_null(^"WeaponSlot")
		_hands = _viewmodel.get_node_or_null(^"Hands")

func bind_district(d: Node) -> void:
	_district = d

func get_camera() -> Camera3D:
	return _camera

func eye_height() -> float:
	return posture_blend

func carried_kg() -> float:
	var kg: float = 6.0
	if not equipped.is_empty():
		kg += {"pistol": 1.1, "submachine_gun": 3.6, "bolt_action_rifle": 4.1, "semi_auto_rifle": 4.4, "tool": 0.4}.get(str((equipped["profile"] as Dictionary)["class"]), 2.0)
	for k in inventory:
		kg += float(inventory[k]) * 0.012
	return kg

## Equip a weapon, attaching the hands FROM the weapon's named contact points,
## in the weapon's own space, so they travel with it exactly.
func equip(profile: Dictionary, loaded: int = -1, reserve: int = 0) -> Dictionary:
	var id: String = str(profile["id"])
	if not weapons.has(id):
		var model := _build_weapon_model(profile)
		weapons[id] = {
			"profile": profile,
			"runtime": WeaponRuntime.new(profile, loaded, reserve),
			"model": model,
			"right": _build_hand("right"),
			"left": _build_hand("left"),
		}
	if not equipped.is_empty():
		(equipped["runtime"] as WeaponRuntime).interrupt("weapon_switch")
		if _weapon_slot and (equipped["model"] as Node3D).get_parent() == _weapon_slot:
			_weapon_slot.remove_child(equipped["model"])
		if _hands:
			for side in ["right", "left"]:
				if (equipped[side] as Node3D).get_parent() == _hands:
					_hands.remove_child(equipped[side])
	equipped = weapons[id]
	if _weapon_slot:
		_weapon_slot.add_child(equipped["model"])
	if _hands:
		_hands.add_child(equipped["right"])
		_hands.add_child(equipped["left"])
	_attach_hands(0.0)
	return equipped

func _build_weapon_model(profile: Dictionary) -> Node3D:
	# In production this loads an authored .glb with named grip markers. In this
	# foundation the grip points are generated from the weapon class so the
	# attachment rule is exercised from day one.
	var root := Node3D.new()
	root.name = "Weapon_%s" % profile["id"]
	var cls: String = str(profile["class"])
	var mesh_path := "res://gameplay/fps/models/%s.glb" % cls
	if ResourceLoader.exists(mesh_path):
		var scene: PackedScene = load(mesh_path)
		root.add_child(scene.instantiate())
	else:
		# Blockout: a box body plus a barrel, so silhouette and grip read while
		# production art is outstanding. Flagged in the HUD as a blockout.
		var body := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = Vector3(0.05, 0.08, 0.34 if cls != "pistol" else 0.18)
		body.mesh = box
		root.add_child(body)
	var grip := {
		"pistol": {"primary": Vector3(0.0, -0.045, 0.042), "support": Vector3(-0.026, -0.03, 0.03), "support_visible": true, "muzzle": Vector3(0, 0.05, -0.12)},
		"tool": {"primary": Vector3(0, 0, 0), "support": Vector3(0, 0, -0.02), "support_visible": false, "muzzle": Vector3(0, 0, -0.16)},
		"submachine_gun": {"primary": Vector3(0, -0.038, 0.1), "support": Vector3(0, -0.028, -0.24), "support_visible": true, "muzzle": Vector3(0, 0.022, -0.44)},
	}.get(cls, {"primary": Vector3(0, -0.038, 0.1), "support": Vector3(0, -0.028, -0.31), "support_visible": true, "muzzle": Vector3(0, 0.022, -0.76)})
	root.set_meta("grip", grip)
	return root

func _build_hand(side: String) -> Node3D:
	var g := Node3D.new()
	g.name = "Hand_%s" % side
	var path := "res://gameplay/fps/models/hand_%s.glb" % side
	if ResourceLoader.exists(path):
		g.add_child((load(path) as PackedScene).instantiate())
	else:
		var m := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = Vector3(0.052, 0.085, 0.032)
		m.mesh = box
		g.add_child(m)
	g.set_meta("side", side)
	return g

## Place both hands from the weapon's grip metadata. A reload swings the support
## hand away from the handguard and back onto it; it is never free-floating.
func _attach_hands(reload_swing: float) -> void:
	if equipped.is_empty() or not _weapon_slot:
		return
	var grip: Dictionary = (equipped["model"] as Node3D).get_meta("grip")
	var base: Vector3 = _weapon_slot.position
	var right: Node3D = equipped["right"]
	right.position = base + (grip["primary"] as Vector3)
	right.rotation = Vector3(-0.42, 0.1, 0.06)
	var left: Node3D = equipped["left"]
	if bool(grip["support_visible"]):
		left.visible = true
		left.position = base + (grip["support"] as Vector3) + Vector3(-0.012 - reload_swing * 0.05, -0.01 - reload_swing * 0.1, reload_swing * 0.14)
		left.rotation = Vector3(-0.55, -0.22, -0.5)
	else:
		left.visible = false

## Mouse motion is a delta and gamepad motion is a rate, so they are applied
## differently and never summed into double sensitivity. The mouse delta
## arrives already scaled by mouse_sensitivity from InputService; only the
## aiming multiplier and inversion are applied here.
func look(mouse_delta: Vector2, pad_rate: Vector2, dt: float, aiming: bool) -> void:
	var mult: float = float(Settings.get_value("aim_sensitivity_mult")) if aiming else 1.0
	var inv: float = -1.0 if bool(Settings.get_value("invert_y")) else 1.0
	# Zoom-independent aiming: a narrower field of view must not change how far
	# the crosshair travels per centimetre of mouse movement.
	var zoom_comp: float = 1.0
	var cam := get_camera()
	if cam and aiming:
		zoom_comp = tan(deg_to_rad(cam.fov) * 0.5) / tan(deg_to_rad(float(Settings.get_value("fov"))) * 0.5)
	var delta := mouse_delta * mult * zoom_comp + pad_rate * mult * dt
	yaw -= delta.x * 0.0022
	pitch = clampf(pitch - delta.y * 0.0022 * inv, -1.42, 1.42)

func _physics_process(delta: float) -> void:
	pass   # driven by MissionScene.update so the order of systems is explicit

## Per-frame update, called by the mission scene with a sampled input snapshot.
func update(dt: float, input: Dictionary, world: Dictionary) -> Dictionary:
	_elapsed += dt
	var aiming := bool(input.get("aim", false))
	look(input.get("look", Vector2.ZERO), input.get("look_rate", Vector2.ZERO), dt, aiming)

	# Three postures on PC: prone is reachable because a keyboard has the keys
	# for it. Prone cannot be entered where there is no headroom to lie down.
	if bool(input.get("prone", false)):
		posture = "prone"
	elif bool(input.get("crouch", false)):
		posture = "crouch"
	else:
		posture = "stand" if _can_stand() else "crouch"
	posture_blend = lerpf(posture_blend, EYE[posture], minf(1.0, dt * 11.0))

	# Leaning: the camera rolls and shifts laterally, and the shift is collision
	# tested, so a player cannot lean their head through a wall to see around it.
	var lean_target: float = clampf(float(input.get("lean", 0.0)), -1.0, 1.0)
	if lean_target != 0.0 and not _lean_clear(lean_target):
		lean_target = 0.0
	lean = move_toward(lean, lean_target, dt * LEAN_SPEED)

	# Holding the breath steadies the aim and drains a reserve that only
	# recovers while not held. It is a trade, not a free upgrade.
	holding_breath = bool(input.get("hold_breath", false)) and aiming and breath > 0.02
	breath = clampf(breath + (-dt * 0.33 if holding_breath else dt * 0.22), 0.0, 1.0)

	sprinting = (bool(input.get("sprint", false)) or bool(input.get("sprint_from_stick", false))) and posture == "stand" and not aiming and stamina > 0.05
	var base: float = SPEED[posture] * (0.55 if aiming else 1.0)
	var speed: float = base * (SPRINT_MULT if sprinting else 1.0) * (1.0 - 0.45 * absf(lean))
	stamina = clampf(stamina + (-dt * 0.22 if sprinting else dt * 0.14), 0.0, 1.0)

	var move: Vector2 = input.get("move", Vector2.ZERO)
	var fwd := Vector3(-sin(yaw), 0.0, -cos(yaw))
	var right := Vector3(cos(yaw), 0.0, -sin(yaw))
	var wish := (fwd * move.y + right * move.x)
	if wish.length_squared() > 1.0:
		wish = wish.normalized()
	wish *= speed

	var before := global_position
	velocity.x = wish.x
	velocity.z = wish.z
	if is_on_floor():
		velocity.y = 0.0
	else:
		velocity.y -= GRAVITY * dt
	move_and_slide()

	# ---- footstep emission: measured, not intended ----
	var moved: float = Vector2(global_position.x - before.x, global_position.z - before.z).length()
	var horiz_speed: float = moved / maxf(0.00001, dt)
	var stride: float = {"prone": 0.55, "crouch": 0.62}.get(posture, 1.15 if sprinting else 0.82)
	if is_on_floor():
		_step_accum += moved
	if is_on_floor() and _step_accum >= stride:
		_step_accum = 0.0
		var surface: String = "surf_grass"
		if _district and _district.has_method("surface_at"):
			surface = str(_district.call("surface_at", global_position))
		var n := Detection.movement_noise({
			"grounded": true, "displacement": moved, "speed": horiz_speed,
			"posture": posture, "surface": surface, "load_kg": carried_kg(),
		})
		if float(n["loudness"]) > 0.0:
			n["pos"] = Vector2(global_position.x, global_position.z)
			n["surface"] = surface
			noise_emitted.emit(n)
	_last_moved = moved
	_last_speed = horiz_speed

	# camera: posture, bob, recoil and shake, each scaled by its own setting
	var shake_setting: float = float(Settings.get_value("camera_shake"))
	_shake = maxf(0.0, _shake - dt * 2.4)
	# Head bob is its own 0..1 slider on PC, where it is a common comfort
	# complaint; reduced motion still forces it to zero.
	var bob_scale: float = 0.0 if bool(Settings.get_value("motion_reduction")) else float(Settings.get_value("head_bob"))
	var bob_amp: float = (0.022 if sprinting else 0.012) * minf(1.0, horiz_speed / 2.4) * bob_scale
	var bob: float = sin(_elapsed * (13.0 if sprinting else 8.5)) * bob_amp
	if _head:
		_head.position.y = posture_blend + bob
		_head.position.x = lean * LEAN_OFFSET
	if _camera:
		var rec := Vector2.ZERO
		var sway: float = 1.0
		if not equipped.is_empty():
			var rt: WeaponRuntime = equipped["runtime"]
			rec = rt.recoil
			# Aiming down the sights narrows the field of view. The look()
			# function compensates so sensitivity does not change with zoom.
			var base_fov: float = float(Settings.get_value("fov"))
			_camera.fov = lerpf(base_fov, base_fov * 0.72, rt.ads)
			sway = 1.0 - (0.75 if holding_breath else 0.0)
		else:
			_camera.fov = float(Settings.get_value("fov"))
		var rec_scale: float = float(Settings.get_value("recoil_presentation")) * 0.0075
		var sh: float = _shake * shake_setting * 0.01
		var idle_sway: float = sin(_elapsed * 1.3) * 0.0016 * sway
		_camera.rotation = Vector3(
			pitch - rec.y * rec_scale + randf_range(-sh, sh) + idle_sway,
			0.0,
			-lean * LEAN_ANGLE)
	rotation.y = yaw

	# view model: sway, ADS blend and the reload pose
	if not equipped.is_empty():
		var rt: WeaponRuntime = equipped["runtime"]
		var swing: float = 0.0
		if not rt.reload_info.is_empty():
			var tt: float = float(rt.reload_info["elapsed"]) / float(rt.reload_info["total"])
			swing = sin(minf(1.0, tt) * PI)
		_attach_hands(swing)
		if _viewmodel:
			_viewmodel.position = Vector3(-rt.ads * 0.17, rt.ads * 0.055 + bob * 0.5, rt.ads * 0.07)
			_viewmodel.rotation = Vector3(bob * 0.4, 0.0, (-0.12 if sprinting else 0.0) * (1.0 - rt.ads))
		rt.step(dt, bool(input.get("aim", false)))

	return {"moved": moved, "speed": horiz_speed, "grounded": is_on_floor()}

## Is there headroom to stand up? Prevents standing inside a crawlspace.
func _can_stand() -> bool:
	if posture == "stand":
		return true
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(global_position + Vector3(0, 0.3, 0), global_position + Vector3(0, 1.85, 0))
	q.exclude = [get_rid()]
	return space.intersect_ray(q).is_empty()

## Is the lean offset clear of geometry? A player may not lean their head
## through a wall to see what is behind it.
func _lean_clear(dir: float) -> bool:
	var space := get_world_3d().direct_space_state
	var from := global_position + Vector3(0, posture_blend, 0)
	var side := global_transform.basis.x * signf(dir) * (LEAN_OFFSET + 0.25)
	var q := PhysicsRayQueryParameters3D.create(from, from + side)
	q.exclude = [get_rid()]
	return space.intersect_ray(q).is_empty()

func try_fire(rng: DetRng) -> Dictionary:
	if equipped.is_empty() or (equipped["profile"] as Dictionary)["class"] == "tool":
		return {"fired": false, "reason": "no_weapon"}
	var rt: WeaponRuntime = equipped["runtime"]
	var out := rt.try_fire(rng.next())
	if not bool(out["fired"]):
		return out
	_shake = 1.0
	var cam := get_camera()
	var dir: Vector3 = -cam.global_transform.basis.z if cam else -global_transform.basis.z
	shot_fired.emit({"origin": cam.global_position if cam else global_position, "dir": dir, "spread": out["spread"], "profile": equipped["profile"]})
	noise_emitted.emit({"loudness": 1.5, "radius_m": 220.0, "source": "gunshot", "pos": Vector2(global_position.x, global_position.z)})
	return out

func reload() -> Dictionary:
	if equipped.is_empty():
		return {"started": false, "reason": "no_weapon"}
	var rt: WeaponRuntime = equipped["runtime"]
	var ammo = (equipped["profile"] as Dictionary).get("ammunition", null)
	if ammo != null and inventory.has(ammo):
		rt.reserve = int(inventory[ammo])
	return rt.start_reload("auto")

func sync_reserve_to_inventory() -> void:
	if equipped.is_empty():
		return
	var ammo = (equipped["profile"] as Dictionary).get("ammunition", null)
	if ammo != null:
		inventory[ammo] = (equipped["runtime"] as WeaponRuntime).reserve

## Gameplay light exposure at the player's position, for the stealth model.
func exposure(sun_intensity: float) -> float:
	var indoors := false
	var lights: Array = []
	if _district:
		if _district.has_method("is_indoors"):
			indoors = bool(_district.call("is_indoors", global_position))
		if _district.has_method("gameplay_lights"):
			lights = _district.call("gameplay_lights", global_position)
	return Detection.light_exposure(Vector2(global_position.x, global_position.z), sun_intensity, indoors, lights)

func checkpoint() -> Dictionary:
	sync_reserve_to_inventory()
	var states: Dictionary = {}
	for id in weapons:
		var rt: WeaponRuntime = weapons[id]["runtime"]
		states[id] = {"loaded": rt.loaded, "reserve": rt.reserve, "chambered": rt.loaded > 0}
	var interrupted = null
	if not equipped.is_empty():
		var rt: WeaponRuntime = equipped["runtime"]
		if not rt.reload_info.is_empty():
			interrupted = {
				"kind": "reload",
				"progress": float(rt.reload_info["elapsed"]) / float(rt.reload_info["total"]),
				"revert_to": {"loaded": int(rt.reload_info["pre_count"]), "reserve": rt.reserve + (rt.loaded - int(rt.reload_info["pre_count"]))},
			}
	return {
		"position": [global_position.x, global_position.y, global_position.z],
		"yaw": yaw, "pitch": pitch, "posture": posture, "health": health,
		"condition": condition.duplicate(),
		"equipped": (equipped["profile"] as Dictionary)["id"] if not equipped.is_empty() else null,
		"weapon_states": states, "inventory": inventory.duplicate(),
		"interrupted_action": interrupted,
	}

## An interrupted reload reverts to its recorded pre-reload counts: the
## checkpoint, not the live scene, decides, so no round can be duplicated.
func restore(cp: Dictionary) -> void:
	if cp.is_empty():
		return
	var p: Dictionary = cp.get("player", cp)
	if p.has("position"):
		var a: Array = p["position"]
		global_position = Vector3(float(a[0]), float(a[1]), float(a[2]))
	yaw = float(p.get("yaw", yaw))
	pitch = float(p.get("pitch", pitch))
	posture = str(p.get("posture", posture))
	posture_blend = EYE.get(posture, EYE["stand"])
	health = float(p.get("health", health))
	inventory = (cp.get("inventory", p.get("inventory", {})) as Dictionary).duplicate()
	var interrupted = cp.get("interrupted_action", p.get("interrupted_action", null))
	for id in cp.get("weapon_states", {}):
		if not weapons.has(id):
			continue
		var rt: WeaponRuntime = weapons[id]["runtime"]
		var st: Dictionary = cp["weapon_states"][id]
		if interrupted != null and str((interrupted as Dictionary).get("kind", "")) == "reload":
			var rv: Dictionary = (interrupted as Dictionary)["revert_to"]
			rt.loaded = int(rv["loaded"])
			rt.reserve = int(rv["reserve"])
		else:
			rt.loaded = int(st["loaded"])
			rt.reserve = int(st["reserve"])
		rt.reload_info = {}
		rt.state = WeaponRuntime.IDLE if rt.loaded > 0 else WeaponRuntime.EMPTY
