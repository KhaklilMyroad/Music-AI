extends RefCounted
class_name Hex
## Pointy-top hexes in axial coordinates. One module, so the map view, the
## pathfinder and the turn resolver cannot disagree about what "adjacent" means.

const DIRS := [Vector2i(1, 0), Vector2i(1, -1), Vector2i(0, -1), Vector2i(-1, 0), Vector2i(-1, 1), Vector2i(0, 1)]

static func key(q: int, r: int) -> String:
	return "%d,%d" % [q, r]

static func neighbors(q: int, r: int) -> Array:
	var out: Array = []
	for d in DIRS:
		out.append(Vector2i(q + d.x, r + d.y))
	return out

static func distance(aq: int, ar: int, bq: int, br: int) -> int:
	var ay: int = -aq - ar
	var by: int = -bq - br
	return maxi(maxi(abs(aq - bq), abs(ay - by)), abs(ar - br))

static func to_pixel(q: int, r: int, size: float) -> Vector2:
	return Vector2(size * sqrt(3.0) * (float(q) + float(r) / 2.0), size * 1.5 * float(r))

static func from_pixel(p: Vector2, size: float) -> Vector2i:
	var q: float = (p.x * sqrt(3.0) / 3.0 - p.y / 3.0) / size
	var r: float = (p.y * 2.0 / 3.0) / size
	var cx: float = q
	var cz: float = r
	var cy: float = -cx - cz
	var rx: int = int(round(cx))
	var ry: int = int(round(cy))
	var rz: int = int(round(cz))
	var dx: float = abs(float(rx) - cx)
	var dy: float = abs(float(ry) - cy)
	var dz: float = abs(float(rz) - cz)
	if dx > dy and dx > dz:
		rx = -ry - rz
	elif dy > dz:
		ry = -rx - rz
	else:
		rz = -rx - ry
	return Vector2i(rx, rz)
