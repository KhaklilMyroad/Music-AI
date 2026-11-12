"""The vocal score: syllables, their place on the notes, the checks and the files. And stems onto Live tracks."""
import json
import os
import sys
from types import SimpleNamespace

import pytest
import soundfile as sf

from track2ableton import midi
from track2ableton.live import stems
from track2ableton.vocal import lyrics as ly
from track2ableton.vocal import score as vs
from track2ableton.vocal.__main__ import main as vocal_main
from track2ableton.vocal.live import score_clip

from . import fake_live as fl
from .synth import SR, make_song

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ableton_bridge"))
from T2A_Bridge.handlers import Handlers  # noqa: E402

TWINKLE = [(60, 0, 1), (60, 1, 1), (67, 2, 1), (67, 3, 1), (69, 4, 1), (69, 5, 1), (67, 6, 2),
           (65, 8, 1), (65, 9, 1), (64, 10, 1), (64, 11, 1), (62, 12, 1), (62, 13, 1), (60, 14, 2)]
WORDS = "Twinkle twinkle little star\nHow I wonder what you are"


def notes_of(melody, length=0.9):
    return [{"pitch": p, "start": float(s), "duration": d * length} for p, s, d in melody]


# ------------------------------------------------------------------------------------------- syllables

def test_spanish_syllables_stress_and_sounds():
    want = {"mañana": "ma-ÑA-na", "corazón": "co-ra-ZÓN", "instrucción": "ins-truc-CIÓN", "abrazo": "a-BRA-zo", "guitarra": "gui-TA-rra",
            "ciudad": "ciu-DAD", "país": "pa-ÍS", "poeta": "po-E-ta", "aire": "AI-re", "ahora": "a-HO-ra", "prohíbe": "pro-HÍ-be",
            "español": "es-pa-ÑOL", "río": "RÍ-o", "héroe": "HÉ-ro-e", "exacto": "e-XAC-to", "transporte": "trans-POR-te",
            "música": "MÚ-si-ca", "caballo": "ca-BA-llo", "noche": "NO-che", "cantar": "can-TAR", "playa": "PLA-ya", "cuando": "CUAN-do"}
    for word, marked in want.items():
        parts = ly.spanish_syllables(word)
        stress = ly.spanish_stress(parts)
        assert "-".join(p.upper() if i == stress else p for i, p in enumerate(parts)) == marked, word
    assert ly.spanish_syllables("buey") == ["buey"] and ly.spanish_syllables("hoy") == ["hoy"]
    said = lambda w: " ".join(x for i, p in enumerate(ly.spanish_syllables(w)) for x in ly.spanish_phonemes(p, i == 0))
    assert said("queso") == "k e s o" and said("gente") == "x e n t e" and said("llorar") == "y o r a r"
    assert said("perro") == "p e rr o" and said("rojo") == "rr o x o" and said("guitarra") == "g i t a rr a"
    assert said("ahora") == "a o r a" and said("mañana") == "m a ny a n a" and said("ciudad") == "s i u d a d"
    assert [s.stressed for s in ly.word_syllables("la", "es")] == [None]         # one syllable: no stress to place


def test_english_syllables_come_from_the_dictionary():
    pytest.importorskip("cmudict")
    tw = ly.word_syllables("twinkle", "en")
    assert [s.phonemes for s in tw] == [["T", "W", "IH", "NG"], ["K", "AH", "L"]]      # ng closes the first: nk cannot start a syllable
    assert [s.stressed for s in tw] == [True, False] and all(s.sure for s in tw)
    assert [len(ly.word_syllables(w, "en")) for w in ("star", "wonder", "beautiful", "spanish", "don't", "fire")] == [1, 2, 3, 2, 1, 2]
    assert ly.word_syllables("star", "en")[0].stressed is None
    unknown = ly.word_syllables("afrotech", "en")
    assert len(unknown) == 3 and not unknown[0].sure and unknown[0].phonemes == []


