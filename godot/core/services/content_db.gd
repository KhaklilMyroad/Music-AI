extends Node
## Content database. Loads the same JSON the web prototype and the tests use, so
## the two implementations cannot drift apart on content.
##
## Also carries the historical register (brief §15) with its provenance and
## review status, and the asset provenance registry.

signal content_loaded(summary: Dictionary)

const DATA := "res://data/"

var atlas: Dictionary = {}
var chapters: Dictionary = {}
var weapons: Dictionary = {}
var history: Dictionary = {}
var districts: Dictionary = {}
var provenance: Dictionary = {}

var installed_districts: PackedStringArray = []
var missing_districts: PackedStringArray = []
var load_errors: Array[String] = []

func _ready() -> void:
	load_all()

func load_all() -> Dictionary:
	atlas = _read("theaters.json")
	chapters = _read("chapters.json")
	weapons = _read("weapons.json")
	history = _read("historical-records.json")
	provenance = _read("asset-provenance.json", false)

	districts.clear()
	var dir := DirAccess.open(DATA + "districts")
	if dir:
		for f in dir.get_files():
			if not f.ends_with(".json"):
				continue
			var d: Dictionary = _read("districts/" + f)
			if d.has("id"):
				districts[d["id"]] = d
	installed_districts = PackedStringArray(districts.keys())

	# Content verification for the launch screen: which required locations are
	# not installed. The player is told the size and offered a download path;
	# the mission entry refuses rather than failing mid-load.
	var missing: Dictionary = {}
	for ch in chapters.get("chapters", []):
		var did: String = str(ch.get("district", ""))
		if did != "" and not districts.has(did):
			missing[did] = true
	missing_districts = PackedStringArray(missing.keys())

	var summary := {
		"installed": installed_districts.size(),
		"missing": missing_districts.size(),
		"chapters": (chapters.get("chapters", []) as Array).size(),
		"weapons": (weapons.get("weapons", []) as Array).size(),
		"history_records": (history.get("records", []) as Array).size(),
		"errors": load_errors.duplicate(),
	}
	content_loaded.emit(summary)
	return summary

func _read(rel: String, required: bool = true) -> Dictionary:
	var path := DATA + rel
	if not FileAccess.file_exists(path):
		if required:
			load_errors.append("missing content file: %s" % rel)
		return {}
	var txt := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(txt)
	if not (parsed is Dictionary):
		load_errors.append("unparseable content file: %s" % rel)
		return {}
	return parsed

# ------------------------------------------------------------------ lookups --

func chapter(id: String) -> Dictionary:
	for ch in chapters.get("chapters", []):
		if ch.get("id") == id:
			return ch
	return {}

func district(id: String) -> Dictionary:
	return districts.get(id, {})

func weapon(id: String) -> Dictionary:
	for w in weapons.get("weapons", []):
		if w.get("id") == id:
			return w
	return {}

func facility(id: String) -> Dictionary:
	for f in atlas.get("facility_catalog", []):
		if f.get("id") == id:
			return f
	return {}

func terrain_rule(terrain: String) -> Dictionary:
	return (atlas.get("terrain_rules", {}) as Dictionary).get(terrain, {"move_cost": 1, "cover": 0.1, "concealment": 0.1, "supply_draw": 1.0, "passable": true})

func timeline_events() -> Array:
	return chapters.get("timeline_events", [])

func turn_length_days() -> int:
	return int(chapters.get("turn_length_days", 7))

func history_record(id: String) -> Dictionary:
	for r in history.get("records", []):
		if r.get("id") == id:
			return r
	return {}

## Records a chapter may not ship without: a sensitive chapter needs a named
## specialist reviewer, and every history_ref needs a citation or an explicit
## pending flag. Called by the release gate in tests/test_content.gd.
func editorial_blockers() -> Array[String]:
	var out: Array[String] = []
	for ch in chapters.get("chapters", []):
		if ch.get("sensitivity") == "high" and ch.get("gate") != "specialist_review_required":
			out.append("%s is sensitive but not gated on specialist review" % ch.get("id"))
		for ref in ch.get("history_refs", []):
			var r := history_record(ref)
			if r.is_empty():
				out.append("%s references unknown history record %s" % [ch.get("id"), ref])
				continue
			var sources: Array = r.get("sources", [])
			var status: String = str(r.get("review_status", ""))
			if sources.is_empty() and not (status.begins_with("pending") or status == "approved_as_fiction"):
				out.append("%s has no sources and no pending flag" % ref)
	for w in weapons.get("weapons", []):
		if w.get("model_status") == "approved" and w.get("provenance_ref") == null:
			out.append("%s is an approved asset with no provenance record" % w.get("id"))
	return out
