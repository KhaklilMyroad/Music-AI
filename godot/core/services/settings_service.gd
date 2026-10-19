extends Node
## Player settings. Two rules from the brief are structural here: only
## categories that actually work are exposed, and a visible slider must control
## its intended output. Every entry therefore names the subsystem it drives, and
## tests/test_settings.gd asserts each `drives` target is consumed somewhere.

signal changed(id: String, value: Variant)

const PATH := "user://settings.cfg"

const SCHEMA := [
	{"group": "graphics", "id": "quality",            "type": "enum",  "values": ["low", "balanced", "high"], "def": "balanced", "drives": "renderer"},
	{"group": "graphics", "id": "frame_target",       "type": "enum",  "values": ["30", "60"], "def": "60", "drives": "renderer"},
	{"group": "graphics", "id": "render_scale",       "type": "range", "min": 0.6, "max": 1.0, "step": 0.05, "def": 0.9, "drives": "renderer"},
	{"group": "graphics", "id": "high_contrast",      "type": "bool",  "def": false, "drives": "theme"},
	{"group": "display",  "id": "text_scale",         "type": "range", "min": 0.85, "max": 1.6, "step": 0.05, "def": 1.0, "drives": "theme"},
	{"group": "display",  "id": "hud_scale",          "type": "range", "min": 0.8, "max": 1.5, "step": 0.05, "def": 1.0, "drives": "theme"},
	{"group": "display",  "id": "language",           "type": "enum",  "values": ["en", "he"], "def": "en", "drives": "i18n"},
	{"group": "display",  "id": "colour_independent", "type": "bool",  "def": true, "drives": "hud"},
	{"group": "camera",   "id": "sensitivity",        "type": "range", "min": 0.3, "max": 3.0, "step": 0.1, "def": 1.2, "drives": "player"},
	{"group": "camera",   "id": "aim_sensitivity",    "type": "range", "min": 0.2, "max": 2.0, "step": 0.1, "def": 0.7, "drives": "player"},
	{"group": "camera",   "id": "invert_y",           "type": "bool",  "def": false, "drives": "player"},
	{"group": "camera",   "id": "gyro",               "type": "bool",  "def": false, "drives": "player"},
	{"group": "camera",   "id": "aim_assist",         "type": "enum",  "values": ["off", "light", "strong"], "def": "light", "drives": "player"},
	{"group": "camera",   "id": "camera_shake",       "type": "range", "min": 0.0, "max": 1.0, "step": 0.1, "def": 0.6, "drives": "player"},
	{"group": "camera",   "id": "recoil_presentation","type": "range", "min": 0.2, "max": 1.0, "step": 0.1, "def": 1.0, "drives": "player"},
	{"group": "camera",   "id": "motion_reduction",   "type": "bool",  "def": false, "drives": "theme"},
	{"group": "controls", "id": "left_handed",        "type": "bool",  "def": false, "drives": "touch"},
	{"group": "controls", "id": "stick_size",         "type": "range", "min": 0.8, "max": 1.5, "step": 0.05, "def": 1.0, "drives": "touch"},
	{"group": "controls", "id": "stick_mode",         "type": "enum",  "values": ["floating", "fixed"], "def": "floating", "drives": "touch"},
	{"group": "controls", "id": "aim_toggle",         "type": "enum",  "values": ["hold", "toggle"], "def": "hold", "drives": "touch"},
	{"group": "controls", "id": "crouch_toggle",      "type": "enum",  "values": ["toggle", "hold"], "def": "toggle", "drives": "touch"},
	{"group": "controls", "id": "haptics",            "type": "bool",  "def": true, "drives": "touch"},
	{"group": "audio",    "id": "vol_master",         "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 0.9, "drives": "audio"},
	{"group": "audio",    "id": "vol_effects",        "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 1.0, "drives": "audio"},
	{"group": "audio",    "id": "vol_ambience",       "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 0.85, "drives": "audio"},
	{"group": "audio",    "id": "vol_dialogue",       "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 1.0, "drives": "audio"},
	{"group": "audio",    "id": "vol_music",          "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 0.6, "drives": "audio"},
	{"group": "audio",    "id": "mono",               "type": "bool",  "def": false, "drives": "audio"},
	{"group": "audio",    "id": "subtitles",          "type": "bool",  "def": true, "drives": "hud"},
	{"group": "audio",    "id": "speaker_names",      "type": "bool",  "def": true, "drives": "hud"},
	{"group": "audio",    "id": "sound_captions",     "type": "bool",  "def": false, "drives": "audio"},
	{"group": "content",  "id": "intensity",          "type": "enum",  "values": ["full", "reduced"], "def": "full", "drives": "content"},
]

var _values: Dictionary = {}

func _ready() -> void:
	for s in SCHEMA:
		_values[s["id"]] = s["def"]
	_load()
	apply_display()

func get_value(id: String) -> Variant:
	return _values.get(id)

func set_value(id: String, v: Variant) -> void:
	var spec := _spec(id)
	assert(not spec.is_empty(), "unknown setting %s" % id)
	match spec["type"]:
		"range": v = clampf(float(v), float(spec["min"]), float(spec["max"]))
		"bool": v = bool(v)
		"enum":
			if not (spec["values"] as Array).has(str(v)):
				return
			v = str(v)
	_values[id] = v
	_save()
	if spec["drives"] == "theme":
		apply_display()
	changed.emit(id, v)

func groups() -> Array:
	var out: Array = []
	for s in SCHEMA:
		if not out.has(s["group"]):
			out.append(s["group"])
	return out

func in_group(g: String) -> Array:
	var out: Array = []
	for s in SCHEMA:
		if s["group"] == g:
			out.append(s)
	return out

func _spec(id: String) -> Dictionary:
	for s in SCHEMA:
		if s["id"] == id:
			return s
	return {}

## Renderer budget per quality tier. These are engineering targets from
## docs/10-DEVICE-PERF-PLAN.md, not measured results on any device.
func renderer_options() -> Dictionary:
	var q: String = str(get_value("quality"))
	return {
		"quality": q,
		"render_scale": float(get_value("render_scale")),
		"shadows": q != "low",
		"shadow_atlas": {"low": 0, "balanced": 1024, "high": 2048}[q],
		"directional_shadow": {"low": 0, "balanced": 1024, "high": 2048}[q],
		"msaa": {"low": Viewport.MSAA_DISABLED, "balanced": Viewport.MSAA_2X, "high": Viewport.MSAA_4X}[q],
		"fog_density": {"low": 0.012, "balanced": 0.008, "high": 0.006}[q],
		"vegetation_density": {"low": 0.4, "balanced": 0.75, "high": 1.0}[q],
		"max_active_characters": {"low": 6, "balanced": 10, "high": 14}[q],
		"max_audio_voices": {"low": 16, "balanced": 24, "high": 32}[q],
		"frame_target": int(str(get_value("frame_target"))),
	}

func audio_options() -> Dictionary:
	return {
		"bus_volumes": {
			"Master": float(get_value("vol_master")),
			"Effects": float(get_value("vol_effects")),
			"Ambience": float(get_value("vol_ambience")),
			"Dialogue": float(get_value("vol_dialogue")),
			"Music": float(get_value("vol_music")),
		},
		"mono": bool(get_value("mono")),
		"sound_captions": bool(get_value("sound_captions")),
		"max_voices": renderer_options()["max_audio_voices"],
	}

## Apply the settings that drive presentation. Scene scale, render scale and
## frame target are presentation only: none of them touches a gameplay rule.
func apply_display() -> void:
	var o := renderer_options()
	var win := get_window()
	if win:
		win.content_scale_factor = float(get_value("text_scale"))
	get_viewport().scaling_3d_scale = float(o["render_scale"])
	get_viewport().msaa_3d = o["msaa"]
	Engine.max_fps = int(o["frame_target"])
	RenderingServer.directional_shadow_atlas_set_size(int(o["directional_shadow"]), true)

func _save() -> void:
	var cfg := ConfigFile.new()
	for k in _values:
		cfg.set_value("settings", k, _values[k])
	var err := cfg.save(PATH)
	if err != OK:
		push_warning("settings could not be saved (%d); defaults will apply next launch" % err)

func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	for k in cfg.get_section_keys("settings"):
		if _spec(k).is_empty():
			continue
		_values[k] = cfg.get_value("settings", k)