def test_without_the_dictionary_english_is_an_estimate_and_says_so(monkeypatch):
    monkeypatch.setattr(ly, "_cmu", {})
    counts = {w: len(ly.word_syllables(w, "en")) for w in ("star", "twinkle", "wonder", "little", "love", "dance", "fire")}
    assert counts == {"star": 1, "twinkle": 2, "wonder": 2, "little": 2, "love": 1, "dance": 1, "fire": 1}
    assert not ly.word_syllables("wonder", "en")[0].sure
    sc = vs.build(notes_of(TWINKLE), WORDS, "en", bpm=100)
    assert any(p["kind"] == "dictionary" for p in sc.problems)


def test_typed_syllables_and_holds():
    assert [s.text for s in ly.word_syllables("sha-lom", "typed")] == ["sha", "lom"]
    assert [s.text for s in ly.word_syllables("shalom", "typed")] == ["shalom"]
    assert [s.text for s in ly.word_syllables("af-ro-tech", "en")] == ["af", "ro", "tech"]        # typed wins over the estimate
    got = ly.parse("Hola, mi amor -\n¿Cómo estás? + +", "es")
    assert [(s.text, s.line, s.hold) for s in got] == [("Ho", 0, False), ("la", 0, False), ("mi", 0, False), ("a", 0, False), ("mor", 0, False),
                                                       ("-", 0, True), ("Có", 1, False), ("mo", 1, False), ("es", 1, False), ("tás", 1, False),
                                                       ("+", 1, True), ("+", 1, True)]
    assert [s.breath_after for s in got][:6] == [False, True, False, False, False, True]       # after the comma and at the line's end


# ------------------------------------------------------------------------------------------- the score

def test_every_note_gets_its_syllable():
    pytest.importorskip("cmudict")
    sc = vs.build(notes_of(TWINKLE), WORDS, "en", bpm=100)
    assert sc.ok and sc.info["note_count"] == 14 == sc.info["syllable_count"]
    assert [n.syllable.text.lower() for n in sc.notes][:7] == ["twin", "kle", "twin", "kle", "lit", "tle", "star"]
    r = sc.info["range"]
    assert (r["lowest"], r["highest"], r["semitones"]) == ("C3", "A3", 9)         # Ableton's names: middle C is C3
    assert "tenor" in r["fits"] and r["fits_after_transposing"]["bass"] == -12


def test_a_wrong_count_is_an_error_that_names_its_line_and_stays_in_it():
    melody = [(60, 0, 1), (62, 1, 1), (64, 2, 1), (65, 3, 1), (67, 8, 1), (65, 9, 1), (64, 10, 1)]       # two phrases: 4 notes, 3 notes
    sc = vs.build(notes_of(melody), "la la la\nsol fa mi", "typed")
    assert not sc.ok
    bad = [p for p in sc.problems if p["kind"] == "count"]
    assert len(bad) == 1 and bad[0]["data"] == {"line": 1, "syllables": 3, "notes": 4, "eased": False}
    assert [n.syllable.text for n in sc.notes[4:]] == ["sol", "fa", "mi"]          # line 2 is untouched by the mistake in line 1
    assert sc.notes[3].syllable is None and not sc.notes[3].hold
    eased = vs.build(notes_of(melody), "la la la\nsol fa mi", "typed", fit="end")
    assert eased.ok and eased.notes[3].hold and [p["level"] for p in eased.problems if p["kind"] == "count"] == ["warning"]
    held = vs.build(notes_of(melody), "la la - la\nsol fa mi", "typed")
    assert held.ok and held.notes[2].hold and held.notes[2].syllable is None and held.notes[3].syllable.text == "la"
    more = vs.build(notes_of(melody), "la la la la la\nsol fa mi", "typed", fit="end")
    assert not more.ok                                                             # syllables left over are never dropped quietly
    assert not vs.build(notes_of(melody), "- la la la\nsol fa mi", "typed").ok     # a hold with nothing before it


