"""Composer: structure, timing, harmony, the validator itself, MIDI round trip, CLI and the push into (fake) Live."""
import dataclasses
import json
import os
import sys

import pytest

from track2ableton import midi
from track2ableton.compose import Spec, all_ok, compose, validate, write
from track2ableton.compose.__main__ import main
from track2ableton.compose.live import push
from track2ableton.compose.model import Note, swing_shift

from . import fake_live as fl

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "ableton_bridge"))
from T2A_Bridge.handlers import Handlers  # noqa: E402


def failed(comp):
    return [c.name for c in validate(comp) if not c.ok]


@pytest.fixture(scope="module")
def song():
    return compose(Spec())


def test_default_song_shape_and_checks(song):
    assert song.total_bars == 200 and [s.start for s in song.sections] == [1, 17, 33, 49, 65, 81, 113, 121, 129, 145, 177, 193]
    assert [s.start for s in song.sections if s.kind == "drop"] == [81, 145]
    assert abs(song.seconds(81) - 147.7) < 0.05 and abs(song.seconds(145) - 265.8) < 0.05
    assert failed(song) == []
    assert {t.name for t in song.tracks} >= {"Kick", "Clap", "Sub", "Mid Bass", "Pad", "Hook", "Chant", "Roll", "Conga Hi"}


@pytest.mark.parametrize("key,prog", [("A minor", None), ("F minor", None), ("C# minor", "minor_loop"), ("D# minor", None),
                                      ("Bb minor", None), ("D dorian", None), ("E phrygian", None), ("D hijaz", None)])
@pytest.mark.parametrize("variant", [0, 1, 2])
def test_every_key_mode_and_variant_passes(key, prog, variant):
    for structure in ("extended", "radio", "loop16"):
        comp = compose(Spec(key=key, progression=prog, variant=variant, structure=structure, bpm=124))
        assert failed(comp) == [], (key, variant, structure)


def test_feel_options_pass():
    for kw in ({"swing_hook": True, "swing_bass": True}, {"bake_feel": False}, {"swing": 50.0, "late_ms": 0.0}, {"swing": 62.0, "late_ms": 12.0}):
        assert failed(compose(Spec(**kw))) == [], kw


def test_deterministic_and_variants_differ():
    def dump(c):
        return [(t.name, [(n.pitch, n.start, n.duration, n.velocity) for n in t.notes]) for t in c.tracks]
    assert dump(compose(Spec())) == dump(compose(Spec()))
    a, b = compose(Spec(variant=0)), compose(Spec(variant=1))
    assert dump(a) != dump(b)
    for name in ("Sub", "Hook", "Wood"):
        assert [(n.pitch, n.grid) for n in a.track(name).notes] != [(n.pitch, n.grid) for n in b.track(name).notes]


