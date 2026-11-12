"""Ableton Live 12 Set (.als) writer.

An .als file is gzip-compressed XML. Live's format is not publicly documented, so this writer never
invents structure: it clones tracks, clips and devices from Live 12.4.x sets that were saved by Live
itself (see templates/NOTICE.md), then fills in names, colours, notes, sample references and a small
set of parameters, and renumbers the shared automation-target Id pool.

Optionally a user template (an empty set saved by *your* Live version, containing at least one MIDI
track, one audio track and one return track) replaces the bundled skeleton and track shells, which
maximises compatibility with that Live version.
"""
from __future__ import annotations

import copy
import gzip
import os
import xml.etree.ElementTree as ET
from typing import Iterable

import numpy as np
import soundfile as sf

HERE = os.path.dirname(__file__)
TEMPLATES = os.path.join(HERE, "templates", "live12_templates.xml.gz")

_lib_cache: ET.Element | None = None


def _lib() -> ET.Element:
    global _lib_cache
    if _lib_cache is None:
        with gzip.open(TEMPLATES) as f:
            _lib_cache = ET.parse(f).getroot()
    return _lib_cache


def _template(kind: str, attr: str) -> ET.Element:
    el = None
    for c in _lib().findall(kind):
        if c.get("kind") == attr or c.get("tag") == attr:
            el = c
            break
    if el is None:
        raise KeyError(f"no template {kind}:{attr}")
    return copy.deepcopy(el[0])


def _is_pool(el: ET.Element) -> bool:
    t = el.tag
    return "Id" in el.attrib and (t.endswith("Target") or t == "Pointee" or t.startswith("ControllerTargets."))


class IdPool:
    def __init__(self, start: int):
        self.next = start

    def take(self) -> int:
        v = self.next
        self.next += 1
        return v

    def renumber(self, root: ET.Element) -> dict[int, int]:
        """Give every pool element under root a fresh Id and fix PointeeId references inside root."""
        mapping: dict[int, int] = {}
        for el in root.iter():
            if _is_pool(el):
                old = int(el.get("Id"))
                new = self.take()
                mapping[old] = new
                el.set("Id", str(new))
        for el in root.iter("PointeeId"):
            v = int(el.get("Value"))
            if v in mapping:
                el.set("Value", str(mapping[v]))
        return mapping


def _set(el: ET.Element | None, path: str, value) -> bool:
    """Set <path><Manual Value=...> (device parameters) or <path Value=...>."""
    if el is None:
        return False
    node = el.find(path)
    if node is None:
        return False
    target = node.find("Manual") if node.find("Manual") is not None else node
    if isinstance(value, bool):
        value = "true" if value else "false"
    target.set("Value", str(value))
    return True


def _target_id(device: ET.Element, path: str) -> int | None:
    node = device.find(path)
    if node is None or node.find("AutomationTarget") is None:
        return None
    return int(node.find("AutomationTarget").get("Id"))


def _clear(el: ET.Element):
    for c in list(el):
        el.remove(c)


# ------------------------------------------------------------------------------------------ clips

