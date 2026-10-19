extends Node
## Input on PC: keyboard and mouse as the primary scheme, gamepad as a
## first-class alternative, every action rebindable.
##
## This replaces the mobile touch layer as the primary path. Touch still works
## (TouchControls is retained and `emulate_mouse_from_touch` is on), but nothing
## in the game requires it, and nothing requires a gamepad either.
##
## Why the binding table lives here rather than in project.godot:
##  * "Reset to defaults" needs a canonical table to reset to.
##  * A keycode written once, by name, cannot drift from a duplicate written as
##    a magic number in an .ini file.
##  * A conflict check can run over the table before anything is applied.

signal binding_changed(action: String)
signal scheme_changed(scheme: String)      ## "keyboard_mouse" | "gamepad"
signal mouse_mode_changed(captured: bool)

const PATH := "user://input.cfg"

## Mouse buttons, named so the rebinding UI and the defaults agree.
const MB_LEFT := MOUSE_BUTTON_LEFT
const MB_RIGHT := MOUSE_BUTTON_RIGHT
const MB_MIDDLE := MOUSE_BUTTON_MIDDLE
const MB_WHEEL_UP := MOUSE_BUTTON_WHEEL_UP
const MB_WHEEL_DOWN := MOUSE_BUTTON_WHEEL_DOWN

## Default bindings. `context` groups them for the rebinding screen and lets the
## conflict check allow the same key in two contexts that are never active at
## once (Escape pauses a mission and closes a map sheet; that is not a clash).
const DEFAULTS := {
	# --- first person: movement ---
	"move_forward":  {"context": "fps", "keys": [KEY_W], "joy_axis": [[JOY_AXIS_LEFT_Y, -1.0]], "label": "input.move_forward"},
	"move_back":     {"context": "fps", "keys": [KEY_S], "joy_axis": [[JOY_AXIS_LEFT_Y, 1.0]], "label": "input.move_back"},
	"move_left":     {"context": "fps", "keys": [KEY_A], "joy_axis": [[JOY_AXIS_LEFT_X, -1.0]], "label": "input.move_left"},
	"move_right":    {"context": "fps", "keys": [KEY_D], "joy_axis": [[JOY_AXIS_LEFT_X, 1.0]], "label": "input.move_right"},
	"sprint":        {"context": "fps", "keys": [KEY_SHIFT], "joy": [JOY_BUTTON_LEFT_STICK], "label": "input.sprint"},
	"crouch":        {"context": "fps", "keys": [KEY_CTRL], "joy": [JOY_BUTTON_B], "label": "input.crouch"},
	"prone":         {"context": "fps", "keys": [KEY_Z], "joy": [JOY_BUTTON_RIGHT_STICK], "label": "input.prone"},
	"traverse":      {"context": "fps", "keys": [KEY_SPACE], "joy": [JOY_BUTTON_A], "label": "input.traverse"},
	"lean_left":     {"context": "fps", "keys": [KEY_Q], "label": "input.lean_left"},
	"lean_right":    {"context": "fps", "keys": [KEY_X], "label": "input.lean_right"},

	# --- first person: weapon and interaction ---
	"fire":          {"context": "fps", "mouse": [MB_LEFT], "joy": [JOY_BUTTON_RIGHT_SHOULDER], "label": "input.fire"},
	"aim":           {"context": "fps", "mouse": [MB_RIGHT], "joy": [JOY_BUTTON_LEFT_SHOULDER], "label": "input.aim"},
	"reload":        {"context": "fps", "keys": [KEY_R], "joy": [JOY_BUTTON_X], "label": "input.reload"},
	"interact":      {"context": "fps", "keys": [KEY_E], "joy": [JOY_BUTTON_Y], "label": "input.interact"},
	"hold_breath":   {"context": "fps", "keys": [KEY_ALT], "label": "input.hold_breath"},
	"weapon_next":   {"context": "fps", "mouse": [MB_WHEEL_DOWN], "keys": [KEY_2], "label": "input.weapon_next"},
	"weapon_prev":   {"context": "fps", "mouse": [MB_WHEEL_UP], "keys": [KEY_1], "label": "input.weapon_prev"},

	# --- strategic map ---
	"map_pan":       {"context": "map", "mouse": [MB_MIDDLE], "label": "input.map_pan"},
	"map_zoom_in":   {"context": "map", "keys": [KEY_EQUAL], "label": "input.map_zoom_in"},
	"map_zoom_out":  {"context": "map", "keys": [KEY_MINUS], "label": "input.map_zoom_out"},
	"end_turn":      {"context": "map", "keys": [KEY_SPACE], "joy": [JOY_BUTTON_RIGHT_SHOULDER], "label": "input.end_turn"},
	"next_unit":     {"context": "map", "keys": [KEY_TAB], "label": "input.next_unit"},

	# --- shared ---
	"journal":       {"context": "shared", "keys": [KEY_J], "joy": [JOY_BUTTON_BACK], "label": "input.journal"},
	"map":           {"context": "shared", "keys": [KEY_M], "label": "input.map"},
	"pause":         {"context": "shared", "keys": [KEY_ESCAPE], "joy": [JOY_BUTTON_START], "shares_with": ["cancel"], "label": "input.pause"},
	"confirm":       {"context": "ui", "keys": [KEY_ENTER], "joy": [JOY_BUTTON_A], "label": "input.confirm"},
	# Escape intentionally pauses a mission and backs out of a menu. The two are
	# never live at once, so the clash is declared rather than discovered.
	"cancel":        {"context": "ui", "keys": [KEY_ESCAPE], "joy": [JOY_BUTTON_B], "shares_with": ["pause"], "label": "input.cancel"},
	"quick_save":    {"context": "shared", "keys": [KEY_F5], "label": "input.quick_save"},
	"quick_load":    {"context": "shared", "keys": [KEY_F9], "label": "input.quick_load"},
	"screenshot":    {"context": "shared", "keys": [KEY_F12], "label": "input.screenshot"},
}

