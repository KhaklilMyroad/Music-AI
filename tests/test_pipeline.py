"""End-to-end on a synthetic song with known ground truth, plus structural checks of the .als."""
import gzip
import json
import os
import xml.etree.ElementTree as ET
from collections import Counter

import numpy as np
import pytest
import soundfile as sf

from track2ableton import pipeline
from track2ableton.ableton.als import _is_pool

from .synth import SR, make_song


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    d = tmp_path_factory.mktemp("song")
    x, truth = make_song(bpm=124.0, offset_s=0.37)
    wav = str(d / "song.wav")
    sf.write(wav, x.T, SR, subtype="PCM_24")
    out = str(d / "out")
    a = pipeline.run(wav, out, separation_method="dsp", log=lambda *_: None)
    return a, out, truth


def test_global_analysis(result):
    a, out, truth = result
    assert a.rhythm.bpm == 124.0
    assert a.tonal.key_name == "A minor"
    assert abs(a.rhythm.first_downbeat - 0.37) < 0.03
    names = [c.name for c in a.chords if c.root >= 0]
    # Am F C G must be the dominant progression in the pad sections (bar 16 onwards)
    seq = [c.name.rstrip("7").replace("maj", "") for c in a.chords if c.start > 0.37 + 16 * 4 * 60 / 124 and c.root >= 0]
    for want in ("Am", "F", "C", "G"):
        assert want in seq, (want, seq)


def test_sections_found(result):
    a, *_ = result
    starts = [s.start_bar for s in a.sections]
    for b in (0, 8, 16, 24):
        assert any(abs(s - b) <= 1 for s in starts), starts


def test_outputs_exist(result):
    a, out, _ = result
    for f in ("recipe.json", "report.html", "REBUILD.md", "MIDI/Bass.mid", "MIDI/Drums.mid", "Stems/Drums.wav"):
        assert os.path.exists(os.path.join(out, f)), f
    data = json.load(open(os.path.join(out, "recipe.json")))
    assert data["tempo"]["bpm"] == 124.0
    bass = next(t for t in data["tracks"] if t["stem"] == "bass")
    assert bass["measurements"]["pumping"]["detected"]  # the bass is sidechained in the test song
    assert bass["sidechain_from"] == "Drums"


def _als(out):
    path = next(os.path.join(out, f) for f in os.listdir(out) if f.endswith(".als"))
    with gzip.open(path) as f:
        return ET.parse(f).getroot()


def test_als_structure(result):
    a, out, _ = result
    root = _als(out)
    assert root.tag == "Ableton" and root.get("MajorVersion") == "5"
    ls = root.find("LiveSet")
    tracks = list(ls.find("Tracks"))
    returns = [t for t in tracks if t.tag == "ReturnTrack"]
    assert tracks[-len(returns):] == returns if returns else True  # returns last
    # tempo
    assert float(ls.find("MainTrack/DeviceChain/Mixer/Tempo/Manual").get("Value")) == 124.0
    # one global pool of automation/modulation target ids, all unique; NextPointeeId above them
    pool = [int(el.get("Id")) for el in root.iter() if _is_pool(el)]
    dup = [k for k, v in Counter(pool).items() if v > 1]
    assert not dup, dup[:10]
    assert int(ls.find("NextPointeeId").get("Value")) > max(pool)
    pool_set = set(pool)
    for pid in root.iter("PointeeId"):
        assert int(pid.get("Value")) in pool_set
    # track ids unique
    tids = [t.get("Id") for t in tracks]
    assert len(tids) == len(set(tids))
    # every non-return track has one send per return track
    for t in tracks:
        assert len(t.findall("DeviceChain/Mixer/Sends/TrackSendHolder")) == len(returns), t.find("Name/EffectiveName").get("Value")
    # clips
    midi_clips = ls.findall(".//MidiTrack/DeviceChain/MainSequencer/ClipTimeable/ArrangerAutomation/Events/MidiClip")
    audio_clips = ls.findall(".//AudioTrack/DeviceChain/MainSequencer/Sample/ArrangerAutomation/Events/AudioClip")
    assert len(audio_clips) == len(a.tracks)
    assert midi_clips
    for c in midi_clips:
        ids = [int(n.get("NoteId")) for n in c.iter("MidiNoteEvent")]
        assert len(ids) == len(set(ids))
        nxt = int(c.find("Notes/NoteIdGenerator/NextId").get("Value"))
        assert nxt > max(ids, default=0)
        keys = [int(k.find("MidiKey").get("Value")) for k in c.find("Notes/KeyTracks")]
        assert keys == sorted(keys)
    # sample references point at files that exist
    for fr in root.iter("FileRef"):
        rel = fr.find("RelativePath").get("Value")
        assert os.path.exists(os.path.join(out, rel)), rel
    # locators from structure
    assert len(ls.findall("Locators/Locators/Locator")) == len(a.sections)


def test_template_option_uses_user_set(result, tmp_path):
    """A user-supplied set (here: a previous output) is accepted as the skeleton."""
    from track2ableton.ableton import als

    a, out, _ = result
    tpl = next(os.path.join(out, f) for f in os.listdir(out) if f.endswith(".als"))
    dst = str(tmp_path / "again.als")
    als.write(a, out, dst, template=tpl)
    with gzip.open(dst) as f:
        root = ET.parse(f).getroot()
    pool = [int(el.get("Id")) for el in root.iter() if _is_pool(el)]
    assert len(pool) == len(set(pool))
