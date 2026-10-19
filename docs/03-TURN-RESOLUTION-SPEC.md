# 03 — Turn resolution (normative)

Implements brief §5's proposed order. Resolution is **deterministic**: the same
`(state, seed)` produces a byte-identical result, verified over 120 consecutive
turns by comparing a stable state digest.

A turn is one week (`turn_length_days: 7` in `shared-data/chapters.json`).

## Determinism rules

- All randomness comes from `DetRng` (mulberry32), seeded
  `rng_seed ^ (turn * 0x9e3779b1)`. `Math.random()` / `randi()` are banned in
  simulation code.
- Each system draws from a **labelled sub-stream** (`rng.fork("attack:u1:12")`),
  so adding a system cannot shift another system's numbers and invalidate a
  saved campaign mid-playthrough.
- Every iteration over a collection sorts by stable id first. Object and
  Dictionary key order is not a contract.
- The GDScript PRNG was verified to produce a bit-identical stream to the
  JavaScript one for the same seed, and the digest functions agree on the same
  input.

## Phase order

### 1. Validate queued orders
Each queued order is re-validated against the state **as it is now**, with
itself removed from the queue so it cannot collide with its own duplicate
check. An order whose preconditions expired is **refunded and reported**, never
silently applied. The report lists the reason code and the exact refund.

### 2. Reserve or spend costs
Costs were already reserved atomically at submission, so the player's resource
readout is honest while orders sit queued. This phase therefore only releases
the reservations belonging to orders that phase 1 rejected. Cancelling a queued
order refunds exactly what it reserved — a test compares the resource object for
equality, not approximate equality.

### 3. Movement, then encounters
Moves resolve in stable `unit_id` order. A unit spends its path's cost, loses
`entrenched`, and claims unheld ground if its type `can_occupy`. Transit over a
sea link decrements and lands the unit at the far end.

A tile holding units from both sides becomes `contested`. **Contested is not
captured**: a contested city keeps its facilities and its control value, and a
test asserts it.

Attacks resolve next, in stable order. Combat power is
`strength × (0.35 + 0.65 × supply)`, multiplied for a defender by terrain
cover, 1.3 if entrenched, and the fortification multiplier if an undamaged
fortification stands (halved if damaged). A ±15% roll from the attack's own
sub-stream gives the ratio, which maps to one of four outcomes with fixed loss
tables. Nothing is hidden: the report carries the ratio.

Covert actions (sabotage, reconnoitre, courier) succeed on
`min(0.95, base + 0.08 × network access − 0.4 × exposure)`. Sabotage raises a
tile's `supply_penalty`; reconnaissance grants intelligence and reveals the
tile; courier work raises network access. Failure always raises exposure more
than success does.

### 4. Strategic opposition
The opponent is bound by **the same rules**. It skips a unit that cannot
attack, is below 0.25 supply, or has no movement left. It evaluates only
adjacent tiles that actually hold an opposing unit, and **declines** an attack
whose power is below 80% of the defence rather than winning for free. Every
decision appears in the report as `attacked` or `held`, with a reason. Tests
assert a starving formation does not attack and no attack resolves at an
impossible ratio.

### 5. Supply and recovery
Supply is recomputed from sources, never carried forward. Propagation is a
highest-value-first relaxation from each active source; each step costs the
destination terrain's `supply_draw` (minimum 0.5); **only a tile the side
controls relays further**, so contested ground can receive supply but cannot
pass it on. A dated event can activate a source — the Normandy beachhead
contributes nothing before 6 June 1944, and a test asserts it.

Unit supply satisfaction moves gradually (`0.45 × old + 0.55 × new`): a
formation does not starve or recover in one week. Below 0.25 it gains the
`isolated` status and its next movement budget is cut.

Civilian needs decay at `0.06 + 0.10 × (restriction_level / 5)`, offset by the
facilities actually standing. Below 0.25 food an `in_place` group becomes
`restricted`. A transmitting radio produces intelligence **and** raises network
exposure, so it is a real trade; above 0.8 exposure a search may compromise a
cell.

### 6. Construction and research
Started projects enter the city's queue with their reserved cost recorded.
Queued projects tick down and complete. Repairs clear `damaged` and `disabled`.
Service capacity is recomputed from the facilities that are actually working,
halved for damaged ones. If the tile's control differs from the city's and is
not contested, the city changes hands and each facility follows its own
`on_control_change` rule.

### 7. Dated events
The turn number and date advance, then every event whose date has now passed
fires once, in date order, and applies its effects: opening theatres, setting a
city's dated state, raising a civilian restriction level, switching a district's
state, activating a supply source, unlocking equipment, flipping theatre
control. Chapter availability is then recomputed from date window, fired
events, completed prerequisites and intelligence — never from a hidden unlock.

### 8. Readable turn report
A fixed-shape report with eleven named sections, in a fixed key order asserted
by a test: `rejected_orders`, `movements`, `engagements`, `opposition`,
`supply_changes`, `construction`, `events`, `civilian`, `network`, plus `turn`
and `date`. The UI renders the sections it has; it never invents a line.

### 9. Commit the checkpoint
`revision` increments, the report is stored on the state, the campaign is
re-validated, and the auto-save is written with `reason: "turn_committed"`.

## Conflict resolution

Simultaneous orders cannot conflict, because one unit may hold at most one
queued order (enforced at submission as `reject.duplicate_order`) and movement
resolves in stable id order before any encounter is evaluated. Two units of the
same side entering the same tile is legal; two sides entering it produces
`contested`, not an arbitrary winner.
