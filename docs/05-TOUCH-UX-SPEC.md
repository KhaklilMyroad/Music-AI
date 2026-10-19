# 05 — Touch controls and interface

Implements brief §10. Landscape for ordinary gameplay; portrait shows a rotate
hint with a "continue anyway" escape, because a hint must never be a trap.

## Control map

| Action | Default input | Required customisation | Implemented |
|---|---|---|---|
| Move | Left virtual stick | position, size, fixed or floating | yes |
| Look | Drag in the right-side look area | sensitivity, inversion, optional gyro | yes |
| Aim | Dedicated button | hold or toggle; separate aim sensitivity | yes |
| Fire | Primary right-side button | position, size | yes (second fire button: not yet) |
| Reload | Dedicated contextual button | availability and progress feedback | yes (radial progress on the button) |
| Interact | Contextual button near the thumb | tap **or** hold alternative | yes (both routes, every staged action) |
| Crouch | Dedicated button | hold or toggle | yes |
| Sprint | Stick threshold or button | toggle alternative; guarded against accidents | yes (threshold at 0.92 plus a button) |
| Climb or jump | Contextual traversal button | shown only when supported | yes (hidden by default) |
| Journal and map | Persistent compact chip | reachable without obscuring the scene | yes |
| Pause | Clear corner button | pauses and opens settings and saves | yes |

## Multi-touch

Fingers are tracked by pointer id / touch index. The first finger inside the
stick half claims the stick; the next claims the look area. A finger released
does not disturb the other. This is the single most common failure when a
desktop scheme is ported, so it is structural rather than incidental.

A left-handed layout mirrors the whole layer, including which half of the screen
owns the stick — not just the button cluster.

## Safe areas

Every cluster is positioned from `env(safe-area-inset-*)` (web) or
`DisplayServer.get_display_safe_area()` (Godot), so controls clear notches,
rounded corners and system gesture strips. Touch targets are at least 48 dp,
per Android's current accessibility guidance (brief T4). Both narrow and wide
aspect ratios need checking on physical phones; that check has not happened.

## Map interaction

Tap to select, drag to pan, pinch to zoom. A tap resolves in priority order:
the player's own orderable unit, then the city, then another visible unit, then
the tile. While a unit with a movement overlay is selected, tapping a
highlighted tile previews the route and its cost and opens the confirmation —
the order is still explicit.

**A long press is never the only way to discover an essential action.** Every
staged interaction also completes on repeated taps, and every map action is
reachable from a visible button or sheet.

## Sheets, not desktop panels

A unit or city selection opens a focused bottom sheet with the primary action
immediately visible. Detailed inventory, logistics and historical information
live in dedicated full panels. No desktop layout is shrunk to fit.

## HUD

Condition, stamina, rounds where relevant, interaction prompt, objectives and
stealth feedback. Nothing else. The first-person hands and weapon must stay
readable without covering the interaction target: the reticle fades out entirely
when no weapon is raised, and the viewmodel sits in the lower-right third.

Stealth indicators show a **word**, a **bar length** and, in
colour-independent mode, a **shape**. The panel carries
`stealth.model_is_gameplay`: "These readings are a gameplay model, not a
measurement." The brief asks for restraint and for honesty about precision; this
is both.

## Error and recovery text

Player-facing text says what the player can do. A test asserts no locale string
contains a stack trace, a node name, a file extension or the word "undefined".

| Condition | What the player is told |
|---|---|
| Damaged save | "That save could not be read. The last known good save is available." |
| Storage full | "There is not enough storage to save. Free some space and try again." |
| Content not installed | "This location's content is not installed." (with its size and a download path) |
| Download stopped | "The download stopped. You can resume it." |
| Cloud unavailable | "Cloud saves are unavailable. Your offline progress is safe." |
| Cloud conflict | "Two different continuations exist. Choose which to keep; neither is deleted." |
| Failed transition | "The operation could not start. Nothing was spent." |

## Hebrew and RTL

Hebrew ships at full key parity with English (273 keys, asserted). The document
direction flips, and interpolated values are wrapped in Unicode isolates
(`U+2068`/`U+2069`) so a Latin place name or a number inside a Hebrew sentence
cannot reorder the sentence around it. Numbers stay in Latin digits with a
left-to-right mark where needed.

In-world signage is **not** translated into modern English to simplify the UI:
a street sign in an occupied city reads as it would have read, and the journal
explains it.

## First-session journey

One strategic order, one first-person interaction, one visible strategic
consequence — taught during play, not in a manual. No sequence of unexplained
resource screens before the player understands the premise.

## Returning-player journey

Restore the last safe state, identify the active objective, make continuation
obvious. A pending mission result resolves safely rather than appearing as a
duplicate reward. If required content is missing, explain its size and offer a
clear download or return path.
