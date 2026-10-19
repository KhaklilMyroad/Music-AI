extends RefCounted
class_name DetRng
## Deterministic, seedable PRNG shared by the turn resolver and every mission
## seed. The same (state, seed) must always produce the same outcome, because
## docs/03-TURN-RESOLUTION-SPEC.md promises determinism and the acceptance
## matrix tests it. randi() is never used in simulation code.
##
## Mirrors mulberry32 in web/src/sim/rng.js so both implementations produce the
## same stream for the same seed.

var _a: int = 0

func _init(seed_value: int = 0x9e3779b9) -> void:
	_a = seed_value & 0xffffffff
	if _a == 0:
		_a = 0x9e3779b9

func next() -> float:
	_a = (_a + 0x6d2b79f5) & 0xffffffff
	var t: int = _a
	t = _imul(t ^ (t >> 15), t | 1)
	t = (t ^ (t + _imul(t ^ (t >> 7), t | 61))) & 0xffffffff
	return float((t ^ (t >> 14)) & 0xffffffff) / 4294967296.0

func int_range(lo: int, hi: int) -> int:
	return lo + int(next() * float(hi - lo + 1))

func float_range(lo: float, hi: float) -> float:
	return lo + next() * (hi - lo)

func chance(p: float) -> bool:
	return next() < p

## A labelled sub-stream, so adding a system cannot shift another system's numbers.
func fork(label: String) -> DetRng:
	return DetRng.new(hash_string(label) ^ (_imul(_a, 2654435761)))

func shuffled(arr: Array) -> Array:
	var out := arr.duplicate()
	for i in range(out.size() - 1, 0, -1):
		var j: int = int(next() * float(i + 1))
		var tmp = out[i]
		out[i] = out[j]
		out[j] = tmp
	return out

## 32-bit multiply with wraparound, matching Math.imul.
static func _imul(a: int, b: int) -> int:
	var al: int = a & 0xffff
	var ah: int = (a >> 16) & 0xffff
	var bl: int = b & 0xffff
	var bh: int = (b >> 16) & 0xffff
	return ((al * bl) + (((ah * bl + al * bh) << 16) & 0xffffffff)) & 0xffffffff

## FNV-1a, used for sub-stream labels and the save integrity digest.
static func hash_string(s: String) -> int:
	var h: int = 0x811c9dc5
	for i in s.length():
		h = h ^ s.unicode_at(i)
		h = _imul(h, 0x01000193)
	return h & 0xffffffff

## Stable JSON: keys sorted recursively, so a digest of equal states matches.
static func stable_stringify(value: Variant) -> String:
	return JSON.stringify(_sorted(value))

static func _sorted(v: Variant) -> Variant:
	if v is Array:
		var out: Array = []
		for x in v:
			out.append(_sorted(x))
		return out
	if v is Dictionary:
		var keys: Array = (v as Dictionary).keys()
		keys.sort()
		var d: Dictionary = {}
		for k in keys:
			d[k] = _sorted(v[k])
		return d
	return v

## Content digest for SaveEnvelope.integrity. An integrity tool, not a security
## control: a determined local attacker can recompute it. Treat it as such.
static func digest(value: Variant) -> String:
	var s := stable_stringify(value)
	var h1: int = 0x811c9dc5
	var h2: int = 0x01000193
	for i in s.length():
		var c: int = s.unicode_at(i)
		h1 = _imul(h1 ^ c, 0x01000193)
		h2 = _imul((h2 + c * (i + 1)) & 0xffffffff, 0x85ebca6b)
	return "%08x%08x" % [h1 & 0xffffffff, h2 & 0xffffffff]
