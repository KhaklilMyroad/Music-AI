# 10 — Performance plan (PC)

**Every number here is an engineering target. None has been measured.** The
authoring environment had no GPU. Replace each target with a measured result,
with its conditions recorded, before quoting it to anyone.

## Renderer

**Forward+**, pinned in `godot/project.godot`. This is the deliberate opposite
of the earlier mobile configuration, and it is the whole technical reason the
art bar in `docs/06` is reachable: Forward+ provides SSIL, SDFGI, volumetric
fog, screen-space reflections and FSR2, which the mobile path does not.

Every one of them is a setting rather than a constant, because the floor GPU
must hold 60 FPS with all of them off and the art direction has to read
correctly either way.

| Feature | Why it is here |
|---|---|
| SDFGI (global illumination) | Interiors lit through a window read as interiors. Four short cascades at 0.2 m, because bocage is a corridor world of hedgerows and small rooms, not an open city. |
| SSIL | Bounce light in a barn or a cellar, where a single lamp is the only source. |
| SSAO | Contact shadows where geometry meets geometry — the brief's "contact with the ground". |
| Volumetric fog | A dawn lane and a shelled street read as air rather than a flat grey curtain. |
| Screen-space reflections | Wet cobble and glass. Off by default below `high`. |
| Depth of field | Near-field only, shallow, so the view model reads against the world without blurring gameplay. |
| FSR2 | Lets a mid-range GPU render at 0.85 scale and still look sharp, which is a bigger win than any single effect. |

Shadows use four parallel splits over a distance tied to the draw distance,
because a 256 × 224 m district would otherwise pop a shadow cascade in the
middle of a field.

## Quality presets

| Setting | low | medium | high | ultra |
|---|---|---|---|---|
| Render scale | 0.70 | 0.85 | 1.00 | 1.00 |
| Upscaler | FSR2 | FSR2 | FSR2 | off |
| Anti-aliasing | FXAA | MSAA 2× | MSAA 2× | MSAA 4× |
| Shadows | 1024 | 2048 | 4096 | 8192 |
| Textures | low | medium | high | high |
| Anisotropic | 2× | 4× | 8× | 16× |
| SSAO | — | yes | yes | yes |
| SSIL | — | — | yes | yes |
| SDFGI | — | — | yes | yes |
| Reflections | off | probes | screen space | screen space |
| Volumetric fog | — | — | yes | yes |
| Depth of field | — | — | yes | yes |
| Draw distance | 160 m | 260 m | 400 m | 600 m |
| Vegetation | 0.30 | 0.60 | 1.00 | 1.00 |
| Active characters | 10 | 18 | 28 | 40 |
| Audio voices | 32 | 48 | 64 | 96 |

Two invariants, both tested: a preset sets **every** graphics option, and
touching any one of them moves the preset to `custom` rather than lying about
what is applied.

## Acceptance targets

| Area | Target | Measurement conditions |
|---|---|---|
| Floor GPU | sustained 60 FPS at 1080p, `medium`, p95 ≤ 20 ms | representative combat and exploration, after a 10-minute warm-up |
| Recommended GPU | sustained 60 FPS at 1440p, `high` | same |
| High-end GPU | 120+ FPS at 1440p, or 60 FPS at 4K, `ultra` | same |
| Traversal hitches | no recurring post-warm-up stall above 50 ms | repeated indoor, outdoor and streaming-boundary routes |
| Shader compilation | no first-encounter stutter | Godot's pipeline pre-compilation on first launch; a cold-cache run is reported separately |
| Loading feedback | visible within 0.2 s | any operation that cannot complete immediately |
| Mission load | ≤ 6 s from an SSD, ≤ 15 s from a mechanical disk | named machine, cold and warm reported separately |
| Return to strategic play | ≤ 2 s | measured after result validation and the durable commit |
| Memory | ≤ 4 GB system, ≤ 6 GB VRAM at `high` 1440p | textures, audio, scene caches and transition peaks |
| CPU | the simulation thread never exceeds 4 ms per frame | a 120-turn campaign, profiled headlessly |
| Long session | targets held through 2 hours | no leak, no thermal throttle on a desktop, no handheld drain anomaly |

The PC targets are tighter than the mobile ones were. 60 FPS is a floor on PC,
not a stretch; 30 FPS is not an acceptable shipping target for a first-person
game with a mouse.

## Proposed hardware matrix (owner decision — `docs/11`)

| Tier | Proposed representative | Target |
|---|---|---|
| Minimum | GTX 1060 6 GB / RX 580 8 GB, 4-core CPU, 8 GB RAM, SSD | 1080p, `medium`, 60 FPS |
| Recommended | RTX 3060 / RX 6600 XT, 6-core CPU, 16 GB RAM | 1440p, `high`, 60 FPS |
| High | RTX 4070 or better, 8-core CPU, 16 GB RAM | 1440p `ultra` 120 FPS, or 4K 60 FPS |
| Handheld | Steam Deck, ROG Ally | 800p, `low`, 40 FPS locked — **needs its own pass**, see below |

The minimum tier is the one that matters. It also happens to be where SDFGI
and volumetric fog must be off and still look right, which is an art
constraint, not just a performance one.

**Verified compatibility, not "should work":** a Steam Deck claim requires a
Deck. Its 40 FPS cap, 16:10 800p screen, gamepad-and-trackpad input and 15 W
budget are a separate test pass, and none of it has been done. Do not put a
Deck badge on the store page before that pass exists.

## Memory strategy

The full strategic map and the full first-person world are never both resident.
The map is drawn on the 2D canvas, so entering a mission leaves the 3D renderer
free; the mission scene is disposed on return. Districts stream in 32 m chunks
with a 48 m preload radius. Validated campaign data is retained across the
transition; scene instances are not.

PC has far more headroom than a phone, but a 256 × 224 m district with 9 hostiles
and 4 civilians is also four times the area of the mobile one — the headroom was
spent on content, not banked.

## Reporting rules

Record build identifier, engine version, OS, CPU, GPU and driver version,
graphics API (Vulkan or Direct3D 12), preset, resolution, duration and
limitations **with every performance or visual claim**. Preserve failed-run
evidence and describe the fix.

A frame-time graph from one machine is not a performance claim. Three machines
across the matrix, each with its conditions recorded, is.