def midi_clip(notes, start: float, end: float, name: str, color: int, bpb: int) -> ET.Element:
    clip = _template("Clip", "midi")
    clip.set("Time", f"{start:g}")
    length = end - start
    _set(clip, "CurrentStart", f"{start:g}")
    _set(clip, "CurrentEnd", f"{end:g}")
    for tag, v in (("LoopStart", 0), ("LoopEnd", length), ("StartRelative", 0), ("OutMarker", length),
                   ("HiddenLoopStart", 0), ("HiddenLoopEnd", length)):
        _set(clip, f"Loop/{tag}", f"{v:g}")
    _set(clip, "Loop/LoopOn", False)
    _set(clip, "Name", name)
    _set(clip, "Color", color)
    _set(clip, "ScrollerTimePreserver/RightTime", f"{min(length, 16):g}")
    _set(clip, "GrooveSettings/GrooveId", -1)
    _set(clip, "TimeSignature/TimeSignatures/RemoteableTimeSignature/Numerator", bpb)
    kts = clip.find("Notes/KeyTracks")
    _clear(kts)
    by_key: dict[int, list] = {}
    for n in notes:
        rel = n.start - start
        if rel < 0 or rel >= length:
            continue
        by_key.setdefault(int(n.pitch), []).append((rel, min(n.duration, length - rel), int(n.velocity)))
    note_id = 1
    for i, key in enumerate(sorted(by_key)):
        kt = ET.SubElement(kts, "KeyTrack", Id=str(i))
        ns = ET.SubElement(kt, "Notes")
        for rel, dur, vel in sorted(by_key[key]):
            ET.SubElement(ns, "MidiNoteEvent", Time=f"{rel:g}", Duration=f"{dur:g}", Velocity=str(vel),
                          OffVelocity="64", NoteId=str(note_id))
            note_id += 1
        ET.SubElement(kt, "MidiKey", Value=str(key))
    _set(clip, "Notes/NoteIdGenerator/NextId", note_id)
    return clip


def _file_ref(fr: ET.Element, abs_path: str, rel_path: str):
    _set(fr, "RelativePathType", 3)
    _set(fr, "RelativePath", rel_path.replace(os.sep, "/"))
    _set(fr, "Path", abs_path.replace(os.sep, "/"))
    _set(fr, "OriginalFileSize", os.path.getsize(abs_path))
    _set(fr, "OriginalCrc", 0)
    _set(fr, "LivePackName", "")
    _set(fr, "LivePackId", "")


def _sample_ref(sr_el: ET.Element, abs_path: str, rel_path: str):
    info = sf.info(abs_path)
    _file_ref(sr_el.find("FileRef"), abs_path, rel_path)
    _set(sr_el, "LastModDate", int(os.path.getmtime(abs_path)))
    _set(sr_el, "DefaultDuration", info.frames)
    _set(sr_el, "DefaultSampleRate", info.samplerate)
    return info


def audio_clip(abs_path: str, rel_path: str, markers: list[tuple[float, float]], name: str, color: int, bpb: int) -> ET.Element:
    """markers: (second in the file, arrangement beat), first one at second 0. Two markers at the measured tempo
    stretch nothing; more markers, or a project tempo that differs from the measured one, make Live warp the stem."""
    clip = _template("Clip", "audio")
    _sample_ref(clip.find("SampleRef"), abs_path, rel_path)
    start = markers[0][1]
    beats = markers[-1][1] - start
    clip.set("Time", f"{start:g}")
    _set(clip, "CurrentStart", f"{start:g}")
    _set(clip, "CurrentEnd", f"{start + beats:g}")
    for tag, v in (("LoopStart", 0), ("LoopEnd", beats), ("StartRelative", 0), ("OutMarker", beats),
                   ("HiddenLoopStart", 0), ("HiddenLoopEnd", beats)):
        _set(clip, f"Loop/{tag}", f"{v:g}")
    _set(clip, "Loop/LoopOn", False)
    _set(clip, "Name", name)
    _set(clip, "Color", color)
    _set(clip, "TimeSignature/TimeSignatures/RemoteableTimeSignature/Numerator", bpb)
    _set(clip, "IsWarped", True)
    _set(clip, "WarpMode", 0)  # as in the donor clip (Beats); pick Complex Pro in Live for tonal stems that get stretched
    wm = clip.find("WarpMarkers")
    _clear(wm)
    for i, (sec, beat) in enumerate(markers):
        ET.SubElement(wm, "WarpMarker", Id=str(i), SecTime=repr(float(sec)), BeatTime=repr(float(beat - start)))
    _set(clip, "Fades/FadeInLength", 0)
    _set(clip, "Fades/FadeOutLength", 0)
    return clip


