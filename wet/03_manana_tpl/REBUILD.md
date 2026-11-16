# Rebuild recipe: Manana

- **Tempo:** 145.5 BPM (4/4), measured 145.87, confidence 0.7
- **Key:** F minor (Camelot 4A), tuning -5 cents (A4 = 438.77 Hz)
- **Loudness:** -5.7 LUFS integrated, 6.4 dBTP true peak, LRA 5.2 LU
- **Swing:** 51.9% (MPC scale, 50 = straight)
- **Stems:** folder

## Structure

| Bars | Section | Letter | Start (s) |
|---|---|---|---|
| 1-5 | Intro | A | 0.2 |
| 6-14 | Verse / Groove | B | 8.5 |
| 15-23 | Drop / Chorus | C | 23.5 |
| 24-30 | Pre-chorus / Build | B | 38.4 |
| 31-39 | Drop / Chorus | C | 50.0 |
| 40-47 | Verse / Groove | B | 64.9 |
| 48-71 | Drop / Chorus | C | 78.0 |
| 72-75 | Pre-chorus / Build | B | 117.5 |
| 76-83 | Drop / Chorus | C | 124.0 |
| 84-89 | Build-up | B | 137.3 |
| 90-95 | Drop / Chorus | D | 147.2 |
| 96-120 | Drop / Chorus | C | 157.1 |
| 121-125 | Pre-chorus / Build | B | 198.3 |
| 126-169 | Drop / Chorus | C | 206.6 |
| 170-176 | Outro | D | 279.1 |

## Chords

`N.C.` `Fsus4` `A#` `N.C.` `C7` `C#` `Fm` `A#maj7` `D#` `Fm` `F` `Fm` `C7` `C` `Fm` `F` `Fm` `F` `D#m` `A#m` `Fm` `F` `Fm` `A#m` `G` `F` `A#m` `F#` `F` `F#` `Fm` `G#m` `Fm` `G#m` `Fm` `G#m` `Fm` `G#m` `G#` `G` `G#m` `Fm` `A#` `A#maj7` `F` `Em` `C#7` `Fm` `F` `E` `Gm` `C#m` `F` `E` `Bmaj7` `E` `Fsus4` `E` `Cm` `E` `F` `G#` `Gm` `A#`

## Drums (Drums, midi)

**Instrument: Drum Rack** (medium). One-shots cut from the cleanest hit of each detected kit piece in the drum stem.

```json
{
 "pads": {
  "kick": {
   "note": 36,
   "pad": "C1",
   "sample": "Samples\\Drums\\kick.wav"
  },
  "perc": {
   "note": 37,
   "pad": "C#1",
   "sample": "Samples\\Drums\\perc.wav"
  },
  "snare": {
   "note": 38,
   "pad": "D1",
   "sample": "Samples\\Drums\\snare.wav"
  },
  "open_hat": {
   "note": 46,
   "pad": "A#1",
   "sample": "Samples\\Drums\\open_hat.wav"
  },
  "closed_hat": {
   "note": 42,
   "pad": "F#1",
   "sample": "Samples\\Drums\\closed_hat.wav"
  }
 },
 "patterns_16_steps": {
  "kick": "x...x...x...x...",
  "perc": "..........x.....",
  "snare": "x.x.x.x.x.x.x.x.",
  "closed_hat": "...x............",
  "open_hat": "..........x....."
 }
}
```
- **EQ Eight** (medium): Drum bus tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 31 Hz - 16000 Hz, tilt -1.9 dB/oct).  
  `{"bands": [{"band": 1, "type": "Bell", "freq_hz": 31.2, "gain_db": -11.2, "q": 1.4}, {"band": 2, "type": "Bell", "freq_hz": 12699.2, "gain_db": 3.3, "q": 1.4}, {"band": 3, "type": "Bell", "freq_hz": 500.0, "gain_db": 3.3, "q": 1.4}]}`
- **Glue Compressor** (low): Crest factor 14.0 dB -> moderate bus compression.  
  `{"threshold_db": -8.4, "ratio": 2, "attack_ms": 10, "release_s": "Auto", "makeup_db": 1.5, "dry_wet": 100}`
