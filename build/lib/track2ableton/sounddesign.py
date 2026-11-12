"""Turns measurements into an Ableton Live 12 rebuild recipe: instruments, device chains,
parameters, sends, sidechain routing and automation, each with a confidence and a reason."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import dsp, mixanalysis as mx

# Ableton track colour indices (Live's 70-colour palette). Values are indices, not RGB.
COLORS = {"drums": 1, "bass": 13, "vocals": 26, "other": 20, "guitar": 9, "piano": 23, "master": 0, "return": 58}


@dataclass
class Device:
    name: str                  # name as shown in Live's browser
    kind: str                  # "instrument" | "audio_effect" | "midi_effect" | "rack"
    params: dict[str, Any]
    confidence: str            # "high" | "medium" | "low"
    why: str
    stock: bool = True         # ships with Live 12 (Suite for some instruments)


@dataclass
class Automation:
    device: str
    param: str
    points: list[tuple[float, float]]  # (beat, value in the parameter's displayed unit)
    why: str


@dataclass
class TrackRecipe:
    name: str
    stem: str
    kind: str                 # "midi" | "audio"
    role: str
    color: int
    instrument: Device | None
    devices: list[Device]
    sends: dict[str, float]   # return name -> send level in dB
    sidechain_from: str | None = None
    automation: list[Automation] = field(default_factory=list)
    midi_file: str | None = None
    audio_file: str | None = None
    notes: list[str] = field(default_factory=list)
    measurements: dict[str, Any] = field(default_factory=dict)
    clip_notes: list = field(default_factory=list)   # transcribe.Note list for .als MIDI clips
    drum_samples: dict[str, str] = field(default_factory=dict)


def _eq_device(spec: mx.SpectrumProfile, purpose: str) -> Device | None:
    if not spec.eq_moves:
        return None
    bands = []
    for i, m in enumerate(spec.eq_moves[:8]):
        if m.kind == "highpass":
            bands.append({"band": i + 1, "type": f"Low Cut ({m.slope_db_oct if m.slope_db_oct in (12, 48) else 48} dB/oct)", "freq_hz": m.freq})
        elif m.kind == "lowpass":
            bands.append({"band": i + 1, "type": "High Cut (12 dB/oct)", "freq_hz": m.freq})
        else:
            bands.append({"band": i + 1, "type": "Bell", "freq_hz": m.freq, "gain_db": m.gain_db, "q": m.q})
    return Device("EQ Eight", "audio_effect", {"bands": bands}, "medium",
                  f"{purpose}: band edges and resonances measured from the stem's 1/3-octave spectrum "
                  f"(content {spec.lowest_hz:.0f} Hz - {spec.highest_hz:.0f} Hz, tilt {spec.tilt_db_per_oct:+.1f} dB/oct).")


def _comp_device(d: mx.Dynamics, glue: bool = False) -> Device:
    if glue:
        ratio = 4 if d.ratio >= 4 else 2
        return Device("Glue Compressor", "audio_effect", {
            "threshold_db": d.threshold_db, "ratio": ratio, "attack_ms": 10 if d.attack_ms >= 5 else 1,
            "release_s": "Auto", "makeup_db": round(min(6, (ratio - 1) * 1.5), 1), "dry_wet": 100},
            "low", f"Crest factor {d.crest_db} dB -> {d.compression_guess} bus compression.")
    return Device("Compressor", "audio_effect", {
        "threshold_db": d.threshold_db, "ratio": d.ratio, "attack_ms": d.attack_ms, "release_ms": d.release_ms,
        "knee_db": 6, "makeup": "auto"},
        "low", f"Crest factor {d.crest_db} dB (peak {d.peak_db} / RMS {d.rms_db} dBFS) -> {d.compression_guess} compression. "
               "Crest factor shows the amount of dynamic control, not the exact compressor settings.")


def _utility(st: mx.Stereo) -> Device | None:
    params: dict[str, Any] = {}
    if st.side_to_mid_db < -30:
        params["width_percent"] = 0
        why = f"Side/mid {st.side_to_mid_db} dB: effectively mono."
    else:
        params["width_percent"] = int(st.width_percent)
        why = f"Side/mid {st.side_to_mid_db} dB, L/R correlation {st.correlation}."
    if st.low_mono_below_hz:
        params["bass_mono"] = True
        params["bass_mono_hz"] = st.low_mono_below_hz
        why += f" No side energy below ~{st.low_mono_below_hz:.0f} Hz -> Bass Mono."
    if abs(st.pan) > 0.15:
        params["pan_hint"] = st.pan
    if params.get("width_percent") in (None, 100) and "bass_mono" not in params:
        return None
    return Device("Utility", "audio_effect", params, "medium", why)


def _reverb_send(rv: mx.ReverbEstimate) -> float:
    if rv.rt60_s <= 0:
        return float("-inf")
    return {"dry": -24.0, "short room": -15.0, "hall / plate": -10.0, "long ambient": -6.0}[rv.wet_hint]


def _env_stats(mono: np.ndarray, sr: int, notes_sec: list[tuple[float, float]]) -> dict[str, float]:
    """ADSR estimate from the amplitude envelope of transcribed notes. Release is only measured
    when the note is followed by enough silence; otherwise it is reported as unknown."""
    hop_s = 0.002
    env = mx.smooth_envelope(mono, sr, hop_s, 0.015)
    fps = 1 / hop_s
    starts = sorted(t0 for t0, _ in notes_sec)
    att, sus, rel, dec = [], [], [], []
    for t0, t1 in notes_sec[:300]:
        a, b = int(t0 * fps), int(t1 * fps)
        if b - a < 15 or b + 10 >= env.size:
            continue
        seg = env[a:b]
        pk_i = int(np.argmax(seg))
        pk = seg[pk_i] + 1e-12
        att.append(pk_i * hop_s * 1000)
        tail = seg[pk_i:]
        sus.append(20 * np.log10(np.median(tail[len(tail) // 2:]) / pk + 1e-9))
        below = np.where(tail < pk * 10 ** (-6 / 20))[0]
        if below.size:
            dec.append(below[0] * hop_s * 1000)
        nxt = next((s for s in starts if s > t1 - 1e-6), None)
        free = (nxt - t1) if nxt is not None else 2.0
        if free > 0.15:
            after = env[b: b + int(min(free, 2.0) * fps)]
            lvl = seg[-1] + 1e-12
            r = np.where(after < lvl * 10 ** (-30 / 20))[0]
            if r.size:
                rel.append(r[0] * hop_s * 1000)
    if not att:
        return {}
    out = {"attack_ms": round(float(np.median(att)), 1), "sustain_db": round(float(np.median(sus)), 1)}
    out["decay_ms"] = round(float(np.median(dec)), 0) if dec else None
    out["release_ms"] = round(float(np.median(rel)), 0) if rel else None
    return out


def bass_instrument(harm: dict, env: dict, glide_ratio: float, f0_median: float, spec: mx.SpectrumProfile) -> Device:
    wf = harm.get("waveform", "unknown")
    hs = harm.get("harmonics_db", [])
    n_strong = sum(1 for h in hs if h > -24)
    cutoff = float(np.clip(f0_median * max(n_strong, 1) * 1.2, 80, 18000)) if f0_median > 0 else spec.rolloff85_hz
    mono_glide = glide_ratio > 0.15
    if wf == "sine":
        return Device("Operator", "instrument", {
            "algorithm": "single carrier (Oscillator A only)", "osc_a_wave": "Sine", "voices": 1,
            "glide": "On" if mono_glide else "Off", "amp_env": env, "transpose": "0 st"},
            "medium", "Harmonics 2-12 are more than 30 dB below the fundamental: a pure sine sub bass.")
    shape = {"saw": "Saw", "filtered saw": "Saw", "square": "Rectangle (pulse width 50%)", "triangle": "Triangle"}.get(wf, "Saw")
    return Device("Drift", "instrument", {
        "osc_1_shape": shape, "osc_2": "Off (or Sine one octave down for sub weight)",
        "filter_type": "Low-pass (24 dB)", "filter_freq_hz": round(cutoff, 0), "filter_resonance": "low",
        "voice_mode": "Mono" + (" + Glide" if mono_glide else ""), "amp_env": env},
        "medium" if wf != "unknown" else "low",
        f"Harmonic series reads as '{wf}' (slope {harm.get('harmonic_slope_db_oct', '?')} dB/oct, "
        f"odd {harm.get('odd_db', '?')} dB / even {harm.get('even_db', '?')} dB). Filter cutoff set where harmonics fall below -24 dB "
        f"(~{n_strong} strong harmonics). Wavetable (Basic Shapes) or Analog can make the same tone.")


def melodic_instrument(stem: str, poly: float, env: dict, harm: dict, spec: mx.SpectrumProfile) -> tuple[Device, str]:
    sustain = env.get("sustain_db", -6)
    decay = env.get("decay_ms") or 500
    attack = env.get("attack_ms", 10)
    plucky = sustain < -14 and decay < 400
    if stem == "piano":
        return Device("Grand Piano (Core Library, Sampler)", "instrument", {"velocity_sens": "high"}, "medium",
                      "Separated piano stem; inharmonic piano partials are not modelled by Live's synths.", True), "Keys"
    if stem == "guitar":
        return Device("Simpler (load the guitar stem slice) or a guitar sample instrument", "instrument", {}, "low",
                      "Guitar timbre is better re-recorded or sliced from the stem than synthesised.", True), "Guitar"
    wf = harm.get("waveform", "saw")
    if poly >= 2.2 and attack > 40 and not plucky:
        return Device("Wavetable", "instrument", {
            "osc_1": "Basic Shapes > " + ("Saw" if "saw" in wf else "Square" if wf == "square" else "Sine/Triangle"),
            "unison": "Classic, 4 voices, amount 25%" if spec.tilt_db_per_oct > -6 else "Off",
            "filter_1": f"Low-pass 12 dB @ {round(min(spec.rolloff85_hz * 1.5, 12000))} Hz",
            "amp_env": env, "voices": 8}, "medium",
            f"Slow attack ({attack} ms), sustained, mean polyphony {poly:.1f} -> pad."), "Pad"
    if plucky:
        return Device("Drift", "instrument", {
            "osc_1_shape": "Saw" if "saw" in wf else "Rectangle", "filter_type": "Low-pass (24 dB)",
            "filter_freq_hz": round(min(spec.centroid_hz * 2, 12000)), "filter_env_amount": "high, short decay",
            "amp_env": env, "voice_mode": "Poly"}, "medium",
            f"Fast decay ({decay} ms) to low sustain ({sustain} dB) -> pluck."), "Pluck"
    if poly < 1.5:
        return Device("Wavetable", "instrument", {
            "osc_1": "Basic Shapes > Saw", "voice_mode": "Mono, Glide on", "filter_1": f"Low-pass 24 dB @ {round(min(spec.rolloff85_hz, 12000))} Hz",
            "amp_env": env}, "low", "Mostly monophonic sustained line -> lead."), "Lead"
    return Device("Drift", "instrument", {"osc_1_shape": "Saw", "filter_type": "Low-pass", "amp_env": env, "voice_mode": "Poly"},
                  "low", f"Polyphonic part (mean polyphony {poly:.1f}) with moderate sustain -> chords/stabs."), "Chords"


def master_chain(lufs: float, true_peak: float, lra: float, spec: mx.SpectrumProfile, dyn: mx.Dynamics) -> list[Device]:
    ceiling = round(min(-0.1, true_peak), 1)
    devs = [
        Device("EQ Eight", "audio_effect", {"bands": [{"band": 1, "type": "Low Cut (12 dB/oct)", "freq_hz": 25}],
                                             "note": f"Overall tilt {spec.tilt_db_per_oct:+.1f} dB/oct (reference only)"},
               "low", "Gentle sub cleanup; the measured tilt is reported so you can compare your rebuild against it."),
        Device("Glue Compressor", "audio_effect", {"ratio": 2, "attack_ms": 10, "release_s": "Auto", "threshold_db": "until 1-2 dB GR", "dry_wet": 100},
               "low", f"Master crest factor {dyn.crest_db} dB, LRA {lra:.1f} LU."),
        Device("Limiter", "audio_effect", {"ceiling_db": ceiling, "gain_db": "raise until integrated loudness reaches the target",
                                           "target_lufs": round(lufs, 1), "lookahead_ms": 3},
               "high" if lufs > -12 else "medium",
               f"Measured: {lufs:.1f} LUFS integrated, true peak {true_peak:.1f} dBTP. The limiter ceiling matches the measured peak."),
    ]
    return devs
