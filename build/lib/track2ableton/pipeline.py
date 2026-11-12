"""End-to-end: audio file -> analysis -> Ableton rebuild package."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from . import __version__, audio as aio, beatmap, midi, mixanalysis as mx, rhythm as rh, separation, sounddesign as sd
from . import structure as st, tonal as tn, transcribe as tr

MIN_SECONDS = 4.0
STEM_ORDER = ["drums", "bass", "piano", "guitar", "other", "vocals"]
STEM_LABEL = {"drums": "Drums", "bass": "Bass", "vocals": "Vocals", "other": "Synths / Other", "piano": "Piano / Keys", "guitar": "Guitar"}


@dataclass
class Analysis:
    source: str
    duration: float
    sr: int
    rhythm: rh.Rhythm
    tonal: tn.Tonal
    sections: list[st.Section]
    chords: list[tn.Chord]
    lead_in_beats: float           # where song time 0 sits in the arrangement (beats)
    lufs: float
    true_peak: float
    lra: float
    master_spectrum: mx.SpectrumProfile
    master_dynamics: mx.Dynamics
    master_stereo: mx.Stereo
    separation_method: str
    separation_note: str
    tracks: list[sd.TrackRecipe]
    returns: list[sd.TrackRecipe]
    master: list[sd.Device]
    timings: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    beat_map: Any = None               # beatmap.BeatMap: where every beat really is
    project_bpm: float | None = None   # tempo of the Live Set when it differs from the measured one (stems get warped)
    skipped_files: list[str] = field(default_factory=list)

    @property
    def drifting(self) -> bool:
        return self.beat_map is not None and self.beat_map.drifting

    @property
    def tempo(self) -> float:
        return float(self.project_bpm or self.rhythm.bpm)

    def to_beats(self, t):
        if self.drifting:
            return self.beat_map.to_beats(t)
        return (np.asarray(t, dtype=float) - self.rhythm.first_downbeat) / self.rhythm.beat_len + self.lead_in_beats

    def to_seconds(self, beats):
        if self.drifting:
            return self.beat_map.to_seconds(beats)
        return (np.asarray(beats, dtype=float) - self.lead_in_beats) * self.rhythm.beat_len + self.rhythm.first_downbeat

    def song_start_beat(self) -> float:
        return float(self.to_beats(0.0))

    def warp_markers(self) -> list[tuple[float, float]]:
        """(second in the audio, arrangement beat): two points for a steady tempo, more where it drifts."""
        if self.drifting:
            return self.beat_map.warp_markers(self.duration)
        return [(0.0, self.song_start_beat()), (float(self.duration), float(self.to_beats(self.duration)))]


def _slug(s: str) -> str:
    return re.sub(r"[^\w-]+", "_", s).strip("_") or "track"          # \w keeps letters of any script


def musical_grid(mono: np.ndarray, sr: int, duration: float):
    """Tempo, key and where the bars are: one constant grid for a steady song, the tracked beats for one that drifts.
    Returns (rhythm, tonal, beat_map, bar_grid in seconds)."""
    chroma_pack = tn.chroma_features(mono, sr)
    onsets = rh.onset_envelopes(mono, sr)
    rhythm = rh.analyze(mono, sr, onsets, chroma_pack[0], tn.FPS)
    tonal = tn.analyze(mono, sr, chroma_pack)
    beat_map = beatmap.track(onsets, rhythm, duration, chroma_pack[0], tn.FPS)
    if beat_map.drifting:
        # One constant grid would slide away from the audio: from here on the tracked beats are the grid.
        inside = beat_map.times[(beat_map.times >= 0) & (beat_map.times < duration)]
        rhythm.beat_times = inside
        rhythm.first_downbeat = float(beat_map.times[beat_map.downbeat])
        rhythm.downbeat_offset = int(np.argmin(np.abs(inside - rhythm.first_downbeat)))
        rhythm.bpm = round(beat_map.bpm, 2)
        rhythm.notes.append(f"Tempo is not steady: beats sit up to {beat_map.drift_ms:.0f} ms away from a constant grid "
                            f"({beat_map.bpm_lo:.2f}-{beat_map.bpm_hi:.2f} BPM). Notes and warp markers follow the tracked beats.")
    else:
        if abs(beat_map.steady_bpm - rhythm.bpm) > 1e-6:
            # The tempo measured along the whole song is not the round number the analysis snapped to: over three
            # minutes 127.93 against 128 is a tenth of a second.
            rhythm.bpm = round(beat_map.steady_bpm, 3)
            rhythm.first_downbeat = float(beat_map.steady_downbeat)
            rhythm.beat_times = rhythm.first_downbeat + np.arange(int((duration - rhythm.first_downbeat) / rhythm.beat_len) + 1) * rhythm.beat_len
            rhythm.downbeat_offset = 0
            rhythm.notes.append(f"Tempo measured along the song: {rhythm.bpm:g} BPM. The grid uses that, not the nearest round number.")
    if beat_map.lost:
        rhythm.notes.append("The beat could not be followed in " + ", ".join(f"{x:.0f}-{y:.0f} s" for x, y in beat_map.lost)
                            + " (a sudden tempo change is the usual reason). Notes and warp markers there are not reliable.")
    if not beat_map.drifting:
        if beat_map.unclear:
            rhythm.notes.append(f"Tempo is NOT steady (beats up to {beat_map.drift_ms:.0f} ms off a constant grid), but following the "
                                "beat did not catch clearly more onsets than a constant grid, so a constant grid was kept. "
                                "A tempo change inside the song is the usual reason: check the grid by ear in every section.")
    bars = rhythm.bar_times()
    pre = []
    t = rhythm.first_downbeat
    while t > 1e-3:
        t -= rhythm.bar_len
        pre.append(t)
    bar_grid = np.array(sorted(b for b in pre if b > -rhythm.bar_len) + [b for b in np.arange(rhythm.first_downbeat, duration, rhythm.bar_len)])
    bar_grid = bar_grid[bar_grid >= -rh.START_S - 1e-6] if (bar_grid >= -rh.START_S - 1e-6).sum() >= 4 else bars
    if beat_map.drifting:
        bar_grid = beat_map.bar_times(duration)
    bar_grid = np.maximum(bar_grid, 0.0)              # a downbeat measured a few ms before second 0 is second 0
    return rhythm, tonal, beat_map, bar_grid


def run(path: str, out_dir: str, separation_method: str = "auto", demucs_model: str = "htdemucs_6s",
        transcription: str = "auto", write_als: bool = True, als_template: str | None = None, log=print) -> Analysis:
    t_start = time.time()
    timings: dict[str, float] = {}
    warnings: list[str] = []

    def tick(name):
        timings[name] = round(time.time() - t_start - sum(timings.values()), 2)
        log(f"  [{timings[name]:6.1f}s] {name}")

    os.makedirs(out_dir, exist_ok=True)
    if os.path.isdir(path):
        audio = sorted(f for f in os.listdir(path) if f.lower().endswith(separation.AUDIO_EXT))
        if len(audio) == 1:
            path = os.path.join(path, audio[0])       # one file in a folder is a song to separate, not a stem
    given = separation.from_folder(path) if os.path.isdir(path) else None
    song = separation.mixdown(given) if given else aio.load(path)
    if song.duration < MIN_SECONDS:
        raise ValueError(f"{song.duration:.1f} s of audio is too short to find a tempo and bars in (at least {MIN_SECONDS:g} s)")
    if song.sr > 48000:
        song = song.resampled(44100)
    if song.channels == 1:
        warnings.append("Mono source: stereo measurements are not meaningful.")
    mono = song.mono
    sr = song.sr
    tick("decode")

    # ------------------------------------------------------------------ global musical analysis
    rhythm, tonal, beat_map, bar_grid = musical_grid(mono, sr, song.duration)
    sections = st.analyze(mono, sr, bar_grid, tonal.chroma, tonal.fps)
    chords = tn.chords_on_grid(tonal, bar_grid, rhythm.beat_times, rhythm.beats_per_bar)
    tick("tempo, key, chords, structure")

    lead_in_grid = float(rhythm.beats_per_bar if rhythm.first_downbeat > rh.START_S else 0)

    def to_beats(t):
        if beat_map.drifting:
            return beat_map.to_beats(t)
        return (np.asarray(t, dtype=float) - rhythm.first_downbeat) / rhythm.beat_len + lead_in_grid

    def to_seconds(b):
        if beat_map.drifting:
            return beat_map.to_seconds(b)
        return (np.asarray(b, dtype=float) - lead_in_grid) * rhythm.beat_len + rhythm.first_downbeat

    # ------------------------------------------------------------------ master measurements
    lufs = mx.integrated_lufs(song)
    tp = mx.true_peak_db(song)
    lra = mx.loudness_range(song)
    mspec = mx.spectrum_profile(mono, sr)
    mdyn = mx.dynamics(mono, sr)
    mst = mx.stereo(song)
    tick("loudness & master")

    # ------------------------------------------------------------------ stems
    stems = given or separation.separate(path, song, separation_method, demucs_model, workdir=os.path.join(out_dir, "_demucs_tmp"))
    tick(f"separation ({stems.method})")

    stem_dir = os.path.join(out_dir, "Stems")
    midi_dir = os.path.join(out_dir, "MIDI")
    for d in (stem_dir, midi_dir):
        os.makedirs(d, exist_ok=True)

    tracks: list[sd.TrackRecipe] = []
    kick_times = None
    reverb_times = []
    echo_hits = []
    kinds = {n: stems.kinds.get(n, n if n in STEM_ORDER else "other") for n in stems.stems}
    names = sorted(stems.stems, key=lambda n: (STEM_ORDER.index(kinds[n]), n not in STEM_ORDER, n))
    used: set[str] = set()
    for stem_name in names:
        a = stems.stems[stem_name]
        name = kinds[stem_name]                       # what the stem is: drums / bass / vocals / piano / guitar / other
        if a.sr != sr:
            a = a.resampled(sr)
        n = min(a.data.shape[1], song.data.shape[1])
        a = aio.Audio(a.data[:, :n], sr)
        m = a.mono
        level = aio.rms_db(m)
        if level < -50:
            log(f"  - {stem_name}: silent ({level:.0f} dBFS), skipped")
            stems.skipped.append(f"{stem_name}: silent")
            continue
        label = STEM_LABEL.get(stem_name, stem_name if given else stem_name.title())
        if name == "vocals" and stems.method.startswith("dsp"):
            label = "Centre Lead"  # the DSP separator cannot tell a vocal from a centred synth lead
        slug = _slug(label)
        while slug in used:                           # two names can clean up to the same file name
            slug += "_2"
        used.add(slug)
        stem_path = aio.save(os.path.join(stem_dir, f"{slug}.wav"), a.data, sr)
        spec = mx.spectrum_profile(m, sr)
        dyn = mx.dynamics(m, sr)
        ster = mx.stereo(a)
        rv = mx.reverb(m, sr)
        if rv.rt60_s > 0:
            reverb_times.append((name, rv.rt60_s))
        meas: dict[str, Any] = {"rms_dbfs": round(level, 1), "spectrum": asdict(spec), "dynamics": asdict(dyn),
                                "stereo": asdict(ster), "reverb": asdict(rv)}
        devices: list[sd.Device] = []
        notes_out: list[str] = []
        sidechain = None
        automation: list[sd.Automation] = []
        clip_notes: list[tr.Note] = []
        drum_samples: dict[str, str] = {}

        if name == "drums":
            hits = tr.detect_drum_hits(m, sr, low_source=mono if stems.method.startswith("dsp") else None)
            trans = tr.drums_to_midi(hits, to_beats)
            kicks = np.array([h.time for h in hits if h.piece == "kick"])
            if kick_times is None or kicks.size > kick_times.size:
                kick_times = kicks
            shots = tr.extract_one_shots(m, sr, hits)
            samp_dir = os.path.join(out_dir, "Samples", slug)
            os.makedirs(samp_dir, exist_ok=True)
            for piece, clip in shots.items():
                drum_samples[piece] = aio.save(os.path.join(samp_dir, f"{piece}.wav"), clip, sr)
            pads = {p: {"note": tr.DRUM_NOTES[p], "pad": _pad_name(tr.DRUM_NOTES[p]), "sample": os.path.relpath(f, out_dir)}
                    for p, f in drum_samples.items()}
            instrument = sd.Device("Drum Rack", "instrument", {"pads": pads, "patterns_16_steps": trans.details["patterns"]},
                                   "medium", "One-shots cut from the cleanest hit of each detected kit piece in the drum stem.")
            meas["drum_counts"] = trans.details["counts"]
            role, kind = "Drums", "midi"
            eq = sd._eq_device(spec, "Drum bus tone")
            if eq:
                devices.append(eq)
            devices.append(sd._comp_device(dyn, glue=True))
            if dyn.crest_db < 10:
                devices.append(sd.Device("Saturator", "audio_effect", {"type": "Soft Sine", "drive_db": 4, "dry_wet": 60}, "low",
                                         "Dense drum bus with low crest factor usually has saturation or clipping."))
        elif name == "bass":
            trans = tr.mono_to_midi(m, sr, to_beats, 28, 420, tonal.tuning_cents)
            d = trans.details
            # The DSP separator low-passes the bass stem (crossover 150-300 Hz): only judge harmonics below it.
            harm = mx.harmonic_profile(d["_x22k"], tr.SR, d["_f0"], d["_hop_s"],
                                       max_freq=280.0 if stems.method.startswith("dsp") else None)
            env = sd._env_stats(m, sr, d["_notes_sec"])
            instrument = sd.bass_instrument(harm, env, d["glide_ratio"], d["f0_median_hz"], spec)
            meas["harmonics"] = harm
            meas["envelope"] = env
            role, kind = "Bass", "midi"
            if (sat := mx.distortion_amount(m, sr)) > 0.25:
                devices.append(sd.Device("Saturator", "audio_effect", {"type": "Analog Clip", "drive_db": round(3 + 9 * sat, 1)}, "low",
                                         f"Flat-topped waveform (clip score {sat:.2f})."))
            eq = sd._eq_device(spec, "Bass tone shaping")
            if eq:
                devices.append(eq)
            devices.append(sd._comp_device(dyn))
        elif name == "vocals":
            trans = tr.mono_to_midi(m, sr, to_beats, 75, 1100, tonal.tuning_cents, min_dur=0.08)
            d = trans.details
            env = {}
            role, kind = "Vocals", "audio"
            instrument = None
            meas["pitch"] = {k: v for k, v in d.items() if not k.startswith("_")}
            if d["voiced_ratio"] > 0.15 and d["median_cents_off_grid"] < 12:
                notes_out.append(f"Pitch sits within ~{d['median_cents_off_grid']:.0f} cents of the semitone grid: "
                                 "probably pitch-corrected. Live 12 has no stock real-time pitch-correction device; "
                                 "use a third-party plug-in or Live's audio-to-MIDI + resynthesis.")
            eq = sd._eq_device(spec, "Vocal tone")
            if eq:
                devices.append(eq)
            devices.append(sd._comp_device(dyn))
        else:
            use_bp = transcription in ("auto", "basic-pitch") and tr.basic_pitch_available()
            if use_bp:
                try:
                    trans = tr.basic_pitch_to_midi(stem_path, to_beats)
                except Exception as exc:  # pragma: no cover - optional dependency
                    warnings.append(f"basic-pitch failed on {name}: {exc}; used salience transcription.")
                    use_bp = False
            if not use_bp:
                trans = tr.poly_to_midi(m, sr, to_beats, tonal.tuning_cents)
            poly = trans.details.get("mean_polyphony", 2.0)
            mono_tr = tr.mono_to_midi(m, sr, to_beats, 80, 2000, tonal.tuning_cents)
            harm = mx.harmonic_profile(mono_tr.details["_x22k"], tr.SR, mono_tr.details["_f0"], mono_tr.details["_hop_s"])
            sec = [(n.start, n.start + n.duration) for n in trans.notes]
            sec_s = [(float(to_seconds(s)), float(to_seconds(e))) for s, e in sec]
            env = sd._env_stats(m, sr, sec_s)
            instrument, role = sd.melodic_instrument(name, poly, env, harm, spec)
            meas["harmonics"] = harm
            meas["envelope"] = env
            meas["polyphony"] = poly
            kind = "midi"
            eq = sd._eq_device(spec, f"{role} tone")
            if eq:
                devices.append(eq)
            # chord-track alternative
            ch = tr.chords_to_midi(chords, to_beats, octave_base=48 if spec.centroid_hz < 1500 else 60)
            midi.write(os.path.join(midi_dir, f"{slug}_chords.mid"), ch.notes, rhythm.bpm, f"{label} chords", 0, rhythm.beats_per_bar)
            notes_out.append(f"Also exported block chords from the chord analysis: MIDI/{slug}_chords.mid")

        # ---------------- shared processing estimates for melodic/vocal stems
        if name != "drums":
            # Fold on detected kicks and on the beat grid; keep the clearer result (kick detection can
            # be noisy, and most sidechain triggers sit on the beat).
            # With the DSP separator the kick's sub body lands in the bass stem: listen above it.
            hp = 120.0 if stems.method.startswith("dsp") and name == "bass" else None
            pump = max((mx.pumping(m, sr, rhythm.beat_times, kick_times, hp), mx.pumping(m, sr, rhythm.beat_times, None, hp)),
                       key=lambda p: (p.detected, p.depth_db))
            meas["pumping"] = asdict(pump)
            if pump.detected:
                sidechain = "Drums"
                devices.append(sd.Device("Compressor", "audio_effect", {
                    "sidechain": "On", "audio_from": "Drums (or a muted ghost-kick track)", "ratio": 4 if pump.depth_db < 8 else 10,
                    "threshold_db": f"set for ~{pump.depth_db:.0f} dB gain reduction on each kick", "attack_ms": 0.5,
                    "release_ms": pump.release_ms, "knee_db": 0},
                    "medium", f"Envelope dips {pump.depth_db} dB right after each kick and recovers in ~{pump.release_ms:.0f} ms: sidechain pumping."))
            ec = mx.echo(m, sr, rhythm.bpm)
            meas["echo"] = asdict(ec)
            if ec.detected:
                echo_hits.append((name, ec))
            ut = sd._utility(ster)
            if ut:
                devices.append(ut)
            sweeps, curve = mx.filter_sweeps(m, sr, bar_grid, to_beats, boundaries_s=[sec.start for sec in sections[1:]])
            meas["filter_sweeps"] = [asdict(s) for s in sweeps]
            for s in sweeps[:6]:
                automation.append(sd.Automation("Auto Filter", "Frequency (Hz)", [(round(s.start_beat, 2), round(s.from_hz)), (round(s.end_beat, 2), round(s.to_hz))],
                                                f"{s.kind}: spectral edge moves {s.from_hz:.0f} -> {s.to_hz:.0f} Hz"))
            if sweeps:
                kind_f = "High-pass" if any(s.kind.startswith("highpass") for s in sweeps) and not any(s.kind.startswith("lowpass") for s in sweeps) else "Low-pass"
                devices.insert(0, sd.Device("Auto Filter", "audio_effect", {"filter_type": kind_f, "slope": "24 dB", "frequency_hz": "automated (see automation)"},
                                            "medium", f"{len(sweeps)} filter sweep(s) of more than one octave detected."))
        else:
            ut = sd._utility(ster)
            if ut:
                devices.append(ut)

        sends = {}
        rv_send = sd._reverb_send(rv)
        if np.isfinite(rv_send) and name != "drums":
            sends["A Reverb"] = rv_send
        if name in [e[0] for e in echo_hits]:
            sends["B Echo"] = -10.0

        mid_path = None
        if kind == "midi" or name == "vocals":
            mid_path = midi.write(os.path.join(midi_dir, f"{slug}.mid"), trans.notes, rhythm.bpm, label,
                                  9 if name == "drums" else 0, rhythm.beats_per_bar)
            clip_notes = trans.notes
        meas["transcription"] = {"method": trans.method, "confidence": trans.confidence, "notes": len(trans.notes),
                                 **{k: v for k, v in trans.details.items() if not k.startswith("_")}}
        tracks.append(sd.TrackRecipe(
            name=label, stem=name, kind=kind, role=role, color=sd.COLORS.get(name, 30), instrument=instrument,
            devices=devices, sends=sends, sidechain_from=sidechain, automation=automation,
            midi_file=os.path.relpath(mid_path, out_dir) if mid_path else None,
            audio_file=os.path.relpath(stem_path, out_dir), notes=notes_out, measurements=meas,
            clip_notes=clip_notes, drum_samples={k: os.path.relpath(v, out_dir) for k, v in drum_samples.items()}))
        tick(f"stem: {stem_name}")

    # ------------------------------------------------------------------ returns
    returns: list[sd.TrackRecipe] = []
    if reverb_times:
        rt = float(np.median([r for _, r in reverb_times]))
        returns.append(sd.TrackRecipe("A Reverb", "return", "audio", "Return", sd.COLORS["return"], None, [
            sd.Device("Reverb", "audio_effect", {"decay_time_s": round(max(0.4, rt), 2), "predelay_ms": 20, "size": 60 if rt < 1.5 else 100,
                                                 "dry_wet": 100, "hi_cut_hz": 6000}, "low",
                      f"Median free-decay RT60 across stems: {rt:.2f} s ({', '.join(f'{n} {r:.2f}s' for n, r in reverb_times)}).")], {}))
    if echo_hits:
        n0, e0 = echo_hits[0]
        returns.append(sd.TrackRecipe("B Echo", "return", "audio", "Return", sd.COLORS["return"], None, [
            sd.Device("Echo", "audio_effect", {"sync": "On", "left": e0.division, "right": e0.division, "feedback_percent": int(e0.feedback * 100),
                                               "dry_wet": 100}, "low",
                      f"Envelope self-similarity at {e0.division} (strength {e0.strength}) on {', '.join(n for n, _ in echo_hits)}.")], {}))

    master = sd.master_chain(lufs, tp, lra, mspec, mdyn)
    if rhythm.confidence < 0.3:
        warnings.append("Low tempo confidence: check the BPM by tapping along before relying on the grid.")
    if tonal.key_confidence < 0.3:
        warnings.append("Low key confidence (atonal, modal or modulating material).")
    warnings += rhythm.notes + tonal.notes

    lead_in = beat_map.lead_in if beat_map.drifting else lead_in_grid
    result = Analysis(path, song.duration, sr, rhythm, tonal, sections, chords, lead_in, lufs, tp, lra, mspec, mdyn, mst,
                      stems.method, stems.quality_note, tracks, returns, master, timings, warnings, beat_map, None, stems.skipped)
    write_outputs(result, out_dir, write_als, log, als_template)
    tick("write outputs")
    return result


def _pad_name(note: int) -> str:
    from .dsp import midi_name
    return midi_name(note)


def to_json(a: Analysis) -> dict:
    r = a.rhythm
    return {
        "tool": f"track2ableton {__version__}",
        "source": os.path.basename(a.source),
        "duration_s": round(a.duration, 2),
        "sample_rate": a.sr,
        "tempo": {"bpm": r.bpm, "bpm_measured": round(r.bpm_raw, 2), "confidence": round(r.confidence, 2),
                  "time_signature": f"{r.beats_per_bar}/4", "first_downbeat_s": round(r.first_downbeat, 3),
                  "swing_percent_mpc": round(r.swing_percent, 1), "tempo_drift_bpm_std": round(r.tempo_stability, 2)},
        "arrangement": {"song_start_beat": a.song_start_beat(), "first_downbeat_beat": a.lead_in_beats,
                        "project_bpm": a.tempo, "warp_markers_sec_beat": [[round(t, 4), round(b, 4)] for t, b in a.warp_markers()]},
        "beat_map": None if a.beat_map is None else {
            "mean_bpm": round(a.beat_map.bpm, 3), "slowest_8_bars_bpm": round(a.beat_map.bpm_lo, 2), "fastest_8_bars_bpm": round(a.beat_map.bpm_hi, 2),
            "furthest_from_constant_grid_ms": round(a.beat_map.drift_ms, 1), "drifting": a.beat_map.drifting,
            "not_steady_but_not_followed": a.beat_map.unclear,
            "map_does_not_fit_audio_s": [[round(x, 1), round(y, 1)] for x, y in a.beat_map.lost],
            "beat_clear_share": round(a.beat_map.tracked, 2), "followed_blind_s": [[round(x, 1), round(y, 1)] for x, y in a.beat_map.weak],
            "found_again_at_s": [round(x, 1) for x in a.beat_map.relocked]},
        "key": {"name": a.tonal.key_name, "camelot": a.tonal.camelot, "confidence": round(a.tonal.key_confidence, 2),
                "candidates": a.tonal.key_candidates, "tuning_cents": round(a.tonal.tuning_cents, 1),
                "a4_hz": round(a.tonal.tuning_a4_hz, 2), "scale_pitch_classes": a.tonal.scale_pcs},
        "chords": [{"start_s": round(c.start, 2), "end_s": round(c.end, 2), "name": c.name, "roman": a.tonal.roman(c)} for c in a.chords],
        "sections": [dict(asdict(s), bars=s.bars) for s in a.sections],
        "master": {"integrated_lufs": round(a.lufs, 1), "true_peak_dbtp": round(a.true_peak, 1), "lra_lu": round(a.lra, 1),
                   "spectrum": asdict(a.master_spectrum), "dynamics": asdict(a.master_dynamics), "stereo": asdict(a.master_stereo),
                   "chain": [asdict(d) for d in a.master]},
        "separation": {"method": a.separation_method, "note": a.separation_note},
        "tracks": [_track_json(t) for t in a.tracks],
        "returns": [_track_json(t) for t in a.returns],
        "warnings": a.warnings,
        "timings_s": a.timings,
    }


def _track_json(t: sd.TrackRecipe) -> dict:
    d = asdict(t)
    d.pop("clip_notes", None)
    return d


class _Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


def write_outputs(a: Analysis, out_dir: str, write_als: bool, log=print, als_template: str | None = None):
    data = to_json(a)
    with open(os.path.join(out_dir, "recipe.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, cls=_Enc)
    from . import report
    report.write_html(a, data, os.path.join(out_dir, "report.html"))
    report.write_markdown(a, data, os.path.join(out_dir, "REBUILD.md"))
    if write_als:
        try:
            from .ableton import als
            base = os.path.basename(os.path.normpath(a.source))
            name = base if os.path.isdir(a.source) else os.path.splitext(base)[0]      # "Song v1.2 stems" is a folder, not a file with an extension
            als.write(a, out_dir, os.path.join(out_dir, f"{_slug(name)} Rebuild.als"), als_template)
        except Exception as exc:  # keep the rest of the package even if .als export fails
            a.warnings.append(f".als export failed: {exc}")
            log(f"  ! .als export failed: {exc}")
            raise