- **Utility** (medium): Side/mid -27.6 dB, L/R correlation 0.997.  
  `{"width_percent": 4}`

## cymbals (Drums, midi)

**Instrument: Drum Rack** (medium). One-shots cut from the cleanest hit of each detected kit piece in the drum stem.

```json
{
 "pads": {
  "kick": {
   "note": 36,
   "pad": "C1",
   "sample": "Samples\\cymbals\\kick.wav"
  },
  "perc": {
   "note": 37,
   "pad": "C#1",
   "sample": "Samples\\cymbals\\perc.wav"
  },
  "snare": {
   "note": 38,
   "pad": "D1",
   "sample": "Samples\\cymbals\\snare.wav"
  },
  "open_hat": {
   "note": 46,
   "pad": "A#1",
   "sample": "Samples\\cymbals\\open_hat.wav"
  },
  "closed_hat": {
   "note": 42,
   "pad": "F#1",
   "sample": "Samples\\cymbals\\closed_hat.wav"
  }
 },
 "patterns_16_steps": {
  "kick": "...x............",
  "perc": "........x.......",
  "snare": "x.xxx.x.x.x.x.x.",
  "closed_hat": "...x............",
  "open_hat": ".........x......"
 }
}
```
- **EQ Eight** (medium): Drum bus tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 157 Hz - 16000 Hz, tilt +2.0 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 126.0}, {"band": 2, "type": "Bell", "freq_hz": 250.0, "gain_db": 9.5, "q": 1.4}, {"band": 3, "type": "Bell", "freq_hz": 500.0, "gain_db": 4.8, "q": 1.4}, {"band": 4, "type": "Bell", "freq_hz": 1259.9, "gain_db": -4.3, "q": 1.4}]}`
- **Glue Compressor** (low): Crest factor 26.8 dB -> light / none bus compression.  
  `{"threshold_db": -16.4, "ratio": 2, "attack_ms": 10, "release_s": "Auto", "makeup_db": 1.5, "dry_wet": 100}`
- **Utility** (medium): Side/mid -18.7 dB, L/R correlation 0.973. No side energy below ~200 Hz -> Bass Mono.  
  `{"width_percent": 12, "bass_mono": true, "bass_mono_hz": 200.0}`

## kick (Drums, midi)

**Instrument: Drum Rack** (medium). One-shots cut from the cleanest hit of each detected kit piece in the drum stem.

```json
{
 "pads": {
  "kick": {
   "note": 36,
   "pad": "C1",
   "sample": "Samples\\kick\\kick.wav"
  },
  "closed_hat": {
   "note": 42,
   "pad": "F#1",
   "sample": "Samples\\kick\\closed_hat.wav"
  },
  "perc": {
   "note": 37,
   "pad": "C#1",
   "sample": "Samples\\kick\\perc.wav"
  },
  "snare": {
   "note": 38,
   "pad": "D1",
   "sample": "Samples\\kick\\snare.wav"
  }
 },
 "patterns_16_steps": {
  "kick": "x...x...x...x...",
  "perc": "..........x.....",
  "snare": "...x............",
  "closed_hat": "...............x"
 }
}
```
- **EQ Eight** (medium): Drum bus tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 31 Hz - 1000 Hz, tilt -4.9 dB/oct).  
  `{"bands": [{"band": 1, "type": "High Cut (12 dB/oct)", "freq_hz": 1250.0}, {"band": 2, "type": "Bell", "freq_hz": 31.2, "gain_db": -11.2, "q": 1.4}]}`
- **Glue Compressor** (low): Crest factor 14.4 dB -> light / none bus compression.  
  `{"threshold_db": -8.8, "ratio": 2, "attack_ms": 10, "release_s": "Auto", "makeup_db": 1.5, "dry_wet": 100}`
- **Utility** (medium): Side/mid -32.0 dB: effectively mono.  
  `{"width_percent": 0}`

## snare (Drums, midi)

**Instrument: Drum Rack** (medium). One-shots cut from the cleanest hit of each detected kit piece in the drum stem.

```json
{
 "pads": {
  "kick": {
   "note": 36,
   "pad": "C1",
   "sample": "Samples\\snare\\kick.wav"
  },
  "perc": {
   "note": 37,
   "pad": "C#1",
   "sample": "Samples\\snare\\perc.wav"
  },
  "snare": {
   "note": 38,
   "pad": "D1",
   "sample": "Samples\\snare\\snare.wav"
  },
  "open_hat": {
   "note": 46,
   "pad": "A#1",
   "sample": "Samples\\snare\\open_hat.wav"
  },
  "closed_hat": {
   "note": 42,
   "pad": "F#1",
   "sample": "Samples\\snare\\closed_hat.wav"
  }
 },
 "patterns_16_steps": {
  "kick": "....x.x.....x.x.",
  "perc": "..............x.",
  "snare": "....x.x.....x...",
  "closed_hat": "...............x",
  "open_hat": "...............x"
 }
}
```
- **EQ Eight** (medium): Drum bus tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 99 Hz - 16000 Hz, tilt -0.7 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 79.4}, {"band": 2, "type": "Bell", "freq_hz": 99.2, "gain_db": -7.4, "q": 1.4}, {"band": 3, "type": "Bell", "freq_hz": 198.4, "gain_db": 6.6, "q": 1.4}, {"band": 4, "type": "Bell", "freq_hz": 500.0, "gain_db": 4.7, "q": 1.4}]}`
- **Glue Compressor** (low): Crest factor 26.1 dB -> light / none bus compression.  
  `{"threshold_db": -15.7, "ratio": 2, "attack_ms": 10, "release_s": "Auto", "makeup_db": 1.5, "dry_wet": 100}`
