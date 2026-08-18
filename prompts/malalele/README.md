# DÉMARRE — Afro Tech, Ibiza peak-time, French vocal

A production-ready **Suno v5.5** prompt package: a fast, analog, fat-bass Afro Tech club
record built on the *structural* DNA of early-2000s Romanian Eurodance (minor-key
`i–VI–III–VII` loop, phonetic non-lexical chant hook, syllabic staccato lead) — but with a
**brand-new French lyric written for the floor**, not a translation of anything.

| File | Suno field | Chars | Limit |
|---|---|---|---|
| `title.txt` | Title | 7 | ~100 |
| `style.txt` | Styles / Style of Music | 986 | 1000 |
| `style-b-dark.txt` | Styles (variant B, after-hours) | 782 | 1000 |
| `exclude.txt` | Advanced Options → Exclude Styles | 433 | 1000 |
| `lyrics.txt` | Lyrics (Custom mode) | 3050 | 5000 |
| `lyrics-ascii.txt` | Lyrics fallback (accent-stripped) | 3051 | 5000 |

**128 BPM · A minor · 5:45 · 184 bars.** Duration slider: **5:45**.

---

## 1. Workflow

The seven passes this package went through. Re-run pass 6–7 on every regeneration.

1. **Genre research** — Afro Tech: tempo band, drum anatomy, harmonic behaviour, arrangement
   convention, mix signature.
2. **Reference deconstruction** — the O-Zone record: key, tempo, chord loop, melodic contour,
   phonetics of the hook, repetition ratio, vocal register.
3. **Intersection map** — what actually transfers between the two, what must be discarded
   (see §4). Anything that reads as pastiche gets cut.
4. **Musical spec** — lock BPM, key, mode, chord loop, bar-accurate arrangement grid, and the
   groove/vocal balance *before* any prompt text is written.
5. **Prompt engineering** — translate the spec into Suno's three-layer model
   (Style / Lyrics+meta tags / Exclude), respecting field limits and first-token weighting.
6. **Self-QA** — the checklist in §7: limits, tag reliability, redundancy, contradiction,
   legal exposure, French grammar and singability.
7. **Generation loop** — 4 renders, judge on the §8 criteria, keep one, extend/remaster.

---

## 2. Afro Tech — what the genre actually is

Afro Tech is the club-focused hybrid where South African / Afro House rhythm meets techno's
drum programming and tension-release architecture. Rhythmic intensity replaces harmonic warmth.

- **Tempo** — 124–129 BPM is the working band (the wider genre stretches to 135). This track
  sits at **128**: top of the band, Ibiza peak-time, still swung.
- **Kick** — tight, dry, punchy, four-on-the-floor. Not a big-room kick, not a boomy house kick.
- **Percussion** — the actual instrument of the genre. Congas, bongos, djembe, shakers on swung
  16ths, off-beat shakers, tom runs, woodblock, rim/cross-stick, shekere — interlocking
  polyrhythms rather than one busy loop. Swing/shuffle is mandatory; straight grids sound wrong.
- **Bass** — deep round mono sub, frequently doubled by a melodic **log-drum** bass (the
  Amapiano import) that carries the hook as much as the vocal does. Here it is pushed further:
  saturated and overdriven, the fattest element in the mix.
- **Harmony** — minimal on purpose. One or two chords, minor mode (Aeolian, occasionally Dorian),
  a hypnotic arpeggio, metallic pluck stabs, dub delay throws, wide airy pads.
- **Vocals** — sparse, mantra-like. Chants, single repeated phrases, spoken fragments,
  call-and-response crowd answers. Rarely a full pop topline.
- **Arrangement** — long DJ tools. 16–32 bar drum-only intro and outro, patient filter builds,
  a percussion-only breakdown, cathartic drop. 6–8 minutes is normal.
- **Mix** — analog warmth, tape saturation, tight sidechain, very wide stereo percussion, dry
  close-mic vocals sitting forward, mono sub.

## 3. The reference record — structural analysis

*O-Zone — "Dragostea Din Tei" (2003).* Used as a **structural** reference only; nothing is
quoted or translated, and the artist/title never appear in any prompt field (Suno rejects artist
names, and the point is DNA, not imitation).

- **Tempo** ~130 BPM, 4/4, allegro. **Key** A minor (databases often report the relative
  C major — same pitch set, minor tonic).
- **Chord loop** — the four-chord `i–VI–III–VII` (Am–F–C–G) two-bar ostinato, unchanged from
  first bar to last. The most-used chord is **VI** — the hook sits on the F, which is why it
  reads as euphoric-sad rather than simply sad.
- **Melody** — one-octave range (≈B3–C5), stepwise descending motif, heavy repeated notes,
  syllabic eighth-note delivery: one syllable per eighth, almost no melisma.
