extends Control
class_name TouchControls
## Touch controls (brief §10). Designed for simultaneous movement and camera
## control with two thumbs, inside the safe area, with every action
## customisable.
##
## Multi-touch is tracked by index, so the look drag never steals the move
## stick's finger and vice versa — the single most common failure in a ported
## desktop control scheme.
##
## Nothing here is the only way to reach an action: every staged interaction
## also has a tap route, and a long press is never the sole discovery path.

signal action_pressed(action: String)
signal action_released(action: String)

const ACTIONS := ["fire", "aim", "reload", "interact", "crouch", "sprint", "traverse", "journal", "pause"]

## Touch is the optional input path on PC: a touchscreen laptop, or a handheld.
## The PC settings menu deliberately does not carry stick size, stick mode or a
## left-handed layout, because a touch-layout group in a keyboard-and-mouse
## game's options is clutter for a path almost nobody will use. These are the
## defaults that layout used to read from settings. If a handheld-focused build
## is ever a target (see the Steam Deck row in docs/10), they become settings
## again.
const LAYOUT := {"left_handed": false, "stick_size": 1.0, "stick_mode": "floating"}
const STICK_RADIUS := 62.0
const MIN_TOUCH := 48.0      # Android accessibility guidance, brief T4

var move := Vector2.ZERO
var look_delta := Vector2.ZERO
var held: Dictionary = {}
var toggled: Dictionary = {}
var pressed_once: Dictionary = {}

var _move_index: int = -1
var _look_index: int = -1
var _move_origin := Vector2.ZERO
var _look_last := Vector2.ZERO
var _gyro_delta := Vector2.ZERO
var _gyro_enabled := false
var _gyro_last := Vector3.ZERO
var _buttons: Dictionary = {}

@onready var _stick: Control = get_node_or_null(^"Stick")
@onready var _knob: Control = get_node_or_null(^"Stick/Knob")

func _ready() -> void:
	set_process_unhandled_input(true)
	Settings.changed.connect(func(id, _v):
		if id == "hud_scale":
			apply_layout())
	_collect_buttons(self)
	apply_layout()

func _collect_buttons(node: Node) -> void:
	for child in node.get_children():
		if child is BaseButton and child.has_meta("action"):
			var action: String = str(child.get_meta("action"))
			_buttons[action] = child
			# Each button is at least 48x48 dp and reports hold and tap, so
			# accessibility can switch a hold action to a tap.
			(child as Control).custom_minimum_size = Vector2(maxf(MIN_TOUCH, (child as Control).custom_minimum_size.x), maxf(MIN_TOUCH, (child as Control).custom_minimum_size.y))
			child.button_down.connect(_on_button_down.bind(action, child))
			child.button_up.connect(_on_button_up.bind(action, child))
		_collect_buttons(child)

func _toggle_mode(action: String) -> bool:
	if action == "aim":
		return str(Settings.get_value("aim_toggle")) == "toggle"
	if action == "crouch":
		return str(Settings.get_value("crouch_toggle")) == "toggle"
	return false

func _on_button_down(action: String, btn: BaseButton) -> void:
	_haptic(12 if action == "fire" else 8)
	if _toggle_mode(action):
		if toggled.has(action):
			toggled.erase(action)
		else:
			toggled[action] = true
		btn.set_pressed_no_signal(toggled.has(action))
	else:
		held[action] = true
	pressed_once[action] = true
	action_pressed.emit(action)

func _on_button_up(action: String, _btn: BaseButton) -> void:
	if not _toggle_mode(action):
		held.erase(action)
	action_released.emit(action)

## Touch is the optional path on PC (a touchscreen laptop, a handheld). It
## honours the same `rumble` strength as a gamepad rather than a setting of its
## own, so there is one control for "give me physical feedback".
func _haptic(ms: int) -> void:
	var strength: float = float(Settings.get_value("rumble"))
	if strength > 0.0:
		Input.vibrate_handheld(int(float(ms) * strength))

func apply_layout() -> void:
	var left_handed: bool = LAYOUT["left_handed"]
	var scale_f: float = LAYOUT["stick_size"]
	if _stick:
		_stick.scale = Vector2(scale_f, scale_f)
	# The whole control layer mirrors for a left-handed player, including the
	# stick half of the screen, so the layout is a true mirror and not a swap
	# of two buttons.
	layout_direction = Control.LAYOUT_DIRECTION_RTL if left_handed else Control.LAYOUT_DIRECTION_LTR
	_apply_safe_area()

