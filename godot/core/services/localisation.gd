extends Node
## Localisation with RTL support (brief §10). Mixed-direction text — a Hebrew
## sentence with a Latin place name or a number — is handled by isolating the
## embedded run, not by reordering it by hand.

signal locale_changed(locale: String)

const RLM := "‏"
const LRM := "‎"
const FSI := "⁨"
const PDI := "⁩"

var locale: String = "en"
var direction: String = "ltr"
var _table: Dictionary = {}
var _tables: Dictionary = {}
var missing_keys: Dictionary = {}

func _ready() -> void:
	_load_tables()
	var preferred := "he" if OS.get_locale_language() == "he" else "en"
	set_locale(str(Settings.get_value("language")) if _tables.has(str(Settings.get_value("language"))) else preferred)
	Settings.changed.connect(func(id, v): if id == "language": set_locale(str(v)))

func _load_tables() -> void:
	var dir := DirAccess.open("res://data/locales")
	if dir == null:
		push_error("no locale files found")
		return
	for f in dir.get_files():
		if not f.ends_with(".json"):
			continue
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/locales/" + f))
		if parsed is Dictionary:
			_tables[f.get_basename()] = parsed

func available() -> Array:
	var out: Array = []
	for code in _tables:
		var meta: Dictionary = (_tables[code] as Dictionary).get("_meta", {})
		out.append({"code": code, "name": meta.get("name", code), "dir": meta.get("direction", "ltr")})
	return out

func set_locale(code: String) -> String:
	locale = code if _tables.has(code) else "en"
	_table = _tables.get(locale, {})
	direction = str((_table.get("_meta", {}) as Dictionary).get("direction", "ltr"))
	TranslationServer.set_locale(locale)
	# RTL affects layout, so the whole UI root is told, not individual labels.
	var root := get_tree().root if get_tree() else null
	if root:
		root.set("layout_direction", Control.LAYOUT_DIRECTION_RTL if direction == "rtl" else Control.LAYOUT_DIRECTION_LTR)
	locale_changed.emit(locale)
	return locale

## A missing key returns the key itself, visibly, so a gap is caught in review
## instead of shipping as blank text.
func t(key: String, vars: Dictionary = {}) -> String:
	if not _table.has(key):
		missing_keys[key] = true
		push_warning("[i18n] missing key %s in %s" % [key, locale])
		return key
	var s: String = str(_table[key])
	for k in vars:
		s = s.replace("{%s}" % k, isolate(str(vars[k])))
	return s

func has(key: String) -> bool:
	return _table.has(key)

## Wrap an interpolated value so its own direction cannot flip the sentence.
func isolate(v: String) -> String:
	return (FSI + v + PDI) if direction == "rtl" else v

func num(n: float, digits: int = 0) -> String:
	var s := String.num(n, digits)
	return (LRM + s) if direction == "rtl" else s

func delta(n: float) -> String:
	var s := ("+" + String.num(n, 0)) if n > 0 else String.num(n, 0)
	return (LRM + s) if direction == "rtl" else s

func date(iso: String) -> String:
	var p := iso.split("-")
	var months_he := ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
	var months_en := ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
	var m: int = int(p[1]) - 1
	if locale == "he":
		return "%s%d ב%s %s" % [LRM, int(p[2]), months_he[m], p[0]]
	return "%d %s %s" % [int(p[2]), months_en[m], p[0]]

## Parity check used by tests/test_content.gd: every key must exist in every
## shipped locale, or the release gate fails.
func locale_parity() -> Dictionary:
	var base: Array = (_tables.get("en", {}) as Dictionary).keys()
	var out: Dictionary = {}
	for code in _tables:
		var t2: Dictionary = _tables[code]
		var missing: Array = []
		var extra: Array = []
		for k in base:
			if not t2.has(k):
				missing.append(k)
		for k in t2.keys():
			if not base.has(k):
				extra.append(k)
		out[code] = {"missing": missing, "extra": extra, "total": t2.size()}
	return out
