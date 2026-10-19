# 04 — Transitions and exactly-once consequences (normative)

Implements brief §17. This is the part of the architecture most likely to
produce a bug the player can exploit or be robbed by, so it is specified
tightly and tested at every boundary.

## State machine

```
StrategicReady → PreparingMission → LoadingMission → MissionReady
               → PlayingMission → ResolvingMission → Returning → StrategicReady
                                                   ↘ TransitionFailed ↗
```

Only the transitions in the `LEGAL` table are permitted. An illegal transition
throws rather than being quietly allowed; a test asserts that calling
`markPlaying` straight after entry raises `transition.illegal_state`.

## The three hard rules

### 1. A double tap cannot create two operations
`beginOperation` refuses while a pending operation exists in any state other
than `StrategicReady`, and the refused attempt reserves nothing — a test
compares the resource digest before and after. `operation_id` is **deterministic**
(`hash(campaign_id | revision | turn | nonce)`), so a retried tap with the same
nonce is recognised as the same operation rather than becoming a second one.

### 2. Delivering the same result twice applies it once
`submitResult` returns `{already_committed: true}` for a repeat, whether the
pending record still exists or has already been cleared. `commitResult` is
itself idempotent and returns the identical applied record on a second call.
`committed_operations` is the barrier, and it lives in the save.

A test asserts the intelligence total and the revision are both unchanged after
a duplicate delivery.

### 3. An interrupted return resumes or loads; it never infers
`recoverOnLaunch` inspects the pending operation's state and decides:

| State found in the save | Action | Why |
|---|---|---|
| `StrategicReady`, `PreparingMission`, `LoadingMission`, `MissionReady`, `TransitionFailed` | `cancelled_entry` — refund and restore the entry snapshot | Nothing was played. Re-entry must be free. |
| `PlayingMission` **with** a district checkpoint | `resume_mission` | Put the player back where they were, same operation id. |
| `PlayingMission` **without** one | `restart_mission` | The mission is replayed. It is **not** treated as finished. |
| `ResolvingMission` | `resumed_commit` — run the idempotent commit, then acknowledge | A result was durably written; the commit may not have landed. |
| `Returning` | `acknowledged` | The commit landed; only the acknowledgement was lost. |

**Completion is never inferred from a missing scene.** A test drives the
machine to `PlayingMission`, discards the scene with no checkpoint and no
result, and asserts the action is `restart_mission`, that the operation is not
in `committed_operations`, and that no chapter was marked complete.

## Order of durable writes

```
validate order → create id → reserve cost → WRITE entry_checkpoint
→ load content → WRITE loading → verify readiness → WRITE mission_ready
→ WRITE mission_playing → [WRITE district_checkpoint on each safe boundary]
→ validate result → WRITE pending_result → APPLY EFFECTS → WRITE committed
→ acknowledge → WRITE return_acknowledged (pending record cleared)
```

The result is written **before** the effects are applied, and the commit is
written **before** the acknowledgement. A crash in either gap is recoverable
because the next launch replays an idempotent step.

## Readiness

`markReady` requires all six of `player`, `collision`, `navigation`,
`objectives`, `ui`, `audio`. A missing item moves the operation to
`TransitionFailed` and names what was missing — it does not hide behind a
permanent loading animation. A test asserts a partial readiness map fails with
`navigation` and `audio` listed.

## Retry cost

`failOperation` refunds the reservation **and restores the entry snapshot**
(resources, the ordering unit, the tile's control) rather than patching fields
back. A test issues a sabotage order, fails the load, retries, and asserts the
player paid for exactly one sabotage.

## Campaign time

Strategic time and conflicting strategic commands are frozen while a mission is
active: `submitOrder` and `endTurn` both refuse with `reject.mission_active`. An
operation consumes campaign time **only** if its chapter declares
`campaign_time_cost_turns`. A test asserts a zero-cost operation does not
advance the war, however long the player spent in it.
