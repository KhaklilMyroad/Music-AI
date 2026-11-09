"""Minimal Standard MIDI File (format 1) writer, no dependencies."""
from __future__ import annotations

import struct

PPQ = 480


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, bytes]]) -> bytes:
    events.sort(key=lambda e: e[0])
    data = bytearray()
    last = 0
    for tick, msg in events:
        data += _vlq(tick - last) + msg
        last = tick
    data += _vlq(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(data)) + bytes(data)


def write(path: str, notes, bpm: float, name: str = "Track", channel: int = 0, beats_per_bar: int = 4) -> str:
    """notes: iterable with .pitch, .start (beats), .duration (beats), .velocity."""
    tempo = int(round(60_000_000 / bpm))
    meta = [
        (0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")),
        (0, b"\xff\x58\x04" + bytes([beats_per_bar, 2, 24, 8])),
    ]
    nb = name.encode("utf-8")[:120]
    ev: list[tuple[int, bytes]] = [(0, b"\xff\x03" + _vlq(len(nb)) + nb)]
    for n in notes:
        on = int(round(n.start * PPQ))
        off = int(round((n.start + n.duration) * PPQ))
        if off <= on:
            off = on + PPQ // 4
        p = int(min(127, max(0, n.pitch)))
        v = int(min(127, max(1, n.velocity)))
        # note-offs sort before note-ons at equal ticks via (tick, 0x80 < 0x90)
        ev.append((off, bytes([0x80 | channel, p, 0])))
        ev.append((on, bytes([0x90 | channel, p, v])))
    ev.sort(key=lambda e: (e[0], e[1][0] & 0xF0 == 0x90))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, 2, PPQ)
    with open(path, "wb") as f:
        f.write(header + _track(meta) + _track(ev))
    return path