# ------------------------------------------------------------------------------------------ devices

EQ_MODES = {"Low Cut (48 dB/oct)": 0, "Low Cut (12 dB/oct)": 1, "Low Cut (24 dB/oct)": 0, "Low Shelf": 2, "Bell": 3,
            "Notch": 4, "High Shelf": 5, "High Cut (12 dB/oct)": 6, "High Cut (48 dB/oct)": 7}


def build_device(dev, ids: IdPool) -> tuple[ET.Element | None, dict[str, int]]:
    """Returns (xml device, {param name: automation target id}) for a sounddesign.Device."""
    name, p = dev.name, dev.params
    tag = {"EQ Eight": "Eq8", "Compressor": "Compressor2", "Glue Compressor": "GlueCompressor", "Reverb": "Reverb",
           "Echo": "Echo", "Auto Filter": "AutoFilter2", "Utility": "StereoGain", "Saturator": "Saturator",
           "Limiter": "Limiter", "Drift": "Drift", "Operator": "Operator", "Wavetable": "InstrumentVector"}.get(name)
    if tag is None:
        return None, {}
    el = _template("Device", tag)
    ids.renumber(el)
    _set(el, "UserName", "")
    _set(el, "Annotation", (dev.why or "")[:500])
    targets: dict[str, int] = {}
    if tag == "Eq8":
        bands = p.get("bands", [])
        for i in range(8):
            _set(el, f"Bands.{i}/ParameterA/IsOn", False)
        for i, b in enumerate(bands[:8]):
            base = f"Bands.{i}/ParameterA"
            _set(el, f"{base}/IsOn", True)
            _set(el, f"{base}/Mode", EQ_MODES.get(b["type"], 3))
            _set(el, f"{base}/Freq", float(np.clip(b["freq_hz"], 10, 22000)))
            _set(el, f"{base}/Gain", float(np.clip(b.get("gain_db", 0), -15, 15)))
            _set(el, f"{base}/Q", float(np.clip(b.get("q", 0.71), 0.1, 18)))
    elif tag == "Compressor2":
        thr = p.get("threshold_db")
        if isinstance(thr, (int, float)):
            _set(el, "Threshold", float(10 ** (np.clip(thr, -60, 0) / 20)))  # stored as linear gain (observed 1 == 0 dB)
        _set(el, "Ratio", float(p.get("ratio", 4)))
        _set(el, "Attack", float(p.get("attack_ms", 1)))
        _set(el, "Release", float(p.get("release_ms", 50)))
        _set(el, "Knee", float(p.get("knee_db", 6)))
        _set(el, "DryWet", 1)
    elif tag == "GlueCompressor":
        thr = p.get("threshold_db")
        if isinstance(thr, (int, float)):
            _set(el, "Threshold", float(np.clip(thr, -40, 0)))
        _set(el, "Makeup", float(p.get("makeup_db", 0)) if isinstance(p.get("makeup_db"), (int, float)) else 0)
        _set(el, "DryWet", 1)
    elif tag == "Reverb":
        _set(el, "DecayTime", float(np.clip(p.get("decay_time_s", 1.2) * 1000, 200, 60000)))
        _set(el, "PreDelay", float(p.get("predelay_ms", 20)))
    elif tag == "Echo":
        _set(el, "Feedback", float(np.clip(p.get("feedback_percent", 40) / 100, 0, 0.95)))
        _set(el, "DryWet", 1)
    elif tag == "AutoFilter2":
        _set(el, "Filter_Frequency", 18000.0)
        targets["Frequency (Hz)"] = _target_id(el, "Filter_Frequency")
    elif tag == "StereoGain":
        w = p.get("width_percent")
        if isinstance(w, (int, float)):
            _set(el, "StereoWidth", float(np.clip(w / 100, 0, 4)))
        if p.get("bass_mono"):
            _set(el, "BassMono", True)
            _set(el, "BassMonoFrequency", float(np.clip(p.get("bass_mono_hz", 120), 50, 500)))
    elif tag == "Saturator":
        _set(el, "PreDrive", float(np.clip(p.get("drive_db", 3), 0, 36)))
        _set(el, "DryWet", float(np.clip(p.get("dry_wet", 100) / 100, 0, 1)))
    elif tag == "Limiter":
        _set(el, "Ceiling", float(np.clip(p.get("ceiling_db", -0.3), -24, 0)))
        _set(el, "Gain", 0)
    elif tag == "Drift":
        f = p.get("filter_freq_hz")
        if isinstance(f, (int, float)):
            _set(el, "Filter_Frequency", float(np.clip(f, 20, 19999)))
        _apply_env(el, p.get("amp_env", {}), "Envelope1_Attack", "Envelope1_Decay", "Envelope1_Sustain", "Envelope1_Release", seconds=True)
    elif tag == "Operator":
        for k in (1, 2, 3):
            _set(el, f"Operator.{k}/IsOn", False)
        _set(el, "Operator.0/WaveForm", 0)
        _set(el, "Operator.0/IsOn", True)
    elif tag == "InstrumentVector":
        txt = str(p.get("filter_1", ""))
        hz = [float(t) for t in txt.replace("Hz", "").split() if t.replace(".", "", 1).isdigit()]
        if hz:
            _set(el, "Voice_Filter1_Frequency", float(np.clip(hz[-1], 30, 20000)))
        _apply_env(el, p.get("amp_env", {}), "Voice_Modulators_AmpEnvelope_Times_Attack", "Voice_Modulators_AmpEnvelope_Times_Decay",
                   "Voice_Modulators_AmpEnvelope_Sustain", "Voice_Modulators_AmpEnvelope_Times_Release", seconds=True)
    return el, {k: v for k, v in targets.items() if v is not None}