def test_what_a_voice_cannot_do_is_reported():
    kinds = lambda sc: {p["kind"] for p in sc.problems}
    chord = vs.build(notes_of([(60, 0, 1), (64, 0, 1), (62, 1, 1)]), "la la", "typed")
    assert "chord" in kinds(chord) and not chord.ok and [n.pitch for n in chord.notes] == [64, 62]
    over = vs.build([{"pitch": 60, "start": 0.0, "duration": 2.0}, {"pitch": 62, "start": 1.0, "duration": 1.0}], "la la", "typed")
    assert "overlap" in kinds(over) and over.ok and over.notes[0].duration == 1.0
    fast = vs.build(notes_of([(60, 0, 0.125), (62, 0.125, 0.125), (64, 0.25, 1)]), "la la la", "typed", bpm=170)
    assert "fast" in kinds(fast)                                                   # a 32nd at 170 BPM is 44 ms
    assert "leap" in kinds(vs.build(notes_of([(48, 0, 1), (64, 1, 1)]), "la la", "typed"))
    assert "range" in kinds(vs.build(notes_of([(45, 0, 1), (57, 1, 1), (72, 2, 1)]), "la la la", "typed"))
    long = [(60 + i % 3, i, 1) for i in range(24)]
    assert "breath" in kinds(vs.build(notes_of(long, 1.0), " ".join(["la"] * 24), "typed", bpm=120))      # 12 s with no gap
    assert "breath" not in kinds(vs.build(notes_of(long, 0.5), " ".join(["la"] * 24), "typed", bpm=120))
    with pytest.raises(ValueError):
        vs.build(notes_of(TWINKLE), WORDS, fit="guess")


def test_word_stress_against_the_bar():
    pytest.importorskip("cmudict")
    on = vs.build(notes_of([(60, 0, 1), (62, 1, 1)]), "wonder", "en")              # WON on the downbeat
    off = vs.build(notes_of([(60, 3.75, 0.25), (62, 4, 1)]), "wonder", "en")       # WON on the last 16th, -der on the downbeat
    assert not [p for p in on.problems if p["kind"] == "stress"]
    assert [p["data"]["word"] for p in off.problems if p["kind"] == "stress"] == ["wonder"]
    es = vs.build(notes_of([(60, 3.5, 0.5), (62, 4, 1), (60, 5, 1)]), "mañana", "es")
    assert not [p for p in es.problems if p["kind"] == "stress"]                   # ma-ÑA-na with ÑA on the downbeat


# ------------------------------------------------------------------------------------------- files

def test_the_midi_carries_the_lyrics_and_other_software_reads_them(tmp_path):
    pytest.importorskip("cmudict")
    res = vs.write(vs.build(notes_of(TWINKLE), WORDS, "en", bpm=100), str(tmp_path))
    words = midi.read_lyrics(res["files"]["midi"])
    assert [w for _, w in words][:7] == ["Twin-", "kle", "twin-", "kle", "lit-", "tle", "star"]
    assert [b for b, _ in words] == [float(s) for _, s, _ in TWINKLE]
    assert [(n["pitch"], n["start"]) for n in midi.read(res["files"]["midi"])] == [(p, float(s)) for p, s, _ in TWINKLE]
    mido = pytest.importorskip("mido")
    heard = [m.text for tr in mido.MidiFile(res["files"]["midi"]).tracks for m in tr if m.is_meta and m.type == "lyrics"]
    assert heard == [w for _, w in words]
    data = json.load(open(res["files"]["json"], encoding="utf-8"))
    assert data["ready"] and data["notes"][0] == {"pitch": 60, "name": "C3", "start": 0.0, "duration": 0.9, "bar_beat": "1.1.1",
                                                  "text": "Twin", "word": "Twinkle", "syllable": "1/2",
                                                  "phonemes": ["T", "W", "IH", "NG"], "stressed": True, "hold": False}
    text = open(res["files"]["report"], encoding="utf-8").read()
    assert "מוכן" in text and "**Twin**" in text


