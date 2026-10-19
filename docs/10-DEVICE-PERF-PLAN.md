# 10 — Device and performance plan

Implements brief §18. **Every number here is an engineering target. None has
been measured on any device.** The authoring environment had no GPU and no
phone. Replace each target with a measured result, with its conditions
recorded, before quoting it to anyone.

## Renderer

Godot's **Mobile** renderer is the primary high-quality path, pinned in
`project.godot`. Compatibility is evaluated separately as a lower-feature
support tier, if at all.

The Mobile path does **not** provide SSIL, SDFGI, volumetric fog or FSR2
(brief T1). The desktop Forward+ settings are therefore not copied: the visual
solution is built from baked lighting, restrained dynamic lights, reflection
probes, authored ambient shading and coherent material response. Features the
backend lacks are absent from the configuration rather than set and silently
ignored.

## Quality tiers

| Setting | Low | Balanced | High |
|---|---|---|---|
| Pixel ratio cap | 1.0 | 1.5 | 2.0 |
| Render scale (default) | 0.9 | 0.9 | 0.9 |
| Shadows | off | 1024 | 2048 |
| MSAA | off | 2× | 4× |
| Fog density | 0.012 | 0.008 | 0.006 |
| Vegetation density | 0.40 | 0.75 | 1.00 |
| Max active characters | 6 | 10 | 14 |
| Max audio voices | 16 | 24 | 32 |

**A quality tier changes presentation only.** It may not remove cover, expose a
hidden opponent or change survival difficulty. The stealth model takes no
rendering parameter at all — a structural guarantee, with a test that greps the
module for render settings and fails if one appears.

## Acceptance targets

| Area | Initial target | Measurement conditions |
|---|---|---|
| Balanced gameplay | sustained 30 FPS; p95 frame time ≤ 40 ms | representative combat and exploration, **after device warm-up** |
| High performance mode | sustained 60 FPS; p95 ≤ 20 ms | only on devices that qualify through actual tests |
| Traversal hitches | no recurring post-warm-up stall above 100 ms | repeated indoor, outdoor and streaming-boundary routes |
| Loading feedback | visible within 0.5 s | any operation that cannot complete immediately |
| Installed mission load | ≤ 12 s | named device, local content, **cold and warm reported separately** |
| Return to strategic play | ≤ 3 s | measured after result validation and the durable commit |
| Memory | per-device limit with a measured safety margin | textures, audio, scene caches and transition peaks |
| Thermal stability | hold the selected target through 30 minutes | device, ambient conditions, brightness and power state recorded |

## Budgets to establish during the representative slice

Memory, texture residency, active characters, draw calls, audio voices and
download size. None is fixed yet, because none can be fixed without a device.

## Memory strategy

The full strategic map rendering and the full first-person world are **never
both resident**. The strategic map is drawn on the 2D canvas, so entering a
mission releases nothing it needs and the 3D renderer is free; the mission
scene is disposed on return. Districts stream in 32 m chunks with a 48 m
preload radius. Validated campaign data is retained across the transition; map
scene instances are not.

## Reporting rules (brief §18, §20)

Record build identifier, engine version, operating system, device, graphics
backend, quality preset, resolution, duration and limitations **with every
performance or visual claim**. Preserve failed-run evidence and describe the
fix. Report battery drain and temperature from a repeatable test.

Desktop performance is not evidence of mobile efficiency. The owner's
workstation (Intel Ultra 9, RTX 4060) is a development machine, not the target.

## Proposed device matrix (owner decision — `docs/11`)

| Tier | Proposed representative | Target |
|---|---|---|
| Floor | 2022 mid-range Android, Snapdragon 695-class, 6 GB | Balanced, 30 FPS |
| Mid | 2023 upper-mid Android, 8 GB | Balanced, 30 FPS stable; High eligible |
| High | current-generation flagship Android, iPhone 13 or newer | High, 60 FPS |

The floor is the one that matters: the first production milestone must run on
the **lower** supported device, not only on a flagship demonstration phone.
Supported OS versions, the storage requirement and the frame-rate modes must all
be established from the first representative mobile build. Do not advertise
support for every phone.