- **The hook is phonetic, not lexical.** The famous line is nonsense syllables — open vowels
  and a single consonant, chantable by anyone who speaks none of the language. That is the
  transferable asset, and it is *exactly* what Afro Tech's mantra-vocal convention wants.
- **Repetition** — extremely high. Same loop, same rhythm, hook restated every 4 bars.
- **Vocal register** — male mid-baritone, dry, forward, octave-doubled, crowd answers.

## 4. The intersection — what transfers, what gets cut

| Transfers | Cut |
|---|---|
| `i–VI–III–VII` minor loop, hook landing on VI | 130 BPM (→ 128, keeps the swing) |
| The *principle* of a phonetic non-lexical hook | The reference's actual syllables |
| Syllabic staccato lead, octave doubling | The Romanian language, and the original imagery |
| Call-and-response crowd answers | 2003 supersaw brass and trance lead |
| Extreme repetition | 3:30 radio arrangement (→ 5:45 DJ arrangement) |
|  | Novelty/comedy tone — the #1 failure mode here |

### Why French, and why this lyric

The lyric is **new writing, not a translation** — a different scene, different images, a
different hook. It works musically for three reasons:

- **The hook is French-native.** `Dé-ma-ré / dé-ma-ro / dé-ma-ré-lé-o` is nonsense you can chant
  after one listen, but it shadows a real French word — so the drop line **"Ça démarre, ça monte,
  ça part"** lands the meaning a bar later. Phonetic hook *and* lexical payoff from the same
  sound. The crowd answer `O-lé-lé-o!` needs no French at all.
- **French cuts through at 128.** Closed `é` endings and hard consonant onsets (`p`, `t`, `k`)
  give the staccato eighth-note grid its attack, while the nasal vowels (`en`, `on`, `an`)
  sustain over the sub without fighting it.
- **Francophone Afro House is a real, current club lineage** — the language reads as native to
  Ibiza terraces, not as a costume.

The lyric itself is written as club copy, not poetry: no story, no chorus-verse narrative arc.
Short declarative lines, present tense, second person, physical images (bass in the stomach,
sweat on the wall, salt on skin, 4am terrace), and two producer-wink build lines
(*"Encore huit mesures"* / *"Quatre… trois… deux…"*) that tell Suno exactly where the tension is.

## 5. Musical spec

- **BPM 128** · 4/4 · **A minor** (Aeolian; Dorian F♯ colour on the breakdown arp)
- **Loop** Am–F–C–G, two bars, unchanged; breakdown collapses to a static Am
- **Sub** on A1 (55 Hz), mono, saturated; overdriven log-drum bass doubles the hook contour
- **Lead melody** stepwise descending, range ≈B3–C5, one syllable per eighth note
- **Balance** groove 75% / vocal 25% — the bass and drums are the lead instrument
- **Length** 5:45 · 184 bars

### Arrangement grid (128 BPM · 1 bar = 1.875 s)

| Section | Bars | In | Out |
|---|---|---|---|
| Intro — drum tool, filtered | 16 | 0:00 | 0:30 |
| Intro — chant hook teaser | 8 | 0:30 | 0:45 |
| Percussion build | 8 | 0:45 | 1:00 |
| Verse 1 | 16 | 1:00 | 1:30 |
| Pre-Chorus / build | 8 | 1:30 | 1:45 |
| **Drop 1 (Chorus)** | 16 | 1:45 | 2:15 |
| Instrumental break | 8 | 2:15 | 2:30 |
| Verse 2 | 16 | 2:30 | 3:00 |
| Breakdown (Bridge) | 16 | 3:00 | 3:30 |
| Build 2 | 8 | 3:30 | 3:45 |
| **Drop 2 (Chorus) — fattest bass** | 32 | 3:45 | 4:45 |
| Chant peak | 16 | 4:45 | 5:15 |
| Outro — drum tool | 16 | 5:15 | 5:45 |

## 6. Why the prompt is written the way it is

- **Percentages *and* order.** Suno weights the first tags most heavily (first tag ≈30% of the
  style influence). The percentages are declared explicitly *and* the tag order matches them, so
  both mechanisms point the same way instead of fighting.
- **One lead genre.** Two stacked genres is the reliable hybrid ceiling; the other two entries
  are colour, kept small and placed last.
- **Analog is stated as hardware, not as a mood.** "Analog warmth" alone is a weak tag, so the
  style names the machines by family — Juno-style pads, Moog-style resonant filter, hardware
  drum machine feel, tape saturation — which pushes the model toward that timbre far harder.
- **The bass is described three times** (fat saturated analog sub / thick overdriven log-drum
  bassline / fat mono sub in the mix clause). Deliberate redundancy: it is the one element the
  brief will not tolerate coming out thin.