var scheme: String = "keyboard_mouse"
var mouse_captured: bool = false
var _mouse_delta := Vector2.ZERO
var _bindings: Dictionary = {}      ## action -> {keys, mouse, joy, joy_axis}
var _last_gamepad_at: float = -999.0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_bindings = _default_bindings()
	_load()
	apply_all()
	for clash in undeclared_clashes():
		push_error("input: %s and %s both bound to %s — declare it with shares_with or rebind one" % [clash["a"], clash["b"], clash["binding"]])

func _default_bindings() -> Dictionary:
	var out: Dictionary = {}
	for action in DEFAULTS:
		var d: Dictionary = DEFAULTS[action]
		out[action] = {
			"keys": (d.get("keys", []) as Array).duplicate(),
			"mouse": (d.get("mouse", []) as Array).duplicate(),
			"joy": (d.get("joy", []) as Array).duplicate(),
			"joy_axis": (d.get("joy_axis", []) as Array).duplicate(true),
		}
	return out

# ------------------------------------------------------------- InputMap I/O --

func apply_all() -> void:
	for action in _bindings:
		_apply_action(str(action))

func _apply_action(action: String) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, _deadzone_for(action))
	InputMap.action_erase_events(action)
	var b: Dictionary = _bindings[action]
	for k in b["keys"]:
		var e := InputEventKey.new()
		e.physical_keycode = int(k)       # physical, so AZERTY and QWERTY agree
		InputMap.action_add_event(action, e)
	for m in b["mouse"]:
		var e := InputEventMouseButton.new()
		e.button_index = int(m)
		InputMap.action_add_event(action, e)
	for j in b["joy"]:
		var e := InputEventJoypadButton.new()
		e.button_index = int(j)
		InputMap.action_add_event(action, e)
	for a in b["joy_axis"]:
		var e := InputEventJoypadMotion.new()
		e.axis = int((a as Array)[0])
		e.axis_value = float((a as Array)[1])
		InputMap.action_add_event(action, e)

func _deadzone_for(action: String) -> float:
	if action.begins_with("move_"):
		return float(Settings.get_value("gamepad_deadzone")) if Settings.has_setting("gamepad_deadzone") else 0.2
	return 0.5