def _apply_env(el, env: dict, a, d, s, r, seconds: bool):
    if not env:
        return
    k = 0.001 if seconds else 1
    if env.get("attack_ms") is not None:
        _set(el, a, float(np.clip(env["attack_ms"] * k, 0.001, 10)))
    if env.get("decay_ms") is not None:
        _set(el, d, float(np.clip(env["decay_ms"] * k, 0.001, 30)))
    if env.get("sustain_db") is not None:
        _set(el, s, float(np.clip(10 ** (env["sustain_db"] / 20), 0, 1)))
    if env.get("release_ms") is not None:
        _set(el, r, float(np.clip(env["release_ms"] * k, 0.001, 30)))


def sampler_device(abs_path: str, rel_path: str, ids: IdPool, name: str) -> ET.Element:
    el = _template("Device", "MultiSampler")
    ids.renumber(el)
    part = el.find(".//MultiSamplePart")
    info = _sample_ref(part.find("SampleRef"), abs_path, rel_path)
    _set(part, "Name", name)
    for rng in ("KeyRange", "VelocityRange", "SelectorRange"):
        lo, hi = (1, 127) if rng == "VelocityRange" else (0, 127)
        for t, v in (("Min", lo), ("Max", hi), ("CrossfadeMin", lo), ("CrossfadeMax", hi)):
            _set(part, f"{rng}/{t}", v)
    _set(part, "RootKey", 60)
    _set(part, "Detune", 0)
    _set(part, "Volume", 1)
    _set(part, "SampleStart", 0)
    _set(part, "SampleEnd", max(1, info.frames - 1))
    _set(part, "SustainLoop/Start", 0)
    _set(part, "SustainLoop/End", max(1, info.frames - 1))
    _set(part, "ReleaseLoop/Start", 0)
    _set(part, "ReleaseLoop/End", max(1, info.frames - 1))
    _set(el, "UserName", "")
    return el


# ------------------------------------------------------------------------------------------ tracks

