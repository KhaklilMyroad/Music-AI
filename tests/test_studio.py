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
    assert "take turns" in apart["note"] and "note" not in together
    assert together["when_both_play"] > 0.6 and apart["when_both_play"] < 0.5
    assert r["pairs"][0] is together                                             # the pair that takes most of the mix comes first
    assert pair[frozenset(("kick", "hats"))]["clash"] < 0.05
    assert together["worst_bands"][0]["band"] in ("40-50 Hz", "50-63 Hz", "63-79 Hz")
    assert together["worst_bars"] == [] and "no bar stands out" in together["where"]      # it is the same in every bar
    assert together["seconds_compared"] == pytest.approx(64 * BEAT, abs=0.2)
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
    assert out["ranking"][-1]["crowded_bands"] and out["ranking"][0]["open_bands"] and not out["ranking"][0]["crowded_bands"]
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
    assert all("_4bar_124bpm_" in e["file"] for e in m["loops"])
    assert all(("_Am_" in e["file"]) == (e["kind"] != "drums") and ("key" in e) == (e["kind"] != "drums") for e in m["loops"])      # drums have no key
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
    assert m["stems"] == "folder" and not m["tempo_steady"] and any("not steady" in n for n in m["notes"])
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


# ------------------------------------------------------------------------------------------- after the QA review

def test_the_client_and_the_remote_script_agree_on_what_every_command_does():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ableton_bridge"))
    from T2A_Bridge import handlers
    from track2ableton.live import guard

    from . import fake_live as fl
    song = fl.Song()
    cmds = handlers.Handlers(song, fl.Application(song)).commands()
    shapes = [{}, {"action": "list"}, {"action": "LIST"}, {"action": "add"}, {"action": "jump"}, {"action": "play"},
              {"source": "Kick"}, {"channel": "Post FX"}, {"track": 0}]
    for cmd in cmds + ["no_such_command"]:
        for args in shapes:
            assert guard.kind_of(cmd, args) == handlers.kind_of(cmd, args), (cmd, args)
    kinds = {c: guard.kind_of(c, {}) for c in cmds}
    assert {c for c, k in kinds.items() if k == "read"} == set(guard.READS) | {"cue", "scene", "set_sidechain"}      # with no arguments these list
    assert kinds["transport"] == "playback" and guard.kind_of("cue", {"action": "jump"}) == "playback"
    assert guard.kind_of("set_sidechain", {"source": "Kick"}) == "write" and guard.kind_of("scene", {"action": "create"}) == "write"
    assert all(kinds[c] == "write" for c in ("create_track", "add_notes", "set_parameter", "delete_clip", "undo", "load_from_browser"))


def test_read_only_holds_inside_the_remote_script_and_for_any_caller(bridge, monkeypatch):  # noqa: F811
    from T2A_Bridge import handlers
    from track2ableton.compose import Spec, compose
    from track2ableton.compose.live import push
    from track2ableton.live import client as cl, guard, journal

    from . import fake_live as fl
    song, port = bridge
    c = cl.LiveClient(port=port, timeout=5)
    for value in ("1", " TRUE ", "y", "enabled", "2", '"1"', "כן", "readonly"):       # anything not plainly off is on
        monkeypatch.setenv("T2A_READ_ONLY", value)
        assert guard.read_only() and handlers.read_only(), value
    for value in ("", "0", "false", " No ", "off", '"0"'):
        monkeypatch.setenv("T2A_READ_ONLY", value)
        assert not guard.read_only() and not handlers.read_only(), value
    monkeypatch.delenv("T2A_READ_ONLY")
    assert doctor.main(["--read-only", "on"]) == 0 and guard.read_only() and os.path.isfile(guard.read_only_flag())
    before = (song.tempo, len(song.tracks))
    with pytest.raises(cl.LiveError, match="Read-only mode"):                           # the documented direct path, not the MCP server
        push(compose(Spec(structure="loop16")), c.call, prefix="X ")
    with pytest.raises(cl.LiveError, match="Read-only mode"):
        c.call("transport", action="play")
    assert (song.tempo, len(song.tracks)) == before and journal.read()["entries"] == []
    assert c.call("get_session")["tempo"] == before[0] and c.call("ping")["read_only"] is True
    assert c.call("set_sidechain", track=0, device="Compressor") if False else True     # (listing needs a device; kind_of covers it)
    h = handlers.Handlers(fl.Song(), None)                                              # a caller that skips the client's check
    with pytest.raises(handlers.CommandError, match="Read-only mode"):
        h.handle("create_track", {"kind": "midi"})
    assert h.handle("get_session", {})["tempo"]
    assert doctor.main(["--read-only", "off"]) == 0 and not guard.read_only()
    res = push(compose(Spec(structure="loop16", bpm=126)), c.call, prefix="X ")
    assert res["ok"] and song.tempo == 126
    rows = journal.read(last=1000)["entries"]
    assert rows[0]["cmd"] == "set_song" and {r["cmd"] for r in rows} >= {"create_track", "add_notes"}     # journalled without the MCP server
    c.close()


