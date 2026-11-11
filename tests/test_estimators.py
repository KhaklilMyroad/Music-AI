"""Each estimator against signals with known answers."""
import numpy as np
import pytest

from track2ableton import dsp, midi, mixanalysis as mx, rhythm as rh, tonal as tn, transcribe as tr
from track2ableton.audio import Audio

from .synth import SR, kick, make_song, midi_hz, reverb_tail, saw, square


@pytest.fixture(scope="module")
def song():
    return make_song(bpm=124.0, offset_s=0.37)


# ---------------------------------------------------------------- loudness (ITU-R BS.1770 reference values)

def test_k_weighting_matches_bs1770_table_at_48k():
    (b1, a1), (b2, a2) = mx.k_weighting(48000)
    np.testing.assert_allclose(b1, [1.53512485958697, -2.69169618940638, 1.19839281085285], atol=1e-6)
    np.testing.assert_allclose(a1, [1.0, -1.69065929318241, 0.73248077421585], atol=1e-6)
    np.testing.assert_allclose(b2, [1.0, -2.0, 1.0])
    np.testing.assert_allclose(a2, [1.0, -1.99004745483398, 0.99007225036621], atol=1e-6)


def test_lufs_of_full_scale_1k_sine_one_channel():
    # BS.1770: a 0 dBFS 997 Hz sine in one channel reads about -3.01 LUFS
    t = np.arange(10 * 48000) / 48000
    x = np.sin(2 * np.pi * 997 * t).astype(np.float32)
    a = Audio(np.stack([x, np.zeros_like(x)]), 48000)
    assert abs(mx.integrated_lufs(a) - (-3.01)) < 0.1


def test_true_peak_detects_intersample_peak():
    # fs/4 sine phase-shifted 45 degrees: samples at 0.707 but true peak at 1.0
    n = np.arange(48000)
    x = np.sin(np.pi / 2 * n + np.pi / 4).astype(np.float32)
    a = Audio(np.stack([x, x]), 48000)
    assert mx.true_peak_db(a) > -0.5
    assert 20 * np.log10(np.max(np.abs(x))) < -2.9


# ---------------------------------------------------------------- rhythm / tonal

def test_tempo_and_downbeat(song):
    x, truth = song
    mono = x.mean(axis=0)
    ch = tn.chroma_features(mono, SR)
    r = rh.analyze(mono, SR, None, ch[0], tn.FPS)
    assert abs(r.bpm - 124.0) < 0.2
    # first downbeat within 30 ms of the truth (modulo one bar)
    bar = 4 * 60 / 124.0
    err = (r.first_downbeat - truth["first_downbeat"]) % bar
    assert min(err, bar - err) < 0.03


@pytest.mark.parametrize("bpm", [92.0, 128.0, 140.0, 174.0])
def test_tempo_various(bpm):
    x, _ = make_song(bpm=bpm, bars=16)
    mono = x.mean(axis=0)
    r = rh.analyze(mono, SR)
    assert abs(r.bpm - bpm) < 0.3, r.bpm


def test_key_and_chords(song):
    x, truth = song
    t = tn.analyze(x.mean(axis=0), SR)
    assert t.key_root == truth["key_root_pc"] and t.mode == "minor"
    assert abs(t.tuning_cents) < 10


def test_tuning_offset_is_measured():
    tt = np.arange(4 * SR) / SR
    x = sum(saw(f * 2 ** (30 / 1200), tt, 10) for f in midi_hz([57, 60, 64]))
    ch, bass, cents = tn.chroma_features(x.astype(np.float32), SR)
    assert 20 < cents < 40


# ---------------------------------------------------------------- timbre / processing

@pytest.mark.parametrize("wave,expect", [("saw", "saw"), ("square", "square"), ("sine", "sine")])
def test_waveform_identification(wave, expect):
    t = np.arange(3 * 22050) / 22050
    f = 55.0
    x = {"saw": saw(f, t), "square": square(f, t), "sine": np.sin(2 * np.pi * f * t)}[wave]
    f0, ap = dsp.yin(x, 22050, 30, 400, 2048, 128)
    h = mx.harmonic_profile(x, 22050, f0, 128 / 22050)
    assert h["waveform"] == expect, h


def test_reverb_rt60_estimate():
    rng = np.random.default_rng(0)
    x = np.zeros(SR * 12)
    for i in range(6):  # dry clicks/bursts every 2 s
        s = i * 2 * SR + SR // 10
        x[s:s + 400] = rng.standard_normal(400)
    wet = reverb_tail(x, 1.5)
    est = mx.reverb((x * 0.1 + wet).astype(np.float32), SR)
    assert 1.0 < est.rt60_s < 2.0, est


