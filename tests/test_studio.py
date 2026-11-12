"""Layers that clash, a master against its reference, sample packs, the installation check, the journal."""
import json
import os
import sys

import numpy as np
import pytest
import soundfile as sf
from scipy.signal import butter, sosfilt

from track2ableton import clash, doctor, mixmaster, samplepack

from .synth import SR, drift_clock, hat, kick, make_song, midi_hz, render_parts, saw
from .test_fix import groove
from .test_live_bridge import bridge  # noqa: F401  (a fake Live behind the real socket protocol)

BEAT = 60 / 125


def layers(tmp_path):
    n = int(16 * 4 * BEAT * SR)
    beats = np.arange(64) * BEAT

    def place(sig, times, gain=1.0):
        x = np.zeros(n)
        for t in times:
            i = int(t * SR)
            j = min(n, i + sig.size)
            x[i:j] += gain * sig[: j - i]
        return x

    def tone(pitch, dur, harm):
        t = np.arange(int(dur * SR)) / SR
        return 0.4 * saw(midi_hz(pitch), t, harm) * np.minimum(1, t / 0.005) * np.minimum(1, (dur - t) / 0.01)

    made = {"kick": place(kick(), beats, 0.9), "bass_offbeat": place(tone(33, BEAT * 0.4, 3), beats + BEAT / 2),
            "bass_on_kick": place(tone(33, BEAT * 0.4, 3), beats), "hats": place(hat(seed=1), beats + BEAT / 2, 0.8),
            "pad_mid": place(tone(69, BEAT * 3.9, 6), beats[::4]), "pad_low": place(tone(36, BEAT * 3.9, 2), beats[::4])}
    files = {}
    for name, x in made.items():
        files[name] = str(tmp_path / f"{name}.wav")
        sf.write(files[name], x, SR)
    return files


# ------------------------------------------------------------------------------------------- clash

def test_layers_that_share_a_band_clash_only_when_they_play_together(tmp_path):
    f = layers(tmp_path)
    r = clash.report({k: f[k] for k in ("kick", "bass_offbeat", "bass_on_kick", "hats", "pad_mid")}, bpm=125)
    pair = {frozenset((p["a"], p["b"])): p for p in r["pairs"]}
    together, apart = pair[frozenset(("kick", "bass_on_kick"))], pair[frozenset(("kick", "bass_offbeat"))]
    assert together["clash"] > 0.5 and apart["clash"] < 0.3
    assert together["same_bands_ignoring_time"] > 0.8 and apart["same_bands_ignoring_time"] > 0.8     # an average spectrum sees no difference
    assert "not at the same time" in apart["note"] and "note" not in together
    assert r["pairs"][0] is together                                             # the worst pair comes first
    assert pair[frozenset(("kick", "hats"))]["clash"] < 0.05
    assert together["worst_bands"][0]["band"] in ("40-50 Hz", "50-63 Hz", "63-79 Hz") and together["worst_bars"]
    assert r["who_owns_each_band"]["50-63 Hz"]["owner"] == "kick"
    assert 0 <= together["a_under_b"] <= 1 and 0 <= together["b_under_a"] <= 1
    with pytest.raises(ValueError):
        clash.report({"kick": f["kick"]})


def test_candidates_are_ranked_by_the_room_the_bed_leaves(tmp_path):
    f = layers(tmp_path)
    out = clash.fit({"kick": f["kick"], "bass": f["bass_offbeat"]}, {k: f[k] for k in ("bass_on_kick", "hats", "pad_mid", "pad_low")})
    order = [r["candidate"] for r in out["ranking"]]
    assert set(order[:2]) == {"hats", "pad_mid"} and set(order[2:]) == {"bass_on_kick", "pad_low"}
    free = {r["candidate"]: r["free"] for r in out["ranking"]}
    assert free["hats"] > 0.95 and free["pad_low"] < 0.5
    quiet = str(tmp_path / "quiet.wav")
    x, _ = sf.read(f["pad_low"])
    sf.write(quiet, x * 0.05, SR)
    again = clash.fit({"kick": f["kick"], "bass": f["bass_offbeat"]}, {"loud": f["pad_low"], "quiet": quiet})
    assert abs(again["ranking"][0]["free"] - again["ranking"][1]["free"]) < 0.02     # the file's own level does not decide
    with pytest.raises(ValueError):
        clash.fit({}, {"a": f["hats"]})