- **Utility** (medium): Side/mid -23.6 dB, L/R correlation 0.991.  
  `{"width_percent": 7}`

## toms (Drums, midi)

**Instrument: Drum Rack** (medium). One-shots cut from the cleanest hit of each detected kit piece in the drum stem.

```json
{
 "pads": {
  "kick": {
   "note": 36,
   "pad": "C1",
   "sample": "Samples\\toms\\kick.wav"
  },
  "closed_hat": {
   "note": 42,
   "pad": "F#1",
   "sample": "Samples\\toms\\closed_hat.wav"
  },
  "perc": {
   "note": 37,
   "pad": "C#1",
   "sample": "Samples\\toms\\perc.wav"
  },
  "snare": {
   "note": 38,
   "pad": "D1",
   "sample": "Samples\\toms\\snare.wav"
  }
 },
 "patterns_16_steps": {
  "kick": "x...x...x...x...",
  "perc": "...x............",
  "snare": "...............x",
  "closed_hat": ".....x.........."
 }
}
```
- **EQ Eight** (medium): Drum bus tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 99 Hz - 5040 Hz, tilt -1.5 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 79.4}, {"band": 2, "type": "High Cut (12 dB/oct)", "freq_hz": 6299.6}, {"band": 3, "type": "Bell", "freq_hz": 99.2, "gain_db": -8.4, "q": 1.4}, {"band": 4, "type": "Bell", "freq_hz": 250.0, "gain_db": 6.0, "q": 1.4}, {"band": 5, "type": "Bell", "freq_hz": 500.0, "gain_db": 5.3, "q": 1.4}]}`
- **Glue Compressor** (low): Crest factor 34.3 dB -> light / none bus compression.  
  `{"threshold_db": -23.1, "ratio": 2, "attack_ms": 10, "release_s": "Auto", "makeup_db": 1.5, "dry_wet": 100}`
- **Utility** (medium): Side/mid -19.5 dB, L/R correlation 0.979. No side energy below ~150 Hz -> Bass Mono.  
  `{"width_percent": 11, "bass_mono": true, "bass_mono_hz": 150.0}`

## Bass (Bass, midi)

**Instrument: Drift** (medium). Harmonic series reads as 'filtered saw' (slope -16.7 dB/oct, odd -35.6 dB / even -28.5 dB). Filter cutoff set where harmonics fall below -24 dB (~4 strong harmonics). Wavetable (Basic Shapes) or Analog can make the same tone.

```json
{
 "osc_1_shape": "Saw",
 "osc_2": "Off (or Sine one octave down for sub weight)",
 "filter_type": "Low-pass (24 dB)",
 "filter_freq_hz": 312.0,
 "filter_resonance": "low",
 "voice_mode": "Mono",
 "amp_env": {
  "attack_ms": 70.0,
  "sustain_db": -1.5,
  "decay_ms": 38.0,
  "release_ms": 154.0
 }
}
```
- **Auto Filter** (medium): 9 filter sweep(s) of more than one octave detected.  
  `{"filter_type": "Low-pass", "slope": "24 dB", "frequency_hz": "automated (see automation)"}`
- **EQ Eight** (medium): Bass tone shaping: band edges and resonances measured from the stem's 1/3-octave spectrum (content 31 Hz - 1260 Hz, tilt -4.8 dB/oct).  
  `{"bands": [{"band": 1, "type": "High Cut (12 dB/oct)", "freq_hz": 1574.9}, {"band": 2, "type": "Bell", "freq_hz": 31.2, "gain_db": -6.6, "q": 1.4}, {"band": 3, "type": "Bell", "freq_hz": 125.0, "gain_db": 3.3, "q": 1.4}]}`
- **Compressor** (low): Crest factor 15.3 dB (peak -0.3 / RMS -15.6 dBFS) -> light / none compression. Crest factor shows the amount of dynamic control, not the exact compressor settings.  
  `{"threshold_db": -9.5, "ratio": 1.5, "attack_ms": 20.0, "release_ms": 200.0, "knee_db": 6, "makeup": "auto"}`
- **Utility** (medium): Side/mid -22.0 dB, L/R correlation 0.988.  
  `{"width_percent": 8}`
- Automation Auto Filter › Frequency (Hz): [(60.0, 3316), (68.0, 194)] (lowpass closing: spectral edge moves 3316 -> 194 Hz)
- Automation Auto Filter › Frequency (Hz): [(124.0, 2261), (134.0, 183)] (lowpass closing: spectral edge moves 2261 -> 183 Hz)
- Automation Auto Filter › Frequency (Hz): [(142.0, 2046), (150.0, 248)] (lowpass closing: spectral edge moves 2046 -> 248 Hz)
- Automation Auto Filter › Frequency (Hz): [(428.0, 17539), (436.0, 215)] (lowpass closing: spectral edge moves 17539 -> 215 Hz)
- Automation Auto Filter › Frequency (Hz): [(590.0, 172), (598.0, 711)] (lowpass opening: spectral edge moves 172 -> 711 Hz)
- Automation Auto Filter › Frequency (Hz): [(622.0, 172), (630.0, 581)] (lowpass opening: spectral edge moves 172 -> 581 Hz)

## Piano / Keys (Keys, midi)

**Instrument: Grand Piano (Core Library, Sampler)** (medium). Separated piano stem; inharmonic piano partials are not modelled by Live's synths.

```json
{
 "velocity_sens": "high"
}
```
- **Auto Filter** (medium): 4 filter sweep(s) of more than one octave detected.  
  `{"filter_type": "High-pass", "slope": "24 dB", "frequency_hz": "automated (see automation)"}`
- **EQ Eight** (medium): Keys tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 250 Hz - 2520 Hz, tilt -4.3 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 200.0}, {"band": 2, "type": "High Cut (12 dB/oct)", "freq_hz": 3149.8}, {"band": 3, "type": "Bell", "freq_hz": 315.0, "gain_db": -13.8, "q": 1.4}, {"band": 4, "type": "Bell", "freq_hz": 793.7, "gain_db": 7.5, "q": 1.4}, {"band": 5, "type": "Bell", "freq_hz": 1587.4, "gain_db": -6.8, "q": 1.4}]}`
- **Compressor** (medium): Envelope dips 10.5 dB right after each kick and recovers in ~13 ms: sidechain pumping.  
  `{"sidechain": "On", "audio_from": "Drums (or a muted ghost-kick track)", "ratio": 10, "threshold_db": "set for ~10 dB gain reduction on each kick", "attack_ms": 0.5, "release_ms": 13.0, "knee_db": 0}`