# ----------------------------------------------------------------- queries --

func bindings_for(action: String) -> Dictionary:
	return _bindings.get(action, {})

func actions_in_context(context: String) -> Array:
	var out: Array = []
	for action in DEFAULTS:
		if (DEFAULTS[action] as Dictionary)["context"] == context:
			out.append(action)
	return out

func contexts() -> Array:
	var out: Array = []
	for action in DEFAULTS:
		var c: String = str((DEFAULTS[action] as Dictionary)["context"])
		if not out.has(c):
			out.append(c)
	return out

## Human-readable binding text for the rebinding screen and the control hints.
func binding_text(action: String) -> String:
	var b: Dictionary = _bindings.get(action, {})
	var parts: Array = []
	for k in b.get("keys", []):
		parts.append(OS.get_keycode_string(int(k)))
	for m in b.get("mouse", []):
		parts.append({
			MB_LEFT: "Mouse 1", MB_RIGHT: "Mouse 2", MB_MIDDLE: "Mouse 3",
			MB_WHEEL_UP: "Wheel up", MB_WHEEL_DOWN: "Wheel down",
		}.get(int(m), "Mouse %d" % int(m)))
	for j in b.get("joy", []):
		parts.append("Pad %s" % Input.get_joy_button_string(int(j)))
	for a in b.get("joy_axis", []):
		parts.append("Stick %s" % Input.get_joy_axis_string(int((a as Array)[0])))
	return " / ".join(parts) if not parts.is_empty() else Loc.t("input.unbound")

# ---------------------------------------------------------------- rebinding --

## Returns the actions that would clash, without applying anything. A key used
## in two contexts that are never simultaneously active is not a clash.
func conflicts_for(action: String, event: InputEvent) -> Array:
	var ctx: String = str((DEFAULTS.get(action, {}) as Dictionary).get("context", "shared"))
	var out: Array = []
	for other in _bindings:
		if other == action:
			continue
		var other_ctx: String = str((DEFAULTS.get(other, {}) as Dictionary).get("context", "shared"))
		if other_ctx != ctx and other_ctx != "shared" and ctx != "shared":
			continue
		if _shares(action, str(other)):
			continue
		if _binding_matches(_bindings[other], event):
			out.append(other)
	return out

## A declared intentional pair (Escape on pause and cancel) is not a conflict.
static func _shares(a: String, b: String) -> bool:
	var da: Dictionary = DEFAULTS.get(a, {})
	var db: Dictionary = DEFAULTS.get(b, {})
	return (da.get("shares_with", []) as Array).has(b) or (db.get("shares_with", []) as Array).has(a)

## Pure check over the default table, so a binding clash is caught at startup
## and by tools/check_input_bindings.py rather than by a player.
static func undeclared_clashes() -> Array:
	var seen: Dictionary = {}
	var out: Array = []
	for action in DEFAULTS:
		var d: Dictionary = DEFAULTS[action]
		var ctx: String = str(d["context"])
		for kind in ["keys", "mouse", "joy"]:
			for code in d.get(kind, []):
				var key := "%s:%d" % [kind, int(code)]
				for other in seen.get(key, []):
					var other_ctx: String = str((DEFAULTS[other] as Dictionary)["context"])
					var overlap: bool = other_ctx == ctx or other_ctx == "shared" or ctx == "shared"
					if overlap and not _shares(str(action), str(other)):
						out.append({"a": action, "b": other, "binding": key, "contexts": [ctx, other_ctx]})
				if not seen.has(key):
					seen[key] = []
				(seen[key] as Array).append(action)
	return out

func _binding_matches(b: Dictionary, event: InputEvent) -> bool:
	if event is InputEventKey:
		return (b.get("keys", []) as Array).has(int((event as InputEventKey).physical_keycode))
	if event is InputEventMouseButton:
		return (b.get("mouse", []) as Array).has(int((event as InputEventMouseButton).button_index))
	if event is InputEventJoypadButton:
		return (b.get("joy", []) as Array).has(int((event as InputEventJoypadButton).button_index))
	return false