# ------------------------------------------------------------------------------------------- reference

def test_a_chain_towards_a_reference_and_the_check_after_it(tmp_path):
    x, _ = make_song(bpm=124.0, bars=16)
    mix, ref = str(tmp_path / "mix.wav"), str(tmp_path / "ref.wav")
    sf.write(mix, (x * 0.15).T, SR, subtype="PCM_24")
    bright = x + 1.5 * sosfilt(butter(2, 5000, "highpass", fs=SR, output="sos"), x, axis=1)      # more top end,
    sf.write(ref, (bright * 0.3).T, SR, subtype="PCM_24")                                        # and louder
    chain = mixmaster.match_chain(mix, ref)
    devices = [d["device"] for d in chain["chain"]]
    assert devices[0] == "EQ Eight" and devices[-1] == "Limiter"
    highs = [b for b in chain["chain"][0]["bands"] if b["freq_hz"] >= 4000]
    assert highs and all(b["gain_db"] > 0 for b in highs)
    limiter = chain["chain"][-1]
    assert limiter["ceiling_db"] == -1.0 and 3.0 < limiter["gain_db"] < 9.0 and chain["reference"]["lufs"] > chain["mix"]["lufs"]
    before = mixmaster.verify_match(mix, ref)
    assert not before["pass"] and not before["checks"]["loudness"] and not before["checks"]["tone"] and before["bands_still_off_db"]
    after = mixmaster.verify_match(ref, ref)
    assert after["pass"] and after["loudness_gap_db"] == 0 and not after["bands_still_off_db"]
    hot = str(tmp_path / "hot.wav")
    sf.write(hot, (bright / np.max(np.abs(bright))).T, SR, subtype="PCM_24")
    assert not mixmaster.verify_match(hot, hot)["checks"]["true_peak"]            # same tone and loudness, but peaking at full scale


# ------------------------------------------------------------------------------------------- sample packs

def test_a_pack_of_loops_that_are_exactly_their_bars_long(tmp_path):
    x, _ = make_song(bpm=124.0, bars=32)
    wav = str(tmp_path / "My Song.wav")
    sf.write(wav, x.T, SR, subtype="PCM_16")
    m = samplepack.build(wav, separation_method="dsp", log=lambda *_: None)
    assert m["tempo_bpm"] == 124.0 and m["key"] == "A minor" and m["tempo_steady"] and "own" in m["rights"]
    want = 4 * 4 * 60 / 124
    assert m["loops"] and all(abs(e["seconds"] - want) < 0.001 and e["bars"] == 4 and e["bpm"] == pytest.approx(124, abs=0.02) for e in m["loops"])
    assert all("_4bar_124bpm_Am_" in e["file"] for e in m["loops"])
    for e in m["loops"] + m["one_shots"]:
        assert os.path.isfile(os.path.join(m["folder"], e["file"]))
    data, sr = sf.read(os.path.join(m["folder"], m["loops"][0]["file"]))
    assert abs(len(data) / sr - want) < 0.001 and abs(np.max(np.abs(data)) - 10 ** (-1 / 20)) < 0.01      # peaks at -1 dBFS
    drums = [e for e in m["loops"] if e["stem"] == "drums"]
    assert 1 <= len(drums) < 8                                                   # eight 4-bar windows, the repeats left out
    assert {"kick"} <= {s["piece"] for s in m["one_shots"]}
    assert json.load(open(os.path.join(m["folder"], "pack.json"), encoding="utf-8"))["loops"] == m["loops"]
    assert "זכויות" in open(os.path.join(m["folder"], "README.md"), encoding="utf-8").read()
    two = samplepack.build(wav, str(tmp_path / "two"), bars=2, max_loops_per_stem=2, separation_method="dsp", log=lambda *_: None)
    assert all(abs(e["seconds"] - want / 2) < 0.001 for e in two["loops"]) and max(sum(e["stem"] == s for e in two["loops"]) for s in ("drums", "bass")) <= 2
    with pytest.raises(ValueError):
        samplepack.build(wav, bars=0)