- **Utility** (medium): Side/mid -8.8 dB, L/R correlation 0.786.  
  `{"width_percent": 36, "pan_hint": 0.21}`
- Automation Auto Filter › Frequency (Hz): [(28.0, 86), (36.0, 915)] (highpass rising: spectral edge moves 86 -> 915 Hz)
- Automation Auto Filter › Frequency (Hz): [(46.0, 65), (58.0, 161)] (highpass rising: spectral edge moves 65 -> 161 Hz)
- Automation Auto Filter › Frequency (Hz): [(222.0, 108), (240.0, 32)] (highpass falling: spectral edge moves 108 -> 32 Hz)
- Automation Auto Filter › Frequency (Hz): [(646.0, 32), (654.0, 861)] (highpass rising: spectral edge moves 32 -> 861 Hz)
- Note: Also exported block chords from the chord analysis: MIDI/Piano_Keys_chords.mid

## Guitar (Guitar, midi)

**Instrument: Simpler (load the guitar stem slice) or a guitar sample instrument** (low). Guitar timbre is better re-recorded or sliced from the stem than synthesised.

```json
{}
```
- **Auto Filter** (medium): 12 filter sweep(s) of more than one octave detected.  
  `{"filter_type": "Low-pass", "slope": "24 dB", "frequency_hz": "automated (see automation)"}`