def test_groove_rules(song):
    kick, sub, clap = song.track("Kick"), song.track("Sub"), song.track("Clap")
    drop_bar = [n.grid - 80 * 4 for n in kick.notes if 80 * 4 <= n.grid < 81 * 4]
    assert drop_bar == [0.0, 1.0, 2.0, 3.0]                               # four on the floor on the drop
    assert all(n.start == n.grid and n.grid % 0.25 == 0 for n in kick.notes + clap.notes)
    kicks = {n.grid for n in kick.notes}
    assert sub.notes and not any(n.grid in kicks for n in sub.notes)
    assert not any(49 <= n.grid // 4 + 1 <= 64 for n in kick.notes)       # Break 1 has no kick
    assert not [t.name for t in song.tracks if t.role == "drum" and any(121 <= n.grid // 4 + 1 <= 128 for n in t.notes)]
    for first in (73, 137):                                               # sub is out for the 8 bars before each drop
        assert not any(first <= n.grid // 4 + 1 <= first + 7 for n in sub.notes)
    assert any(n.grid // 4 + 1 == 81 for n in sub.notes) and any(n.grid // 4 + 1 == 145 for n in sub.notes)
    assert {n.pitch for n in sub.notes if 80 * 4 <= n.grid < 81 * 4} == {33}  # A = 55 Hz under A minor
    for b in (80, 144):                                                   # beat 4 before the drop: only the shout
        lo = (b - 1) * 4 + 3
        assert [t.name for t in song.tracks if any(lo <= n.grid < lo + 1 for n in t.notes)] == ["Chant"]


def test_build_rises_bar_by_bar(song):
    drums = [t for t in song.tracks if t.role == "drum"]
    for first in (73, 137):
        e = []
        for k in range(8):
            lo = (first + k - 1) * 4
            e.append(sum(n.velocity for t in drums for n in t.notes if lo <= n.grid < lo + 4) / (3 if k == 7 else 4))
        assert e == sorted(e) and len(set(e)) == 8, e
        roll = [n.velocity for n in song.track("Roll").notes if (first - 1) * 4 <= n.grid < (first + 7) * 4]
        assert roll == sorted(roll) and roll[-1] > roll[0] + 50
    assert not any(abs(n.grid * 3 - round(n.grid * 3)) < 1e-9 and n.grid % 0.125 for t in drums for n in t.notes)  # no triplets


def test_feel_is_written_into_the_midi(song):
    sh = swing_shift(57.5)
    late = 0.006 * 130 / 60
    shaker, conga = song.track("Shaker"), song.track("Conga Hi")
    odd = [n for n in shaker.notes if round(n.grid / 0.25) % 2 == 1]
    even = [n for n in shaker.notes if round(n.grid / 0.25) % 2 == 0]
    assert odd and all(abs(n.start - n.grid - sh) < 1e-9 for n in odd) and all(n.start == n.grid for n in even)
    assert all(abs(n.start - n.grid - late - (sh if round(n.grid / 0.25) % 2 else 0)) < 1e-9 for n in conga.notes)
    assert abs(sh * 60 / 130 * 1000 - 17.3) < 0.1                         # 57.5 % at 130 BPM = 17.3 ms
    straight = compose(Spec(bake_feel=False))
    assert all(n.start == n.grid for t in straight.tracks for n in t.notes)


def test_harmony(song):
    assert [song.bars[b].chord.label for b in (81, 83, 85, 87)] == ["Am", "G", "F", "E7(b9)"]
    assert [song.bars[b].chord.label for b in (49, 51, 53, 55)] == ["Dm", "E7(b9)", "Am", "Am"]
    hook = song.track("Hook")
    assert all(n.grid % 4 >= 2.0 for n in hook.notes)                      # beats 3-4 only
    run = [n.pitch % 12 for n in hook.notes if 87 * 4 <= n.grid < 88 * 4]  # bar 88: Phrygian-dominant run over E
    assert run == [4, 5, 8, 9, 11, 8]
    pad = song.track("Pad")
    assert min(n.pitch for n in pad.notes) >= 52
    g_sharp = [n for n in song.track("Sub").notes if n.pitch % 12 == 8]
    assert g_sharp and all(song.bars[int(n.grid // 4) + 1].chord.label == "E7(b9)" for n in g_sharp)  # leading tone only over V


def _with(comp, name, notes):
    tracks = [dataclasses.replace(t, notes=notes) if t.name == name else t for t in comp.tracks]
    return dataclasses.replace(comp, tracks=tracks)


def test_validator_catches_planted_errors(song):
    sub, hook, kick, conga = (song.track(n) for n in ("Sub", "Hook", "Kick", "Conga Hi"))
    n0 = next(n for n in sub.notes if n.grid >= 80 * 4)
    cases = {
        "bass never starts together with a kick":
            _with(song, "Sub", sub.notes + [Note(33, 320.0, 0.1, 100, 320.0)]),
        "bass is monophonic (no overlapping notes)":
            _with(song, "Sub", [dataclasses.replace(n, duration=0.6) if n is n0 else n for n in sub.notes]),
        "harmony: every pitched note belongs to the scale or chord of its bar":
            _with(song, "Hook", hook.notes + [Note(70, 322.0, 0.2, 90, 322.0)]),          # A# over A minor
        "hook never holds a minor 2nd / tritone / major 7th against the bass for longer than a 16th":
            _with(song, "Hook", hook.notes + [Note(70, 320.5, 1.5, 90, 320.5)]),
        "kick and clap exactly on the straight grid":
            _with(song, "Kick", [dataclasses.replace(n, start=n.start + 0.01) if n.grid == 320.0 else n for n in kick.notes]),
        "timing: every note on the grid plus its planned swing / laid-back offset":
            _with(song, "Conga Hi", [dataclasses.replace(n, start=n.start + 0.02) if i == 5 else n for i, n in enumerate(conga.notes)]),
        "arrangement: each section contains exactly the planned instruments":
            _with(song, "Kick", kick.notes + [Note(60, 200.0, 0.2, 110, 200.0)]),         # kick inside Break 1
        "drops: beat 4 before a drop is empty, the sub is out for the build's last 8 bars and back on the drop":
            _with(song, "Kick", kick.notes + [Note(60, 319.0, 0.2, 110, 319.0)]),
        "hook stays on beats 3-4, leaving beats 1-2 to the vocal":
            _with(song, "Hook", hook.notes + [Note(69, 320.25, 0.2, 90, 320.25)]),
        "every note is inside the song with a valid length, pitch and velocity":
            _with(song, "Hook", hook.notes + [Note(69, 799.9, 0.5, 90, 799.9)]),
        "builds: drum energy per played beat rises in every bar of the last 8":
            _with(song, "Roll", [n for n in song.track("Roll").notes if not 78 * 4 <= n.grid < 79 * 4]),
        "no note overlaps the next note of the same pitch":
            _with(song, "Kick", [dataclasses.replace(n, duration=1.5) if n.grid == 320.0 else n for n in kick.notes]),
    }
    for check, broken in cases.items():
        assert check in failed(broken), check


def test_radio_edit_is_cut_from_the_extended_mix(song):
    radio = compose(Spec(structure="radio"))
    assert radio.total_bars == 96 and abs(radio.seconds(97) - 177.2) < 0.1
    assert [(s.name, s.start, s.bars) for s in radio.sections] == [
        ("Groove", 1, 16), ("Break 1", 17, 8), ("Build 1", 25, 8), ("Drop 1", 33, 32), ("Break 2", 65, 8), ("Build 2", 73, 8),
        ("Drop 2", 81, 8), ("Outro", 89, 8)]
    src = [(n.pitch, n.grid - 80 * 4, n.velocity) for n in song.track("Sub").notes if 80 * 4 <= n.grid < 112 * 4]
    dst = [(n.pitch, n.grid - 32 * 4, n.velocity) for n in radio.track("Sub").notes if 32 * 4 <= n.grid < 64 * 4]
    assert src == dst and src


def test_midi_files_round_trip(tmp_path, song):
    info = write(song, str(tmp_path))
    assert info["all_checks_passed"] and info["length"] == "6:09.2" and info["chords"]["main"] == ["Am", "G", "F", "E7(b9)"]
    saved = json.load(open(tmp_path / "arrangement.json", encoding="utf-8"))
    assert saved["tracks"][0]["name"] == "Kick" and all(t["groove_in_live"] == "None" for t in saved["tracks"])
    for t, meta in zip(song.tracks, saved["tracks"]):
        back = sorted(midi.read(str(tmp_path / meta["file"])), key=lambda n: (round(n["start"], 4), n["pitch"]))
        want = sorted(t.notes, key=lambda n: (round(n.start, 4), n.pitch))
        assert len(back) == len(want) == meta["notes"]
        for b, w in zip(back, want):
            assert b["pitch"] == w.pitch and b["velocity"] == w.velocity and abs(b["start"] - w.start) <= 1 / 480 + 1e-9
    gm = midi.read(str(tmp_path / "MIDI" / "drums_gm.mid"))
    assert len(gm) == sum(len(t.notes) for t in song.tracks if t.role == "drum") and {n["pitch"] for n in gm} >= {36, 39, 42}
    report = open(tmp_path / "REPORT.md", encoding="utf-8").read()
    assert "Drop 1" in report and "נכשל" not in report


def test_cli_and_bad_input(tmp_path, capsys):
    assert main(["--out", str(tmp_path / "x"), "--structure", "loop16", "--variants", "2", "--key", "F minor", "--show", "1-2"]) == 0
    out = capsys.readouterr().out
    assert "checks 14/14 passed" in out and "Kick       x...x...x...x..." in out
    assert os.path.exists(tmp_path / "x" / "v1" / "MIDI" / "01 Kick.mid")
    for bad in (Spec(key="H minor"), Spec(key="A major"), Spec(swing=70), Spec(bpm=20), Spec(key="A minor", progression="hijaz"),
                Spec(structure="nope")):
        with pytest.raises(ValueError):
            compose(bad)


def test_push_into_fake_live():
    s = fl.Song()
    h = Handlers(s, fl.Application(s))
    comp = compose(Spec(structure="loop16", bpm=126))
    before = len(s.tracks)
    res = push(comp, lambda cmd, **kw: h.handle(cmd, kw), at_bar=5, prefix="N ")
    assert res["ok"] and s.tempo == 126 and len(s.tracks) == before + len(comp.tracks)
    kick = next(t for t in s.tracks if t.name == "N Kick")
    clip = kick.arrangement_clips[-1]
    assert clip.start_time == 16.0 and len(clip.notes) == len(comp.track("Kick").notes)
    with pytest.raises(ValueError):
        push(comp, lambda cmd, **kw: h.handle(cmd, kw), prefix="N ")       # refuses to create duplicates
