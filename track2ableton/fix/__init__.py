"""Put a finished recording right: steady round tempo, notes that agree with their repetitions, one chord loop."""
from .notes import Report, chord_loop, loop_length, repair_drums, repair_mono, repair_poly


def run(*args, **kwargs):
    from .project import run as _run          # imported late: the pipeline is heavy and notes.py is usable without it
    return _run(*args, **kwargs)


__all__ = ["Report", "chord_loop", "loop_length", "repair_drums", "repair_mono", "repair_poly", "run"]