## Rebind an action. `replace` clears its existing bindings of the same kind
## first, which is what a player expects from a single-slot rebinding row.
## Returns {"ok": bool, "conflicts": Array}; with allow_conflict false a clash
## changes nothing.
func rebind(action: String, event: InputEvent, replace: bool = true, allow_conflict: bool = false) -> Dictionary:
	if not _bindings.has(action):
		return {"ok": false, "conflicts": [], "reason": "unknown_action"}
	var clashes := conflicts_for(action, event)
	if not clashes.is_empty() and not allow_conflict:
		return {"ok": false, "conflicts": clashes, "reason": "conflict"}
	# Taking a binding from another action removes it there, so no two actions
	# silently share a key after the player confirmed the clash.
	for other in clashes:
		_remove_event_from(str(other), event)
		_apply_action(str(other))
		binding_changed.emit(str(other))

	var b: Dictionary = _bindings[action]
	if event is InputEventKey:
		if replace: b["keys"] = []
		(b["keys"] as Array).append(int((event as InputEventKey).physical_keycode))
	elif event is InputEventMouseButton:
		if replace: b["mouse"] = []
		(b["mouse"] as Array).append(int((event as InputEventMouseButton).button_index))
	elif event is InputEventJoypadButton:
		if replace: b["joy"] = []
		(b["joy"] as Array).append(int((event as InputEventJoypadButton).button_index))
	elif event is InputEventJoypadMotion:
		var m := event as InputEventJoypadMotion
		if replace: b["joy_axis"] = []
		(b["joy_axis"] as Array).append([int(m.axis), signf(m.axis_value)])
	else:
		return {"ok": false, "conflicts": [], "reason": "unsupported_event"}

	_apply_action(action)
	_save()
	binding_changed.emit(action)
	return {"ok": true, "conflicts": clashes}

func _remove_event_from(action: String, event: InputEvent) -> void:
	var b: Dictionary = _bindings[action]
	if event is InputEventKey:
		b["keys"] = (b["keys"] as Array).filter(func(k): return int(k) != int((event as InputEventKey).physical_keycode))
	elif event is InputEventMouseButton:
		b["mouse"] = (b["mouse"] as Array).filter(func(m): return int(m) != int((event as InputEventMouseButton).button_index))
	elif event is InputEventJoypadButton:
		b["joy"] = (b["joy"] as Array).filter(func(j): return int(j) != int((event as InputEventJoypadButton).button_index))

func unbind(action: String) -> void:
	if not _bindings.has(action):
		return
	_bindings[action] = {"keys": [], "mouse": [], "joy": [], "joy_axis": []}
	_apply_action(action)
	_save()
	binding_changed.emit(action)

func reset_action(action: String) -> void:
	var d := _default_bindings()
	if not d.has(action):
		return
	_bindings[action] = d[action]
	_apply_action(action)
	_save()
	binding_changed.emit(action)

func reset_all() -> void:
	_bindings = _default_bindings()
	apply_all()
	_save()
	binding_changed.emit("*")

# ------------------------------------------------------------ mouse capture --

## The cursor is captured during a mission and free on the map and in menus.
## Alt-tab releases it; returning re-captures only if a mission is still live.
func capture_mouse(on: bool) -> void:
	mouse_captured = on
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if on else Input.MOUSE_MODE_VISIBLE
	Input.use_accumulated_input = not on
	mouse_mode_changed.emit(on)

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and mouse_captured:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN and mouse_captured:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and mouse_captured:
		# Relative motion only. No OS acceleration, no smoothing: 1:1 aiming is
		# the single most important feel decision on PC.
		_mouse_delta += (event as InputEventMouseMotion).relative
		_note_scheme("keyboard_mouse")
	elif event is InputEventKey or event is InputEventMouseButton:
		_note_scheme("keyboard_mouse")
	elif event is InputEventJoypadButton or event is InputEventJoypadMotion:
		if event is InputEventJoypadMotion and absf((event as InputEventJoypadMotion).axis_value) < 0.3:
			return
		_note_scheme("gamepad")

