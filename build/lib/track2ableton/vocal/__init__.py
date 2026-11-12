"""A melody and its words as a vocal score for a singing engine: a syllable on every note, checked, in standard files."""
from .lyrics import Syllable, parse, spanish_syllables, word_syllables
from .score import Score, Sung, build, musicxml, report, to_json, write

__all__ = ["Score", "Sung", "Syllable", "build", "musicxml", "parse", "report", "spanish_syllables", "to_json", "word_syllables", "write"]