- **Reliable section labels first inside the bracket.** Every meta tag opens with a label from
  the dependable set (`[Intro]`, `[Verse]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`,
  `[Instrumental Break]`, `[Outro]`, `[End]`) and then uses the `:` parameter syntax to describe
  the arrangement event — so `[Chorus: drop — …]` gets chorus-grade structural reliability while
  still reading as a drop.
- **Exclude field, not inline negatives.** The dedicated Exclude field is more reliable than
  `no …` inside the style prompt, and it is where the real risk lives: big-room lead, novelty
  tone, autotune warble.
- **`[End]`** stops Suno inventing an outro fade or a spoken tail.

## 7. Self-QA — checks run on this package

| Check | Result |
|---|---|
| All fields inside character limits | Pass — style 986/1000 is the tightest |
| Lyrics inside the 2000–3500 sweet spot | Pass — 3050 |
| Percentages sum to 100 (A: 65/15/10/10, B: 60/20/15/5) | Pass |
| Tag order matches declared percentages | Pass |
| BPM / key / balance consistent between Style, spec and grid | Pass — 128, A minor, 75/25 |
| No artist or track names in any field | Pass — grep-verified |
| No quoted or translated lyrics; hook syllables original | Pass — grep-verified, no residue |
| Lyric is new writing, not a translation of the reference | Pass — new scene, images and hook |
| Every section tag from the reliable label set | Pass |
| Style vs Exclude contradiction | None |
| French grammar and singability at 128 BPM | Reviewed; accent-stripped fallback shipped |
| Arrangement sums to the stated duration | Pass — 184 bars × 1.875 s = 5:45 exactly |

## 8. Generation protocol

1. Custom mode → paste `lyrics.txt`, `style.txt`, `title.txt`, `exclude.txt`. Model **v5.5**.
   Duration slider **5:45**.
2. Generate **4** renders. Judge only on: (a) does the drop actually hit, (b) is the bass fat and
   saturated or thin and polite, (c) is the percussion swung and layered or a flat loop,
   (d) can you chant `Dé-ma-ré-lé-o` after one listen.
3. Bass still thin → move `Fat saturated analog sub bass, thick overdriven log-drum bassline` to
   the very front of the style prompt, ahead of the genre percentages, for one render.
4. Too clean / too digital → swap in `style-b-dark.txt` (130 BPM, after-hours, 85/15 groove).
5. French pronunciation mangled → swap in `lyrics-ascii.txt`.
6. Too vocal-heavy → drop the balance line to `Groove 80% / vocal 20%` and delete the second
   `(O-lé-lé-o!)` in each chorus.
7. Keep the best take → **Persona** it, then **Extend** to 7:00 for the DJ edit, and **Cover**
   the same persona for a 3:30 radio edit if needed.

### Alternate titles
`DÉMARRE` · `DÉMARRE (Ibiza Terrace Mix)` · `O-LÉ-LÉ-O` · `Encore Huit Mesures` · `Quatre Heures`

---

### Sources
- [Afro Tech — Melodigging](https://www.melodigging.com/genre/afro-tech)
- [Afro Tech vs Afro House — Slice_Mewzeeck](https://www.slicemewzeeck.co.za/afro-tech-vs-afro-house-music-difference/)
- [How To Make Afro Tech Music — The Producer School](https://theproducerschool.com/blogs/featured-blogs/how-to-make-afro-tech-music-like-da-capo-joezi)
- [Step-by-Step Guide to Creating an Afro House Track — Beatportal](https://www.beatportal.com/articles/647491-step-by-step-guide-to-creating-an-afro-house-track-keinemusik-black-coffee-caiiro-alex-wann-style)
- [Dragostea Din Tei — Hooktheory theory analysis](https://www.hooktheory.com/theorytab/view/o-zone/dragostea-din-tei)
- [Dragostea Din Tei — SongBPM](https://songbpm.com/@o-zone/dragostea-din-tei)
- [Dragostea Din Tei — SongData.io](https://songdata.io/track/5B0tUbgCTcvsZgIPjpNKtE/Dragostea-Din-Tei-Original-Romanian-Version-by-O-Zone)
- [Suno Meta Tags Guide — Jack Righteous](https://jackrighteous.com/en-us/pages/suno-ai-meta-tags-guide)
- [Suno Character Limits 2026 — aimusicapi](https://aimusicapi.ai/en/blog/suno-ai-prompt-character-limits)
- [Suno Prompt Guide 2026 — HookGenius](https://hookgenius.app/learn/suno-prompt-guide-2026/)
- [Suno Custom Lyrics Guide v5.5 — Jack Righteous](https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/structuring-lyrics-prompts)
