# MALALELE (Luna Plină) — Afro Tech × Eurodance-hook DNA

A production-ready **Suno v5.5** prompt package: an Afro Tech club record built on the
structural DNA of early-2000s Romanian Eurodance (minor-key `i–VI–III–VII` loop, syllabic
non-lexical chant hook, Romanian-language lead) — **not a cover**. All lyrics and the hook
syllables are original.

| File | Suno field | Chars | Limit |
|---|---|---|---|
| `title.txt` | Title | 22 | ~100 |
| `style.txt` | Styles / Style of Music | 850 | 1000 |
| `style-b-dark.txt` | Styles (variant B, underground) | 677 | 1000 |
| `exclude.txt` | Advanced Options → Exclude Styles | 433 | 1000 |
| `lyrics.txt` | Lyrics (Custom mode) | 2713 | 5000 |
| `lyrics-no-diacritics.txt` | Lyrics fallback (ASCII Romanian) | 2713 | 5000 |

Duration slider: **5:45** (v5.5, web). Arrangement is written to land at 5:40.

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
   legal exposure, Romanian grammar.
7. **Generation loop** — 4 renders, judge on the §8 criteria, keep one, extend/remaster.

---

## 2. Afro Tech — what the genre actually is

Afro Tech is the club-focused hybrid where South African / Afro House rhythm meets techno's
drum programming and tension-release architecture. Rhythmic intensity replaces harmonic warmth.

- **Tempo** — 124–129 BPM is the working band (the wider genre stretches to 135).
- **Kick** — tight, dry, punchy, four-on-the-floor. Not a big-room kick, not a boomy house kick.
- **Percussion** — the actual instrument of the genre. Congas, bongos, djembe, shakers on swung
  16ths, off-beat shakers, tom runs, woodblock, rim/cross-stick, shekere — interlocking
  polyrhythms rather than one busy loop. Swing/shuffle is mandatory; straight grids sound wrong.
- **Bass** — deep round mono sub, frequently doubled by a melodic **log-drum** bass (the
  Amapiano import) that carries the hook as much as the vocal does.
- **Harmony** — minimal on purpose. One or two chords, minor mode (Aeolian, occasionally Dorian),
  a hypnotic arpeggio, metallic pluck stabs, dub delay throws, wide airy pads.
- **Vocals** — sparse, mantra-like. Chants, single repeated phrases, spoken fragments,
  call-and-response group answers. Rarely a full pop topline.
- **Arrangement** — long DJ tools. 16–32 bar drum-only intro and outro, patient filter builds,
  a percussion-only breakdown, cathartic drop. 6–8 minutes is normal.
- **Mix** — analog warmth, tape saturation, tight sidechain, very wide stereo percussion, dry
  close-mic vocals sitting forward, mono sub.

## 3. The reference record — structural analysis

*O-Zone — "Dragostea Din Tei" (2003).* Used as a **structural** reference only; nothing is
quoted, and the artist/title never appear in any prompt field (Suno rejects artist names, and
the point is DNA, not imitation).

- **Tempo** ~130 BPM, 4/4, allegro. **Key** A minor (databases often report the relative
  C major — same pitch set, minor tonic).
- **Chord loop** — the four-chord `i–VI–III–VII` (Am–F–C–G) two-bar ostinato, unchanged from
  first bar to last. The most-used chord is **VI** — the hook sits on the F, which is why it
  reads as euphoric-sad rather than simply sad.
- **Melody** — one-octave range (≈B3–C5), stepwise descending motif, heavy repeated notes,
  syllabic eighth-note delivery: one syllable per eighth, almost no melisma.
- **The hook is phonetic, not lexical.** The famous line is nonsense syllables — open vowels
  and a single consonant, chantable by anyone who speaks no Romanian. That is the transferable
  asset, and it is *exactly* what Afro Tech's mantra-vocal convention wants.
- **Repetition** — extremely high. Same loop, same rhythm, hook restated every 4 bars.
- **Vocal register** — male mid-baritone, dry, forward, octave-doubled, group answers.

## 4. The intersection — what transfers, what gets cut

