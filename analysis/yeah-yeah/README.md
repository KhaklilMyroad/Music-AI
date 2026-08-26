# Yeah Yeah — production deconstruction

Measured breakdown of the uploaded reference track, and the spec for rebuilding
one in the same style. The full illustrated version is [`anatomy.html`](anatomy.html).

Reproduce every number with:

```
python3 tools/track_anatomy.py Yeah_Yeah.mp3 --bpm 125 --drop 57 72
```

## Core specs

| | |
|---|---|
| Tempo | 125.00 BPM, constant. Bar = 1.920 s, first downbeat at 0.200 s |
| Key | F minor (F Aeolian). Tonic sub sits on F1 = 43.65 Hz |
| Length | 2:22.55 — 74 bars, no DJ intro, no outro |
| Loudness | −8.44 LUFS-I, short-term −13.6 to −6.6, range 4.7 LU |
| Peaks | +1.19 dBTP, 8537 samples at full scale — the master clips |
| Genre read | Future house / bass house, radio-edit form |

## Arrangement

| Section | Bars | Time | Bars | RMS |
|---|---|---|---|---|
| Pickup | 0 | 0:00.2 | 1 | −15.6 |
| Verse 1 | 1–8 | 0:02.1 | 8 | −14.1 |
| Build 1 | 9–15 | 0:17.5 | 7 | −10.4 |
| Gap | 16 | 0:30.9 | 1 | −14.0 |
| **Drop 1** | 17–32 | 0:32.8 | 16 | **−7.3** |
| Verse 2 | 33–48 | 1:03.6 | 16 | −14.3 |
| Build 2 | 49–55 | 1:34.3 | 7 | −10.8 |
| Gap | 56 | 1:47.7 | 1 | −12.3 |
| **Drop 2** | 57–72 | 1:49.6 | 16 | **−7.3** |
| Tail | 73 | 2:20.4 | 1 | −24.6 |

Bar-similarity scores of 0.90–0.97 between bars 57–72 and 17–32 mean drop 2 is
the same audio as drop 1. Verse 2 is verse 1 played twice. Nothing is 32 bars —
everything is built from 8-bar units.

## Harmony

Two different progressions, not one:

- **Verse**, 8-bar loop, 2 bars per chord: `Fm – Eb – Db – Bbm` (i – ♭VII – ♭VI – iv).
  Bass walks F1 → Eb2 → Db2 → Bb1, so the lowest note of the verse is its first note.
- **Drop**, 8-bar loop: `F ×4 bars – Db ×2 – Bb ×2`. Sub stays on F1 as a pedal
  underneath all three chords.

Third-degree energy is ambiguous in both sections (A and A♭ measure nearly equal
in the drop), which is the signature of sus and power-chord voicings rather than
full triads. Play fifths and fourths, not thirds.

## Drums and bass

Step grid over the drop, 16 steps per bar:

```
              1  e  &  a  2  e  &  a  3  e  &  a  4  e  &  a
kick          X  .  .  .  X  .  .  .  X  .  .  .  X  .  .  .
clap          .  .  .  .  X  .  .  .  .  .  .  .  X  .  .  .
closed hat    -  x  x  o  -  o  x  x  -  x  o  o  -  x  o  x
open hat      .  .  O  .  .  .  O  .  .  .  O  .  .  .  O  .
bass          .  .  .  X  .  .  X  o  .  o  o  o  .  .  X  o
```

Hi-hat energy measures exactly `0.00` on every downbeat step — the sidechain
swallows it. The bass never lands on a downbeat; it fills only the gaps the kick
leaves. Envelope modulation of the 150–500 Hz band peaks at 8.34 Hz, which is the
sixteenth-note rate at 125 BPM.

## Sound design targets

- **Kick** — pitch glides 86 Hz → 43.1 Hz in roughly 25 ms, then holds. 43.65 Hz
  is F1, so the kick is tuned to the tonic.
- **Sub** — pure sine on F1, fully mono (correlation 0.999 below 60 Hz). The
  31–50 Hz band is 20+ dB louder in the drop than in the verse; it is an element
  that enters, not an EQ move.
- **Sidechain** — 14.1 dB of gain reduction on everything except kick and sub.
  Minimum about 90 ms after the hit, 90% recovery at ~460 ms against a 480 ms
  beat. Ratio ~8:1, attack 5 ms, release 440 ms from a separate trigger.
- **Verse pad** — wide (side/mid −7.9 dB at 300–800 Hz), high-passed around
  200 Hz, plate tail near 1.2 s.

## Transitions

The build runs a *constant* sixteenth-note percussion rate (8.61 Hz, identical in
every bar) — no accelerating snare roll. What moves instead is HF level
(−19.8 → −17.7 dB) and spectral centroid (4296 → 4911 Hz) across eight bars.

The gap bar is a high-pass sweep: 20–80 Hz energy falls from +34 dB to −17 dB
across one bar while the mids hold station. On the final sixteenth an impact hits
— sub jumps 27 dB and centroid spikes to 6205 Hz. The drop's first bar then
measures *less* 3–16 kHz energy than the bar before it: kick and sub enter naked,
with no crash on top.

## Mix and master targets

Stereo width climbs monotonically with frequency — mono below 120 Hz, widening
gradually above:

| Band | Side/Mid | Correlation |
|---|---|---|
| 20–60 Hz | −32.9 dB | 0.999 |
| 60–120 Hz | −26.7 dB | 0.996 |
| 120–300 Hz | −10.0 dB | 0.820 |
| 300–800 Hz | −7.9 dB | 0.721 |
| 800–2500 Hz | −10.9 dB | 0.849 |
| 2.5–7 kHz | −8.3 dB | 0.742 |
| 7–16 kHz | −6.3 dB | 0.623 |

The one defect worth not copying is the master's +1.19 dBTP. Limit in true-peak
mode to −1.0 dBTP instead; the cost is under 0.5 LU.

## Limits of this analysis

- **Vocals.** Centred melodic content above 250 Hz runs through the whole track,
  but formant bandwidths measure 2–50 Hz — far too narrow for a sung human voice —
  and vibrato modulation is low. Most likely a synth lead, possibly with a short
  vocal chop on the hook. Not certain from measurement alone.
- **Air above 15 kHz** is unverifiable: the source is a 134 kbps MP3 with a
  cutoff near 16 kHz.
- Nothing here identifies which plugins or samples were used. These are target
  values, not a reconstruction of a specific chain.