def test_the_musicxml_is_a_score_another_program_reads_back(tmp_path):
    music21 = pytest.importorskip("music21")
    melody = [(57, 0.5, 0.5), (60, 1, 1), (64, 2, 6), (62, 9, 0.75), (60, 9.75, 0.25), (59, 10, 2)]      # a note over two bar lines, a rest
    sc = vs.build(notes_of(melody, 1.0), "ma-ña-na - es hoy", "es", bpm=130)
    assert sc.ok
    path = vs.write(sc, str(tmp_path))["files"]["musicxml"]
    part = music21.converter.parse(path).parts[0]
    assert all(m.duration.quarterLength == 4 for m in part.getElementsByClass("Measure"))               # every bar is full
    got = [(n.pitch.midi, float(n.offset), float(n.quarterLength), n.lyric) for n in part.stripTies().flatten().notes]
    assert got == [(57, 0.5, 0.5, "ma"), (60, 1.0, 1.0, "ña"), (64, 2.0, 6.0, "na"), (62, 9.0, 0.75, None), (60, 9.75, 0.25, "es"),
                   (59, 10.0, 2.0, "hoy")]
    first = [n for n in part.flatten().notes if n.lyrics]
    assert [(n.lyric, n.lyrics[0].syllabic) for n in first[:3]] == [("ma", "begin"), ("ña", "middle"), ("na", "end")]
    assert len([n for n in part.flatten().notes if n.lyric == "na"]) == 1                                # once, on the first tied note


# ------------------------------------------------------------------------------------------- Live

def live_call():
    s = fl.Song()
    h = Handlers(s, fl.Application(s))
    return s, (lambda cmd, **kw: h.handle(cmd, kw))


def test_a_clip_in_live_becomes_a_vocal_score(tmp_path):
    song, call = live_call()
    call("set_song", tempo=130)
    idx = call("create_track", kind="midi", name="Vocal melody")["index"]
    call("create_clip", track=idx, slot=0, length=16)
    call("add_notes", track=idx, slot=0, notes=[{"pitch": p, "start": s, "duration": d * 0.9, "velocity": 100} for p, s, d in TWINKLE])
    res = score_clip(call, idx, "la la la la la la la\nla la la la la la la", str(tmp_path / "v"), lang="typed", slot=0, phrase_gap=0.05)
    assert res["ready"] and res["bpm"] == 130 and res["note_count"] == 14 and os.path.isfile(res["files"]["musicxml"])
    assert "where the clip starts" in res["next"]
    bad = score_clip(call, idx, "la la la", str(tmp_path / "v2"), lang="typed", slot=0)
    assert not bad["ready"] and "Fix the errors" in bad["next"]
    with pytest.raises(ValueError):
        score_clip(call, idx, "la", str(tmp_path / "v3"))                          # neither a slot nor an arrangement clip


def test_stems_of_a_file_go_onto_their_own_tracks(tmp_path):
    x, _ = make_song(bpm=124.0, bars=8)
    wav = str(tmp_path / "song.wav")
    sf.write(wav, x.T, SR, subtype="PCM_16")
    res = stems.split(wav, method="dsp")
    assert res["method"].startswith("dsp") and "rough" in res["note"] and set(res["stems"]) >= {"drums", "bass"}
    assert all(os.path.isfile(f) for f in res["stems"].values()) and res["folder"].endswith("song stems")
    song, call = live_call()
    before = len(song.tracks)
    made = stems.to_live(call, res["stems"], position=16.0, prefix="STEM ")
    assert len(song.tracks) == before + len(res["stems"]) == before + len(made)
    track = next(t for t in song.tracks if t.name == "STEM drums")
    assert track.arrangement_clips[0].start_time == 16.0 and track.arrangement_clips[0].file_path.endswith("song - drums.wav")
    calls = {"n": 0}

    def failing(cmd, **kw):
        if cmd == "create_audio_clip":
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("disk gone")
        return call(cmd, **kw)

    count = len(song.tracks)
    with pytest.raises(RuntimeError):
        stems.to_live(failing, res["stems"], prefix="X ")
    assert len(song.tracks) == count                                               # what the failed run made is gone again
    with pytest.raises(FileNotFoundError):
        stems.split(str(tmp_path / "nothing.wav"))


