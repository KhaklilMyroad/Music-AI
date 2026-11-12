"""Bridge logic against a fake Live Object Model, over a real TCP socket, and through the MCP tools."""
import importlib
import json
import os
import sys
import threading
import time
import types

import numpy as np
import pytest
import soundfile as sf

from . import fake_live as fl

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "ableton_bridge"))

from T2A_Bridge.handlers import CommandError, Handlers  # noqa: E402


@pytest.fixture()
def h():
    song = fl.Song()
    return Handlers(song, fl.Application(song))


def test_session_and_transport(h):
    s = h.handle("get_session", {})
    assert s["tempo"] == 120 and len(s["tracks"]) == 2 and len(s["returns"]) == 2
    h.handle("set_song", {"tempo": 124, "loop": True, "loop_start": 8})
    assert h.song.tempo == 124 and h.song.loop and h.song.loop_start == 8
    h.handle("transport", {"action": "play"})
    assert h.song.is_playing


def test_track_lookup_by_name_index_return_master(h):
    assert h._track(0).name == "1-MIDI"
    assert h._track("audio").name == "2-Audio"
    assert h._track("A").name == "A-Reverb"
    assert h._track("return:1").name == "B-Delay"
    assert h._track("master").name == "Main"
    with pytest.raises(CommandError):
        h._track("nope")


def test_volume_by_db_uses_lives_display(h):
    r = h.handle("set_track", {"track": 0, "volume_db": -6})
    assert r["volume"] == "-6.0 dB"
    r = h.handle("set_send", {"track": 0, "send": "B", "level_db": -12})
    assert r["display"] == "-12.0 dB"


def test_create_clip_notes_quantize(h):
    h.handle("create_clip", {"track": 0, "slot": 1, "length": 8, "name": "Bass"})
    h.handle("add_notes", {"track": 0, "slot": 1, "notes": [{"pitch": 36, "start": 0.02, "duration": 0.5}, {"pitch": 43, "start": 1.1, "duration": 0.5}]})
    h.handle("quantize_clip", {"track": 0, "slot": 1, "grid": "1/16"})
    notes = h.handle("get_notes", {"track": 0, "slot": 1})
    assert [round(n["start"], 2) for n in notes] == [0.0, 1.0]
    h.handle("add_notes", {"track": 0, "slot": 1, "notes": [{"pitch": 60, "start": 2, "duration": 1}], "replace": True})
    assert [n["pitch"] for n in h.handle("get_notes", {"track": 0, "slot": 1})] == [60]
    h.handle("clip_action", {"track": 0, "slot": 1, "action": "to_arrangement", "time": 16})
    assert h.song.tracks[0].arrangement_clips[0].start_time == 16


def test_devices_parameters(h):
    h.handle("insert_device", {"track": 0, "name": "EQ Eight"})
    info = h.handle("get_device", {"track": 0, "device": "EQ Eight"})
    assert any(p["name"] == "1 Gain A" for p in info["parameters"])
    r = h.handle("set_parameter", {"track": 0, "device": "EQ Eight", "parameter": "1 Frequency A", "display_value": 1200})
    assert r["display"].startswith("1.20 kHz"), r
    r = h.handle("set_parameter", {"track": 0, "device": 0, "parameter": "1 Filter Type A", "value": "HighShelf"})
    assert r["value"] == 5
    h.handle("device_action", {"track": 0, "device": "EQ Eight", "action": "off"})
    assert h.song.tracks[0].devices[0].parameters[0].value == 0


def test_browser_search_and_load(h):
    res = h.handle("search_browser", {"query": "reverb"})["results"]
    assert res and res[0]["path"] == "audio_effects/Reverb"
    out = h.handle("load_from_browser", {"track": "1-MIDI", "query": "Reverb"})
    assert "Reverb" in out["devices"]
    assert h.handle("browse", {"path": "instruments/Drift"})[0]["name"] == "Pad.adv"


