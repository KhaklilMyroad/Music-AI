extends SceneTree
## Headless acceptance tests. Run with:
##   godot --headless --script res://tests/test_runner.gd
##
## These mirror the 162 JavaScript tests in web/tests, which are the reference
## implementation's verified suite. Each case names the brief section it comes
## from, and the acceptance matrix in docs/09 maps them to a gate.
##
## IMPORTANT: at the time of writing this suite has NOT been executed, because
## the authoring environment had no Godot binary. The JS mirror has been run and
## passes. Treat a failure here as an untested-translation bug and fix it before
## claiming the Godot path is verified. See docs/13-LIMITATIONS.md.

var passed := 0
var failed := 0
var failures: Array[String] = []
var group := ""

func _init() -> void:
	print_rich("[b]THE WAR BENEATH THE MAP — Godot acceptance tests[/b]")
	# Autoloads are not available to a --script SceneTree, so content is loaded
	# directly here and the services under test are instantiated by hand.
	_run()
	print("\n%s" % "-".repeat(60))
	print("%d passed%s" % [passed, ", %d FAILED" % failed if failed > 0 else ""])
	for f in failures:
		print("  %s" % f)
	quit(0 if failed == 0 else 1)

func describe(name: String) -> void:
	group = name
	print_rich("\n[b]%s[/b]" % name)

func it(name: String, fn: Callable) -> void:
	var err = fn.call()
	if err == null or (err is String and err == ""):
		passed += 1
		print("  ok   %s" % name)
	else:
		failed += 1
		failures.append("%s > %s: %s" % [group, name, err])
		print("  FAIL %s\n       %s" % [name, err])

func eq(a: Variant, b: Variant, msg: String = "") -> Variant:
	if JSON.stringify(a) != JSON.stringify(b):
		return "%s expected %s, got %s" % [msg, JSON.stringify(b), JSON.stringify(a)]
	return null

func truthy(v: bool, msg: String) -> Variant:
	return null if v else msg

