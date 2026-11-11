"""Composer: writes a whole club track as MIDI, bar by bar, from a short spec (tempo, key, structure).

    from track2ableton.compose import Spec, compose, validate, write
    comp = compose(Spec(bpm=130, key="A minor"))
    write(comp, "out")            # MIDI/*.mid, arrangement.json, REPORT.md

Deterministic: the same spec always gives the same notes. `variant` (0-2) selects alternative figures.
"""
from .arrange import Composition, Section, Spec, compose, cut
from .export import bar_table, summary, write
from .validate import Check, all_ok, validate

__all__ = ["Check", "Composition", "Section", "Spec", "all_ok", "bar_table", "compose", "cut", "summary", "validate", "write"]