def _new_track(kind: str, user_tpl: ET.Element | None) -> ET.Element:
    if user_tpl is not None:
        tag = {"midi": "MidiTrack", "audio": "AudioTrack", "return": "ReturnTrack"}[kind]
        t = user_tpl.find(f"LiveSet/Tracks/{tag}")
        if t is not None:
            t = copy.deepcopy(t)
            _clear(t.find("DeviceChain/DeviceChain/Devices"))
            for v in t.findall(".//ClipSlotList/ClipSlot/ClipSlot/Value"):
                _clear(v)
            for ev in t.findall(".//ArrangerAutomation/Events"):
                _clear(ev)
            env = t.find("AutomationEnvelopes/Envelopes")
            if env is not None:
                _clear(env)
            return t
    return _template("Track", kind)


def _fix_sends(track: ET.Element, n_returns: int, ids: IdPool, levels: list[float]):
    sends = track.find("DeviceChain/Mixer/Sends")
    if sends is None:
        return
    holders = list(sends)
    if not holders and n_returns:
        raise RuntimeError("template track has no send slot to copy")
    proto = holders[0] if holders else None
    _clear(sends)
    for i in range(n_returns):
        h = copy.deepcopy(proto)
        h.set("Id", str(i))
        ids.renumber(h)
        lvl = levels[i] if i < len(levels) else float("-inf")
        lin = 10 ** (lvl / 20) if np.isfinite(lvl) else 0.0003162277571
        _set(h, "Send", float(np.clip(lin, 0.0003162277571, 1)))
        sends.append(h)


def _name_track(t: ET.Element, name: str, color: int, annotation: str):
    _set(t, "Name/EffectiveName", name)
    _set(t, "Name/UserName", name)
    _set(t, "Name/Annotation", annotation[:2000])
    _set(t, "Color", color)


def _automation(track: ET.Element, target_id: int, points: Iterable[tuple[float, float]], env_id: int, ids: IdPool):
    envs = track.find("AutomationEnvelopes/Envelopes")
    ae = ET.SubElement(envs, "AutomationEnvelope", Id=str(env_id))
    ET.SubElement(ET.SubElement(ae, "EnvelopeTarget"), "PointeeId", Value=str(target_id))
    auto = ET.SubElement(ae, "Automation")
    evs = ET.SubElement(auto, "Events")
    pts = sorted(points)
    first = pts[0][1] if pts else 18000
    ET.SubElement(evs, "FloatEvent", Id=str(ids.take()), Time="-63072000", Value=f"{first:g}")
    for t, v in pts:
        ET.SubElement(evs, "FloatEvent", Id=str(ids.take()), Time=f"{max(0, t):g}", Value=f"{float(np.clip(v, 20, 19999)):g}")
    tv = ET.SubElement(auto, "AutomationTransformViewState")
    ET.SubElement(tv, "IsTransformPending", Value="false")
    ET.SubElement(tv, "TimeAndValueTransforms")


def _max_pool_id(root: ET.Element) -> int:
    return max((int(el.get("Id")) for el in root.iter() if _is_pool(el)), default=0)


