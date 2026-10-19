# 01 — Mobile game design document

## The game in one paragraph

An original, historically grounded World War II strategy and survival game for
phones and tablets. You command formations or underground networks on a
turn-based strategic map, enter the particular place where an operation happens,
live through it in first person, and return to a world that changed because of
what you did. The emotional centre is the distance between the scale of the war
and a single household in it: military campaigns, occupied and liberated cities,
Jewish communities, resistance networks and civilian survival all belong to the
same connected world.

## The complete loop (brief §4)

1. **Read the situation.** Date, controlled territory, supply, formations,
   civilian needs, city projects, underground activity — all on one map that
   describes one authoritative campaign state.
2. **Select and inspect.** A unit, city, network or operation. Movement range,
   travel cost, route, risks and the strategic consequence are all visible
   *before* committing.
3. **Issue an order.** Movement, construction, relief, reconnaissance,
   sabotage, defence, attack, or a historically appropriate civilian operation.
   Only the verbs that kind of group can actually perform are offered.
4. **Activate an encounter.** An eligible chapter builds a MissionContext from
   the current strategic state.
5. **Transition.** A briefing with its history references, then visible loading
   progress. Location, time, mission identity and control expectations are
   preserved across the cut.
6. **Play the operation.** Combat, stealth, cooperation, resource management or
   another supported objective. Success, partial success, failure and withdrawal
   are all meaningful where the chapter allows them.
7. **Resolve once.** The result is validated against the context, the permitted
   effects commit exactly once, and the return screen names **precisely what
   changed and why**.
8. **Save and continue.** The next strategic decision, or continued exploration.

Strategic time freezes while a mission is active. An operation consumes campaign
time only if its chapter says so. The war does not advance because the player
took a phone call.

## Modes

**Campaign** follows authored chronology and consequence, 1939-09-01 to
1945-05-08, one week per turn. **Sandbox** offers persistent exploration and
more freedom inside eligible historical settings, in its own save slot with its
own campaign id, so it can never overwrite the chronological campaign. Returning
to an earlier period is an explicit separate replay, not a rewind.

If an alternate-history mode is ever added it gets its own label and its changed
outcomes stay separate from the historical record the journal presents.

## The strategic layer

Four theatres (Western Europe, Eastern Europe, North Africa, Home Front), 124
tiles on a pointy-top hex grid, connected across theatres by three sea links
with transit times and capacity. A readable theatre selector sits above a
zoomable regional grid; both describe the same state.

Military formations depend on routes, frontlines, control, supply and readiness.
Underground movement depends on access, exposure, contacts and safe routes. The
capability table in `docs/02` is the whole of it — there is no shared "unit"
behaviour underneath.

Cities carry construction: medical depot, underground radio, escape route,
fortification, relief kitchen. Each has prerequisites, a cost, a build time, a
visible benefit, and defined behaviour when control changes or it is damaged.
A radio produces intelligence and raises exposure. That tension is the point.

## The first-person layer

**Fundamentals:** move, look, aim, fire, reload, interact, crouch, run, and
navigate the obstacles the level actually supports. Climbing and mantling appear
only where geometry and animation support them, and the traversal button is
hidden otherwise.

**Weapons** are data-driven profiles with their own handling, reload rules and
audio event list. Ammunition changes only at the declared insert point. Single
round, partial and empty reloads follow the weapon's own rules. Interruption
follows the declared cancel policy, and the round count is conserved across any
interleaving of fire, reload, cancel and death.

**Stealth** uses a calibrated gameplay model of posture, light exposure,
distance, occlusion, movement and observer attention. Detection accumulates: it
is never instant, and never omniscient. Awareness has a middle band so patrols
can *investigate* rather than snapping between oblivious and alerted. Noise
requires ground contact and horizontal displacement, so a wall-push and a jump
are silent by construction.

**Survival** means choices under restriction: obtaining and allocating food,
water, medicine or shelter where the setting calls for it; avoiding exposure;
helping people; communicating; moving supplies; weighing an immediate need
against a future risk. The resource categories are tailored per setting, not a
universal checklist bolted onto every chapter.

**Not every story ends in a firefight.** Seven of eleven mission families need
no lethal action at all, and the Warsaw courier chapter issues no firearm.

## Persistent exploration

Authored districts stream in 32 m chunks. Continuity is preserved inside the
playable area; the strategic map or a deliberate travel transition carries the
player between distant places. Each district has a navigation structure,
landmarks, useful interiors, a local mission network and ambient life
appropriate to its date and restrictions. Every building in the shipped
district has an interior, because a street of decorative doors that imply
interaction and never support it is the specific failure the brief names.

What persists and what resets is declared per district, not assumed. Objective
flags persist, which is what prevents a revisited objective paying twice.

## Campaign structure

Twelve chapters across six locations, with dates, prerequisites, perspectives,
research references and explicit strategic effects. Three are authored, six are
outlined, three are registered placeholders reserving a required location. The
register is in `shared-data/chapters.json` and its status words mean exactly
what `status_legend` says they mean.

The 1943 Warsaw ghetto uprising chapter deliberately does **not** offer a
"success" outcome. Its authored outcomes concern who the player gets out and
what the network retains. A game may not offer to win it.

## Accessibility (defaults on)

Scalable text (0.85–1.6×), adjustable HUD (0.8–1.5×), high contrast,
colour-independent indicators (a word and a shape as well as a colour),
subtitles with speaker identity, directional sound captions, motion reduction,
camera-shake control, separate recoil presentation, five separate audio buses, a
mono mode that converts essential directional cues into captions, left-handed
layout, hold-or-toggle for aim and crouch, and ≥48 dp touch targets throughout.

Reduced-intensity presentation preserves historical meaning. It never conceals
or denies a documented event.

## What is deliberately absent

No multiplayer, no live-service economy, no advertising, no subscription, no
in-app purchase, no telemetry requirement, no microphone, camera or contacts
permission. The brief did not specify any of them, so none was assumed. The
core campaign works offline once the required content is installed.
