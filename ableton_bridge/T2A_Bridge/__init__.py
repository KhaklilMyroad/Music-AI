# Ableton Live loads this folder as a MIDI Remote Script ("Control Surface: T2A_Bridge").
from __future__ import absolute_import


def create_instance(c_instance):
    from .bridge import T2ABridge
    return T2ABridge(c_instance)
