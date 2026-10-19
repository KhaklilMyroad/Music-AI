extends Control
## Launch and content verification (brief §11). The first screen tells the
## player what is installed, what is missing and how large it is, then restores
## the last safe state or offers a new campaign.

@onready var _steps: VBoxContainer = $Centre/Steps
@onready var _progress: ProgressBar = $Centre/Progress
@onready var _actions: VBoxContainer = $Centre/Actions
@onready var _subtitle: Label = $Centre/Subtitle

var _done := 0
var _total := 4

func _ready() -> void:
	$Centre/Title.text = Loc.t("app.title")
	_verify()

func _step(label: String, ok: bool, detail: String = "") -> void:
	var l := Label.new()
	l.text = "%s  %s%s" % ["OK " if ok else "!! ", label, (" — " + detail) if detail != "" else ""]
	l.modulate = Color(0.78, 0.85, 0.72) if ok else Color(0.85, 0.45, 0.35)
	_steps.add_child(l)
	_done += 1
	_progress.value = float(_done) / float(_total)
	await get_tree().process_frame

func _verify() -> void:
	var summary := ContentDB.load_all()
	await _step(Loc.t("menu.history"), summary["errors"].is_empty(),
		"%d installed, %d not installed" % [summary["installed"], summary["missing"]])

	var probe := Campaign.new_campaign({"date": "1944-06-06"})
	var issues := Contracts.validate_campaign(probe)
	await _step("data contracts", issues.is_empty(), "%d tiles" % (probe["tiles"] as Dictionary).size() if issues.is_empty() else issues[0])

	var blockers := ContentDB.editorial_blockers()
	# An editorial blocker does not stop the build: it stops a chapter shipping.
	# It is surfaced here so it cannot be forgotten.
	await _step("editorial register", true, "%d open items" % blockers.size())

	var resume := Saves.load_slot("auto")
	await _step(Loc.t("menu.saves"), true,
		("week %d" % int((resume["campaign"] as Dictionary)["turn"])) if bool(resume["ok"]) else "no save")
	if bool(resume["ok"]) and str(resume.get("recovered_from", "")) != "":
		_subtitle.text = Loc.t("error.save_corrupt")
	else:
		_subtitle.text = ""

	_offer(resume)

func _offer(resume: Dictionary) -> void:
	if bool(resume["ok"]):
		_add_button(Loc.t("menu.continue"), func():
			Campaign.adopt(resume["campaign"])
			_handle_recovery(resume))
	_add_button(Loc.t("menu.new_campaign"), func():
		Campaign.adopt(Campaign.new_campaign({"date": "1944-06-06", "seed": int(Time.get_unix_time_from_system()) & 0x7fffffff}))
		get_tree().change_scene_to_file("res://scenes/strategic_map.tscn"))
	_add_button(Loc.t("menu.sandbox"), func():
		Campaign.adopt(Campaign.new_campaign({"date": "1944-06-06", "mode": "sandbox", "campaign_id": "cmp_sandbox"}))
		get_tree().change_scene_to_file("res://scenes/strategic_map.tscn"))
	if ContentDB.missing_districts.size() > 0:
		var l := Label.new()
		l.text = "%s: %s" % [Loc.t("error.content_missing"), ", ".join(ContentDB.missing_districts)]
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.modulate = Color(0.78, 0.56, 0.21)
		_actions.add_child(l)

## A pending operation found in the save decides where the player lands. The
## returning-player journey never shows a duplicate reward and never pretends
## an interrupted mission finished.
func _handle_recovery(resume: Dictionary) -> void:
	var rec := Campaign.recover()
	match str(rec["action"]):
		"resume_mission", "restart_mission":
			get_tree().change_scene_to_file("res://scenes/mission.tscn")
		_:
			get_tree().change_scene_to_file("res://scenes/strategic_map.tscn")

func _add_button(text: String, fn: Callable) -> void:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(240, 48)
	b.pressed.connect(fn)
	_actions.add_child(b)