- **EQ Eight** (medium): Guitar tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 125 Hz - 16000 Hz, tilt +0.2 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 100.0}, {"band": 2, "type": "Bell", "freq_hz": 315.0, "gain_db": -7.7, "q": 1.4}, {"band": 3, "type": "Bell", "freq_hz": 1587.4, "gain_db": -6.3, "q": 1.4}, {"band": 4, "type": "Bell", "freq_hz": 630.0, "gain_db": 4.9, "q": 1.4}]}`
- **Compressor** (medium): Envelope dips 6.5 dB right after each kick and recovers in ~103 ms: sidechain pumping.  
  `{"sidechain": "On", "audio_from": "Drums (or a muted ghost-kick track)", "ratio": 4, "threshold_db": "set for ~6 dB gain reduction on each kick", "attack_ms": 0.5, "release_ms": 103.0, "knee_db": 0}`
- **Utility** (medium): Side/mid -14.1 dB, L/R correlation 0.925.  
  `{"width_percent": 20}`
- Automation Auto Filter › Frequency (Hz): [(176.0, 17905), (186.0, 528)] (lowpass closing: spectral edge moves 17905 -> 528 Hz)
- Automation Auto Filter › Frequency (Hz): [(342.0, 12112), (352.0, 323)] (lowpass closing: spectral edge moves 12112 -> 323 Hz)
- Automation Auto Filter › Frequency (Hz): [(486.0, 280), (498.0, 19132)] (lowpass opening: spectral edge moves 280 -> 19132 Hz)
- Automation Auto Filter › Frequency (Hz): [(660.0, 19681), (668.0, 291)] (lowpass closing: spectral edge moves 19681 -> 291 Hz)
- Automation Auto Filter › Frequency (Hz): [(10.0, 172), (22.0, 86)] (highpass falling: spectral edge moves 172 -> 86 Hz)
- Automation Auto Filter › Frequency (Hz): [(46.0, 65), (56.0, 151)] (highpass rising: spectral edge moves 65 -> 151 Hz)
- Note: Also exported block chords from the chord analysis: MIDI/Guitar_chords.mid

## Synths / Other (Pad, midi)

**Instrument: Wavetable** (medium). Slow attack (84.0 ms), sustained, mean polyphony 3.2 -> pad.

```json
{
 "osc_1": "Basic Shapes > Saw",
 "unison": "Classic, 4 voices, amount 25%",
 "filter_1": "Low-pass 12 dB @ 1195 Hz",
 "amp_env": {
  "attack_ms": 84.0,
  "sustain_db": -4.2,
  "decay_ms": 42.0,
  "release_ms": 146.0
 },
 "voices": 8
}
```
- **Auto Filter** (medium): 21 filter sweep(s) of more than one octave detected.  
  `{"filter_type": "Low-pass", "slope": "24 dB", "frequency_hz": "automated (see automation)"}`
- **EQ Eight** (medium): Pad tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 39 Hz - 16000 Hz, tilt -0.5 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 31.5}, {"band": 2, "type": "Bell", "freq_hz": 49.6, "gain_db": -6.2, "q": 1.4}]}`
- **Compressor** (medium): Envelope dips 10.8 dB right after each kick and recovers in ~103 ms: sidechain pumping.  
  `{"sidechain": "On", "audio_from": "Drums (or a muted ghost-kick track)", "ratio": 10, "threshold_db": "set for ~11 dB gain reduction on each kick", "attack_ms": 0.5, "release_ms": 103.0, "knee_db": 0}`
