# 02 — Data contracts (normative)

This is the shared source of truth for brief §16. Two implementations follow it:
`web/src/sim/contracts.js` (verified by tests) and
`godot/core/models/contracts.gd` (mirror). A rule changed here must be changed
in both, or the suites diverge.

## Principles

1. **Typed runtime models and services own gameplay. Scene nodes are views.**
   A node may read campaign state and submit requests. It may never write it.
2. **JSON is the persistence and interchange format.** Nothing serialised holds
   a node reference, a live engine resource or an unvalidated dictionary.
3. **Stable IDs carry every relationship.** Never an array index, never a
   pointer, never a scene path.
4. **Validation is strict on load.** A damaged save must be *detected*, not
   half-applied.
5. **One authority applies commands and outcomes.** `CampaignService`. Nothing
   else mutates campaign state, and `submitOrder` asserts it did not change the
   revision.

## Versions

| Constant | Value | Meaning |
|---|---|---|
| `SCHEMA_VERSION` | 4 | CampaignState and SaveEnvelope shape |
| `RESULT_VERSION` | 2 | MissionResult shape |
| `CHECKPOINT_VERSION` | 2 | DistrictCheckpoint shape |

Each has its own number because they move at different speeds: a mission tuning
pass should not force a save migration.

## The contracts

### CampaignState
`schema_version`, `campaign_id`, `revision`, `turn`, `date` (ISO), `mode`
(`campaign` | `sandbox`), `player_faction`, `resources`, and the entity indexes
`tiles`, `units`, `cities`, `civilian_groups`, `networks` — each keyed by its own
stable id, and each validated to match the id inside it. Plus `fired_events`,
`completed_chapters`, `unlocked_chapters`, `unlocked_equipment`,
`history_flags`, `pending_operation`, `committed_operations`, `order_queue`,
`last_turn_report`, `rng_seed`.

`revision` is the concurrency token. Only `resolveTurn` and `commitResult` may
increment it. A MissionResult carrying a stale `source_revision` is refused.

### TileState
Stable `tile_id` of the form `"<theater>:<q>,<r>"`, axial coordinates, `terrain`,
`control`, `passable`, `naval_only`, `neighbors` (tile ids, validated to exist),
`city_id`, `poi_refs`, `supply` (0..10, recomputed every turn),
`supply_penalty` (set by mission effects), `discovered`,
`contested_since_turn`.

