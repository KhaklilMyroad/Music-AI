extends RefCounted
class_name CampaignDate
## Campaign dates are plain ISO strings in the save contract so a save stays
## readable and diffable. All arithmetic goes through here.

const SECONDS_PER_DAY := 86400

static func parse(iso: String) -> int:
	var p := iso.split("-")
	assert(p.size() == 3, "bad ISO date %s" % iso)
	return int(Time.get_unix_time_from_datetime_dict({
		"year": int(p[0]), "month": int(p[1]), "day": int(p[2]),
		"hour": 0, "minute": 0, "second": 0,
	}))

static func format(unix: int) -> String:
	var d := Time.get_datetime_dict_from_unix_time(unix)
	return "%04d-%02d-%02d" % [d["year"], d["month"], d["day"]]

static func add_days(iso: String, days: int) -> String:
	return format(parse(iso) + days * SECONDS_PER_DAY)

static func days_between(a: String, b: String) -> int:
	return int(round(float(parse(b) - parse(a)) / float(SECONDS_PER_DAY)))

static func is_on_or_after(a: String, b: String) -> bool:
	return parse(a) >= parse(b)

static func is_before(a: String, b: String) -> bool:
	return parse(a) < parse(b)

## Inclusive window test; an empty bound is open-ended.
static func in_window(iso: String, from_iso: String, to_iso: String) -> bool:
	if from_iso != "" and is_before(iso, from_iso):
		return false
	if to_iso != "" and is_before(to_iso, iso):
		return false
	return true