- **Utility** (medium): Side/mid -8.1 dB, L/R correlation 0.734.  
  `{"width_percent": 39}`
- Automation Auto Filter › Frequency (Hz): [(64.0, 312), (76.0, 4360)] (lowpass opening: spectral edge moves 312 -> 4360 Hz)
- Automation Auto Filter › Frequency (Hz): [(142.0, 786), (150.0, 18163)] (lowpass opening: spectral edge moves 786 -> 18163 Hz)
- Automation Auto Filter › Frequency (Hz): [(178.0, 12629), (186.0, 506)] (lowpass closing: spectral edge moves 12629 -> 506 Hz)
- Automation Auto Filter › Frequency (Hz): [(338.0, 19391), (346.0, 409)] (lowpass closing: spectral edge moves 19391 -> 409 Hz)
- Automation Auto Filter › Frequency (Hz): [(370.0, 1378), (382.0, 8538)] (lowpass opening: spectral edge moves 1378 -> 8538 Hz)
- Automation Auto Filter › Frequency (Hz): [(392.0, 1238), (408.0, 12608)] (lowpass opening: spectral edge moves 1238 -> 12608 Hz)
- Note: Also exported block chords from the chord analysis: MIDI/Synths_Other_chords.mid

## Vocals (Vocals, audio)

- **Auto Filter** (medium): 15 filter sweep(s) of more than one octave detected.  
  `{"filter_type": "Low-pass", "slope": "24 dB", "frequency_hz": "automated (see automation)"}`
