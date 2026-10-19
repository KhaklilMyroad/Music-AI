extends Node
## Saving, integrity, last-known-good and schema migration (brief §19).
##
## Write protocol (survives process termination mid-write):
##   1 write <slot>.part with write_complete=false
##   2 attach the integrity digest and rewrite <slot>.part complete
##   3 copy the current <slot> to <slot>.lkg
##   4 rename <slot>.part -> <slot>
## A crash at any step leaves either the old save or the .lkg intact.
##
## Mobile reality: we never depend on receiving a shutdown callback. The game
## saves at meaningful boundaries and whenever focus is lost.

signal save_failed(code: String, detail: String)
signal save_written(slot: String, reason: String)

const DIR := "user://saves/"
const ENGINE_BUILD := "godot-0.1.0"

const ERR_NOT_FOUND := "save.not_found"
const ERR_CORRUPT := "save.corrupt"
const ERR_INCOMPLETE := "save.incomplete_write"
const ERR_INTEGRITY := "save.integrity_mismatch"
const ERR_UNSUPPORTED := "save.unsupported_schema"
const ERR_NO_SPACE := "save.no_space"

func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DIR))
	if not DirAccess.dir_exists_absolute(DIR):
		DirAccess.make_dir_recursive_absolute(DIR)

func _slot_path(slot: String) -> String: return DIR + "%s.json" % slot
func _lkg_path(slot: String) -> String: return DIR + "%s.lkg.json" % slot
func _part_path(slot: String) -> String: return DIR + "%s.part.json" % slot

## Durable write. `reason` is recorded so a QA log shows which boundary saved.
func write(slot: String, campaign: Dictionary, district_checkpoint: Variant, reason: String = "manual") -> Dictionary:
	var payload := {
		"campaign": campaign,
		"district_checkpoint": district_checkpoint,
		"reason": reason,
	}
	var env := {
		"schema_version": Contracts.SCHEMA_VERSION,
		"content_versions": _content_versions(),
		"save_id": "%s:%s:%d" % [campaign.get("campaign_id", "cmp"), slot, int(campaign.get("revision", 0))],
		"slot": slot,
		"mode": campaign.get("mode", "campaign"),
		"revision": int(campaign.get("revision", 0)),
		"saved_at": Time.get_datetime_string_from_system(true, true),
		"engine_build": ENGINE_BUILD,
		"payload": payload,
		"recovery": {"is_last_known_good": false, "write_complete": false, "previous_save_id": _peek_id(slot)},
		"integrity": null,
	}

	# step 1: incomplete marker
	if not _write_text(_part_path(slot), JSON.stringify(env)):
		return {}
	# step 2: digest over the payload only, so recovery metadata can change
	#         without invalidating it
	env["integrity"] = DetRng.digest(payload)
	env["recovery"]["write_complete"] = true
	if not _write_text(_part_path(slot), JSON.stringify(env)):
		return {}
	# step 3: roll the current save down to last-known-good
	if FileAccess.file_exists(_slot_path(slot)):
		var current := FileAccess.get_file_as_string(_slot_path(slot))
		_write_text(_lkg_path(slot), current)
	# step 4: publish
	var part := FileAccess.get_file_as_string(_part_path(slot))
	if not _write_text(_slot_path(slot), part):
		return {}
	DirAccess.remove_absolute(ProjectSettings.globalize_path(_part_path(slot)))
	save_written.emit(slot, reason)
	return env

## Load with full validation. Falls back to last-known-good and says which.
## Returns {"ok": bool, "code": String, "campaign": Dictionary,
##          "district_checkpoint": Variant, "source": String, "recovered_from": String}
func load_slot(slot: String, allow_lkg: bool = true) -> Dictionary:
	var primary := _attempt(_slot_path(slot), "primary")
	if primary["ok"]:
		return primary
	if not allow_lkg:
		return primary
	var lkg := _attempt(_lkg_path(slot), "last_known_good")
	if lkg["ok"]:
		lkg["recovered_from"] = primary["code"]
		return lkg
	# An orphaned .part may be the only thing left after a crash.
	var part := _attempt(_part_path(slot), "interrupted_part")
	if part["ok"]:
		part["recovered_from"] = primary["code"]
		return part
	return primary

func _attempt(path: String, source: String) -> Dictionary:
	var fail := func(code: String, detail: String) -> Dictionary:
		return {"ok": false, "code": code, "detail": detail, "source": source, "campaign": {}, "district_checkpoint": null, "recovered_from": ""}
	if not FileAccess.file_exists(path):
		return fail.call(ERR_NOT_FOUND, path)
	var txt := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(txt)
	if not (parsed is Dictionary):
		return fail.call(ERR_CORRUPT, "%s: unparseable" % path)
	var env: Dictionary = parsed
	var rec: Dictionary = env.get("recovery", {})
	if not bool(rec.get("write_complete", false)):
		return fail.call(ERR_INCOMPLETE, path)
	if str(env.get("integrity", "")) == "":
		return fail.call(ERR_CORRUPT, "integrity digest missing")
	if DetRng.digest(env.get("payload", {})) != str(env["integrity"]):
		return fail.call(ERR_INTEGRITY, path)
	var mig := migrate(((env.get("payload", {}) as Dictionary).get("campaign", {}) as Dictionary))
	if not mig["ok"]:
		return fail.call(ERR_UNSUPPORTED, str(mig["error"]))
	var issues := Contracts.validate_campaign(mig["campaign"])
	if not issues.is_empty():
		return fail.call(ERR_CORRUPT, "\n".join(issues))
	return {
		"ok": true, "code": "", "detail": "",
		"envelope": env, "campaign": mig["campaign"],
		"district_checkpoint": (env["payload"] as Dictionary).get("district_checkpoint", null),
		"source": source, "recovered_from": "",
	}