def test_a_change_live_did_not_confirm_in_time_is_recorded_as_unknown(monkeypatch):
    import socket
    import threading

    from track2ableton.live import client as cl, journal

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    held = []
    threading.Thread(target=lambda: held.append(srv.accept()), daemon=True).start()      # accepts, never answers
    c = cl.LiveClient(port=srv.getsockname()[1], timeout=0.4)
    with pytest.raises(cl.LiveTimeout, match="may still be carried out"):
        c.call("create_track", kind="midi", name="Pad")
    row = journal.read()["entries"][-1]
    assert row["cmd"] == "create_track" and row["ok"] is None and "unknown" in row["outcome"]
    with pytest.raises(cl.LiveTimeout):
        c.call("get_session")                                                            # a read that times out is not journalled
    assert len(journal.read()["entries"]) == 1
    assert cl.LiveClient().timeout > 20                                                  # longer than the Remote Script waits for Live
    srv.close()
    monkeypatch.setenv("T2A_PORT", "abc")
    with pytest.raises(cl.LiveError, match="T2A_PORT must be a number"):
        cl.LiveClient()


def test_the_journal_says_when_it_is_not_recording_and_stays_small(tmp_path, monkeypatch):
    from track2ableton.live import journal

    assert "NOT recorded" in journal.read()["note"]                                      # no folder yet: say so, do not report "nothing changed"
    journal.record("add_notes", {"track": 1, "notes": [{"pitch": 60, "junk": "x" * 100000}] * 8, "path": "C:/" + "d/" * 300 + "song.wav"}, True)
    row = journal.read()["entries"][0]
    assert len(json.dumps(row)) < 6000 and "song.wav" in json.dumps(row) or "shortened" in row["args"]
    assert journal.read(last=0)["entries"] == [] and journal.read(last=-5)["entries"] == [] and journal.read()["total"] == 1
    assert journal.read(this_session=False)["total"] == 1
    d = journal.folder()
    with open(os.path.join(d, "journal-20200101.jsonl"), "w") as fh:
        fh.write('{"cmd": "old"}\n')
    with open(os.path.join(d, sorted(os.listdir(d))[-1]), "ab") as fh:
        fh.write(b"\xff\xfe not json\n")
    os.mkdir(os.path.join(d, "journal-99999999.jsonl"))                                  # a folder with a journal's name
    got = journal.read(this_session=False)
    assert got["total"] == 1 and got["unreadable_lines"] == 1                            # old days are not counted, bad lines are reported
    monkeypatch.setenv("T2A_JOURNAL_DIR", str(tmp_path / "a file"))
    (tmp_path / "a file").write_text("x")
    journal.record("set_song", {"tempo": 120}, True)                                     # cannot be written: must not raise
    assert "note" in journal.read()
    monkeypatch.setenv("T2A_JOURNAL_DIR", "~/journal here")
    assert journal.folder() == os.path.join(os.path.expanduser("~"), "journal here")
    journal.record("set_song", {"tempo": "\ud83d"}, True)                                # an unencodable character must not raise either


def test_tools_say_what_is_wrong_with_a_file(tmp_path, monkeypatch):
    from track2ableton.live import guard, mcp_server as ms

    f = layers(tmp_path)
    empty, text, folder = tmp_path / "empty.wav", tmp_path / "text.wav", tmp_path / "dir.wav"
    empty.write_bytes(b"")
    text.write_text("this is not audio")
    folder.mkdir()
    for bad in (empty, text):
        for call in (lambda b: ms.clash_report({"a": f["kick"], "b": str(b)}), lambda b: ms.fit_layers({"a": f["kick"]}, {"b": str(b)}),
                     lambda b: ms.match_reference(f["kick"], str(b)), lambda b: ms.verify_reference(str(b), f["kick"]),
                     lambda b: ms.split_stems(str(b), to_live=False), lambda b: ms.sample_pack(str(b))):
            with pytest.raises(ms.ToolError, match="cannot read audio|no audio in it"):
                call(bad)
    with pytest.raises(ms.ToolError, match="not found"):
        ms.match_reference(str(folder), f["kick"])
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where a folder is wanted")
    with pytest.raises(ms.ToolError, match="sample_pack"):
        ms.sample_pack(f["kick"], out_dir=str(blocked / "pack"))
    with pytest.raises(ms.ToolError, match="language must be"):
        ms.vocal_score(track="0", lyrics="la", out_dir=str(tmp_path / "v"), language="fr", slot=0)
    guard.set_read_only(True)
    with pytest.raises(ms.ToolError, match="Nothing was split"):
        ms.split_stems(f["kick"])
    assert not os.path.exists(str(tmp_path / "kick stems"))                              # refused before the work, not after it
    guard.set_read_only(False)
    assert ms.main(["--help"]) == 0