def test_a_pack_from_stems_whose_tempo_drifts(tmp_path):
    st = render_parts(groove(), drift_clock(bpm=129.6, beats=192, wobble=0.004, ramp=0.006), offset_s=0.21)
    src = tmp_path / "stems"
    src.mkdir()
    sf.write(src / "S - Drums.wav", (st["kick"] + st["clap"] + st["hat"]) * 0.8, SR, subtype="PCM_16")
    sf.write(src / "S - Bass.wav", st["bass"], SR, subtype="PCM_16")
    m = samplepack.build(str(src), log=lambda *_: None)
    assert m["stems"] == "folder" and not m["tempo_steady"] and any("drifts" in n for n in m["notes"])
    assert {e["stem"] for e in m["loops"]} == {"Drums", "Bass"} and all(129 < e["bpm"] < 131 for e in m["loops"])
    data, sr = sf.read(os.path.join(m["folder"], next(e["file"] for e in m["loops"] if e["stem"] == "Drums")))
    mono = data.mean(axis=1) if data.ndim > 1 else data
    first = np.argmax(np.abs(mono) > 0.2 * np.max(np.abs(mono))) / sr
    assert first < 0.02                                                          # the loop opens on its first kick, not somewhere in the bar
    assert samplepack.main([str(src), "-o", str(tmp_path / "cli"), "--bars", "2"]) == 0
    assert samplepack.main([str(tmp_path / "none")]) == 2


# ------------------------------------------------------------------------------------------- installation check

def test_the_user_library_is_looked_for_where_windows_really_keeps_it():
    env = {"OneDrive": r"C:\Users\me\OneDrive"}
    got = doctor.user_library_candidates("Windows", env, r"C:\Users\me")
    assert got[0].startswith(r"C:\Users\me\OneDrive") and got[0].endswith("User Library") and len(got) == len(set(got)) >= 2
    assert any(p.replace("\\", "/").replace("//", "/").endswith("me/Documents/Ableton/User Library") for p in got)
    assert doctor.user_library_candidates("Darwin", {}, "/Users/me") == ["/Users/me/Music/Ableton/User Library"]


def test_install_and_recognise_the_remote_script(tmp_path, monkeypatch, capsys):
    lib = tmp_path / "User Library"
    lib.mkdir()
    monkeypatch.setattr(doctor, "user_library_candidates", lambda *a, **k: [str(tmp_path / "nowhere"), str(lib)])
    assert doctor.bridge_state(str(lib)) == "missing"
    dst = doctor.install_bridge()
    assert dst == str(lib / "Remote Scripts" / "T2A_Bridge") and os.path.isfile(os.path.join(dst, "handlers.py"))
    assert doctor.bridge_state(str(lib)) == "current"
    with open(os.path.join(dst, "handlers.py"), "a", encoding="utf-8") as fh:
        fh.write("\n# an older copy\n")
    assert doctor.bridge_state(str(lib)) == "differs"
    assert doctor.main(["--install-bridge"]) == 0 and doctor.bridge_state(str(lib)) == "current"
    with pytest.raises(FileNotFoundError):
        doctor.install_bridge(str(tmp_path / "not a library"))
    assert doctor.main(["--install-bridge", "--user-library", str(tmp_path / "x")]) == 2
    capsys.readouterr()
    assert doctor.main([]) == 1                                                  # nothing is listening where Live should be
    text = capsys.readouterr().out
    assert "PROBLEM   Ableton Live" in text and "Control Surface: T2A_Bridge" in text and "installed, same as this version" in text