## Save list for the slot-selection screen: readable without loading each save.
func list_saves() -> Array:
	var out: Array = []
	var dir := DirAccess.open(DIR)
	if dir == null:
		return out
	for f in dir.get_files():
		if not f.ends_with(".json") or f.contains(".lkg.") or f.contains(".part."):
			continue
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(DIR + f))
		if not (parsed is Dictionary):
			out.append({"slot": f.get_basename(), "corrupt": true})
			continue
		var e: Dictionary = parsed
		var c: Dictionary = (e.get("payload", {}) as Dictionary).get("campaign", {})
		out.append({
			"slot": e.get("slot"), "save_id": e.get("save_id"), "revision": e.get("revision"),
			"mode": e.get("mode"), "saved_at": e.get("saved_at"),
			"turn": c.get("turn"), "date": c.get("date"),
			"reason": (e.get("payload", {}) as Dictionary).get("reason"),
			"in_mission": (e.get("payload", {}) as Dictionary).get("district_checkpoint") != null,
		})
	out.sort_custom(func(a, b): return str(a.get("saved_at", "")) > str(b.get("saved_at", "")))
	return out

func _write_text(path: String, text: String) -> bool:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		var err := FileAccess.get_open_error()
		# A full device is a player-facing condition, not a crash.
		var code := ERR_NO_SPACE if err == ERR_FILE_CANT_WRITE or err == ERR_OUT_OF_MEMORY else ERR_CORRUPT
		save_failed.emit(code, "%s (%d)" % [path, err])
		return false
	f.store_string(text)
	f.flush()
	f.close()
	return true

func _peek_id(slot: String) -> Variant:
	if not FileAccess.file_exists(_slot_path(slot)):
		return null
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(_slot_path(slot)))
	return (parsed as Dictionary).get("save_id", null) if parsed is Dictionary else null

func _content_versions() -> Dictionary:
	var out: Dictionary = {}
	for id in ContentDB.districts:
		out[id] = (ContentDB.districts[id] as Dictionary).get("content_version", "unknown")
	return out

# ------------------------------------------------------------- migrations ----
# A migration is explicit and ordered. Sharing JSON syntax is not
# compatibility: a save from a schema we have no migration for is refused,
# loudly, rather than half-loaded.

static func migrate(campaign_in: Dictionary) -> Dictionary:
	var c: Dictionary = campaign_in.duplicate(true)
	var v: int = int(c.get("schema_version", 1))
	if v > Contracts.SCHEMA_VERSION:
		return {"ok": false, "error": "save schema %d is newer than this build (%d); update the game to load it" % [v, Contracts.SCHEMA_VERSION], "campaign": {}}
	while v < Contracts.SCHEMA_VERSION:
		match v:
			1:
				if not c.has("networks"): c["networks"] = {}
				if not c.has("committed_operations"): c["committed_operations"] = []
				v = 2
			2:
				for gid in c.get("civilian_groups", {}):
					var g: Dictionary = c["civilian_groups"][gid]
					g.erase("strength")
					var needs: Dictionary = {"food": 1.0, "water": 1.0, "medicine": 1.0, "shelter": 1.0}
					for k in g.get("needs", {}):
						needs[k] = g["needs"][k]
					g["needs"] = needs
				v = 3
			3:
				for tid in c.get("tiles", {}):
					var t: Dictionary = c["tiles"][tid]
					if not t.has("supply_penalty"): t["supply_penalty"] = 0.0
				if not c.has("unlocked_equipment"): c["unlocked_equipment"] = []
				v = 4
			_:
				return {"ok": false, "error": "no migration path from schema %d to %d" % [v, Contracts.SCHEMA_VERSION], "campaign": {}}
		c["schema_version"] = v
	return {"ok": true, "error": "", "campaign": c}

## Cloud conflict handling: never merge field by field. Both branches are kept
## and described so the player chooses a continuation.
static func describe_conflict(local_env: Dictionary, remote_env: Dictionary) -> Dictionary:
	var d := func(e: Dictionary) -> Dictionary:
		var c: Dictionary = (e.get("payload", {}) as Dictionary).get("campaign", {})
		return {
			"save_id": e.get("save_id"), "revision": e.get("revision"),
			"turn": c.get("turn"), "date": c.get("date"), "mode": e.get("mode"),
			"saved_at": e.get("saved_at"),
			"completed_chapters": (c.get("completed_chapters", []) as Array).size(),
			"in_mission": (e.get("payload", {}) as Dictionary).get("district_checkpoint") != null,
		}
	return {"strategy": "keep_both_let_player_choose", "local": d.call(local_env), "remote": d.call(remote_env), "merged": null}