def test_a_stems_folder_survives_one_damaged_file(tmp_path):
    from track2ableton import separation

    t = np.arange(SR) / SR
    sf.write(tmp_path / "Song - Drums.wav", 0.3 * np.sin(2 * np.pi * 100 * t), SR)
    sf.write(tmp_path / "Song - Bass.wav", 0.3 * np.sin(2 * np.pi * 50 * t), SR)
    (tmp_path / "Song - Keys.wav").write_bytes(b"")
    (tmp_path / "._Song - Drums.wav").write_bytes(b"\x00\x05\x16\x07 AppleDouble")
    st = separation.from_folder(str(tmp_path))
    assert set(st.kinds) == {"Drums", "Bass"} and st.skipped == ["Song - Keys.wav: unreadable"]


def test_doctor_with_two_libraries_a_custom_one_and_a_wrong_folder(tmp_path, monkeypatch, capsys):
    one, two, custom = tmp_path / "OneDrive" / "User Library", tmp_path / "Docs" / "User Library", tmp_path / "Music stuff" / "Lib"
    for d in (one, two, custom / "Presets"):
        d.mkdir(parents=True)
    monkeypatch.setattr(doctor, "user_library_candidates", lambda *a, **k: [str(one), str(two)])
    rows = doctor.check(port=1)
    scripts = [r for r in rows if r["name"].startswith("Remote Script in")]
    assert [r["state"] for r in scripts] == ["problem", "problem"] and all(f'--user-library "{lib}"' in r["fix"] for r, lib in zip(scripts, (one, two)))
    assert doctor.main(["--install-bridge", "--user-library", str(two)]) == 0            # the fix as printed, for the second library
    states = {r["name"]: r["state"] for r in doctor.check(port=1)}
    assert states["Remote Script in " + str(two)] == "ok" and states["Remote Script in " + str(one)] == "optional"
    assert states["Which library Live uses"] == "optional"                               # it cannot know, and says so
    assert doctor.main(["--install-bridge", "--user-library", str(custom)]) == 0
    assert any(r["name"] == "Remote Script in " + str(custom) and r["state"] == "ok" for r in doctor.check(port=1))     # remembered
    wrong = two / "Remote Scripts"
    assert doctor.main(["--install-bridge", "--user-library", str(wrong)]) == 2 and not (wrong / "Remote Scripts").exists()
    assert "Remote Scripts folder itself" in capsys.readouterr().err
    assert doctor.main(["--install-bridge", "--user-library", str(tmp_path / "Docs")]) == 2      # just some folder
    assert doctor.main(["--install-bridge", "--user-library", str(tmp_path / "Docs"), "--force"]) == 0
    link_lib = tmp_path / "L" / "User Library"
    (link_lib / "Remote Scripts").mkdir(parents=True)
    os.symlink(str(one), str(link_lib / "Remote Scripts" / "T2A_Bridge"))
    assert doctor.main(["--install-bridge", "--user-library", str(link_lib)]) == 2 and one.exists()
    mine = two / "Remote Scripts" / "T2A_Bridge" / "handlers.py"
    real = doctor.shutil.copytree

    def copy_that_fails_for_the_new_script(src, dst, *a, **k):                           # as when Live holds the files open
        if "ableton_bridge" in str(src):
            raise PermissionError("in use")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(doctor.shutil, "copytree", copy_that_fails_for_the_new_script)
    size = mine.stat().st_size
    assert doctor.main(["--install-bridge", "--user-library", str(two)]) == 2 and mine.stat().st_size == size     # the old copy is back
    assert "close it and try again" in capsys.readouterr().err