### UnitState
Stable `unit_id`, `unit_type`, `faction`, `label_key`, `tile_id`, `strength`
(0..1), `supply` (0..1), `move_budget` (validated against the type's maximum),
`allowed_actions` (validated as a subset of the type's capabilities),
`equipment`, `status`, `transit`.

**Capabilities are per unit type and no two types share a set.** A test asserts
it. This is what stops a civilian group inheriting a division's verbs:

| Type | Actions | Budget | Supply draw | Occupies | On map | Moves by |
|---|---|---|---|---|---|---|
| infantry_division | move, attack, defend, reconnoitre, entrench | 3 | 4 | yes | yes | routes |
| armoured_division | move, attack, defend, reconnoitre | 5 | 7 | yes | yes | routes |
| garrison | defend, entrench | 0 | 2 | yes | yes | — |
| partisan_squad | move, sabotage, reconnoitre, ambush, hide | 2 | 1 | no | no | access |
| underground_cell | move_covert, sabotage, courier, shelter, recruit, hide | 1 | 0 | no | no | access |
| civil_defence_team | relieve, evacuate, treat, move | 2 | 1 | no | yes | routes |
| relief_column | move, relieve, deliver | 2 | 1 | no | yes | routes |
| supply_column | move, deliver | 3 | 1 | no | yes | routes |

A unit whose `supply_draw` is 0 never starves for lack of a depot: an
underground cell lives off the city it is in.

### CityState
Stable `city_id`, `label_key`, `theater`, `tile_id`, `place_date_context`
(which dated state the city is in), `control`, `facilities`,
`construction_queue`, `facilities_max`, `supply_access`, `service_capacity`,
`civilian_group_ids`, `network_ids`, `districts`, `restriction_level` (0..5, set
by dated events).

Each facility declares its prerequisites, cost, build time, benefit, behaviour
on control change and behaviour when damaged. `on_control_change` is one of
`captured_disabled` (a depot stops working for its new owner),
`captured_intact` (a fortification serves whoever holds it) or `survives_hidden`
(a concealed radio or escape route is not captured with the city).

### CivilianGroupState
Stable `group_id`, `label_key`, `is_fictional`, `community_id`,
`household_ids`, `headcount`, `city_id`, `tile_id`, `needs`
(food/water/medicine/shelter, each 0..1 **satisfaction**),
`access_restrictions`, `displacement`
(`in_place` | `restricted` | `displaced` | `evacuated` | `unaccounted`),
`narrative_flags`, `relationships`.

**A `strength` field on a civilian group is a validation error.** The brief
names this bug; the validator rejects it by name. `needs` are satisfaction
levels, never a suffering score, and nothing in the UI renders persecution as a
measured percentage.

### UndergroundNetworkState
Stable `network_id`, `label_key`, `city_id`, `cells` (each with its own id,
tile and `compromised` flag), `contacts` (role, reliability, compromised),
`area_tiles`, `access` (0..5), `intelligence`, `resources`, `exposure` (0..1),
`safe_routes`, `compromised_links`.

### MissionContext (immutable once created)
`operation_id` (deterministic from campaign id + revision + turn + nonce),
`source_revision`, `campaign_id`, `unit_id`, `tile_id`, `city_id`,
`district_id`, `district_content_version`, `chapter_id`, `date`,
`mission_type`, `seed`, `permitted_objectives`, `allowed_outcomes`,
**`outcome_bounds`**, `entry_snapshot`, `reserved_cost`,
`campaign_time_cost_turns`, `loadout`.

`outcome_bounds` is derived from the chapter's authored `strategic_effects` and
is the *only* channel by which a mission can change the campaign. It carries
`max_intelligence`, `max/min_materiel`, `max/min_personnel`,
`may_remove_attacking_formation`, `may_flip_tile_control`,
`max/min_civilian_health_delta`, `max_network_exposure_delta`,
`max_network_access_delta`.

### MissionResult
`result_version`, `operation_id`, `source_revision`, `outcome`,
`completed_objectives`, `failed_objectives`, `metrics`, `declared_losses`,
`declared_resources`, `requests`.

**It may not carry a world-state patch.** The validator checks the *raw* object
for `world_patch`, `campaign`, `tiles`, `units` and `resources` before
normalising, because normalising would silently drop an unknown field and turn
an attempted patch into an invisible no-op. Everything else is clamped to the
context's bounds and the clamped field names are reported, so a tuning mistake
surfaces instead of being swallowed.

### DistrictCheckpoint
`checkpoint_version`, `district_id`, **`district_content_version`**,
`saved_at_boundary`, `player` (position, yaw, pitch, posture, health,
condition, equipped), `inventory`, `weapon_states`, **`mission_flags`**,
`poi_states`, `door_states`, `container_states`, `local_entities`,
`local_time_hours`, `weather`, `interrupted_action`.

`mission_flags` is what prevents a revisited objective paying twice.
`interrupted_action` carries `revert_to` counts so a reload cut short by a
process kill cannot duplicate a round: the checkpoint decides, not the scene.

### SaveEnvelope
`schema_version`, `content_versions`, `save_id`, `slot`, `mode`, `revision`,
`saved_at`, `engine_build`, `payload` (`{campaign, district_checkpoint,
reason}`), `recovery` (`is_last_known_good`, `write_complete`,
`previous_save_id`), `integrity`.

The digest covers the **payload only**, so recovery metadata can change without
invalidating it. It is an integrity tool, not a security control: a local
attacker can recompute it. A future multiplayer or competitive service needs its
own trust model, designed separately.

## Migration policy

Migrations are an explicit ordered list. A save from a schema with no path is
**refused loudly**, not half-loaded. Sharing JSON syntax is not compatibility.

| From → to | What it does |
|---|---|
| 1 → 2 | adds `networks` and `committed_operations` |
| 2 → 3 | removes the illegal `strength` field from civilian groups; fills `needs` |
| 3 → 4 | adds `supply_penalty` to tiles and `unlocked_equipment` |

Cross-platform save compatibility is **not** a current requirement. If it
becomes one — a PC save opened on a future mobile build, or the reverse — it
needs its own migration entries and its own tests. It is not established by both
sides emitting JSON.

Nothing in these contracts is platform-specific, which is why the move from
mobile to PC changed none of them and left all of their tests passing. The
platform lives in the renderer, the input layer and the display settings; the
campaign does not know what it is running on.
