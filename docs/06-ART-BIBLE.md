# 06 — Art bible and the commercial quality bar

Implements brief §12 and §13. **Nothing in this repository currently meets this
bar.** Every mesh is a blockout and every material is generated. This page is
the standard the production art must be judged against, written so it can be
applied by a reviewer rather than argued about.

## Direction

Cinematic historical realism with coherent art direction. Realism comes from
proportion, construction, use and wear — not from large textures or heavy
post-processing. A building must look like it was built the way buildings in
that place were built, and then lived in.

## The eight fixed camera comparisons

Brief §12 requires judging the result through continuous native gameplay and
fixed camera comparisons. These are the eight, to be captured in the same order
every time, on the **lower** supported device, with the device, quality preset,
resolution and build id recorded on every frame:

1. **Spawn view** — the first thing the player sees on entering the district.
2. **Ordinary street or lane** — mid-distance, no favourable framing.
3. **Reverse view** — the same spot, turned 180°. Catches the "one good angle"
   failure.
4. **Interior** — a lived room with its own light sources.
5. **Close character** — a civilian at conversation distance, face filling a
   third of the frame.
6. **Aiming** — down the sights, hands and weapon at full close scrutiny.
7. **Reload** — mid-reload, at the frame where the hand leaves the handguard.
8. **Combat** — in motion, under fire, with muzzle flash and dust.

Generated concept art, offline renders and selectively polished screenshots
**cannot** pass this gate and must be labelled when shown at all.

## Characters

Priority, not background dressing.

- **Faces** need credible anatomy, eye wetness and parallax, skin with
  subsurface response, hair with real silhouette, and expression that reads at
  conversation distance.
- **Bodies** need natural proportion. Clothing and uniforms must drape and
  crease where a body creases.
- **Equipment** hangs and attaches plausibly: a strap over a shoulder bears
  weight, a pouch sits where a belt holds it.
- **Banned:** mannequin faces, rigid fingers, modern garment silhouettes, and
  the same face twice in one prominent view.

## First-person hands and weapons

The highest close-range scrutiny in the game, and the place a reviewer should
look first.

| Check | Fail condition |
|---|---|
| Support-hand contact | The hand detaches from, or intersects, the handguard at any point in the motion |
| Finger contact | A finger passes through the stock or the trigger guard |
| Thumb placement | The thumb floats, or wraps through the grip |
| Palm support | The palm does not contact the surface bearing the weapon's weight |
| Wrist | The wrist breaks past its anatomical range during a reload swing |
| Sleeves and cuffs | A cuff clips the receiver, or a sleeve has no thickness |
| Weapon scale | The weapon reads larger or smaller than its real dimensions against the hand |
| Transitions | Idle → aim → fire → reload → interact snaps, slides or pops |

A good static pose is not enough. The architecture supports this: the hands are
parented to **named grip contacts on the weapon**, in the weapon's own space,
so they travel with it exactly and a reload moves the support hand along an
authored path away from and back onto its contact.

## Environments

- Structural detail: wall thickness, window recesses, doors with hinges, stair
  dimensions that match a real rise and run, roofing, pipes, furniture, work
  tools, believable damage. The district data already encodes wall thickness,
  opening recesses, hinge sides and swing directions, and stair rise and run —
  the art must honour them rather than contradict them.
- Wear is **localised and function-based**: worn where hands and feet go,
  clean where nothing touches. Uniform grime over every surface is a fail.
- Props are placed because something uses them. Density for its own sake is a
  fail.

## Lighting

Motivated by actual sources: sky, windows, lamps, fire. Readable interior and
exterior exposure. Contact with the ground. Depth across near, middle and
distant scenery. Weather affects surfaces, visibility and sound coherently.

Expensive fog, reflections and particles may not hide weak geometry or
destabilise ordinary play. The Mobile renderer does not provide SSIL, SDFGI,
volumetric fog or FSR2 (brief T1), so the solution is built from what the
backend supports: baked lighting where appropriate, restrained dynamic lights,
reflection probes, authored ambient shading, coherent material response.

## Animation

- Required states per character class: standing, walking, running, crouching,
  aiming, firing, reloading, reacting, interacting, incapacitation.
- No sliding feet, no body snapping, no weapon moving independently of the
  hands.
- **Timing must agree with gameplay.** Ammunition does not appear before the
  profile's declared insert point. A door is not passable before it is
  sufficiently open (>55% in the implementation). Footsteps follow contact and
  displacement. An interrupted action stops producing mechanism sound.
- Rigs and retargeting preserve anatomy. Hand contact, shoulders, elbows, knees,
  facial movement and cloth deformation are reviewed **in the actual game
  lighting**, not in a turntable.
- First-person and third-person representations of the same action must agree
  wherever both are visible.

## Living environments

Populate according to conditions. A ghetto, an active frontline, a home-front
street and a deserted bunker must not share one crowd-and-bird loop. Civilian
routines, patrol routes, sheltering, work and conversation must be plausible for
the date and the restrictions in force.

Ambient motion supports the scene: restrained vegetation, hanging fabric, smoke,
water. **Attachment points and collision are preserved** — wind moves a tree
crown, never the trunk, and never a whole grass patch as one object. The
implementation enforces this by moving only crown meshes and never the
colliding trunk.

Scale with distance: nearby people get full animation and behaviour, distant
life gets simplified schedules. **Story state persists independently of whether
a model is loaded** — a civilian with a narrative flag keeps it across a
streaming boundary, and no visible person despawns abruptly.

## Asset provenance

Every model, texture, font, photograph, music cue, voice and sound effect needs
a record in `shared-data/asset-provenance.json`: creator, source, licence,
permissions, processing history and use restrictions. A generated asset requires
visual **and** historical review before it enters the approved library, and the
weapon registry refuses to mark an asset `approved` without a provenance
reference — a test asserts it.