- **EQ Eight** (medium): Vocal tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 50 Hz - 16000 Hz, tilt -0.2 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 39.7}, {"band": 2, "type": "Bell", "freq_hz": 49.6, "gain_db": -5.6, "q": 1.4}, {"band": 3, "type": "Bell", "freq_hz": 10079.4, "gain_db": 4.3, "q": 1.4}, {"band": 4, "type": "Bell", "freq_hz": 630.0, "gain_db": 4.2, "q": 1.4}]}`
- **Compressor** (low): Crest factor 22.6 dB (peak -0.4 / RMS -23.0 dBFS) -> light / none compression. Crest factor shows the amount of dynamic control, not the exact compressor settings.  
  `{"threshold_db": -14.0, "ratio": 1.5, "attack_ms": 20.0, "release_ms": 200.0, "knee_db": 6, "makeup": "auto"}`
- **Compressor** (medium): Envelope dips 9.5 dB right after each kick and recovers in ~64 ms: sidechain pumping.  
  `{"sidechain": "On", "audio_from": "Drums (or a muted ghost-kick track)", "ratio": 10, "threshold_db": "set for ~10 dB gain reduction on each kick", "attack_ms": 0.5, "release_ms": 64.0, "knee_db": 0}`
- **Utility** (medium): Side/mid -12.6 dB, L/R correlation 0.897.  
  `{"width_percent": 23}`
- Automation Auto Filter › Frequency (Hz): [(44.0, 13038), (56.0, 538)] (lowpass closing: spectral edge moves 13038 -> 538 Hz)
- Automation Auto Filter › Frequency (Hz): [(102.0, 194), (110.0, 915)] (lowpass opening: spectral edge moves 194 -> 915 Hz)
- Automation Auto Filter › Frequency (Hz): [(414.0, 19832), (422.0, 5071)] (lowpass closing: spectral edge moves 19832 -> 5071 Hz)
- Automation Auto Filter › Frequency (Hz): [(464.0, 16215), (474.0, 721)] (lowpass closing: spectral edge moves 16215 -> 721 Hz)
- Automation Auto Filter › Frequency (Hz): [(568.0, 11983), (576.0, 2369)] (lowpass closing: spectral edge moves 11983 -> 2369 Hz)
- Automation Auto Filter › Frequency (Hz): [(680.0, 560), (688.0, 19864)] (lowpass opening: spectral edge moves 560 -> 19864 Hz)
- Note: Pitch sits within ~9 cents of the semitone grid: probably pitch-corrected. Live 12 has no stock real-time pitch-correction device; use a third-party plug-in or Live's audio-to-MIDI + resynthesis.

## backing_vocals (Vocals, audio)

- **Auto Filter** (medium): 19 filter sweep(s) of more than one octave detected.  
  `{"filter_type": "Low-pass", "slope": "24 dB", "frequency_hz": "automated (see automation)"}`
- **EQ Eight** (medium): Vocal tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 50 Hz - 16000 Hz, tilt -0.8 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 39.7}, {"band": 2, "type": "Bell", "freq_hz": 6349.6, "gain_db": -6.2, "q": 1.4}, {"band": 3, "type": "Bell", "freq_hz": 315.0, "gain_db": -5.2, "q": 1.4}, {"band": 4, "type": "Bell", "freq_hz": 49.6, "gain_db": -5.2, "q": 1.4}]}`
- **Compressor** (low): Crest factor 22.1 dB (peak -2.6 / RMS -24.7 dBFS) -> light / none compression. Crest factor shows the amount of dynamic control, not the exact compressor settings.  
  `{"threshold_db": -15.8, "ratio": 1.5, "attack_ms": 20.0, "release_ms": 200.0, "knee_db": 6, "makeup": "auto"}`
- **Compressor** (medium): Envelope dips 11.1 dB right after each kick and recovers in ~64 ms: sidechain pumping.  
  `{"sidechain": "On", "audio_from": "Drums (or a muted ghost-kick track)", "ratio": 10, "threshold_db": "set for ~11 dB gain reduction on each kick", "attack_ms": 0.5, "release_ms": 64.0, "knee_db": 0}`
- **Utility** (medium): Side/mid -11.7 dB, L/R correlation 0.872.  
  `{"width_percent": 26}`
- Automation Auto Filter › Frequency (Hz): [(44.0, 3531), (56.0, 538)] (lowpass closing: spectral edge moves 3531 -> 538 Hz)
- Automation Auto Filter › Frequency (Hz): [(102.0, 194), (110.0, 915)] (lowpass opening: spectral edge moves 194 -> 915 Hz)
- Automation Auto Filter › Frequency (Hz): [(176.0, 2099), (186.0, 4457)] (lowpass opening: spectral edge moves 2099 -> 4457 Hz)
- Automation Auto Filter › Frequency (Hz): [(310.0, 151), (318.0, 2832)] (lowpass opening: spectral edge moves 151 -> 2832 Hz)
- Automation Auto Filter › Frequency (Hz): [(418.0, 19444), (426.0, 258)] (lowpass closing: spectral edge moves 19444 -> 258 Hz)
- Automation Auto Filter › Frequency (Hz): [(464.0, 16042), (474.0, 721)] (lowpass closing: spectral edge moves 16042 -> 721 Hz)
- Note: Pitch sits within ~9 cents of the semitone grid: probably pitch-corrected. Live 12 has no stock real-time pitch-correction device; use a third-party plug-in or Live's audio-to-MIDI + resynthesis.

## lead_vocals (Vocals, audio)

- **Auto Filter** (medium): 6 filter sweep(s) of more than one octave detected.  
  `{"filter_type": "Low-pass", "slope": "24 dB", "frequency_hz": "automated (see automation)"}`
