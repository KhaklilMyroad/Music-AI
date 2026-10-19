extends Control
class_name MissionHud
## First-person HUD (brief §10). Concise by design: condition, rounds,
## interaction prompt, objectives and stealth feedback. Detailed inventory,
## logistics and historical information live in their own panels.
##
## Every indicator carries a word as well as a bar, so nothing depends on
## colour, and every size derives from the HUD scale setting.

@onready var _objectives: VBoxContainer = get_node_or_null(^"TopLeft/Objectives")
@onready var _stealth: VBoxContainer = get_node_or_null(^"BottomLeft/Stealth")
@onready var _ammo: Label = get_node_or_null(^"BottomRight/Ammo")
@onready var _weapon_name: Label = get_node_or_null(^"BottomRight/WeaponName")
@onready var _condition: ProgressBar = get_node_or_null(^"BottomRight/Condition")
@onready var _stamina: ProgressBar = get_node_or_null(^"BottomRight/Stamina")
@onready var _subtitles: VBoxContainer = get_node_or_null(^"Subtitles")
@onready var _prompt: Label = get_node_or_null(^"Prompt")
@onready var _reticle: Control = get_node_or_null(^"Reticle")

var _subtitle_until: float = 0.0

func _ready() -> void:
	var s := float(Settings.get_value("hud_scale"))
	scale = Vector2(s, s)
	Settings.changed.connect(func(id, v):
		if id == "hud_scale":
			scale = Vector2(float(v), float(v)))

func render(state: Dictionary) -> void:
	if _objectives:
		for child in _objectives.get_children():
			child.queue_free()
		for o in state.get("objectives", []):
			var od: Dictionary = o
			var l := Label.new()
			var mark := "[x]" if bool(od["done"]) else ("[!]" if bool(od["failed"]) else "[ ]")
			l.text = "%s %s%s" % [mark, od["label"], "" if bool(od["required"]) else " (%s)" % Loc.t("mission.optional")]
			l.modulate = Color(0.6, 0.6, 0.56) if bool(od["done"]) else Color(0.95, 0.93, 0.89)
			_objectives.add_child(l)

	if _stealth:
		for child in _stealth.get_children():
			child.queue_free()
		var st: Dictionary = state.get("stealth", {})
		for key in ["visibility", "noise", "awareness"]:
			var band: Dictionary = st.get(key, {})
			if band.is_empty():
				continue
			var row := HBoxContainer.new()
			var l := Label.new()
			# The word carries the meaning; the shape and bar are redundant cues.
			var shape := ""
			if bool(Settings.get_value("colour_independent")):
				shape = {"high": "▲ ", "detected": "▲ ", "medium": "◆ ", "suspicious": "◆ "}.get(str(band["band"]), "")
			l.text = "%s%s" % [shape, Loc.t(str(band["label_key"]))]
			var bar := ProgressBar.new()
			bar.custom_minimum_size = Vector2(60, 4)
			bar.show_percentage = false
			bar.max_value = 1.0
			bar.value = float(band["value"])
			row.add_child(l)
			row.add_child(bar)
			_stealth.add_child(row)

	var w = state.get("weapon")
	if _ammo:
		if w == null:
			_ammo.text = "—"
		elif bool((w as Dictionary)["is_tool"]):
			_ammo.text = "—"
		else:
			_ammo.text = "%d / %d" % [int((w as Dictionary)["loaded"]), int((w as Dictionary)["reserve"])]
	if _weapon_name:
		_weapon_name.text = Loc.t(str((w as Dictionary)["label_key"])) if w != null else Loc.t("hud.no_weapon")
	if _condition:
		_condition.value = float(state.get("health", 100.0))
	if _stamina:
		_stamina.value = float(state.get("stamina", 1.0)) * 100.0
	if _reticle:
		# The hands and weapon must not cover the interaction target: the
		# reticle fades out entirely when no weapon is raised.
		_reticle.modulate.a = 0.0 if w == null or bool((w as Dictionary)["is_tool"]) else 0.35 + float((w as Dictionary)["ads"]) * 0.6

	if _prompt:
		var interact = state.get("interact")
		_prompt.text = Loc.t(str((interact as Dictionary)["label_key"])) if interact != null else ""

	if _subtitles:
		for c in state.get("captions", []):
			var cd: Dictionary = c
			if _subtitles.get_child_count() > 3:
				_subtitles.get_child(0).queue_free()
			var l := Label.new()
			l.text = "⟨ %s · %d m ⟩" % [cd["direction"], int(float(cd["dist"]))]
			l.modulate = Color(0.72, 0.70, 0.65)
			_subtitles.add_child(l)

func show_subtitle(speaker: String, text: String) -> void:
	if not _subtitles:
		return
	var l := Label.new()
	l.text = ("%s: %s" % [speaker, text]) if speaker != "" else text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_subtitles.add_child(l)
	await get_tree().create_timer(4.2).timeout
	if is_instance_valid(l):
		l.queue_free()