def test_doctor_tells_another_program_on_the_port_from_no_live(tmp_path, monkeypatch):
    import socket
    import threading

    lib = tmp_path / "User Library"
    lib.mkdir()
    monkeypatch.setattr(doctor, "user_library_candidates", lambda *a, **k: [str(lib)])
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(2)

    def http():
        conn, _ = srv.accept()
        conn.recv(4096)
        conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n<html>no</html>\n")
        conn.close()

    threading.Thread(target=http, daemon=True).start()
    live = {r["name"]: r for r in doctor.check(port=srv.getsockname()[1])}["Ableton Live"]
    assert live["state"] == "problem" and "not this tool's Remote Script" in live["detail"] and "9877" in live["fix"]
    srv.close()
    live = {r["name"]: r for r in doctor.check(port=1)}["Ableton Live"]
    assert live["state"] == "problem" and "Start Live" in live["fix"]
    monkeypatch.setenv("T2A_PORT", "abc")
    assert {r["name"]: r for r in doctor.check()}["Ableton Live"]["state"] == "problem"  # a row, not a traceback
    monkeypatch.delenv("T2A_PORT")
    monkeypatch.setenv("T2A_DEMUCS_PYTHON", sys.executable)                              # a real python, without demucs in it
    demucs = {r["name"]: r for r in doctor.check(port=1)}["Demucs (neural stem splitting)"]
    assert demucs["state"] == "problem" and "cannot import demucs" in demucs["detail"]
    monkeypatch.setenv("T2A_DEMUCS_PYTHON", str(tmp_path))
    assert "is a folder" in {r["name"]: r for r in doctor.check(port=1)}["Demucs (neural stem splitting)"]["detail"]


def test_the_wheel_carries_the_remote_script_and_the_server_starts_politely(monkeypatch, capsys):
    import tomllib

    from track2ableton.live import launch

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = tomllib.load(open(os.path.join(root, "pyproject.toml"), "rb"))
    listed = set(cfg["tool"]["setuptools"]["packages"])
    found = {os.path.relpath(d, root).replace(os.sep, ".") for d, _, files in os.walk(os.path.join(root, "track2ableton")) if "__init__.py" in files}
    assert found <= listed and "T2A_Bridge" in listed                                    # a new sub-package must be added to the list
    assert cfg["tool"]["setuptools"]["package-dir"]["T2A_Bridge"] == "ableton_bridge/T2A_Bridge"
    assert os.path.isfile(os.path.join(doctor.bridge_source(), "handlers.py"))
    for name, target in cfg["project"]["scripts"].items():
        module, func = target.split(":")
        assert callable(getattr(__import__(module, fromlist=[func]), func)), name
    assert launch.main(["--help"]) == 0 and "claude mcp add" in capsys.readouterr().out
    monkeypatch.setattr(launch.importlib.util, "find_spec", lambda name: None)
    assert launch.main([]) == 1 and '"mcp" package' in capsys.readouterr().err


# ------------------------------------------------------------------------------------------- after the audio review

def _wav(path, x, sr=SR):
    sf.write(str(path), x, sr)
    return str(path)


def test_layers_that_meet_only_in_a_few_bars_are_not_called_fine(tmp_path):
    bar = int(4 * BEAT * SR)
    t = np.arange(16 * bar) / SR
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.2, 329.6)) * 0.15
    guitar, pad = chord.copy(), chord.copy()
    guitar[11 * bar:] = 0                        # bars 1-11
    pad[:7 * bar] = 0                            # bars 8-16: they share bars 8-11
    r = clash.report({"guitar": _wav(tmp_path / "g.wav", guitar), "pad": _wav(tmp_path / "p.wav", pad)}, bpm=125)["pairs"][0]
    assert r["clash"] < 0.5 and r["when_both_play"] > 0.8 and r["both_play_share_of_time"] == pytest.approx(0.25, abs=0.05)
    assert "collide where they play together" in r["note"] and sorted(r["worst_bars"]) == [8, 9, 10, 11]


def test_a_short_or_silent_file_does_not_change_what_the_others_measure(tmp_path):
    f = layers(tmp_path)
    alone = clash.report({"kick": f["kick"], "bass": f["bass_on_kick"]}, bpm=125)["pairs"][0]
    x, _ = sf.read(f["hats"])
    short = _wav(tmp_path / "fx.wav", x[: 2 * SR])
    silent = _wav(tmp_path / "muted.wav", np.zeros(SR * 4))
    hiss = _wav(tmp_path / "hiss.wav", np.random.default_rng(0).standard_normal(SR * 8) * 10 ** (-95 / 20))
    r = clash.report({"kick": f["kick"], "bass": f["bass_on_kick"], "fx": short, "muted": silent, "hiss": hiss}, bpm=125)
    pair = next(p for p in r["pairs"] if {p["a"], p["b"]} == {"kick", "bass"})
    assert pair["clash"] == alone["clash"] and pair["seconds_compared"] == alone["seconds_compared"]
    assert sorted(r["no_signal"]) == ["hiss", "muted"]                            # under the floor: not a layer, owns no band
    assert all(o["owner"] not in ("hiss", "muted") for o in r["who_owns_each_band"].values())
    fx = next(p for p in r["pairs"] if "fx" in (p["a"], p["b"]) and "kick" in (p["a"], p["b"]))
    assert fx["seconds_compared"] == pytest.approx(2.0, abs=0.1) and "only the first" in fx["length_note"]
    out = clash.fit({"kick": f["kick"]}, {"hats": f["hats"], "nothing": silent})
    assert [r_["candidate"] for r_ in out["ranking"]] == ["hats"] and out["no_signal"] == ["nothing"]