def write(analysis, out_dir: str, path: str, template: str | None = None) -> str:
    a = analysis
    bpb = a.rhythm.beats_per_bar
    bpm = a.tempo
    user_tpl = None
    if template:
        with gzip.open(template) as f:
            user_tpl = ET.parse(f).getroot()
    root = copy.deepcopy(user_tpl) if user_tpl is not None else copy.deepcopy(_lib().find("Skeleton")[0])
    ls = root.find("LiveSet")
    tracks_el = ls.find("Tracks")
    _clear(tracks_el)
    ids = IdPool(max(_max_pool_id(root), _max_pool_id(_lib())) + 1)
    markers = a.warp_markers()
    total_beats = markers[-1][1]
    end_beat = float(np.ceil(total_beats / bpb) * bpb)

    returns = list(a.returns)
    ret_names = [r.name for r in returns]
    track_id = 100

    def add_devices(track_el, devices, track_xml_devices):
        tmap = {}
        for dv in devices:
            x, targets = build_device(dv, ids)
            if x is None:
                continue
            x.set("Id", str(len(track_xml_devices)))
            track_xml_devices.append(x)
            for k, v in targets.items():
                tmap[(dv.name, k)] = v
        return tmap

    def add_track(kind, name, color, annotation, sends, mute=False, volume_db=0.0):
        nonlocal track_id
        t = _new_track(kind, user_tpl)
        ids.renumber(t)
        t.set("Id", str(track_id))
        track_id += 1
        _name_track(t, name, color, annotation)
        _set(t, "TrackGroupId", -1)
        if kind != "return":
            _fix_sends(t, len(returns), ids, [sends.get(n, float("-inf")) for n in ret_names])
        else:
            _fix_sends(t, len(returns), ids, [])
        _set(t, "DeviceChain/Mixer/Speaker", not mute)
        _set(t, "DeviceChain/Mixer/Volume", float(np.clip(10 ** (volume_db / 20), 0.0003162277571, 1.99)))
        return t

    regular = []
    for tr in a.tracks:
        ann = _annotation(tr)
        # 1) reference stem (audio)
        ref = add_track("audio", f"REF {tr.name}", tr.color, f"Separated stem ({a.separation_method}). " + ann, tr.sends,
                        mute=tr.stem != "vocals")
        abs_stem = os.path.join(out_dir, tr.audio_file)
        ref.find("DeviceChain/MainSequencer/Sample/ArrangerAutomation/Events").append(
            audio_clip(abs_stem, tr.audio_file, markers, f"{tr.name} stem", tr.color, bpb))
        if tr.kind == "audio":  # vocals: processing lives on the stem itself
            add_devices(ref, tr.devices, ref.find("DeviceChain/DeviceChain/Devices"))
            regular.append(ref)
            continue
        regular.append(ref)
        # 2) rebuild tracks (MIDI)
        if tr.stem == "drums" and tr.drum_samples:
            from ..transcribe import DRUM_NOTES
            for piece, rel in tr.drum_samples.items():
                notes = [type(n)(60, n.start, n.duration, n.velocity) for n in tr.clip_notes if n.pitch == DRUM_NOTES[piece]]
                if not notes:
                    continue
                t = add_track("midi", f"{piece.replace('_', ' ').title()}", tr.color, f"Sampler with the {piece} one-shot cut from the drum stem. Notes play C3.", tr.sends)
                devs = t.find("DeviceChain/DeviceChain/Devices")
                smp = sampler_device(os.path.join(out_dir, rel), rel, ids, piece)
                smp.set("Id", "0")
                devs.append(smp)
                t.find("DeviceChain/MainSequencer/ClipTimeable/ArrangerAutomation/Events").append(
                    midi_clip(notes, 0, end_beat, piece, tr.color, bpb))
                regular.append(t)
            # One extra (muted) track with every drum note on the GM map carries the drum-bus chain.
            bus = add_track("midi", "Drums (full MIDI, GM map)", tr.color,
                            "All drum notes on one track (C1 kick, D1 snare, D#1 clap, F#1 closed hat, A#1 open hat). Load any Drum Rack. " + ann,
                            tr.sends, mute=True)
            add_devices(bus, tr.devices, bus.find("DeviceChain/DeviceChain/Devices"))
            bus.find("DeviceChain/MainSequencer/ClipTimeable/ArrangerAutomation/Events").append(
                midi_clip(tr.clip_notes, 0, end_beat, "Drums", tr.color, bpb))
            regular.append(bus)
            continue
        t = add_track("midi", f"{tr.name} ({tr.role})", tr.color, ann, tr.sends)
        devs_el = t.find("DeviceChain/DeviceChain/Devices")
        chain = ([tr.instrument] if tr.instrument else []) + list(tr.devices)
        tmap = add_devices(t, chain, devs_el)
        t.find("DeviceChain/MainSequencer/ClipTimeable/ArrangerAutomation/Events").append(
            midi_clip(tr.clip_notes, 0, end_beat, tr.name, tr.color, bpb))
        env_id = 0
        for au in tr.automation:
            tid = tmap.get((au.device, au.param))
            if tid:
                _automation(t, tid, au.points, env_id, ids)
                env_id += 1
        regular.append(t)

    for r in regular:
        tracks_el.append(r)
    for r in returns:
        t = add_track("return", r.name, r.color, _annotation(r), {})
        add_devices(t, r.devices, t.find("DeviceChain/DeviceChain/Devices"))
        tracks_el.append(t)

    # master chain, tempo, time signature
    main = ls.find("MainTrack") if ls.find("MainTrack") is not None else ls.find("MasterTrack")
    mdevs = main.find("DeviceChain/DeviceChain/Devices")
    _clear(mdevs)
    for dv in a.master:
        x, _ = build_device(dv, ids)
        if x is not None:
            x.set("Id", str(len(mdevs)))
            mdevs.append(x)
    _set(main, "DeviceChain/Mixer/Tempo", f"{bpm:g}")
    tempo_target = main.find("DeviceChain/Mixer/Tempo/AutomationTarget")
    ts_target = main.find("DeviceChain/Mixer/TimeSignature/AutomationTarget")
    ts_value = 2 * 99 + (bpb - 1)  # observed: 4/4 == 201 (encoding inferred, see NOTICE)
    _set(main, "DeviceChain/Mixer/TimeSignature", ts_value)
    for ae in main.findall("AutomationEnvelopes/Envelopes/AutomationEnvelope"):
        pid = int(ae.find("EnvelopeTarget/PointeeId").get("Value"))
        evs = ae.find("Automation/Events")
        if tempo_target is not None and pid == int(tempo_target.get("Id")):
            for e in list(evs):
                if e.get("Time") != "-63072000":
                    evs.remove(e)
                else:
                    e.set("Value", f"{bpm:g}")
        if ts_target is not None and pid == int(ts_target.get("Id")):
            for e in evs:
                if e.get("Time") == "-63072000":
                    e.set("Value", str(ts_value))

    # section locators (structure observed in a Live 12.0 set)
    loc_parent = ls.find("Locators/Locators")
    if loc_parent is not None:
        _clear(loc_parent)
        for i, s in enumerate(a.sections):
            beat = float(a.to_beats(s.start))
            loc = ET.SubElement(loc_parent, "Locator", Id=str(i))
            ET.SubElement(loc, "LomId", Value="0")
            ET.SubElement(loc, "Time", Value=f"{max(0.0, round(beat, 3)):g}")
            ET.SubElement(loc, "Name", Value=f"{s.role} {s.letter} ({s.bars} bars)")
            ET.SubElement(loc, "Annotation", Value="")
            ET.SubElement(loc, "IsSongStart", Value="false")

    # transport loop over the first drop/chorus if any
    drop = next((s for s in a.sections if s.role.startswith("Drop")), None)
    if drop is not None:
        _set(ls, "Transport/LoopStart", f"{float(a.to_beats(drop.start)):g}")
        _set(ls, "Transport/LoopLength", f"{min(drop.bars, 8) * bpb:g}")

    _set(ls, "NextPointeeId", ids.next + 1)
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with gzip.open(path, "wb") as f:
        f.write(data)
    return path


def _annotation(tr) -> str:
    parts = []
    if tr.instrument:
        parts.append(f"Instrument: {tr.instrument.name} - {tr.instrument.why}")
    for d in tr.devices:
        parts.append(f"{d.name}: {d.why}")
    if tr.sidechain_from:
        parts.append(f"Sidechain: route Compressor input from {tr.sidechain_from} (not pre-routed in this file).")
    parts += tr.notes
    return " | ".join(parts)
