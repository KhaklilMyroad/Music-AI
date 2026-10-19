extends Node
## Player settings for the PC edition.
##
## Two rules from the brief are still structural here: only categories that
## actually work are exposed, and a visible slider must control its intended
## output. Every entry therefore names the subsystem it drives, and
## tests/test_runner.gd asserts each `drives` target is consumed somewhere.
##
## What changed from the mobile configuration: device tiers became GPU presets,
## the touch layout group became an input group with rebinding and mouse
## sensitivity, and the Forward+ renderer features the mobile path lacks (SSIL,
## SDFGI, volumetric fog, screen-space reflections, FSR2) are each exposed
## individually, because the floor GPU must still hold 60 FPS with them off.

signal changed(id: String, value: Variant)

const PATH := "user://settings.cfg"

const PRESETS := ["low", "medium", "high", "ultra", "custom"]

const SCHEMA := [
	# --- display: window, resolution, frame pacing -------------------------
	{"group": "display", "id": "display_mode",    "type": "enum",  "values": ["windowed", "fullscreen", "borderless"], "def": "windowed", "drives": "window"},
	{"group": "display", "id": "resolution",      "type": "enum",  "values": ["1280x720", "1600x900", "1920x1080", "2560x1440", "3440x1440", "3840x2160", "native"], "def": "native", "drives": "window"},
	{"group": "display", "id": "monitor",         "type": "int",   "min": 0, "max": 7, "def": 0, "drives": "window"},
	{"group": "display", "id": "vsync",           "type": "enum",  "values": ["off", "on", "adaptive", "mailbox"], "def": "on", "drives": "window"},
	{"group": "display", "id": "fps_cap",         "type": "enum",  "values": ["off", "60", "120", "144", "165", "240"], "def": "off", "drives": "window"},
	{"group": "display", "id": "fov",             "type": "range", "min": 70.0, "max": 110.0, "step": 1.0, "def": 90.0, "drives": "player"},

	# --- graphics: a preset, plus every Forward+ feature individually ------
	{"group": "graphics", "id": "preset",          "type": "enum",  "values": PRESETS, "def": "high", "drives": "renderer"},
	{"group": "graphics", "id": "render_scale",    "type": "range", "min": 0.5, "max": 2.0, "step": 0.05, "def": 1.0, "drives": "renderer"},
	{"group": "graphics", "id": "upscaler",        "type": "enum",  "values": ["bilinear", "fsr2"], "def": "fsr2", "drives": "renderer"},
	{"group": "graphics", "id": "anti_aliasing",   "type": "enum",  "values": ["off", "fxaa", "msaa_2x", "msaa_4x", "msaa_8x", "taa"], "def": "msaa_2x", "drives": "renderer"},
	{"group": "graphics", "id": "shadow_quality",  "type": "enum",  "values": ["off", "low", "medium", "high", "ultra"], "def": "high", "drives": "renderer"},
	{"group": "graphics", "id": "texture_quality", "type": "enum",  "values": ["low", "medium", "high"], "def": "high", "drives": "renderer"},
	{"group": "graphics", "id": "anisotropic",     "type": "enum",  "values": ["off", "2x", "4x", "8x", "16x"], "def": "8x", "drives": "renderer"},
	{"group": "graphics", "id": "ssao",            "type": "bool",  "def": true,  "drives": "renderer"},
	{"group": "graphics", "id": "ssil",            "type": "bool",  "def": true,  "drives": "renderer"},
	{"group": "graphics", "id": "sdfgi",           "type": "bool",  "def": true,  "drives": "renderer"},
	{"group": "graphics", "id": "reflections",     "type": "enum",  "values": ["off", "probes", "screen_space"], "def": "screen_space", "drives": "renderer"},
	{"group": "graphics", "id": "volumetric_fog",  "type": "bool",  "def": true,  "drives": "renderer"},
	{"group": "graphics", "id": "depth_of_field",  "type": "bool",  "def": true,  "drives": "renderer"},
	{"group": "graphics", "id": "bloom",           "type": "range", "min": 0.0, "max": 0.6, "step": 0.05, "def": 0.15, "drives": "renderer"},
	{"group": "graphics", "id": "draw_distance",   "type": "range", "min": 120.0, "max": 600.0, "step": 20.0, "def": 400.0, "drives": "renderer"},
	{"group": "graphics", "id": "vegetation",      "type": "range", "min": 0.3, "max": 1.0, "step": 0.05, "def": 1.0, "drives": "renderer"},
	{"group": "graphics", "id": "max_characters",  "type": "int",   "min": 8, "max": 48, "def": 28, "drives": "renderer"},

	# --- input: keyboard, mouse, gamepad ----------------------------------
	{"group": "input", "id": "mouse_sensitivity",   "type": "range", "min": 0.05, "max": 1.5, "step": 0.01, "def": 0.25, "drives": "player"},
	{"group": "input", "id": "aim_sensitivity_mult","type": "range", "min": 0.2, "max": 1.5, "step": 0.05, "def": 0.65, "drives": "player"},
	{"group": "input", "id": "invert_y",            "type": "bool",  "def": false, "drives": "player"},
	{"group": "input", "id": "gamepad_look_speed",  "type": "range", "min": 0.5, "max": 4.0, "step": 0.1, "def": 2.0, "drives": "player"},
	{"group": "input", "id": "gamepad_deadzone",    "type": "range", "min": 0.05, "max": 0.4, "step": 0.01, "def": 0.2, "drives": "input"},
	{"group": "input", "id": "aim_assist",          "type": "enum",  "values": ["off", "light", "strong"], "def": "off", "drives": "player"},
	{"group": "input", "id": "aim_toggle",          "type": "enum",  "values": ["hold", "toggle"], "def": "hold", "drives": "input"},
	{"group": "input", "id": "crouch_toggle",       "type": "enum",  "values": ["hold", "toggle"], "def": "toggle", "drives": "input"},
	{"group": "input", "id": "prone_toggle",        "type": "enum",  "values": ["hold", "toggle"], "def": "toggle", "drives": "input"},
	{"group": "input", "id": "sprint_toggle",       "type": "enum",  "values": ["hold", "toggle"], "def": "hold", "drives": "input"},
	# Rumble replaces the phone's haptics: it only reaches a connected gamepad,
	# and zero means a player who finds it unpleasant can switch it off entirely.
	{"group": "input", "id": "rumble",              "type": "range", "min": 0.0, "max": 1.0, "step": 0.1, "def": 0.6, "drives": "player"},

	# --- accessibility ----------------------------------------------------
	{"group": "accessibility", "id": "ui_scale",           "type": "range", "min": 0.8, "max": 1.6, "step": 0.05, "def": 1.0, "drives": "theme"},
	{"group": "accessibility", "id": "text_scale",         "type": "range", "min": 0.85, "max": 1.6, "step": 0.05, "def": 1.0, "drives": "theme"},
	{"group": "accessibility", "id": "hud_scale",          "type": "range", "min": 0.8, "max": 1.5, "step": 0.05, "def": 1.0, "drives": "theme"},
	{"group": "accessibility", "id": "language",           "type": "enum",  "values": ["en", "he"], "def": "en", "drives": "i18n"},
	{"group": "accessibility", "id": "high_contrast",      "type": "bool",  "def": false, "drives": "theme"},
	{"group": "accessibility", "id": "colour_independent", "type": "bool",  "def": true,  "drives": "hud"},
	{"group": "accessibility", "id": "motion_reduction",   "type": "bool",  "def": false, "drives": "theme"},
	{"group": "accessibility", "id": "camera_shake",       "type": "range", "min": 0.0, "max": 1.0, "step": 0.1, "def": 0.6, "drives": "player"},
	{"group": "accessibility", "id": "recoil_presentation","type": "range", "min": 0.2, "max": 1.0, "step": 0.1, "def": 1.0, "drives": "player"},
	{"group": "accessibility", "id": "head_bob",           "type": "range", "min": 0.0, "max": 1.0, "step": 0.1, "def": 0.7, "drives": "player"},
	{"group": "accessibility", "id": "subtitles",          "type": "bool",  "def": true,  "drives": "hud"},
	{"group": "accessibility", "id": "speaker_names",      "type": "bool",  "def": true,  "drives": "hud"},
	{"group": "accessibility", "id": "sound_captions",     "type": "bool",  "def": false, "drives": "audio"},
	{"group": "accessibility", "id": "hold_to_press",      "type": "enum",  "values": ["hold", "tap"], "def": "hold", "drives": "input"},

	# --- audio ------------------------------------------------------------
	{"group": "audio", "id": "vol_master",   "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 0.9, "drives": "audio"},
	{"group": "audio", "id": "vol_effects",  "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 1.0, "drives": "audio"},
	{"group": "audio", "id": "vol_ambience", "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 0.85, "drives": "audio"},
	{"group": "audio", "id": "vol_dialogue", "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 1.0, "drives": "audio"},
	{"group": "audio", "id": "vol_music",    "type": "range", "min": 0.0, "max": 1.0, "step": 0.05, "def": 0.6, "drives": "audio"},
	{"group": "audio", "id": "output_mode",  "type": "enum",  "values": ["stereo", "mono", "headphones"], "def": "stereo", "drives": "audio"},

	# --- content ----------------------------------------------------------
	{"group": "content", "id": "intensity", "type": "enum", "values": ["full", "reduced"], "def": "full", "drives": "content"},
]

## What each preset sets. Touching any individual graphics option moves the
## preset to "custom", so the UI never lies about what is actually applied.
const PRESET_VALUES := {
	"low":    {"render_scale": 0.7, "upscaler": "fsr2", "anti_aliasing": "fxaa", "shadow_quality": "low", "texture_quality": "low", "anisotropic": "2x", "ssao": false, "ssil": false, "sdfgi": false, "reflections": "off", "volumetric_fog": false, "depth_of_field": false, "draw_distance": 160.0, "vegetation": 0.3, "bloom": 0.0, "max_characters": 10},
	"medium": {"render_scale": 0.85, "upscaler": "fsr2", "anti_aliasing": "msaa_2x", "shadow_quality": "medium", "texture_quality": "medium", "anisotropic": "4x", "ssao": true, "ssil": false, "sdfgi": false, "reflections": "probes", "volumetric_fog": false, "depth_of_field": false, "draw_distance": 260.0, "vegetation": 0.6, "bloom": 0.1, "max_characters": 18},
	"high":   {"render_scale": 1.0, "upscaler": "fsr2", "anti_aliasing": "msaa_2x", "shadow_quality": "high", "texture_quality": "high", "anisotropic": "8x", "ssao": true, "ssil": true, "sdfgi": true, "reflections": "screen_space", "volumetric_fog": true, "depth_of_field": true, "draw_distance": 400.0, "vegetation": 1.0, "bloom": 0.15, "max_characters": 28},
	"ultra":  {"render_scale": 1.0, "upscaler": "bilinear", "anti_aliasing": "msaa_4x", "shadow_quality": "ultra", "texture_quality": "high", "anisotropic": "16x", "ssao": true, "ssil": true, "sdfgi": true, "reflections": "screen_space", "volumetric_fog": true, "depth_of_field": true, "draw_distance": 600.0, "vegetation": 1.0, "bloom": 0.2, "max_characters": 40},
}

var _values: Dictionary = {}
var _applying_preset := false

func _ready() -> void:
	for s in SCHEMA:
		_values[s["id"]] = s["def"]
	_load()
	apply_window()
	apply_renderer()
	apply_display()

func has_setting(id: String) -> bool:
	return not _spec(id).is_empty()

func get_value(id: String) -> Variant:
	return _values.get(id)

func set_value(id: String, v: Variant) -> void:
	var spec := _spec(id)
	assert(not spec.is_empty(), "unknown setting %s" % id)
	match spec["type"]:
		"range": v = clampf(float(v), float(spec["min"]), float(spec["max"]))
		"int": v = clampi(int(v), int(spec["min"]), int(spec["max"]))
		"bool": v = bool(v)
		"enum":
			if not (spec["values"] as Array).has(str(v)):
				return
			v = str(v)
	if _values[id] == v:
		return
	_values[id] = v

	# Changing an individual graphics option means the named preset no longer
	# describes what is applied, so it becomes "custom" rather than lying.
	if spec["group"] == "graphics" and id != "preset" and not _applying_preset:
		_values["preset"] = "custom"
		changed.emit("preset", "custom")
	if id == "preset" and str(v) != "custom":
		apply_preset(str(v))

	_save()
	match spec["drives"]:
		"theme": apply_display()
		"window": apply_window()
		"renderer": apply_renderer()
	changed.emit(id, v)

func apply_preset(name: String) -> void:
	var vals: Dictionary = PRESET_VALUES.get(name, {})
	if vals.is_empty():
		return
	_applying_preset = true
	for k in vals:
		_values[k] = vals[k]
		changed.emit(str(k), vals[k])
	_applying_preset = false
	apply_renderer()
	_save()

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

# --------------------------------------------------------- window and frame --

func apply_window() -> void:
	var win := get_window()
	if win == null:
		return
	var screen: int = clampi(int(get_value("monitor")), 0, maxi(0, DisplayServer.get_screen_count() - 1))
	match str(get_value("display_mode")):
		"fullscreen":
			win.mode = Window.MODE_EXCLUSIVE_FULLSCREEN
			win.borderless = false
		"borderless":
			win.mode = Window.MODE_FULLSCREEN
			win.borderless = true
		_:
			win.mode = Window.MODE_WINDOWED
			win.borderless = false
			var res := _resolution_for(screen)
			win.size = res
			# Centre on the chosen monitor rather than assuming the primary one.
			var usable := DisplayServer.screen_get_usable_rect(screen)
			win.position = usable.position + (usable.size - res) / 2
	if win.mode != Window.MODE_WINDOWED:
		win.current_screen = screen

	DisplayServer.window_set_vsync_mode({
		"off": DisplayServer.VSYNC_DISABLED,
		"on": DisplayServer.VSYNC_ENABLED,
		"adaptive": DisplayServer.VSYNC_ADAPTIVE,
		"mailbox": DisplayServer.VSYNC_MAILBOX,
	}.get(str(get_value("vsync")), DisplayServer.VSYNC_ENABLED))

	var cap: String = str(get_value("fps_cap"))
	Engine.max_fps = 0 if cap == "off" else int(cap)

func _resolution_for(screen: int) -> Vector2i:
	var r: String = str(get_value("resolution"))
	if r == "native":
		var usable := DisplayServer.screen_get_usable_rect(screen)
		# A "native" window is not a fullscreen window: leave room for the
		# title bar and the taskbar so it does not open half off-screen.
		return Vector2i(int(float(usable.size.x) * 0.9), int(float(usable.size.y) * 0.9))
	var parts := r.split("x")
	return Vector2i(int(parts[0]), int(parts[1]))

# ------------------------------------------------------------------ renderer --

## Everything the Forward+ renderer exposes, applied from the settings rather
## than hard-coded. A quality option may change presentation only: none of these
## reaches a gameplay rule, and the stealth model takes no rendering parameter
## at all (see gameplay/fps/detection.gd).
func apply_renderer() -> void:
	var vp := get_viewport()
	if vp == null:
		return
	vp.scaling_3d_scale = float(get_value("render_scale"))
	vp.scaling_3d_mode = (Viewport.SCALING_3D_MODE_FSR2 if str(get_value("upscaler")) == "fsr2" else Viewport.SCALING_3D_MODE_BILINEAR)

	var aa: String = str(get_value("anti_aliasing"))
	vp.msaa_3d = {
		"msaa_2x": Viewport.MSAA_2X, "msaa_4x": Viewport.MSAA_4X, "msaa_8x": Viewport.MSAA_8X,
	}.get(aa, Viewport.MSAA_DISABLED)
	vp.screen_space_aa = (Viewport.SCREEN_SPACE_AA_FXAA if aa == "fxaa" else Viewport.SCREEN_SPACE_AA_DISABLED)
	vp.use_taa = aa == "taa"

	var shadow: String = str(get_value("shadow_quality"))
	var dir_size: int = {"off": 0, "low": 1024, "medium": 2048, "high": 4096, "ultra": 8192}.get(shadow, 4096)
	RenderingServer.directional_shadow_atlas_set_size(dir_size, true)
	vp.positional_shadow_atlas_size = maxi(0, dir_size)
	var filter_q: int = {"off": 0, "low": 0, "medium": 1, "high": 3, "ultra": 4}.get(shadow, 3)
	RenderingServer.directional_soft_shadow_filter_set_quality(filter_q)
	RenderingServer.positional_soft_shadow_filter_set_quality(filter_q)

	RenderingServer.environment_set_ssao_quality(
		2 if bool(get_value("ssao")) else 0, true, 0.5, 2, 50.0, 300.0)
	RenderingServer.environment_set_ssil_quality(
		2 if bool(get_value("ssil")) else 0, true, 0.5, 4, 50.0, 300.0)
	RenderingServer.environment_set_sdfgi_ray_count(
		RenderingServer.ENV_SDFGI_RAY_COUNT_32 if bool(get_value("sdfgi")) else RenderingServer.ENV_SDFGI_RAY_COUNT_4)
	RenderingServer.environment_set_volumetric_fog_filter_active(bool(get_value("volumetric_fog")))

	var aniso: String = str(get_value("anisotropic"))
	ProjectSettings.set_setting("rendering/textures/default_filters/anisotropic_filtering_level",
		{"off": 0, "2x": 1, "4x": 2, "8x": 3, "16x": 4}.get(aniso, 3))

	# Texture quality is a streaming/mip decision, not a filter one.
	ProjectSettings.set_setting("rendering/textures/default_filters/texture_mipmap_bias",
		{"low": 0.5, "medium": 0.0, "high": -0.25}.get(str(get_value("texture_quality")), 0.0))

## Values the mission scene reads when it builds its environment and district.
func renderer_options() -> Dictionary:
	return {
		"preset": str(get_value("preset")),
		"shadows": str(get_value("shadow_quality")) != "off",
		"ssao": bool(get_value("ssao")),
		"ssil": bool(get_value("ssil")),
		"sdfgi": bool(get_value("sdfgi")),
		"reflections": str(get_value("reflections")),
		"volumetric_fog": bool(get_value("volumetric_fog")),
		"depth_of_field": bool(get_value("depth_of_field")),
		"bloom": float(get_value("bloom")),
		"draw_distance": float(get_value("draw_distance")),
		"vegetation_density": float(get_value("vegetation")),
		"max_active_characters": int(get_value("max_characters")),
		"max_audio_voices": {"low": 32, "medium": 48, "high": 64, "ultra": 96}.get(str(get_value("preset")), 64),
		"fov": float(get_value("fov")),
	}

func audio_options() -> Dictionary:
	var mode: String = str(get_value("output_mode"))
	return {
		"bus_volumes": {
			"Master": float(get_value("vol_master")),
			"Effects": float(get_value("vol_effects")),
			"Ambience": float(get_value("vol_ambience")),
			"Dialogue": float(get_value("vol_dialogue")),
			"Music": float(get_value("vol_music")),
		},
		"mono": mode == "mono",
		"headphones": mode == "headphones",
		"sound_captions": bool(get_value("sound_captions")),
		"max_voices": renderer_options()["max_audio_voices"],
	}

## Presentation scale. On PC the UI scales by the player's choice rather than by
## device pixel ratio, and it has to stay legible from 720p to 4K.
func apply_display() -> void:
	var win := get_window()
	if win:
		win.content_scale_factor = float(get_value("ui_scale")) * float(get_value("text_scale"))

func _save() -> void:
	var cfg := ConfigFile.new()
	for k in _values:
		cfg.set_value("settings", k, _values[k])
	if cfg.save(PATH) != OK:
		push_warning("settings could not be saved; defaults will apply next launch")

func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	for k in cfg.get_section_keys("settings"):
		if _spec(k).is_empty():
			continue        # a setting this build dropped is ignored, not applied
		_values[k] = cfg.get_value("settings", k)