def test_vocal_command_line(tmp_path, capsys):
    mid = str(tmp_path / "melody.mid")
    midi.write(mid, [SimpleNamespace(pitch=p, start=s, duration=d * 0.9, velocity=100) for p, s, d in TWINKLE], 100)
    (tmp_path / "words.txt").write_text("ma-ña-na ma-ña-na es hoy\nco-mo se di-ce en es-pa-ñol", encoding="utf-8")
    assert vocal_main([mid, str(tmp_path / "words.txt"), "--lang", "es", "--bpm", "100", "-o", str(tmp_path / "out")]) == 1
    assert "17 syllables for 14 notes" in capsys.readouterr().out                  # it says exactly what is off
    (tmp_path / "words.txt").write_text("ma-ña-na ma-ña-na hoy\nco-mo se di-ce a-quí", encoding="utf-8")
    assert vocal_main([mid, str(tmp_path / "words.txt"), "--lang", "es", "--bpm", "100", "-o", str(tmp_path / "out")]) == 0
    assert sorted(os.listdir(tmp_path / "out")) == ["VOCAL_REPORT.md", "vocal.json", "vocal.mid", "vocal.musicxml"]
    assert vocal_main([str(tmp_path / "none.mid"), str(tmp_path / "words.txt")]) == 2


FAKE_DEMUCS = '''
import os, sys
import soundfile as sf
a = sys.argv[1:]
model, out, path = a[a.index("-n") + 1], a[a.index("-o") + 1], a[-1]
print("PROGRESS 100%")                      # what the real one prints; it must not reach our own standard output
x, sr = sf.read(path, always_2d=True)
d = os.path.join(out, model, os.path.splitext(os.path.basename(path))[0])
os.makedirs(d)
for name, gain in (("drums", 0.6), ("bass", 0.4)):
    sf.write(os.path.join(d, name + ".wav"), x * gain, sr)
'''


def test_demucs_can_live_in_another_python(tmp_path, monkeypatch, capfd):
    from track2ableton import separation

    x, _ = make_song(bpm=124.0, bars=4)
    wav = str(tmp_path / "song.wav")
    sf.write(wav, x.T, SR, subtype="PCM_16")
    monkeypatch.setenv("T2A_DEMUCS_PYTHON", str(tmp_path / "no" / "python.exe"))
    assert not separation.demucs_available()
    res = stems.split(wav, out_dir=str(tmp_path / "a"))
    assert res["method"].startswith("dsp") and "T2A_DEMUCS_PYTHON" in res["note"]          # it says why the rough split was used
    with pytest.raises(RuntimeError, match="does not exist"):
        stems.split(wav, out_dir=str(tmp_path / "b"), method="demucs")
    (tmp_path / "pkg" / "demucs").mkdir(parents=True)                                       # a stand-in for the real package
    (tmp_path / "pkg" / "demucs" / "__main__.py").write_text(FAKE_DEMUCS, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "pkg"))
    monkeypatch.setenv("T2A_DEMUCS_PYTHON", sys.executable)
    capfd.readouterr()
    res = stems.split(wav, out_dir=str(tmp_path / "c"), method="demucs")
    assert res["method"] == "demucs:htdemucs_6s" and set(res["stems"]) == {"drums", "bass"}
    assert "PROGRESS" not in capfd.readouterr().out
    assert sorted(os.listdir(tmp_path / "c")) == ["song - bass.wav", "song - drums.wav"]    # no working folder left behind
    (tmp_path / "pkg" / "demucs" / "__main__.py").write_text("import sys; sys.stderr.write('CUDA out of memory'); sys.exit(3)", encoding="utf-8")
    res = stems.split(wav, out_dir=str(tmp_path / "d"))
    assert res["method"].startswith("dsp") and "CUDA out of memory" in res["note"]          # a failed run falls back and says why