def test_sidechain_pumping_detected(song):
    x, truth = song
    bass = truth["stems"]["bass"]
    beats = truth["first_downbeat"] + np.arange(128) * 60 / 124.0
    p = mx.pumping(bass.astype(np.float32), SR, beats, beats[32:96])
    assert p.detected and p.depth_db > 5, p


def test_no_pumping_on_steady_tone():
    t = np.arange(20 * SR) / SR
    x = (0.3 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    beats = np.arange(40) * 0.5
    assert not mx.pumping(x, SR, beats).detected


def test_stereo_width():
    rng = np.random.default_rng(1)
    m = rng.standard_normal(SR * 3)
    a_mono = Audio(np.stack([m, m]).astype(np.float32), SR)
    assert mx.stereo(a_mono).side_to_mid_db < -60
    a_wide = Audio(rng.standard_normal((2, SR * 3)).astype(np.float32), SR)
    assert abs(mx.stereo(a_wide).side_to_mid_db) < 1


# ---------------------------------------------------------------- transcription

def test_drum_transcription_pattern(song):
    x, truth = song
    hits = tr.detect_drum_hits(truth["stems"]["drums"].astype(np.float32), SR)
    off = truth["first_downbeat"]
    beat = 60 / 124.0
    trans = tr.drums_to_midi(hits, lambda t: (t - off) / beat)
    assert trans.details["patterns"].get("kick") == "x...x...x...x..."
    hats = trans.details["patterns"].get("closed_hat") or trans.details["patterns"].get("open_hat")
    assert hats == "..x...x...x...x."


def test_bass_transcription_pitches(song):
    x, truth = song
    off = truth["first_downbeat"]
    beat = 60 / 124.0
    res = tr.mono_to_midi(truth["stems"]["bass"].astype(np.float32), SR, lambda t: (np.asarray(t) - off) / beat, 28, 420)
    pcs = {n.pitch % 12 for n in res.notes}
    # A, F, C, G
    assert {9, 5, 0, 7} <= pcs
    assert {n.pitch for n in res.notes} <= {33, 29, 36, 31, 45, 41, 48, 43}  # octave errors at most


def test_midi_writer_roundtrip(tmp_path):
    notes = [tr.Note(60, 0, 1, 100), tr.Note(64, 1, 0.5, 90)]
    p = midi.write(str(tmp_path / "x.mid"), notes, 120.0, "T")
    data = open(p, "rb").read()
    assert data[:4] == b"MThd" and data.count(b"MTrk") == 2
    mido = pytest.importorskip("mido")
    mf = mido.MidiFile(p)
    ons = [m for m in mf.tracks[1] if m.type == "note_on" and m.velocity > 0]
    assert [m.note for m in ons] == [60, 64]
    assert mf.ticks_per_beat == 480


def test_filter_sweep_detected():
    from scipy.signal import butter, sosfilt
    bpm, bars = 120.0, 16
    beat = 60 / bpm
    n = int(bars * 4 * beat * SR)
    t = np.arange(n) / SR
    src = np.zeros(n)
    for f in midi_hz([45, 52, 57]):
        src += saw(f, t, 60)
    out = np.zeros(n)
    blk = 1024
    for s in range(0, n, blk):  # low-pass opening from 300 Hz to 6 kHz over bars 4..12
        pos = s / SR / (4 * beat)
        fc = 300 * (20 ** np.clip((pos - 4) / 8, 0, 1))
        sos = butter(2, fc, "lowpass", fs=SR, output="sos")
        out[s:s + blk] = sosfilt(sos, src[s:s + blk])
    bar_times = np.arange(bars) * 4 * beat
    sweeps, _ = mx.filter_sweeps(out.astype(np.float32), SR, bar_times, lambda x: x / beat)
    assert any(s.kind == "lowpass opening" and s.to_hz > 2 * s.from_hz for s in sweeps), sweeps


def test_dotted_echo_detected():
    bpm = 120.0
    beat = 60 / bpm
    n = int(32 * beat * SR)
    x = np.zeros(n)
    t = np.arange(int(0.08 * SR)) / SR
    pl = saw(440, t, 20) * np.exp(-t * 60)
    rng = np.random.default_rng(2)
    for k in range(0, 32, 2):  # a plucked note every 2 beats, irregular velocity
        i = int(k * beat * SR)
        x[i:i + pl.size] += pl * (0.6 + 0.4 * rng.random())
    y = x.copy()
    d = int(0.75 * beat * SR)  # 1/8 dotted
    for r in range(1, 5):
        y[r * d:] += x[: n - r * d] * 0.55 ** r
    e = mx.echo(y.astype(np.float32), SR, bpm)
    assert e.detected and e.division == "1/8 dotted", e