func _note_scheme(s: String) -> void:
	if s == "gamepad":
		_last_gamepad_at = float(Time.get_ticks_msec()) / 1000.0
	if scheme != s:
		scheme = s
		scheme_changed.emit(s)

# ------------------------------------------------------------------ sampling --

## Per-frame input snapshot, the same shape the touch layer produced, so the
## mission scene and the player controller did not change when the platform did.
func sample() -> Dictionary:
	var look := _mouse_delta * float(Settings.get_value("mouse_sensitivity"))
	_mouse_delta = Vector2.ZERO

	# Gamepad look is rate-based, not delta-based, so it needs the frame time;
	# the caller multiplies by dt. Reported separately so the two never add up
	# to double sensitivity when both devices are touched in one frame.
	var pad_look := Vector2(
		Input.get_axis("look_left", "look_right") if InputMap.has_action("look_left") else _joy_axis(JOY_AXIS_RIGHT_X),
		_joy_axis(JOY_AXIS_RIGHT_Y),
	) * float(Settings.get_value("gamepad_look_speed")) * 1000.0

	var move := Input.get_vector("move_left", "move_right", "move_back", "move_forward")
	return {
		"move": move,
		"look": look,
		"look_rate": pad_look,
		"fire": Input.is_action_pressed("fire"),
		"aim": Input.is_action_pressed("aim"),
		"crouch": _posture_pressed("crouch"),
		"prone": _posture_pressed("prone"),
		"sprint": Input.is_action_pressed("sprint"),
		"hold_breath": Input.is_action_pressed("hold_breath"),
		"lean": (-1.0 if Input.is_action_pressed("lean_left") else 0.0) + (1.0 if Input.is_action_pressed("lean_right") else 0.0),
		"interact_held": Input.is_action_pressed("interact"),
		"pressed": _pressed_this_frame(),
		"sprint_from_stick": move.length() > 0.92 and scheme == "gamepad",
	}

func _joy_axis(axis: int) -> float:
	var v := Input.get_joy_axis(0, axis)
	var dz := float(Settings.get_value("gamepad_deadzone"))
	return 0.0 if absf(v) < dz else v

## Hold-or-toggle, honoured per posture action, because a player who cannot hold
## a key still has to be able to crouch.
var _toggled: Dictionary = {}
func _posture_pressed(action: String) -> bool:
	var mode: String = str(Settings.get_value("%s_toggle" % action)) if Settings.has_setting("%s_toggle" % action) else "hold"
	if mode != "toggle":
		return Input.is_action_pressed(action)
	if Input.is_action_just_pressed(action):
		if _toggled.has(action):
			_toggled.erase(action)
		else:
			_toggled[action] = true
	return _toggled.has(action)

func _pressed_this_frame() -> Dictionary:
	var out: Dictionary = {}
	for action in ["reload", "interact", "traverse", "weapon_next", "weapon_prev", "journal", "map", "pause", "quick_save", "quick_load", "screenshot", "end_turn", "next_unit", "confirm", "cancel"]:
		if InputMap.has_action(action) and Input.is_action_just_pressed(action):
			out[action] = true
	return out

# ---------------------------------------------------------------- persistence --

func _save() -> void:
	var cfg := ConfigFile.new()
	for action in _bindings:
		cfg.set_value("bindings", str(action), _bindings[action])
	if cfg.save(PATH) != OK:
		push_warning("input bindings could not be saved; defaults will apply next launch")

func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	for action in cfg.get_section_keys("bindings"):
		if not DEFAULTS.has(action):
			continue        # a binding for an action this build dropped is ignored, not applied
		var v = cfg.get_value("bindings", action)
		if v is Dictionary:
			_bindings[action] = {
				"keys": (v.get("keys", []) as Array).duplicate(),
				"mouse": (v.get("mouse", []) as Array).duplicate(),
				"joy": (v.get("joy", []) as Array).duplicate(),
				"joy_axis": (v.get("joy_axis", []) as Array).duplicate(true),
			}
