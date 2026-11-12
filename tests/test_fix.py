"""The fix stage: beat map on steady and drifting audio, note repair against a known song with planted errors,
stem folders, and one end-to-end run."""
import gzip
import json
import os
import re

import numpy as np
import pytest
import soundfile as sf

from track2ableton import beatmap, midi, rhythm as rh, separation, tonal as tn
from track2ableton.compose import Spec, compose
from track2ableton.fix import notes as nt
from track2ableton.fix import project
from track2ableton.fix.__main__ import main as fix_main
from track2ableton.transcribe import Note

from .synth import SR, drift_clock, make_song, render_parts

A_MINOR = {9, 11, 0, 2, 4, 5, 7}


def in_a_minor(pc, beat):
    return pc in A_MINOR or pc == 8          # with the raised seventh of the V chord


# ------------------------------------------------------------------------------------------- beat map

def groove(bars=48, quiet=(24, 32)):
    kick, hat, clap, bass, pad = [], [], [], [], []
    roots = [45, 43, 41, 40]
    for bar in range(bars):
        b0, root = bar * 4, roots[(bar // 2) % 4]
        if not quiet[0] <= bar < quiet[1]:
            kick += [b0 + i for i in range(4)]
            hat += [b0 + i + 0.5 for i in range(4)]
            clap += [b0 + 1, b0 + 3]
            bass += [(root - 12, b0 + i + 0.5, 0.25) for i in range(4)]
        if bar % 2 == 0:
            pad += [(root + 12 + iv, b0, 8.0) for iv in (0, 3 if root == 45 else 4, 7)]
    return {"kick": kick, "clap": clap, "hat": hat, "bass": bass, "pad": pad}


def tracked(clock, offset):
    parts = groove()
    stems = render_parts(parts, clock, offset_s=offset)
    mono = sum(stems.values())
    on = rh.onset_envelopes(mono, SR)
    ch = tn.chroma_features(mono, SR)
    r = rh.analyze(mono, SR, on, ch[0], tn.FPS)
    bm = beatmap.track(on, r, mono.size / SR, ch[0], tn.FPS)
    true = offset + clock(np.arange(0, 48 * 4))
    err = np.array([np.min(np.abs(bm.times - t)) for t in true]) * 1000
    grid = r.first_downbeat + np.arange(-8, 260) * r.beat_len
    err_grid = np.array([np.min(np.abs(grid - t)) for t in true]) * 1000
    return bm, parts, stems, err, err_grid, mono.size / SR, true


def test_a_steady_tempo_that_is_not_round_is_not_called_drift():
    bm, _, _, err, _, duration, _ = tracked(drift_clock(bpm=129.63, beats=192, wobble=0, ramp=0), 0.21)
    assert not bm.drifting
    assert abs(bm.bpm - 129.63) < 0.03
    assert err.max() < 10


def test_the_existing_steady_test_songs_are_not_bent():
    for bpm, off in ((124.0, 0.37), (128.0, 0.0), (99.5, 0.2)):
        x, _ = make_song(bpm=bpm, offset_s=off)
        mono = x.mean(axis=0)
        on = rh.onset_envelopes(mono, SR)
        ch = tn.chroma_features(mono, SR)
        bm = beatmap.track(on, rh.analyze(mono, SR, on, ch[0], tn.FPS), mono.size / SR, ch[0], tn.FPS)
        assert not bm.drifting, (bpm, bm.drift_ms, bm.gain)


def test_a_drifting_tempo_is_followed_where_a_constant_grid_slides_away():
    clock = drift_clock(bpm=129.6, beats=192, wobble=0.004, ramp=0.006)
    bm, _, _, err, err_grid, duration, true = tracked(clock, 0.21)
    assert bm.drifting and bm.gain > 0.3
    assert err_grid.max() > 60                      # the problem is real: one grid is far off somewhere
    assert np.median(err) < 6 and err.max() < 25    # the map stays on the beat (the 8 bars without drums included)
    bars = bm.to_beats(true[::4])
    assert np.abs(bars - np.round(bars / 4) * 4).max() < 0.06      # every true downbeat lands on a bar line
    marks = bm.warp_markers(duration)
    sec, beat = np.array(marks).T
    assert sec[0] == 0 and abs(sec[-1] - duration) < 1e-9 and len(marks) > 4
    assert np.all(np.diff(sec) > 0) and np.all(np.diff(beat) > 0)
    # the few markers reproduce the whole map: warped by them, every true beat is within 6 ms of its grid line
    warped = np.interp(true, sec, beat)
    assert np.abs(warped - np.round(warped)).max() * 60 / 130 * 1000 < 25
    assert np.median(np.abs(warped - np.round(warped))) * 60 / 130 * 1000 < 6


def test_beat_map_round_trip():
    bm, *_ = tracked(drift_clock(bpm=129.6, beats=192, wobble=0.004, ramp=0.006), 0.21)
    t = np.linspace(0.5, 60, 50)
    assert np.allclose(bm.to_seconds(bm.to_beats(t)), t, atol=1e-9)
    assert bm.lead_in == 4 and abs(float(bm.to_beats(bm.times[bm.downbeat])) - 4) < 1e-9


def beat_map_of(stems):
    mono = sum(stems.values())
    on = rh.onset_envelopes(mono, SR)
    ch = tn.chroma_features(mono, SR)
    r = rh.analyze(mono, SR, on, ch[0], tn.FPS)
    return beatmap.track(on, r, mono.size / SR, ch[0], tn.FPS), r


def test_a_clip_of_two_bars_does_not_crash():
    x, _ = make_song(bpm=124.0, bars=2)
    mono = x.mean(axis=0)
    on = rh.onset_envelopes(mono, SR)
    bm = beatmap.track(on, rh.analyze(mono, SR, on), mono.size / SR)
    assert np.all(np.diff(bm.times) > 0) and not bm.drifting


def test_a_steady_tempo_just_off_a_round_number_is_not_snapped_to_it():
    clock = drift_clock(bpm=127.93, beats=96 * 4, wobble=0, ramp=0)
    parts = groove(bars=96, quiet=(40, 48))
    bm, r = beat_map_of(render_parts(parts, clock, offset_s=0.21))
    assert r.bpm == 128.0 and not bm.drifting                       # the analysis rounds; the map must not follow it
    assert abs(bm.steady_bpm - 127.93) < 0.01
    true = 0.21 + clock(np.arange(0, 96 * 4))
    grid = bm.steady_downbeat + np.arange(-4, 96 * 4 + 4) * 60 / bm.steady_bpm
    assert max(np.min(np.abs(grid - t)) for t in true) < 0.010      # 128 would be off by a tenth of a second at the end
    bm, r = beat_map_of(render_parts(groove(), drift_clock(bpm=128.0, beats=192, wobble=0, ramp=0), offset_s=0.21))
    assert bm.steady_bpm == pytest.approx(r.bpm, abs=1e-9) and r.bpm == 128.0     # and a round tempo stays round


def test_a_steady_song_is_not_bent_when_only_off_beats_play_after_a_break():
    kick, hat, bass, pad = [], [], [], []
    for bar in range(48):
        b0 = bar * 4
        if bar < 16:
            kick += [b0 + i for i in range(4)]
        if bar < 16 or bar >= 24:
            hat += [b0 + i + 0.5 for i in range(4)]
            bass += [(33, b0 + i + 0.5, 0.25) for i in range(4)]
        if bar % 2 == 0:
            pad += [(57 + iv, b0, 8.0) for iv in (0, 3, 7)]
    bm, _ = beat_map_of(render_parts({"kick": kick, "hat": hat, "bass": bass, "pad": pad},
                                     drift_clock(bpm=126.4, beats=192, wobble=0, ramp=0), offset_s=0.2))
    assert not bm.drifting and bm.drift_ms < 20


def two_tempos(first_bpm, first_bars, then_bpm, bars=48):
    b = np.arange(0, bars * 4 + 8, 1 / 32)
    tempo = np.where(b < first_bars * 4, first_bpm, then_bpm)
    sec = np.concatenate([[0.0], np.cumsum(60.0 / tempo[:-1] / 32)])
    return lambda x: np.interp(np.asarray(x, dtype=float), b, sec)


def test_a_small_tempo_step_is_followed_and_a_large_one_is_reported_not_called_steady():
    clock = two_tempos(126.7, 8, 128.0, bars=64)
    bm, _ = beat_map_of(render_parts(groove(bars=64, quiet=(99, 99)), clock, offset_s=0.21))
    true = 0.21 + clock(np.arange(0, 64 * 4))
    assert bm.drifting and max(np.min(np.abs(bm.times - t)) for t in true) < 0.03
    bm, _ = beat_map_of(render_parts(groove(bars=48, quiet=(99, 99)), two_tempos(126.0, 24, 120.0), offset_s=0.21))
    assert bm.drift_ms > 100 and (bm.drifting or bm.unclear)       # five per cent at once cannot be followed,
    assert bm.lost and bm.lost[0][0] < 20                          # and the stretch where the map is wrong is named


# ------------------------------------------------------------------------------------------- note repair

def truth(structure="extended"):
    comp = compose(Spec(structure=structure, bake_feel=False))
    tracks = {t.name: (t.role, [Note(n.pitch, round(n.grid / 0.25) * 0.25, max(0.25, round(n.duration / 0.25) * 0.25), n.velocity)
                                for n in t.notes]) for t in comp.tracks if t.notes and t.name != "Chant"}
    turns = {b for s in comp.sections for b in range(s.start - 1, s.start - 1 + s.bars) if (b - s.start + 2) % 4 == 0}
    return tracks, turns


def copy(notes):
    return [Note(n.pitch, n.start, n.duration, n.velocity) for n in notes]


def spoil(notes, rng, drum):
    """What a transcription does to a part: misses notes, hears ghosts, octave and semitone errors, late onsets."""
    out = []
    for n in notes:
        if rng.random() < 0.12:
            continue
        m = Note(n.pitch, n.start, n.duration, n.velocity)
        r = rng.random()
        if not drum and r < 0.05:
            m.pitch += 12 * int(rng.choice([-1, 1]))
        elif not drum and r < 0.09 and m.duration <= 0.5:
            m.pitch += int(rng.choice([-1, 1]))
        if rng.random() < 0.04:
            m.start = max(0.0, m.start + 0.25 * int(rng.choice([-1, 1])))
        out.append(m)
    pitches = sorted({n.pitch for n in notes})
    for b in sorted({int(n.start // 4) for n in notes}):
        if rng.random() < 0.3:
            p = pitches[0] if drum else int(rng.choice(pitches)) + int(rng.choice([0, 0, 1, -1, 7, 12]))
            out.append(Note(p, b * 4 + int(rng.integers(0, 16)) * 0.25, 0.25, 60))
    return out


def f1(a, b):
    A = {(round(n.start / 0.25), n.pitch) for n in a}
    B = {(round(n.start / 0.25), n.pitch) for n in b}
    return 2 * len(A & B) / (len(A) + len(B)) if A or B else 1.0


def repair(role, name, notes, turns, light=False):
    if role == "drum":
        return nt.repair_drums(notes, 4, turns, light)[0]
    return (nt.repair_mono if name in ("Sub", "Mid Bass") else nt.repair_poly)(notes, 4, turns, in_a_minor, light)[0]


@pytest.mark.parametrize("structure", ["extended", "radio"])
def test_a_song_that_is_already_right_is_left_alone(structure):
    tracks, turns = truth(structure)
    for name, (role, notes) in tracks.items():
        for light in (False, True):
            assert f1(notes, repair(role, name, copy(notes), turns, light)) >= 0.975, (name, light)


@pytest.mark.parametrize("structure", ["extended", "radio"])
def test_planted_errors_are_repaired_in_every_part(structure):
    tracks, turns = truth(structure)
    before, after = [], []
    for i, (name, (role, notes)) in enumerate(tracks.items()):
        bad = spoil(notes, np.random.default_rng(100 + i), role == "drum")
        b, a = f1(notes, bad), f1(notes, repair(role, name, copy(bad), turns))
        assert a >= b - 0.02, (name, b, a)                # a part may lose a note or two, never more
        before.append(b)
        after.append(a)
    assert np.mean(after) - np.mean(before) > 0.035       # about a third of the planted errors are gone
    assert np.mean(after) > 0.89 and np.mean(before) < 0.88


def test_light_mode_changes_less_and_still_helps():
    tracks, turns = truth("extended")
    role, notes = tracks["Hat"]                      # a one-bar loop: five voters, where the two modes differ
    bad = spoil(notes, np.random.default_rng(1), True)
    normal, light = repair(role, "Hat", copy(bad), turns), repair(role, "Hat", copy(bad), turns, light=True)
    diff = lambda x: len({(n.start, n.pitch) for n in x} ^ {(n.start, n.pitch) for n in bad})
    assert 0 < diff(light) < diff(normal)
    assert f1(notes, bad) < f1(notes, light) <= f1(notes, normal)


def bar(steps, b, pitch=36, vel=100):
    return [Note(pitch, b * 4 + s * 0.25, 0.25, vel) for s in steps]


def test_a_missed_hit_is_put_back_and_a_ghost_removed():
    notes = []
    for b in range(8):
        steps = [0, 4, 8, 12]
        if b == 3:
            steps = [0, 4, 12]              # one kick missed
        if b == 5:
            steps = [0, 4, 7, 8, 12]        # one ghost
        notes += bar(steps, b)
    fixed, reps = nt.repair_drums(notes, 4, set())
    assert sorted(nt._step(n.start) % 16 for n in fixed if n.start // 4 == 3) == [0, 4, 8, 12]
    assert sorted(nt._step(n.start) % 16 for n in fixed if n.start // 4 == 5) == [0, 4, 8, 12]
    assert reps[36].added == 1 and reps[36].removed == 1 and reps[36].loop_bars == 1 and reps[36].voted == 8


def test_the_gap_before_a_drop_and_a_fill_survive():
    notes = []
    for b in range(16):
        steps = [0, 4, 8, 12]
        if b == 7:
            steps = [0, 4, 8, 10, 12, 13, 14, 15]     # a fill in the last two beats of the phrase
        if b == 15:
            steps = [0, 4, 8]                         # no kick on beat 4 before the drop
        notes += bar(steps, b)
    turns = {3, 7, 11, 15}
    fixed, reps = nt.repair_drums(notes, 4, turns)
    assert sorted(nt._step(n.start) % 16 for n in fixed if n.start // 4 == 7) == [0, 4, 8, 10, 12, 13, 14, 15]
    assert sorted(nt._step(n.start) % 16 for n in fixed if n.start // 4 == 15) == [0, 4, 8]
    assert reps[36].turns_kept == 2
    # without the phrase line the same two bars are voted flat: the protection is what keeps them
    flat, _ = nt.repair_drums(notes, 4, set())
    assert sorted(nt._step(n.start) % 16 for n in flat if n.start // 4 == 7) == [0, 4, 8, 12]


def test_what_a_whole_section_does_differently_is_kept():
    notes = []
    for b in range(24):
        notes += bar([2, 6, 10, 14] if b < 12 else [2, 3, 6, 10, 11, 14], b, 42)     # hats get busier from bar 13
    fixed, _ = nt.repair_drums(notes, 4, set())
    assert f1(notes, fixed) == 1.0


def test_loop_length_finds_a_two_bar_figure():
    ev = {b: frozenset([0, 6, 12] if b % 2 == 0 else [3, 10]) for b in range(16)}
    assert nt.loop_length(ev) == (2, 1.0)
    assert nt.loop_length({b: frozenset([b % 16]) for b in range(12)})[0] == 0       # nothing repeats: no vote
    assert nt.loop_length({0: frozenset([0]), 4: frozenset([0])})[0] == 0            # too few bars to tell


def bass_line(bars=16):
    roots = [33, 31, 29, 28]
    return [Note(roots[(b // 2) % 4], b * 4 + s * 0.25, 0.25, 100) for b in range(bars) for s in (2, 6, 10, 14)]


def test_bass_octave_error_wrong_pitch_and_missing_note():
    notes = bass_line(32)
    notes[5].pitch += 12                 # an octave error
    notes[54].pitch += 2                 # a wrong pitch that is in the scale (bar 14: a repetition on either side)
    missing = notes.pop(40)
    fixed, rep = nt.repair_mono(notes, 4, set(), in_a_minor)
    assert f1(bass_line(32), fixed) == 1.0
    assert rep.folded == 1 and rep.repitched == 1 and rep.added == 1 and rep.guessed == 0
    assert any(n.start == missing.start and n.pitch == missing.pitch for n in fixed)
    assert rep.loop_bars == 1 and rep.pitch_loop_bars == 8


def test_bass_is_one_note_at_a_time():
    notes = bass_line() + [Note(45, 2.5, 2.0, 60), Note(33, 0.5, 4.0, 90)]
    fixed, _ = nt.repair_mono(notes, 4, set(), in_a_minor)
    for a, b in zip(fixed, fixed[1:]):
        assert a.start + a.duration <= b.start + 1e-9


def test_a_short_stray_semitone_is_snapped_but_a_recurring_one_stays():
    notes = bass_line()
    notes[9].pitch = 34                  # A#: once, a 16th, next to the A the line plays
    fixed, rep = nt.repair_mono(copy(notes), 4, set(), lambda pc, beat: pc in A_MINOR)
    assert rep.snapped == 1 and all(n.pitch % 12 != 10 for n in fixed)
    for b in range(0, 16, 2):            # G# on the last 8th of every other bar: a figure, not an accident
        notes.append(Note(32, b * 4 + 3.75, 0.25, 100))
    fixed, rep = nt.repair_mono(copy(notes), 4, set(), lambda pc, beat: pc in A_MINOR)
    assert sum(1 for n in fixed if n.pitch == 32) == 8


def drum_f1(notes, **kw):
    fixed, _ = nt.repair_drums(copy(notes), 4, kw.get("turns", set()), kw.get("light", False))
    return f1(notes, fixed)


def test_short_sections_ties_and_odd_loops_are_left_alone():
    verse = lambda b: bar([4, 12] + ([15] if b % 4 == 3 else []), b, 38)             # snare with a pickup every 4th bar
    chorus = lambda b: bar([4, 7, 12] + ([15] if b % 4 == 3 else []), b, 38)         # the chorus adds a ghost
    song = [n for b in range(32) for n in (chorus(b) if (b // 8) % 2 else verse(b))]  # V8 C8 V8 C8: two loops per section
    assert drum_f1(song) == 1.0
    a, b_ = [0, 4, 8, 12], [0, 4, 6, 8, 12, 14]
    assert drum_f1([n for b in range(4) for n in bar(a if b % 2 == 0 else b_, b)]) == 1.0     # A B A B: a tie changes nothing
    assert drum_f1([n for b in range(4) for n in bar(a if b < 2 else b_, b)]) == 1.0          # A A B B
    three = [[0, 6, 12], [0, 4, 10], [2, 8, 12, 14]]
    notes = [n for b in range(24) for n in bar(three[b % 3], b)]
    assert drum_f1(notes) == 1.0 and nt.repair_drums(copy(notes), 4, set())[1][36].loop_bars == 3
    gap = [n for b in range(32) for n in bar([s for s in range(16) if not (b % 8 == 4 and s == 6)], b, 42)]
    assert drum_f1(gap) == 1.0                       # a hit left out every 8th bar is the 8-bar loop, not a 1-bar loop with errors


def test_the_last_repetition_may_differ_and_nothing_is_added_outside_the_part():
    am, f = (57, 60, 64), (53, 57, 60)
    notes = [Note(p, b * 4, 4.0, 90) for b in range(32) for p in (am, f)[(b // 4) % 2]]
    notes += [Note(72, b * 4, 4.0, 90) for b in range(24, 32)]                         # the last round adds a top note
    fixed, _ = nt.repair_poly(copy(notes), 4, set(), in_a_minor)
    assert f1(notes, fixed) == 1.0
    part = [n for b in range(2, 10) for n in bar([0, 4, 8, 12], b)]
    part = [n for n in part if n.start >= 2 * 4 + 2 and n.start < 9 * 4 + 2]           # enters and leaves in mid-bar
    fixed, _ = nt.repair_drums(copy(part), 4, set())
    assert min(n.start for n in fixed) == min(n.start for n in part) and max(n.start for n in fixed) == max(n.start for n in part)


def test_bass_figure_of_a_section_and_the_phrase_end_are_not_corrected():
    roots = [33, 31, 29, 28]
    notes = []
    for b in range(64):
        root = roots[(b // 2) % 4]
        chorus = (b // 16) % 2 == 1
        notes += [Note(root + (7 if chorus and s == 14 else 0), b * 4 + s * 0.25, 0.25, 100) for s in (2, 6, 10, 14)]
    fixed, rep = nt.repair_mono(copy(notes), 4, set(), in_a_minor)
    assert f1(notes, fixed) == 1.0 and rep.repitched == 0            # a fifth at the end of every chorus bar is the chorus
    line = bass_line(32)
    line[7 * 4 + 2].pitch += 12                                      # an octave pop in the last two beats of bar 8
    line[15 * 4 + 3].pitch = 34                                      # a chromatic pickup on the last 8th of bar 16
    turns = {7, 15, 23, 31}
    fixed, rep = nt.repair_mono(copy(line), 4, turns, lambda pc, beat: pc in A_MINOR)
    assert f1(line, fixed) == 1.0 and rep.folded == 0 and rep.snapped == 0
    fixed, rep = nt.repair_mono(copy(line), 4, set(), lambda pc, beat: pc in A_MINOR)
    assert rep.folded == 1 and rep.snapped == 1                      # the same two notes anywhere else are errors


def test_the_counts_in_the_report_add_up_when_a_snapped_note_lands_on_another():
    notes = [Note(p, b * 4, 1.0, 90) for b in range(8) for p in (57, 60, 64)]
    notes.append(Note(61, 3 * 4, 0.25, 70))                          # C# for a 16th, next to the C that is already there
    fixed, rep = nt.repair_poly(copy(notes), 4, set(), lambda pc, beat: pc in A_MINOR)
    assert rep.snapped == 1 and rep.fixed == len(fixed) == rep.raw - rep.removed + rep.added == 24


def test_chords_one_bar_of_a_different_section_is_not_voted_away():
    am, f, e = (57, 60, 64), (53, 57, 60), (52, 56, 59)
    notes = []
    for b in range(24):
        ch = (am, f)[b % 2] if not 8 <= b < 12 else (e, f)[b % 2]     # four bars where E replaces Am
        notes += [Note(p, b * 4, 4.0, 90) for p in ch]
    notes = [n for n in notes if not (n.start == 12 * 4 and n.pitch == 64)]      # one note missed in a plain bar
    fixed, rep = nt.repair_poly(copy(notes), 4, set(), in_a_minor)
    assert {n.pitch for n in fixed if n.start == 8 * 4} == set(e)     # Am and E share one note: not the same bar
    assert {n.pitch for n in fixed if n.start == 12 * 4} == set(am)   # and the missed note is back
    assert rep.added == 1 and rep.removed == 0


def test_chord_loop_votes_the_progression_and_keeps_a_real_change():
    name = lambda r, q: tn.Chord(0, 0, r, q).name
    loop = [(9, "m"), (9, "m"), (7, ""), (7, ""), (5, ""), (5, ""), (4, ""), (4, "")]
    seq = loop * 8
    seq[10] = (0, "")                    # C where the loop has G
    seq[19] = (9, "m7")                  # Am7 where the loop has G
    seq[33] = (2, "m")                   # Dm where the loop has Am
    seq[40] = (-1, "")                   # silence
    p = nt.chord_loop(seq, name)
    assert p.loop_bars == 4 and p.chords == ["Am", "Am", "G", "G", "F", "F", "E", "E"]
    assert p.fixed[10] == (0, "") and p.fixed[19] == (9, "m7") and p.fixed[33] == (2, "m")   # another root: a real change
    assert p.fixed[40] == (-1, "") and p.changed == 0
    seq[11] = (7, "7")                   # G7 where the loop has G: the same harmony heard differently
    p = nt.chord_loop(seq, name)
    assert p.fixed[11] == (7, "") and p.changed == 1
    assert 0.9 < p.share < 1.0                       # the share counts chords as heard, not after the repair
    wander = [(int(r), "") for r in np.random.default_rng(0).integers(0, 12, 40)]
    assert nt.chord_loop(wander, name).loop_bars == 0 and nt.chord_loop(wander, name).fixed == wander


def test_chord_loop_leaves_a_chorus_with_relative_chords_alone():
    name = lambda r, q: tn.Chord(0, 0, r, q).name
    verse = [(9, "m"), (9, "m"), (5, ""), (5, ""), (0, ""), (0, ""), (7, ""), (7, "")]
    chorus = [(0, ""), (0, ""), (9, "m"), (9, "m"), (4, "m"), (4, "m"), (7, ""), (7, "")]
    seq = verse * 8 + chorus * 4
    p = nt.chord_loop(seq, name)
    assert p.fixed == seq and p.changed == 0         # C where the verse has Am shares two notes and is still the song
    six = ([(0, "")] * 8 + [(9, "m")] * 4) * 6       # C C C C Am Am: a six-bar loop
    p = nt.chord_loop(six, name)
    assert p.loop_bars == 6 and p.fixed == six


# ------------------------------------------------------------------------------------------- stem folders

def test_stem_names():
    want = {"Drums": "drums", "Percussion": "drums", "Bass Drum": "drums", "Kick Drum": "drums", "Hi-Hats": "drums", "HH": "drums",
            "Ride": "drums", "Tambourine": "drums", "Toms": "drums", "Bass": "bass", "Synth Bass": "bass", "Sub Bass": "bass",
            "Bass Guitar": "bass", "808": "bass", "Vocals": "vocals", "Backing Vocals": "vocals", "Lead Vox": "vocals",
            "Hat Trick - Vocals": "vocals", "Guitar": "guitar", "Keyboard": "piano", "Synth": "other", "Strings": "other",
            "FX": "other", "What": "other", "Brass": "other", "Bassoon": "other", "Subtle Pad": "other", "Submix": "other",
            "Singing Bowl": "other", "Backing Track": "other", "Percussive Synth": "other", "Tomorrow Pad": "other",
            "תופים": "drums", "בס": "bass"}
    assert {k: separation.stem_kind(k) for k in want} == want


def write_stems(folder, names):
    folder.mkdir(parents=True, exist_ok=True)
    t = np.arange(SR // 4) / SR
    for i, name in enumerate(names):
        sf.write(folder / f"{name}.wav", 0.3 * np.sin(2 * np.pi * (80 + 40 * i) * t), SR)
    return separation.from_folder(str(folder))


def test_stem_folder_titles_shared_words_and_mixes(tmp_path):
    st = write_stems(tmp_path / "a", ["Drums 1", "Drums 2"])
    assert st.kinds == {"Drums 1": "drums", "Drums 2": "drums"}             # the shared word is the instrument, not a title
    st = write_stems(tmp_path / "b", ["Vocals - Lead", "Vocals - Backing", "Bass - DI", "Bass - Amp"])
    assert sorted(st.kinds.values()) == ["bass", "bass", "vocals", "vocals"]
    st = write_stems(tmp_path / "c", ["Bass Drum", "Bass Guitar"])
    assert st.kinds == {"Bass Drum": "drums", "Bass Guitar": "bass"}
    st = write_stems(tmp_path / "d", ["Full Moon - Drums", "Full Moon - Bass", "Full Moon"])
    assert st.kinds == {"Drums": "drums", "Bass": "bass"} and len(st.skipped) == 1      # the bare title is the mix
    st = write_stems(tmp_path / "e", ["Song (Drums)", "Song (Full Drums)", "Song (Instrumental Guitar)", "Song (Instrumental)"])
    assert set(st.kinds) == {"Drums", "Full Drums", "Instrumental Guitar"} and len(st.skipped) == 1


def test_stem_folder_leaves_out_the_mix_and_pads_lengths(tmp_path):
    t = np.arange(SR) / SR
    sf.write(tmp_path / "Song - Drums.wav", 0.3 * np.sin(2 * np.pi * 100 * t), SR)
    sf.write(tmp_path / "Song - Bass.wav", 0.3 * np.sin(2 * np.pi * 50 * t[: SR // 2]), SR)
    sf.write(tmp_path / "Song - Full Mix.wav", 0.3 * np.sin(2 * np.pi * 100 * t), SR)
    sf.write(tmp_path / "Song - Strings.wav", np.zeros(SR), SR)
    (tmp_path / "notes.txt").write_text("not audio")
    st = separation.from_folder(str(tmp_path))
    assert st.kinds == {"Drums": "drums", "Bass": "bass"} and st.method == "folder"
    assert {a.data.shape for a in st.stems.values()} == {(2, SR)}
    assert len(st.skipped) == 2 and "mix" in " ".join(st.skipped) and "silent" in " ".join(st.skipped)
    assert separation.mixdown(st).data.shape == (2, SR)
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError):
        separation.from_folder(str(tmp_path / "empty"))


# ------------------------------------------------------------------------------------------- end to end

@pytest.fixture(scope="module")
def fixed_song(tmp_path_factory):
    """48 bars whose tempo wobbles and climbs, exported as a folder of stems the way a generator would."""
    root = tmp_path_factory.mktemp("fix")
    parts = groove()
    stems = render_parts(parts, drift_clock(bpm=129.6, beats=192, wobble=0.004, ramp=0.006), offset_s=0.21)
    src = root / "My Song stems"
    src.mkdir()
    sf.write(src / "My Song - Drums.wav", (stems["kick"] + stems["clap"] + stems["hat"]) * 0.8, SR, subtype="PCM_16")
    sf.write(src / "My Song - Bass.wav", stems["bass"], SR, subtype="PCM_16")
    sf.write(src / "My Song - Synth.wav", stems["pad"], SR, subtype="PCM_16")
    sf.write(src / "My Song - Full Mix.wav", sum(stems.values()) * 0.5, SR, subtype="PCM_16")
    out = str(root / "out")
    info = project.run(str(src), out, log=lambda *_: None)
    return info, out, parts


def test_fix_tempo_and_report(fixed_song):
    info, out, _ = fixed_song
    t = info["tempo"]
    assert t["project_bpm"] == 130.0 and t["drifting"] and t["warp_markers"] > 4 and t["time_signature"] == "4/4"
    assert info["key"]["name"] == "A minor"
    assert info["stems"] == "folder" and len(info["skipped_files"]) == 1
    assert info["progression"]["loop_bars"] == 8
    assert info["progression"]["chords_per_half_bar"] == ["Am"] * 4 + ["G"] * 4 + ["F"] * 4 + ["E"] * 4
    for f in ("FIX_REPORT.md", "fix.json", "recipe.json", "MIDI/Drums.mid", "MIDI_raw/Drums.mid", "MIDI/Bass.mid", "Stems/Bass.wav"):
        assert os.path.exists(os.path.join(out, f)), f
    assert json.load(open(os.path.join(out, "fix.json"), encoding="utf-8"))["tempo"] == t
    text = open(os.path.join(out, "FIX_REPORT.md"), encoding="utf-8").read()
    assert "130" in text and "Am (2 תיבות)" in text and "Full Mix" in text


def test_fix_puts_the_notes_where_they_were_played(fixed_song):
    info, out, parts = fixed_song
    lead = 4.0                                        # the audio starts before the first downbeat: that is bar 2
    drums = midi.read(os.path.join(out, "MIDI", "Drums.mid"))
    kicks = {round(n["start"] / 0.25) for n in drums if n["pitch"] == 36}
    assert kicks == {round((b + lead) / 0.25) for b in parts["kick"]}       # every kick, on its own 16th, despite the drift
    bass = midi.read(os.path.join(out, "MIDI", "Bass.mid"))
    assert {(round(n["start"] / 0.25), n["pitch"]) for n in bass} == {(round((b + lead) / 0.25), p) for p, b, _ in parts["bass"]}
    hats = [n for n in drums if n["pitch"] == 42]
    row = next(r for r in info["tracks"] if r["kind"] == "drums")
    assert abs(len(hats) - len(parts["hat"])) < abs(row["pieces"]["closed_hat"]["raw"] - len(parts["hat"]))   # closer to the truth than heard


def test_fix_live_set_has_the_project_tempo_and_warp_markers(fixed_song):
    info, out, _ = fixed_song
    path = next(os.path.join(out, f) for f in os.listdir(out) if f.endswith(".als"))
    xml = gzip.open(path).read().decode()
    assert re.search(r'<Tempo>\s*<LomId Value="0" />\s*<Manual Value="130"', xml)
    clips = re.findall(r"<AudioClip .*?</AudioClip>", xml, flags=re.S)
    assert len(clips) == 3
    for c in clips:
        marks = [(float(s), float(b)) for s, b in re.findall(r'<WarpMarker Id="\d+" SecTime="([^"]+)" BeatTime="([^"]+)"', c)]
        assert len(marks) == info["tempo"]["warp_markers"] and marks[0] == (0.0, 0.0)
        assert all(a[0] < b[0] and a[1] < b[1] for a, b in zip(marks, marks[1:]))


def test_fix_command_line_on_one_file(tmp_path, capsys):
    x, _ = make_song(bpm=123.4, bars=16, offset_s=0.1)
    wav = str(tmp_path / "song.wav")
    sf.write(wav, x.T, SR, subtype="PCM_16")
    assert fix_main([wav, "--bpm", "124", "--no-als", "--light", "--separation", "dsp"]) == 0
    out = tmp_path / "song Fixed Project"
    info = json.load(open(out / "fix.json", encoding="utf-8"))
    assert info["tempo"]["project_bpm"] == 124.0 and abs(info["tempo"]["measured_bpm"] - 123.4) < 0.1
    assert info["tempo"]["stretch_percent"] == pytest.approx(0.49, abs=0.1) and info["mode"] == "light"
    assert not info["tempo"]["drifting"] and info["tempo"]["warp_markers"] == 2
    assert not [f for f in os.listdir(out) if f.endswith(".als")]
    assert "124" in capsys.readouterr().out
    assert fix_main([str(tmp_path / "missing.wav")]) == 2
    with pytest.raises(SystemExit):
        fix_main([wav, "--bpm", "900"])


def test_fix_names_that_collide_a_second_run_and_a_file_that_starts_on_the_downbeat(tmp_path):
    stems = render_parts(groove(bars=16, quiet=(99, 99)), drift_clock(bpm=126.0, beats=64, wobble=0, ramp=0), offset_s=0.0)
    src = tmp_path / "Song v1.2 stems"
    src.mkdir()
    sf.write(src / "תופים.wav", (stems["kick"] + stems["clap"] + stems["hat"]) * 0.8, SR, subtype="PCM_16")
    sf.write(src / "בס.wav", stems["bass"], SR, subtype="PCM_16")
    sf.write(src / "Synth A+B.wav", stems["pad"], SR, subtype="PCM_16")
    sf.write(src / "Synth A B.wav", stems["pad"] * 0.5, SR, subtype="PCM_16")
    out = tmp_path / "out"
    info = project.run(str(src), str(out), log=lambda *_: None)
    kinds = {r["track"]: r["kind"] for r in info["tracks"]}
    assert kinds["תופים"] == "drums" and kinds["בס"] == "bass"
    assert len(os.listdir(out / "Stems")) == 4 and len({r["midi"] for r in info["tracks"]}) == 4     # no stem overwrote another
    assert "Song_v1_2_stems Rebuild.als" in os.listdir(out)
    assert info["sections"][0]["first_bar"] == 1                    # the file starts on the downbeat: that is bar 1
    kicks = {round(n["start"] / 0.25) for n in midi.read(str(out / "MIDI" / "תופים.mid")) if n["pitch"] == 36}
    assert kicks == {b * 4 for b in range(64)}
    os.remove(src / "Synth A B.wav")
    info = project.run(str(src), str(out), log=lambda *_: None)     # again, with one stem fewer
    assert len(os.listdir(out / "Stems")) == 3 and not [f for f in os.listdir(out / "MIDI_raw") if "_2" in f]
    assert len(info["tracks"]) == 3


def test_fix_command_line_says_what_is_wrong_with_the_input(tmp_path, capsys):
    t = np.arange(SR) / SR
    (tmp_path / "mixes").mkdir()
    sf.write(tmp_path / "mixes" / "Song - Full Mix.wav", 0.3 * np.sin(2 * np.pi * 100 * t), SR)
    sf.write(tmp_path / "mixes" / "Song - Master.wav", 0.3 * np.sin(2 * np.pi * 100 * t), SR)
    assert fix_main([str(tmp_path / "mixes")]) == 2 and "no usable stems" in capsys.readouterr().err
    x, _ = make_song(bpm=124.0, bars=8)
    sf.write(tmp_path / "song.wav", x.T, SR, subtype="PCM_16")
    assert fix_main([str(tmp_path / "song.wav"), "--template", str(tmp_path / "nothing.als")]) == 2
    assert "template not found" in capsys.readouterr().err and not (tmp_path / "song Fixed Project").exists()
    sf.write(tmp_path / "blip.wav", x.T[: SR], SR, subtype="PCM_16")
    assert fix_main([str(tmp_path / "blip.wav"), "--separation", "dsp"]) == 2 and "too short" in capsys.readouterr().err