def test_routing(h):
    r = h.handle("set_routing", {"track": 1, "input_type": "Resampling", "monitoring": "in"})
    assert r["input_type"] == "Resampling" and h.song.tracks[1].current_monitoring_state == 0
    with pytest.raises(CommandError):
        h.handle("set_routing", {"track": 1, "output_type": "Nowhere"})


def test_scenes_and_audio_files(h):
    h.handle("scene", {"action": "create", "index": -1})
    sc = h.handle("scene", {"action": "set", "index": 4, "name": "Drop", "tempo": 126})
    assert sc[4]["name"] == "Drop"
    h.handle("create_audio_clip", {"track": 1, "slot": 0, "file_path": "/x/stem.wav"})
    files = h.handle("get_audio_files", {})
    assert files == [{"track": "2-Audio", "slot": 0, "clip": "", "file_path": "/x/stem.wav"}]


def test_unknown_command_lists_available(h):
    with pytest.raises(CommandError) as e:
        h.handle("fly", {})
    assert "set_tempo" not in str(e.value) and "transport" in str(e.value)


# ------------------------------------------------------------------------- socket bridge + MCP tools

class _FakeControlSurface(object):
    def __init__(self, c_instance):
        self._song = c_instance
        self._stop = False
        self._t = threading.Thread(target=self._tick, daemon=True)  # plays Live's periodic update_display()
        self._t.start()

    def song(self):
        return self._song

    def _tick(self):
        while not self._stop:
            time.sleep(0.01)
            self.update_display()

    def update_display(self):
        pass

    def schedule_message(self, delay, cb):
        pass  # rely on update_display draining, like a busy Live main thread would

    def log_message(self, *a):
        pass

    def show_message(self, *a):
        pass

    def disconnect(self):
        self._stop = True


@pytest.fixture()
def bridge(monkeypatch):
    song = fl.Song()
    live_mod = types.ModuleType("Live")
    live_mod.Application = types.SimpleNamespace(get_application=lambda: fl.Application(song))
    fw = types.ModuleType("_Framework")
    cs = types.ModuleType("_Framework.ControlSurface")
    cs.ControlSurface = _FakeControlSurface
    monkeypatch.setitem(sys.modules, "Live", live_mod)
    monkeypatch.setitem(sys.modules, "_Framework", fw)
    monkeypatch.setitem(sys.modules, "_Framework.ControlSurface", cs)
    import T2A_Bridge.bridge as br
    br = importlib.reload(br)
    monkeypatch.setattr(br, "PORT", 0)
    # bind to an ephemeral port: patch socket bind via PORT=0, then read the real port
    inst = br.T2ABridge(song)
    for _ in range(100):
        if inst._server is not None:
            break
        time.sleep(0.01)
    port = inst._server.getsockname()[1]
    yield song, port
    inst.disconnect()


def test_socket_roundtrip_and_errors(bridge):
    from track2ableton.live.client import LiveClient, LiveError

    song, port = bridge
    c = LiveClient(port=port, timeout=5)
    assert c.call("ping")["pong"]
    c.call("set_song", tempo=128)
    assert song.tempo == 128
    with pytest.raises(LiveError):
        c.call("get_track", track="does-not-exist")
    assert c.call("get_session")["tempo"] == 128  # connection still usable after an error
    c.close()


def test_mcp_tools_drive_fake_live(bridge, tmp_path, monkeypatch):
    from track2ableton.live import client as cl, mcp_server as ms

    song, port = bridge
    monkeypatch.setattr(ms, "_client", cl.LiveClient(port=port, timeout=5))
    json.loads(ms.set_song(tempo=126))
    assert song.tempo == 126
    ms.create_track(kind="midi", name="Bass")
    ms.create_clip(track="Bass", slot=0, length=4)
    ms.write_notes(track="Bass", slot=0, notes=[{"pitch": 36, "start": 0, "duration": 1, "velocity": 100}])
    assert json.loads(ms.get_notes(track="Bass", slot=0))[0]["pitch"] == 36
    ms.add_device(track="Bass", name="EQ Eight")
    out = json.loads(ms.set_parameter(track="Bass", device="EQ Eight", parameter="1 Gain A", display_value=-3))
    assert out["display"] == "-3.0 dB"
    # analysis tool on a generated file
    sr = 44100
    t = np.arange(sr * 2) / sr
    wav = str(tmp_path / "tone.wav")
    sf.write(wav, np.stack([0.5 * np.sin(2 * np.pi * 220 * t)] * 2).T, sr)
    m = json.loads(ms.analyze_audio(wav))
    assert -12 < m["integrated_lufs"] < -6
    img = ms.waveform(wav, width=300)
    assert img.data[:4] == b"\x89PNG"