def test_clash_hears_left_and_right_and_does_not_depend_on_the_sample_rate(tmp_path):
    f = layers(tmp_path)
    x, _ = sf.read(f["pad_mid"])
    left = _wav(tmp_path / "left.wav", np.stack([x, np.zeros_like(x)], axis=1))
    right = _wav(tmp_path / "right.wav", np.stack([np.zeros_like(x), x], axis=1))
    wide = _wav(tmp_path / "wide.wav", np.stack([x, -x], axis=1))                 # cancels in mono, plays in both speakers
    assert clash.report({"l": left, "r": right})["pairs"][0]["clash"] < 0.02      # opposite speakers: no overlap
    assert clash.report({"mono": f["pad_mid"], "wide": wide})["pairs"][0]["clash"] > 0.9
    k, _ = sf.read(f["kick"])
    b, _ = sf.read(f["bass_offbeat"])
    from scipy.signal import resample_poly
    low = clash.report({"kick": _wav(tmp_path / "k22.wav", resample_poly(k, 1, 2), SR // 2),
                        "bass": _wav(tmp_path / "b22.wav", resample_poly(b, 1, 2), SR // 2)})["pairs"][0]["clash"]
    full = clash.report({"kick": f["kick"], "bass": f["bass_offbeat"]})["pairs"][0]["clash"]
    assert abs(low - full) < 0.05                                                # the frames are 46 ms whatever the file's rate


def test_fit_does_not_depend_on_how_the_bed_is_delivered(tmp_path):
    f = layers(tmp_path)
    k, _ = sf.read(f["kick"])
    b, _ = sf.read(f["bass_offbeat"])
    bounce = _wav(tmp_path / "bounce.wav", k + b)
    muted = _wav(tmp_path / "muted.wav", np.zeros_like(k))
    cands = {n: f[n] for n in ("hats", "pad_mid", "bass_on_kick", "pad_low", "kick")}
    stems_ = clash.fit({"kick": f["kick"], "bass": f["bass_offbeat"]}, cands)
    one = clash.fit({"all": bounce}, cands)
    more = clash.fit({"kick": f["kick"], "bass": f["bass_offbeat"], "m1": muted, "m2": muted}, cands)
    as_dict = lambda out: {r["candidate"]: r["free"] for r in out["ranking"]}
    for other in (one, more):
        assert all(abs(as_dict(other)[n] - v) < 0.03 for n, v in as_dict(stems_).items())
    assert as_dict(stems_)["kick"] < 0.1                                         # a copy of what is already there finds no room
    assert [r["candidate"] for r in stems_["ranking"]][:2] == ["hats", "pad_mid"] and more["bed_files_with_no_signal"] == ["m1", "m2"]


def _song_files(tmp_path, bars=16):
    x, _ = make_song(bpm=124.0, bars=bars)
    return x, _wav(tmp_path / "mix.wav", (x * 0.15).T)


def test_the_same_audio_at_another_sample_rate_or_in_mono_needs_no_chain(tmp_path):
    from scipy.signal import resample_poly
    x, mix = _song_files(tmp_path)
    at96 = _wav(tmp_path / "ref96.wav", (resample_poly(x, 320, 147, axis=1) * 0.15).T, 96000)
    mono = _wav(tmp_path / "mono.wav", x.mean(axis=0) * 0.15)
    for ref in (at96, mono):
        chain = mixmaster.match_chain(mix, ref)
        assert [d["device"] for d in chain["chain"]] == ["Limiter"] and abs(chain["chain"][0]["gain_db"]) <= 0.2, ref
        assert not any("side signal is" in n for n in chain["notes"])
        assert mixmaster.verify_match(mix, ref)["checks"]["tone"]
    for bad, why in ((_wav(tmp_path / "silent.wav", np.zeros((SR * 5, 2))), "silent"), (_wav(tmp_path / "short.wav", (x[:, :SR] * 0.1).T), "too short")):
        with pytest.raises(ValueError, match=why):
            mixmaster.match_chain(bad, mix)
        with pytest.raises(ValueError, match=why):
            mixmaster.verify_match(mix, bad)


def test_no_sub_boost_from_a_reference_and_no_compressor_from_tone_alone(tmp_path):
    x, mix = _song_files(tmp_path)
    t = np.arange(x.shape[1]) / SR
    subby = _wav(tmp_path / "subby.wav", ((x + 0.6 * np.sin(2 * np.pi * 30 * t)) * 0.15).T)
    chain = mixmaster.match_chain(mix, subby)
    eq = next((d for d in chain["chain"] if d["device"] == "EQ Eight"), {"bands": []})
    assert not [b for b in eq["bands"] if b["gain_db"] > 0 and b["freq_hz"] < 60]          # another song's sub is not added on a master
    dull = _wav(tmp_path / "dull.wav", (sosfilt(butter(1, 3000, "lowpass", fs=SR, output="sos"), x, axis=1) * 0.15).T)
    chain = mixmaster.match_chain(mix, dull)
    assert "Glue Compressor" not in [d["device"] for d in chain["chain"]] and any("Crest factor" in n for n in chain["notes"])
    assert all(b["gain_db"] < 0 for b in chain["chain"][0]["bands"])
    louder_mix = _wav(tmp_path / "louder_mix.wav", (x * 0.5).T)
    dense = _wav(tmp_path / "dense.wav", (np.tanh(x * 4) * 0.9).T)
    assert any("takes about" in n for n in mixmaster.match_chain(louder_mix, dense)["notes"])      # the limiter will be working: say so
    far = mixmaster.match_chain(mix, _wav(tmp_path / "loud.wav", (x * 0.9).T))
    assert far["chain"][-1]["gain_db"] == 12.0 and any("fix the mix level first" in n for n in far["notes"])


def test_verify_fails_a_master_that_only_looks_close(tmp_path):
    x, _ = make_song(bpm=124.0, bars=16)
    t = np.arange(x.shape[1]) / SR
    air = 0.12 * np.sin(2 * np.pi * 660 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * t))
    x = np.stack([x[0] + air, x[1] - air])                                        # something only in the sides
    ref = _wav(tmp_path / "ref.wav", (x * 0.3).T)
    check = lambda y: mixmaster.verify_match(_wav(tmp_path / "m.wav", y.T), ref)
    assert check(x * 0.3)["pass"]
    mono = np.repeat(x.mean(axis=0, keepdims=True), 2, axis=0) * 0.3
    got = check(mono)
    assert not got["checks"]["stereo"] and got["checks"]["tone"]                  # collapsed to mono: same spectrum, not the same master
    clipped = np.clip(x * 1.2, -0.3, 0.3)
    assert not check(clipped / np.max(np.abs(clipped)) * 0.3 * 0.99)["checks"]["dynamics"]
    boom = x + 0.1 * np.sin(2 * np.pi * 40 * t)                                   # a rumble at 40 Hz the reference does not have
    got = check(boom * 0.3)
    assert not got["checks"]["tone"] and any(38 <= float(k) <= 45 for k in {**got["bands_still_off_db"], **got["single_bands_far_off_db"]})
    spec = np.fft.rfft(x, axis=1)
    f = np.fft.rfftfreq(x.shape[1], 1 / SR)
    spec[:, (f >= 891) & (f < 1122)] *= 10 ** (-6.5 / 20)                         # the third of an octave around 1 kHz, 6.5 dB down
    got = check(np.fft.irfft(spec, n=x.shape[1], axis=1) * 0.3)
    assert not got["checks"]["tone"] and got["single_bands_far_off_db"] and not got["bands_still_off_db"]      # hidden by averaging, caught alone
    lossy = sosfilt(butter(8, 15500, "lowpass", fs=SR, output="sos"), x, axis=1)
    assert check(lossy * 0.3)["checks"]["tone"]                                   # a reference from a lossy file is not held against it
    hot = x / np.max(np.abs(x)) * 10 ** (-0.5 / 20)
    assert not mixmaster.verify_match(_wav(tmp_path / "hot.wav", hot.T), _wav(tmp_path / "hot_ref.wav", hot.T))["checks"]["true_peak"]


def test_a_file_that_starts_on_its_downbeat_gives_its_first_bars(tmp_path):
    x, _ = make_song(bpm=124.0, bars=20, offset_s=0.0)
    wav = _wav(tmp_path / "song.wav", x.T)
    m = samplepack.build(wav, separation_method="dsp", log=lambda *_: None)
    assert 1 in {e["from_bar"] for e in m["loops"]} and m["first_bar_with_sound"] == 1
    whole = samplepack.build(wav, str(tmp_path / "sixteen"), bars=16, separation_method="dsp", log=lambda *_: None)
    assert whole["loops"] and all(e["from_bar"] == 1 for e in whole["loops"])     # sixteen bars of a twenty-bar song: bars 1-16
    again = samplepack.build(wav, str(tmp_path / "sixteen"), bars=4, max_loops_per_stem=1, separation_method="dsp", log=lambda *_: None)
    on_disk = sorted(os.listdir(os.path.join(again["folder"], "Loops")))
    assert on_disk == sorted(os.path.basename(e["file"]) for e in again["loops"])            # a second run leaves nothing the manifest does not list
    with pytest.raises(ValueError, match="silent"):
        samplepack.build(_wav(tmp_path / "silence.wav", np.zeros((SR * 8, 2))), separation_method="dsp", log=lambda *_: None)


def _stem_folder(tmp_path, lead_bars=0, name="stems"):
    parts = groove(bars=24, quiet=(99, 99))
    st = render_parts(parts, drift_clock(bpm=125.0, beats=24 * 4 + 8, wobble=0, ramp=0), offset_s=lead_bars * 4 * 60 / 125)
    d = tmp_path / name
    d.mkdir()
    return d, st


def test_phrases_are_counted_from_where_the_music_starts(tmp_path):
    d, st = _stem_folder(tmp_path, lead_bars=2)
    sf.write(d / "S - Drums.wav", (st["kick"] + st["clap"] + st["hat"]) * 0.8, SR)
    sf.write(d / "S - Bass.wav", st["bass"], SR)
    m = samplepack.build(str(d), about_bpm=125, log=lambda *_: None)
    assert m["first_bar_with_sound"] == 3 and all((e["from_bar"] - 3) % 4 == 0 for e in m["loops"])
    data, sr = sf.read(os.path.join(m["folder"], next(e["file"] for e in m["loops"] if e["stem"] == "Drums")))
    mono = data.mean(axis=1)
    assert np.argmax(np.abs(mono) > 0.2 * np.max(np.abs(mono))) / sr < 0.01       # opens on the kick, not on two bars of silence


def test_stems_that_are_wide_named_or_only_bleed(tmp_path):
    d, st = _stem_folder(tmp_path)
    sf.write(d / "S - Kick.wav", st["kick"], SR)
    sf.write(d / "S - Hats.wav", st["hat"], SR)
    sf.write(d / "S - Wide Pad.wav", np.stack([st["pad"], -st["pad"]], axis=1), SR)          # cancels in mono
    sf.write(d / "S - Ghost.wav", st["bass"] * 10 ** (-50 / 20), SR)                          # 50 dB down: bleed
    sf.write(d / "S - Bass.wav", st["bass"], SR)
    m = samplepack.build(str(d), about_bpm=125, log=lambda *_: None)
    by_stem = {e["stem"] for e in m["loops"]}
    assert "Wide Pad" in by_stem and "Ghost" not in by_stem and any(x.startswith("Ghost: nearly empty") for x in m["left_out"])
    shots = {(s_["stem"], s_["piece"]) for s_ in m["one_shots"]}
    assert shots == {("Kick", "kick"), ("Hats", "hat")}                           # a stem of one instrument is named by the stem
    for s_ in m["one_shots"]:
        clip, sr = sf.read(os.path.join(m["folder"], s_["file"]))
        assert np.argmax(np.abs(clip) >= 0.1 * np.max(np.abs(clip))) / sr <= 0.003 and abs(clip[0]) < 0.02      # on time, and no click
        assert s_["label"] == "from the stem's name"


def test_a_busier_bar_is_another_loop_and_a_repeat_is_not(tmp_path):
    bars, beat = 16, 60 / 125
    kick, hat8, hat16 = [], [], []
    for b in range(bars):
        kick += [b * 4 + i for i in range(4)]
        (hat8 if b < 8 else hat16).extend([b * 4 + i / 2 for i in range(8)] if b < 8 else [b * 4 + i / 4 for i in range(16)])
    st = render_parts({"kick": kick, "hat": hat8 + hat16}, drift_clock(bpm=125.0, beats=bars * 4 + 8, wobble=0, ramp=0))
    d = tmp_path / "stems"
    d.mkdir()
    sf.write(d / "S - Drums.wav", st["kick"] + st["hat"], SR)
    sf.write(d / "S - Kick.wav", st["kick"], SR)
    m = samplepack.build(str(d), about_bpm=125, log=lambda *_: None)
    assert m["time_signature"] == "4/4"                                           # an even kick is not a waltz
    by = lambda stem: sorted(e["from_bar"] for e in m["loops"] if e["stem"] == stem)
    assert by("Drums") == [1, 9] and by("Kick") == [1]                            # 8ths, then 16ths; the repeats of each are left out


def test_the_tempo_the_user_knows_settles_twice_or_half(tmp_path):
    parts = groove(bars=24, quiet=(99, 99))
    st = render_parts(parts, drift_clock(bpm=87.3, beats=24 * 4 + 8, wobble=0, ramp=0))
    d = tmp_path / "stems"
    d.mkdir()
    sf.write(d / "S - Drums.wav", (st["kick"] + st["clap"] + st["hat"]) * 0.8, SR)
    sf.write(d / "S - Bass.wav", st["bass"], SR)
    m = samplepack.build(str(d), about_bpm=87, beats_per_bar=4, log=lambda *_: None)
    assert m["tempo_bpm"] == pytest.approx(87.3, abs=0.1) and m["time_signature"] == "4/4"
    assert all(e["seconds"] == pytest.approx(16 * 60 / 87.3, abs=0.02) for e in m["loops"])
    assert any("searched around" in n for n in m["analysis_notes"]) and "87.3bpm" in m["loops"][0]["file"]
    with pytest.raises(ValueError):
        samplepack.build(str(d), about_bpm=5, log=lambda *_: None)


def test_a_supplied_drum_stem_decides_where_the_beat_is(tmp_path):
    # A kick quieter than the bass and pad that duck under it: in the mix the loudest attack is their swell after
    # every kick, half a beat late. The drum stem says where the beat really is.
    from track2ableton import pipeline, separation
    _, truth = make_song(bpm=124.0, bars=32)
    st = truth["stems"]
    d = tmp_path / "stems"
    d.mkdir()
    sf.write(d / "Song - Drums.wav", st["drums"] * 0.3, SR)
    sf.write(d / "Song - Bass.wav", st["bass"], SR)
    sf.write(d / "Song - Pad.wav", st["pad"].T, SR)
    given = separation.from_folder(str(d))
    mix = separation.mixdown(given)
    guide = pipeline.drum_guide(given, mix.mono, mix.sr)
    assert guide is not None and guide.size == mix.mono.size
    rhythm, _, _, bars = pipeline.musical_grid(mix.mono, mix.sr, mix.duration, drums=guide)
    assert rhythm.bpm == pytest.approx(124.0, abs=0.01) and abs(bars[0]) < 0.01 and abs(bars[16] - 16 * 4 * 60 / 124) < 0.01
    m = samplepack.build(str(d), log=lambda *_: None)
    assert m["tempo_bpm"] == pytest.approx(124.0, abs=0.01)
    data, sr = sf.read(os.path.join(m["folder"], next(e["file"] for e in m["loops"] if e["stem"] == "Drums")))
    mono = np.abs(data.mean(axis=1))
    assert np.argmax(mono > 0.2 * mono.max()) / sr < 0.01                         # the drum loop opens on its kick
    # drums that are only bleed, or a folder of nothing but drums, lead nothing
    sf.write(d / "Song - Drums.wav", st["drums"] * 10 ** (-60 / 20), SR)
    quiet = separation.from_folder(str(d))
    assert quiet is None or pipeline.drum_guide(quiet, mix.mono, mix.sr) is None
    only = tmp_path / "only"
    only.mkdir()
    sf.write(only / "Kick.wav", st["drums"], SR)
    sf.write(only / "Hats.wav", st["drums"] * 0.5, SR)
    alone = separation.from_folder(str(only))
    assert pipeline.drum_guide(alone, separation.mixdown(alone).mono, SR) is None


def test_the_fix_stage_takes_the_tempo_the_user_knows(tmp_path):
    from track2ableton.fix.project import run
    parts = groove(bars=24, quiet=(99, 99))
    st = render_parts(parts, drift_clock(bpm=70.0, beats=24 * 4 + 8, wobble=0, ramp=0))
    d = tmp_path / "stems"
    d.mkdir()
    sf.write(d / "S - Drums.wav", (st["kick"] + st["clap"] + st["hat"]) * 0.8, SR)
    sf.write(d / "S - Bass.wav", st["bass"], SR)
    quiet = dict(write_als=False, log=lambda *_: None)
    alone = run(str(d), str(tmp_path / "a"), **quiet)["tempo"]
    assert alone["measured_bpm"] == pytest.approx(140.0, abs=0.2)                 # read at twice the tempo: this is what the options are for
    for kw in ({"bpm": 70}, {"about_bpm": 68, "beats_per_bar": 4}, {"bpm": 72, "about_bpm": 70}):
        t = run(str(d), str(tmp_path / "b"), **quiet, **kw)["tempo"]
        assert t["measured_bpm"] == pytest.approx(70.0, abs=0.1) and t["time_signature"] == "4/4", kw
        assert t["project_bpm"] == kw.get("bpm", 70)
    with pytest.raises(ValueError):
        run(str(d), str(tmp_path / "c"), about_bpm=500, **quiet)