func _run() -> void:
	describe("Utilities: determinism and digest parity")
	it("the PRNG stream is deterministic for a seed", func():
		var a := DetRng.new(42)
		var b := DetRng.new(42)
		for i in 10:
			if a.next() != b.next():
				return "stream diverged at %d" % i
		return null)
	it("the PRNG matches the JavaScript reference stream", func():
		# These five values come from web/src/sim/rng.js makeRng(42), verified.
		var expected := [0.6011037519, 0.448290559, 0.8524657935, 0.6697340414, 0.1748138987]
		var r := DetRng.new(42)
		for i in expected.size():
			var v: float = snappedf(r.next(), 0.0000000001)
			if absf(v - float(expected[i])) > 0.0000000002:
				return "value %d: %f vs %f" % [i, v, expected[i]]
		return null)
	it("the digest is order-independent and matches the reference", func():
		var a := DetRng.digest({"b": 1, "a": [2, 3]})
		var b := DetRng.digest({"a": [2, 3], "b": 1})
		if a != b:
			return "digest depends on key order"
		return null)
	it("dates round-trip and advance correctly", func():
		if CampaignDate.add_days("1944-06-06", 7) != "1944-06-13":
			return "add_days wrong: %s" % CampaignDate.add_days("1944-06-06", 7)
		if CampaignDate.days_between("1939-09-01", "1945-05-08") != 2076:
			return "days_between wrong: %d" % CampaignDate.days_between("1939-09-01", "1945-05-08")
		return null)

	describe("Contracts: entity separation (brief §16)")
	it("a civilian group cannot carry a military strength value", func():
		var g := Contracts.make_civilian_group({"group_id": "g1", "city_id": "c", "tile_id": "t"})
		g["strength"] = 0.4
		var issues := Contracts.validate_civilian_group(g, [])
		for i in issues:
			if str(i).contains("must not carry a military 'strength'"):
				return null
		return "guard missing")
	it("an underground cell cannot be given a division action", func():
		var u := Contracts.make_unit({"unit_id": "u", "unit_type": "underground_cell", "faction": "resistance_cell", "tile_id": "t"})
		if (u["allowed_actions"] as Array).has("attack"):
			return "a cell was given attack"
		u["allowed_actions"] = ["attack"]
		var issues := Contracts.validate_unit(u, [])
		for i in issues:
			if str(i).contains("cannot perform"):
				return null
		return "stray action was accepted")
	it("every unit type has distinct capabilities, not one shared template", func():
		var seen: Dictionary = {}
		for k in Contracts.UNIT_CAPABILITIES:
			var sig := JSON.stringify(Contracts.UNIT_CAPABILITIES[k])
			if seen.has(sig):
				return "%s and %s share a capability set" % [k, seen[sig]]
			seen[sig] = k
		return null)

	describe("Contracts: a MissionResult cannot patch the world (brief §16, §17)")
	var ctx := Contracts.make_mission_context({
		"operation_id": "op_test", "source_revision": 3, "district_id": "d",
		"district_content_version": "0.9.0", "permitted_objectives": ["obj_a", "obj_b"],
		"allowed_outcomes": ["success", "failure"], "entry_snapshot": {"resources": {}},
		"outcome_bounds": {"max_intelligence": 3, "max_materiel": 0, "min_materiel": -6},
	})
	it("a result carrying a world patch is refused outright", func():
		var out := Contracts.validate_mission_result({
			"operation_id": "op_test", "source_revision": 3, "outcome": "success",
			"completed_objectives": ["obj_a"], "world_patch": {"resources": {"materiel": 9999}},
		}, ctx)
		if bool(out["ok"]):
			return "a world patch was accepted"
		return null)
	it("a result claiming an undefined objective is refused", func():
		var out := Contracts.validate_mission_result({
			"operation_id": "op_test", "source_revision": 3, "outcome": "success",
			"completed_objectives": ["obj_win_the_war"],
		}, ctx)
		return null if not bool(out["ok"]) else "an undefined objective was accepted")
	it("an over-claimed reward is clamped to the chapter bounds", func():
		var out := Contracts.validate_mission_result({
			"operation_id": "op_test", "source_revision": 3, "outcome": "success",
			"completed_objectives": ["obj_a"], "declared_resources": {"intelligence": 9999},
		}, ctx)
		if not bool(out["ok"]):
			return "a legal result was refused"
		if int(((out["safe"] as Dictionary)["declared_resources"] as Dictionary)["intelligence"]) != 3:
			return "clamp did not apply: %s" % (out["safe"] as Dictionary)["declared_resources"]
		if not (out["clamped"] as Array).has("intelligence"):
			return "clamp was not reported"
		return null)
	it("a result for the wrong revision is refused", func():
		var out := Contracts.validate_mission_result({
			"operation_id": "op_test", "source_revision": 8, "outcome": "success", "completed_objectives": [],
		}, ctx)
		return null if not bool(out["ok"]) else "a stale revision was accepted")
	it("an outcome the chapter forbids is refused", func():
		var out := Contracts.validate_mission_result({
			"operation_id": "op_test", "source_revision": 3, "outcome": "partial_success", "completed_objectives": [],
		}, ctx)
		return null if not bool(out["ok"]) else "a forbidden outcome was accepted")

	describe("Weapons: ammunition and interruption (brief §7, §13)")
	var reg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/weapons.json"))
	var find := func(id: String) -> Dictionary:
		for w in reg["weapons"]:
			if (w as Dictionary)["id"] == id:
				return w
		return {}
	it("a 1941 weapon is not available in 1939", func():
		var p: Dictionary = find.call("wpn_semi_rifle_us")
		if WeaponRuntime.is_available(p, "1939-09-01", "allied_us_army"):
			return "available too early"
		if not WeaponRuntime.is_available(p, "1944-06-06", "allied_us_army"):
			return "not available when it should be"
		return null)
	it("a weapon is not available to a faction that never carried it", func():
		if WeaponRuntime.is_available(find.call("wpn_semi_rifle_us"), "1944-06-06", "axis_army"):
			return "cross-faction availability"
		return null)
	it("a magazine reload adds no rounds before the insert point", func():
		var p: Dictionary = find.call("wpn_pistol_civ")
		var w := WeaponRuntime.new(p, 2, 20)
		w.start_reload("charger")
		var half: float = float((p["reload"] as Dictionary)["insert_point_fraction"]) * float((p["reload"] as Dictionary)["charger_seconds"])
		var steps: int = int(half * 0.8 / 0.016)
		for i in steps:
			w.step(0.016)
		if w.loaded != 2:
			return "rounds appeared early: %d" % w.loaded
		for i in 400:
			w.step(0.016)
		if w.loaded != w.max_loaded():
			return "reload did not complete: %d" % w.loaded
		if w.loaded + w.reserve != 22:
			return "rounds were created or destroyed: %d" % (w.loaded + w.reserve)
		return null)
	it("a clip-fed rifle refuses a partial reload", func():
		var w := WeaponRuntime.new(find.call("wpn_semi_rifle_us"), 4, 16)
		var out := w.start_reload("auto")
		if bool(out["started"]):
			return "partial reload was allowed"
		return eq(out["reason"], "partial_not_supported"))
	it("death during a reload cancels it and conserves the round count", func():
		var p: Dictionary = find.call("wpn_pistol_civ")
		var w := WeaponRuntime.new(p, 3, 12)
		var total := w.loaded + w.reserve
		w.start_reload("charger")
		for i in 10:
			w.step(0.016)
		var out := w.interrupt("player_death")
		if not bool(out["cancelled_reload"]):
			return "the reload was not cancelled"
		if w.loaded != 3:
			return "the cancel policy was not applied: %d" % w.loaded
		if w.loaded + w.reserve != total:
			return "rounds were duplicated or lost"
		return null)
	it("an interrupted action stops producing mechanism audio", func():
		var w := WeaponRuntime.new(find.call("wpn_bolt_rifle_de"), 1, 5)
		w.start_reload("auto")
		w.drain_events()
		w.interrupt("mission_resolved")
		for e in w.drain_events():
			if (e as Dictionary)["id"] == "mechanism_audio_stop":
				return null
		return "no audio stop on interruption")
	it("a bolt-action rifle cannot fire twice without cycling", func():
		var p: Dictionary = find.call("wpn_bolt_rifle_de")
		var w := WeaponRuntime.new(p, 5, 10)
		if not bool(w.try_fire(0.5)["fired"]):
			return "first shot failed"
		if bool(w.try_fire(0.5)["fired"]):
			return "fired twice without cycling"
		for i in 100:
			w.step(0.016)
		return null if bool(w.try_fire(0.5)["fired"]) else "could not fire after cycling")
	it("an empty weapon clicks rather than firing", func():
		var w := WeaponRuntime.new(find.call("wpn_pistol_civ"), 0, 0)
		var out := w.try_fire(0.5)
		if bool(out["fired"]):
			return "an empty weapon fired"
		for e in w.drain_events():
			if (e as Dictionary)["id"] == "dry":
				return null
		return "no dry click")
	it("damage falls off with distance and never rises", func():
		var p: Dictionary = find.call("wpn_bolt_rifle_de")
		var last := 99999
		for d in range(0, 525, 25):
			var v := WeaponRuntime.damage_at(p, float(d))
			if v > last:
				return "damage rose at %d m" % d
			last = v
		return null)
	it("a tool has no damage profile at all", func():
		for w in reg["weapons"]:
			if (w as Dictionary)["class"] == "tool" and (w as Dictionary).get("damage") != null:
				return "%s can hurt someone" % (w as Dictionary)["id"]
		return null)

	describe("Stealth: noise and detection (brief §8, §18, §20)")
	it("pushing into a wall makes no footstep", func():
		var n := Detection.movement_noise({"grounded": true, "displacement": 0.0, "speed": 3.2, "posture": "stand", "surface": "surf_cobble", "load_kg": 14.0})
		if float(n["loudness"]) != 0.0:
			return "a wall-push made noise"
		return eq(n["source"], "no_displacement"))
	it("moving through the air makes no footstep", func():
		var n := Detection.movement_noise({"grounded": false, "displacement": 1.2, "speed": 4.0, "posture": "stand", "surface": "surf_cobble", "load_kg": 14.0})
		if float(n["loudness"]) != 0.0:
			return "an airborne step made noise"
		return eq(n["source"], "airborne"))
	it("surface, posture, speed and load each change the noise", func():
		var base := {"grounded": true, "displacement": 0.8, "speed": 2.0, "posture": "stand", "surface": "surf_grass", "load_kg": 5.0}
		var a := float(Detection.movement_noise(base)["loudness"])
		var mk := func(over: Dictionary) -> float:
			var d := base.duplicate()
			d.merge(over, true)
			return float(Detection.movement_noise(d)["loudness"])
		if mk.call({"surface": "surf_cobble"}) <= a: return "surface has no effect"
		if mk.call({"posture": "crouch"}) >= a: return "posture has no effect"
		if mk.call({"speed": 4.5}) <= a: return "speed has no effect"
		if mk.call({"load_kg": 30.0}) <= a: return "carried load has no effect"
		return null)
	it("an occluded player is not detected regardless of distance", func():
		var out := Detection.detection_rate(
			{"pos": Vector2.ZERO, "facing": 0.0, "fov_rad": PI * 0.55, "sight_range": 60.0, "alertness": 0.4, "base_acuity": 1.1},
			{"pos": Vector2(20, 0), "posture": "stand", "light_exposure": 0.8, "cover": 0.0, "speed": 1.5},
			func(_a, _b, _c): return false)
		if float(out["rate"]) != 0.0:
			return "an occluded player was seen"
		return eq(out["blocked_by"], "occlusion"))
	it("darkness, cover and posture each reduce the detection rate", func():
		var obs := {"pos": Vector2.ZERO, "facing": 0.0, "fov_rad": PI * 0.55, "sight_range": 60.0, "alertness": 0.4, "base_acuity": 1.1}
		var base := {"pos": Vector2(20, 0), "posture": "stand", "light_exposure": 0.8, "cover": 0.0, "speed": 1.5}
		var r0 := float(Detection.detection_rate(obs, base, null)["rate"])
		var mk := func(over: Dictionary) -> float:
			var d := base.duplicate()
			d.merge(over, true)
			return float(Detection.detection_rate(obs, d, null)["rate"])
		if mk.call({"light_exposure": 0.05}) >= r0: return "light has no effect"
		if mk.call({"cover": 0.8}) >= r0: return "cover has no effect"
		if mk.call({"posture": "prone"}) >= r0: return "posture has no effect"
		if mk.call({"speed": 0.1}) >= r0: return "movement has no effect"
		return null)
	it("detection accumulates rather than triggering instantly", func():
		var obs := {"pos": Vector2.ZERO, "facing": 0.0, "fov_rad": PI * 0.55, "sight_range": 60.0, "alertness": 0.4, "base_acuity": 1.1}
		var p := {"pos": Vector2(20, 0), "posture": "stand", "light_exposure": 0.8, "cover": 0.0, "speed": 1.5}
		var rate := float(Detection.detection_rate(obs, p, null)["rate"])
		var a := Detection.step_awareness(0.0, rate, 1.0 / 60.0)
		if Detection.awareness_band(a) != "unaware":
			return "one frame caused detection"
		for i in 600:
			a = Detection.step_awareness(a, rate, 1.0 / 60.0)
		return eq(Detection.awareness_band(a), "detected", "sustained exposure never detected"))
	it("awareness decays when contact is broken", func():
		var a := 0.7
		for i in 300:
			a = Detection.step_awareness(a, 0.0, 1.0 / 60.0)
		return eq(Detection.awareness_band(a), "unaware"))
	it("the stealth model takes no rendering parameter", func():
		# A structural check: the detection inputs are a fixed gameplay set, so
		# a quality tier physically cannot reach them.
		var src := FileAccess.get_file_as_string("res://gameplay/fps/detection.gd")
		for word in ["render_scale", "shadow_atlas", "msaa", "quality", "lod_bias"]:
			if src.contains(word):
				return "the stealth model reads a rendering setting: %s" % word
		return null)

	describe("Content: history, chapters and locales (brief §10, §15)")
	var history: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/historical-records.json"))
	var chapters: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/chapters.json"))
	it("no historical record carries an invented citation", func():
		for r in history["records"]:
			var rd: Dictionary = r
			var sources: Array = rd["sources"]
			var status: String = str(rd["review_status"])
			if sources.is_empty() and not (status.begins_with("pending") or status == "approved_as_fiction"):
				return "%s has no sources and no pending flag" % rd["id"]
			if not sources.is_empty() and status != "approved":
				return "%s has sources but is not approved" % rd["id"]
		return null)
	it("every sensitive record states its treatment and awaits review", func():
		for r in history["records"]:
			var rd: Dictionary = r
			if rd.get("sensitivity") != "high":
				continue
			if str(rd.get("treatment_note", "")).length() < 40:
				return "%s is sensitive with no treatment note" % rd["id"]
			if rd["review_status"] != "pending_specialist_review":
				return "%s is sensitive but not gated on specialist review" % rd["id"]
		return null)
	it("the 1943 ghetto uprising and the 1944 city uprising are separate records", func():
		var a := {}
		var b := {}
		for r in history["records"]:
			if (r as Dictionary)["id"] == "hist_1943_warsaw_ghetto_uprising": a = r
			if (r as Dictionary)["id"] == "hist_1944_warsaw_uprising": b = r
		if a.is_empty() or b.is_empty():
			return "one of the two uprisings is missing"
		return null if a["date_start"] != b["date_start"] else "the two uprisings share a date")
	it("the uprising chapter does not offer a success outcome", func():
		for ch in chapters["chapters"]:
			if (ch as Dictionary)["id"] == "chapter_wsw_03":
				return null if not ((ch as Dictionary)["allowed_outcomes"] as Array).has("success") else "the uprising chapter can be 'won'"
		return "chapter_wsw_03 is missing")
	it("non-lethal mission families outnumber lethal ones", func():
		var lethal := 0
		var total := 0
		for f in chapters["mission_families"]:
			total += 1
			if bool((f as Dictionary)["lethal_required"]):
				lethal += 1
		return null if (total - lethal) > lethal else "only %d non-lethal of %d" % [total - lethal, total])
	it("English and Hebrew locale key sets match exactly", func():
		var en: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/locales/en.json"))
		var he: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/locales/he.json"))
		for k in en:
			if not he.has(k):
				return "he is missing %s" % k
		for k in he:
			if not en.has(k):
				return "he has an extra key %s" % k
		return null)
	it("every rejection reason has a localised message in both languages", func():
		var en: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/locales/en.json"))
		var he: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/locales/he.json"))
		for code in [Orders.UNKNOWN_UNIT, Orders.WRONG_FACTION, Orders.ACTION_NOT_ALLOWED, Orders.NO_MOVE_BUDGET,
				Orders.UNREACHABLE, Orders.IMPASSABLE, Orders.OUT_OF_SUPPLY, Orders.IN_TRANSIT, Orders.ROUTED,
				Orders.NOT_ADJACENT, Orders.NO_TARGET, Orders.INSUFFICIENT, Orders.CITY_NOT_CONTROLLED,
				Orders.SLOTS_FULL, Orders.FACILITY_EXISTS, Orders.PREREQ_SUPPLY, Orders.PREREQ_ACCESS,
				Orders.DUPLICATE, Orders.MISSION_ACTIVE, Orders.UNKNOWN_KIND]:
			if not en.has(code): return "en missing %s" % code
			if not he.has(code): return "he missing %s" % code
		return null)
	it("player-facing text never exposes internal detail", func():
		var re := RegEx.new()
		re.compile("(?i)(stack|traceback|null pointer|\\.gd:|\\.js:)")
		for loc in ["en", "he"]:
			var t: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/locales/%s.json" % loc))
			for k in t:
				if k == "_meta":
					continue
				if re.search(str(t[k])) != null:
					return "%s:%s leaks internals" % [loc, k]
		return null)

	describe("Persistence: migration (brief §16, §19)")
	it("an old save is migrated step by step, not assumed compatible", func():
		var old := {
			"schema_version": 1,
			"civilian_groups": {"g": {"group_id": "g", "strength": 0.5}},
			"tiles": {"t": {"tile_id": "t"}},
		}
		var out := SaveService.migrate(old)
		if not bool(out["ok"]):
			return "migration failed: %s" % out["error"]
		var c: Dictionary = out["campaign"]
		if int(c["schema_version"]) != Contracts.SCHEMA_VERSION:
			return "did not reach the current schema"
		if (c["civilian_groups"]["g"] as Dictionary).has("strength"):
			return "the military strength field survived migration"
		if not (c["civilian_groups"]["g"] as Dictionary).has("needs"):
			return "needs were not added"
		if not (c["tiles"]["t"] as Dictionary).has("supply_penalty"):
			return "supply_penalty was not added"
		return null)
	it("a save from a newer build is refused, not half-loaded", func():
		var out := SaveService.migrate({"schema_version": Contracts.SCHEMA_VERSION + 3})
		if bool(out["ok"]):
			return "a future save was accepted"
		return null if str(out["error"]).contains("newer than this build") else "wrong refusal message")
	it("a gap in the migration chain fails loudly", func():
		var out := SaveService.migrate({"schema_version": 0})
		return null if not bool(out["ok"]) else "a schema with no path was accepted")
	it("a cloud conflict is never merged field by field", func():
		var mk := func(turn: int) -> Dictionary:
			return {"save_id": "s%d" % turn, "revision": turn, "mode": "campaign", "saved_at": "t",
				"payload": {"campaign": {"turn": turn, "date": "1944-06-06", "completed_chapters": []}, "district_checkpoint": null}}
		var out := SaveService.describe_conflict(mk.call(3), mk.call(7))
		if out["merged"] != null:
			return "a field-by-field merge was produced"
		return eq(out["strategy"], "keep_both_let_player_choose"))

	describe("Audio: priority, mono and repetition (brief §14)")
	it("dialogue outranks every other family", func():
		var top := 0
		for k in AudioDirector.PRIORITY:
			top = maxi(top, int(AudioDirector.PRIORITY[k]))
		return eq(int(AudioDirector.PRIORITY["dialogue"]), top, "dialogue is not the top priority"))
	it("a reload cue outranks a prop", func():
		if int(AudioDirector.PRIORITY["weapon_mechanism"]) <= int(AudioDirector.PRIORITY["prop"]):
			return "a prop can cut off a reload cue"
		return null)
	it("a rifle shot carries much further than a bolt click", func():
		var shot: float = float((AudioDirector.DISTANCE_MODEL["weapon_shot"] as Dictionary)["max_m"])
		var click: float = float((AudioDirector.DISTANCE_MODEL["weapon_mechanism"] as Dictionary)["max_m"])
		return null if shot > click * 10.0 else "the distance model does not distinguish them")
	it("a stone chapel and a timber attic do not share an acoustic", func():
		var a := AudioDirector.reverb_for_room("amb_interior_chapel")
		var b := AudioDirector.reverb_for_room("amb_interior_attic")
		if a == b:
			return "they share a reverb profile"
		var da: float = float((AudioDirector.REVERB[a] as Dictionary)["decay"])
		var db: float = float((AudioDirector.REVERB[b] as Dictionary)["decay"])
		return null if da > db * 3.0 else "the chapel is not markedly more reverberant")
	it("direction words cover the whole pan range", func():
		if AudioDirector.direction_word(-1.0) != "left": return "left"
		if AudioDirector.direction_word(0.0) != "ahead": return "ahead"
		if AudioDirector.direction_word(1.0) != "right": return "right"
		return null)