def test_rebuild_from_analysis(bridge, tmp_path, monkeypatch):
    """track2ableton output folder -> built in (fake) Live through the bridge."""
    from track2ableton import pipeline
    from track2ableton.live import client as cl
    from track2ableton.live.rebuild import rebuild

    from .synth import SR, make_song

    song, port = bridge
    x, _ = make_song(bpm=124.0, bars=8)
    wav = str(tmp_path / "s.wav")
    sf.write(wav, x.T, SR)
    out = str(tmp_path / "proj")
    pipeline.run(wav, out, separation_method="dsp", write_als=False, log=lambda *a: None)
    c = cl.LiveClient(port=port, timeout=10)
    res = rebuild(out, c.call)
    assert song.tempo == 124
    names = [t.name for t in song.tracks]
    assert any(n.startswith("REF Drums") for n in names) and any(n.startswith("Bass") for n in names)
    bass = next(t for t in song.tracks if t.name.startswith("Bass"))
    assert bass.clip_slots[0].clip is not None and len(bass.clip_slots[0].clip.notes) > 10
    assert res["done"]


def test_sidechain_routing(h):
    h.handle("insert_device", {"track": 0, "name": "Compressor"})
    opts = h.handle("set_sidechain", {"track": 0, "device": "Compressor"})
    assert "1-Kick" in opts["types"]
    r = h.handle("set_sidechain", {"track": 0, "device": "Compressor", "source": "Kick"})
    assert r["source"] == "1-Kick" and r["enabled_parameter"] == "S/C On"
    h.handle("insert_device", {"track": 0, "name": "EQ Eight"})
    with pytest.raises(CommandError):
        h.handle("set_sidechain", {"track": 0, "device": "EQ Eight", "source": "Kick"})


def test_mcp_vocal_score_and_split_stems(bridge, tmp_path, monkeypatch):
    from track2ableton.live import client as cl, mcp_server as ms

    from .synth import SR, make_song

    song, port = bridge
    monkeypatch.setattr(ms, "_client", cl.LiveClient(port=port, timeout=10))
    ms.create_track(kind="midi", name="Vox")
    ms.create_clip(track="Vox", slot=0, length=8)
    ms.write_notes(track="Vox", slot=0, notes=[{"pitch": 60 + i, "start": float(i), "duration": 0.9, "velocity": 100} for i in range(6)])
    out = json.loads(ms.vocal_score(track="Vox", lyrics="ma-ña-na es hoy -", out_dir=str(tmp_path / "v"), language="es", slot=0))
    assert out["ready"] and out["note_count"] == 6 and out["syllable_count"] == 5 and os.path.isfile(out["files"]["midi"])
    bad = json.loads(ms.vocal_score(track="Vox", lyrics="hola", out_dir=str(tmp_path / "v"), language="es", slot=0))
    assert not bad["ready"] and bad["problems"][0]["kind"] == "count"
    with pytest.raises(ms.ToolError):
        ms.vocal_score(track="Vox", lyrics="hola", out_dir=str(tmp_path / "v"))            # no slot, no arrangement clip
    x, _ = make_song(bpm=124.0, bars=8)
    wav = str(tmp_path / "song.wav")
    sf.write(wav, x.T, SR, subtype="PCM_16")
    before = len(song.tracks)
    res = json.loads(ms.split_stems(wav, position=8.0))
    assert len(song.tracks) == before + len(res["stems"]) and res["tracks"][0]["track"] in res["stems"]
    assert song.tracks[-1].arrangement_clips[0].start_time == 8.0