| Transfers | Cut |
|---|---|
| `i–VI–III–VII` minor loop, hook landing on VI | 130 BPM (→ 124, for the rolling swing) |
| Phonetic non-lexical chant hook | 2003 supersaw brass and trance lead |
| Syllabic staccato Romanian lead, octave doubling | Bright pop-major sheen |
| Call-and-response group answers | 3:30 radio arrangement (→ 5:40 DJ arrangement) |
| Extreme repetition | Novelty/comedy tone — the #1 failure mode here |

## 5. Musical spec

- **BPM 124** · 4/4 · **A minor** (Aeolian; Dorian F♯ colour on the breakdown arp)
- **Loop** Am–F–C–G, two bars, unchanged; breakdown collapses to a static Am
- **Sub** on A1 (55 Hz), mono; log-drum bass doubles the hook contour
- **Lead melody** stepwise descending, range ≈B3–C5, one syllable per eighth note
- **Balance** groove 70% / vocal 30%
- **Length** 5:40 · 176 bars

### Arrangement grid (124 BPM · 1 bar ≈ 1.94 s)

| Section | Bars | In | Out |
|---|---|---|---|
| Intro — drum tool, filtered | 16 | 0:00 | 0:31 |
| Intro — chant hook teaser | 8 | 0:31 | 0:46 |
| Percussion build | 8 | 0:46 | 1:02 |
| Verse 1 | 16 | 1:02 | 1:33 |
| Pre-Chorus / build | 8 | 1:33 | 1:49 |
| **Drop 1 (Chorus)** | 16 | 1:49 | 2:19 |
| Instrumental break | 8 | 2:19 | 2:35 |
| Verse 2 | 16 | 2:35 | 3:06 |
| Breakdown (Bridge) | 16 | 3:06 | 3:37 |
| Build 2 | 8 | 3:37 | 3:52 |
| **Drop 2 (Chorus)** | 24 | 3:52 | 4:39 |
| Chant peak | 16 | 4:39 | 5:10 |
| Outro — drum tool | 16 | 5:10 | 5:41 |

## 6. Why the prompt is written the way it is

- **Percentages *and* order.** Suno weights the first tags most heavily (first tag ≈30% of the
  style influence). The percentages are declared explicitly *and* the tag order matches them, so
  both mechanisms point the same way instead of fighting.
- **One lead genre.** Two stacked genres is the reliable hybrid ceiling; the other two entries
  are colour, kept small and placed last.
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
| All fields inside character limits | Pass (see table above) |
| Lyrics inside the 2000–3500 sweet spot | Pass — 2713 |
| Percentages sum to 100 (A: 65/15/10/10, B: 60/20/15/5) | Pass |
| Tag order matches declared percentages | Pass |
| BPM / key / mode consistent between Style, spec and grid | Pass — 124, A minor |
| No artist or track names anywhere in any field | Pass — grep-verified |
| No quoted lyrics; hook syllables original | Pass |
| Every section tag from the reliable label set | Pass |
| Style vs Exclude contradiction | None |
| Romanian grammar and diacritics | Reviewed; ASCII fallback shipped |
| Arrangement sums to the stated duration | Pass — 176 bars = 5:40 |

## 8. Generation protocol

1. Custom mode → paste `lyrics.txt`, `style.txt`, `title.txt`, `exclude.txt`. Model **v5.5**.
   Duration slider **5:45**.
2. Generate **4** renders. Judge only on: (a) does the drop hit, (b) is the percussion swung and
   layered or a flat loop, (c) is the chant hook actually singable after one listen,
   (d) is the vocal dry and forward or drowned.
3. If it comes out too poppy → swap in `style-b-dark.txt` and re-roll.
4. If Romanian pronunciation mangles → swap in `lyrics-no-diacritics.txt`.
5. If the drums stay thin → move `Tight punchy kick, deep round sub bass, log-drum bass melody`
   to the front of the style prompt, ahead of the genre percentages, for one render.
6. Keep the best take → **Persona** it, then **Extend** to 7:00 for the DJ edit, and **Cover**
   the same persona for a 3:30 radio edit if needed.

### Alternate titles
`MALALELE` · `Luna Plină` · `AI-O-MA` · `Tobele Vorbesc` · `Malalele (Full Moon Mix)`

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