- **EQ Eight** (medium): Vocal tone: band edges and resonances measured from the stem's 1/3-octave spectrum (content 50 Hz - 16000 Hz, tilt +1.3 dB/oct).  
  `{"bands": [{"band": 1, "type": "Low Cut (48 dB/oct)", "freq_hz": 39.7}, {"band": 2, "type": "Bell", "freq_hz": 49.6, "gain_db": -6.8, "q": 1.4}, {"band": 3, "type": "Bell", "freq_hz": 10079.4, "gain_db": 3.7, "q": 1.4}]}`
- **Compressor** (low): Crest factor 28.2 dB (peak -0.4 / RMS -28.6 dBFS) -> light / none compression. Crest factor shows the amount of dynamic control, not the exact compressor settings.  
  `{"threshold_db": -17.4, "ratio": 1.5, "attack_ms": 20.0, "release_ms": 200.0, "knee_db": 6, "makeup": "auto"}`
- **Compressor** (medium): Envelope dips 7.3 dB right after each kick and recovers in ~39 ms: sidechain pumping.  
  `{"sidechain": "On", "audio_from": "Drums (or a muted ghost-kick track)", "ratio": 4, "threshold_db": "set for ~7 dB gain reduction on each kick", "attack_ms": 0.5, "release_ms": 39.0, "knee_db": 0}`
- **Utility** (medium): Side/mid -17.4 dB, L/R correlation 0.964.  
  `{"width_percent": 13}`
- Automation Auto Filter › Frequency (Hz): [(454.0, 18562), (462.0, 3618)] (lowpass closing: spectral edge moves 18562 -> 3618 Hz)
- Automation Auto Filter › Frequency (Hz): [(60.0, 86), (68.0, 1227)] (highpass rising: spectral edge moves 86 -> 1227 Hz)
- Automation Auto Filter › Frequency (Hz): [(272.0, 20), (280.0, 3661)] (highpass rising: spectral edge moves 20 -> 3661 Hz)
- Automation Auto Filter › Frequency (Hz): [(280.0, 3661), (288.0, 20)] (highpass falling: spectral edge moves 3661 -> 20 Hz)
- Automation Auto Filter › Frequency (Hz): [(426.0, 65), (434.0, 129)] (highpass rising: spectral edge moves 65 -> 129 Hz)
- Automation Auto Filter › Frequency (Hz): [(484.0, 108), (492.0, 1303)] (highpass rising: spectral edge moves 108 -> 1303 Hz)

## A Reverb (Return, audio)

- **Reverb** (low): Median free-decay RT60 across stems: 1.00 s (drums 0.37s, drums 0.32s, drums 0.35s, drums 0.26s, drums 0.31s, bass 1.89s, piano 0.64s, guitar 3.69s, other 2.16s, vocals 1.70s, vocals 2.54s, vocals 1.35s).  
  `{"decay_time_s": 1.0, "predelay_ms": 20, "size": 60, "dry_wet": 100, "hi_cut_hz": 6000}`

## Master

- **EQ Eight**: Gentle sub cleanup; the measured tilt is reported so you can compare your rebuild against it. `{"bands": [{"band": 1, "type": "Low Cut (12 dB/oct)", "freq_hz": 25}], "note": "Overall tilt -1.6 dB/oct (reference only)"}`
- **Glue Compressor**: Master crest factor 12.8 dB, LRA 5.2 LU. `{"ratio": 2, "attack_ms": 10, "release_s": "Auto", "threshold_db": "until 1-2 dB GR", "dry_wet": 100}`
- **Limiter**: Measured: -5.7 LUFS integrated, true peak 6.4 dBTP. The limiter ceiling matches the measured peak. `{"ceiling_db": -0.1, "gain_db": "raise until integrated loudness reaches the target", "target_lufs": -5.7, "lookahead_ms": 3}`

## Warnings

- Tempo searched around the 146 BPM that was given.
- Tempo drifts across the track (live playing or tempo automation). The grid is an average.
- Tempo is not steady: beats sit up to 216 ms away from a constant grid (143.95-146.53 BPM). Notes and warp markers follow the tracked beats.
- The beat could not be followed in -1-26 s, 171-191 s (a sudden tempo change is the usual reason). Notes and warp markers there are not reliable.
- 12 stems supplied in a folder; nothing was separated here.