## Keep every control inside the safe area, around notches, rounded corners and
## system gesture strips.
func _apply_safe_area() -> void:
	var safe := DisplayServer.get_display_safe_area()
	var win := DisplayServer.window_get_size()
	if win.x <= 0 or win.y <= 0:
		return
	var pad_l: float = float(safe.position.x)
	var pad_t: float = float(safe.position.y)
	var pad_r: float = float(win.x - safe.end.x)
	var pad_b: float = float(win.y - safe.end.y)
	for name in ["RightCluster", "LeftCluster", "CornerCluster"]:
		var n := get_node_or_null(NodePath(name))
		if n is Control:
			(n as Control).offset_left += pad_l if name != "RightCluster" else 0.0
			(n as Control).offset_right -= pad_r if name == "RightCluster" else 0.0
			(n as Control).offset_top += pad_t if name == "CornerCluster" else 0.0
			(n as Control).offset_bottom -= pad_b if name != "CornerCluster" else 0.0

func _stick_zone_contains(pos: Vector2) -> bool:
	var w := size.x
	var left_handed: bool = LAYOUT["left_handed"]
	return pos.x >= w * 0.55 if left_handed else pos.x <= w * 0.45

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var e := event as InputEventScreenTouch
		if e.pressed:
			if _move_index < 0 and _stick_zone_contains(e.position):
				_move_index = e.index
				var fixed: bool = str(LAYOUT["stick_mode"]) == "fixed"
				_move_origin = _fixed_stick_centre() if fixed else e.position
				if _stick:
					_stick.position = _move_origin - _stick.size * 0.5
					_stick.visible = true
				_update_stick(e.position)
			elif _look_index < 0:
				_look_index = e.index
				_look_last = e.position
		else:
			if e.index == _move_index:
				_move_index = -1
				move = Vector2.ZERO
				if _stick:
					_stick.visible = false
				if _knob:
					_knob.position = (_stick.size - _knob.size) * 0.5 if _stick else Vector2.ZERO
			elif e.index == _look_index:
				_look_index = -1
	elif event is InputEventScreenDrag:
		var e := event as InputEventScreenDrag
		if e.index == _move_index:
			_update_stick(e.position)
		elif e.index == _look_index:
			look_delta += e.position - _look_last
			_look_last = e.position

func _fixed_stick_centre() -> Vector2:
	var pad: float = 110.0 * float(LAYOUT["stick_size"])
	var left_handed: bool = LAYOUT["left_handed"]
	return Vector2(size.x - pad if left_handed else pad, size.y - pad * 0.85)

func _update_stick(pos: Vector2) -> void:
	var radius: float = STICK_RADIUS * float(LAYOUT["stick_size"])
	var d := pos - _move_origin
	if d.length() > radius:
		d = d.normalized() * radius
	move = Vector2(d.x / radius, -d.y / radius)
	if _knob and _stick:
		_knob.position = (_stick.size - _knob.size) * 0.5 + d / maxf(0.01, _stick.scale.x)

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_SIZE_CHANGED:
		_apply_safe_area()

func _process(dt: float) -> void:
	if _gyro_enabled:
		var g := Input.get_gyroscope()
		_gyro_delta += Vector2(-g.y, -g.x) * 240.0 * dt

## Per-frame input snapshot. Drains one-shot presses.
func sample() -> Dictionary:
	var down := func(a: String) -> bool: return held.has(a) or toggled.has(a)
	var out := {
		"move": move,
		"look": look_delta + _gyro_delta,
		"fire": down.call("fire"),
		"aim": down.call("aim"),
		"crouch": down.call("crouch"),
		"sprint": down.call("sprint"),
		# Held separately from the one-shot press, so a staged interaction can
		# run while the button stays down and still be completed by tapping.
		"interact_held": held.has("interact"),
		"pressed": pressed_once.duplicate(),
		"sprint_from_stick": move.length() > 0.92,
	}
	look_delta = Vector2.ZERO
	_gyro_delta = Vector2.ZERO
	pressed_once.clear()
	return out

## Show only the actions the controller actually supports right now, so the
## player is never offered a traversal button the level cannot honour.
func set_available(map: Dictionary) -> void:
	for action in _buttons:
		if not ACTIONS.has(action):
			continue
		(_buttons[action] as Control).visible = bool(map.get(action, true))

func set_context(label: String, progress: float) -> void:
	var btn := _buttons.get("interact")
	if btn == null:
		return
	(btn as Control).visible = label != ""
	if btn is Button:
		(btn as Button).text = label
	if (btn as Node).has_node(^"Progress"):
		((btn as Node).get_node(^"Progress") as Range).value = progress

func set_reload_progress(p: float) -> void:
	var btn := _buttons.get("reload")
	if btn != null and (btn as Node).has_node(^"Progress"):
		((btn as Node).get_node(^"Progress") as Range).value = p