def test_the_check_sees_a_running_live(bridge, tmp_path, monkeypatch):  # noqa: F811
    _, port = bridge
    lib = tmp_path / "User Library"
    lib.mkdir()
    monkeypatch.setattr(doctor, "user_library_candidates", lambda *a, **k: [str(lib)])
    rows = {r["name"]: r for r in doctor.check(port=port)}
    assert rows["Ableton Live"]["state"] == "ok" and "commands" in rows["Ableton Live"]["detail"]
    script = next(r for n, r in rows.items() if n.startswith("Remote Script in"))
    assert script["state"] == "problem" and "--install-bridge" in script["fix"]
    assert rows["Demucs (neural stem splitting)"]["state"] in ("ok", "optional") and rows["Python"]["state"] == "ok"


# ------------------------------------------------------------------------------------------- journal and read-only mode

def test_every_change_is_journalled_and_read_only_mode_changes_nothing(bridge, monkeypatch):  # noqa: F811
    from track2ableton.live import client as cl, mcp_server as ms

    song, port = bridge
    monkeypatch.setattr(ms, "_client", cl.LiveClient(port=port, timeout=5))
    ms.live_session()
    ms.set_song(tempo=126)
    ms.create_track(kind="midi", name="Lead")
    ms.create_clip(track="Lead", slot=0, length=8)
    ms.write_notes(track="Lead", slot=0, notes=[{"pitch": 60 + i, "start": i * 0.5, "duration": 0.5, "velocity": 100} for i in range(12)])
    ms.get_notes(track="Lead", slot=0)
    with pytest.raises(ms.ToolError):
        ms.set_track(track="No such track", mute=True)
    rows = json.loads(ms.journal())["entries"]
    assert [r["cmd"] for r in rows] == ["set_song", "create_track", "create_clip", "add_notes", "set_track"]      # reading is not listed
    assert rows[3]["args"]["notes"] == "<12 items>" and rows[0]["args"] == {"tempo": 126}
    assert [r["ok"] for r in rows] == [True, True, True, True, False] and "error" in rows[4]
    assert json.loads(ms.journal(last=2))["entries"] == rows[-2:]
    monkeypatch.setenv("T2A_READ_ONLY", "1")
    tracks = len(song.tracks)
    with pytest.raises(ms.ToolError, match="Read-only mode"):
        ms.create_track(kind="midi", name="Nope")
    with pytest.raises(ms.ToolError, match="Read-only mode"):
        ms.set_song(tempo=90)
    assert len(song.tracks) == tracks and song.tempo == 126
    assert json.loads(ms.live_session())["tempo"] == 126 and json.loads(ms.get_notes(track="Lead", slot=0))      # looking still works
    assert len(json.loads(ms.journal())["entries"]) == 5                           # a refused command never reached Live: not journalled
    monkeypatch.delenv("T2A_READ_ONLY")
    monkeypatch.setenv("T2A_JOURNAL", "0")
    ms.set_song(tempo=128)
    assert song.tempo == 128 and json.loads(ms.journal())["entries"] == []


def test_the_new_tools_through_the_mcp_module(tmp_path):
    from track2ableton.live import mcp_server as ms

    f = layers(tmp_path)
    r = json.loads(ms.clash_report({"kick": f["kick"], "bass": f["bass_on_kick"]}, bpm=125))
    assert r["pairs"][0]["clash"] > 0.5
    fit = json.loads(ms.fit_layers({"kick": f["kick"]}, {"hats": f["hats"], "low": f["pad_low"]}))
    assert fit["ranking"][0]["candidate"] == "hats"
    chain = json.loads(ms.match_reference(f["pad_mid"], f["pad_low"]))
    assert chain["chain"][-1]["device"] == "Limiter"
    assert "pass" in json.loads(ms.verify_reference(f["pad_mid"], f["pad_mid"]))
    with pytest.raises(ms.ToolError):
        ms.clash_report({"only": f["kick"]})
    with pytest.raises(ms.ToolError):
        ms.sample_pack(str(tmp_path / "missing.wav"))
    x, _ = make_song(bpm=124.0, bars=12)
    wav = str(tmp_path / "song.wav")
    sf.write(wav, x.T, SR, subtype="PCM_16")
    pack = json.loads(ms.sample_pack(wav, out_dir=str(tmp_path / "pack")))
    assert pack["loops"] and os.path.isdir(pack["folder"])
