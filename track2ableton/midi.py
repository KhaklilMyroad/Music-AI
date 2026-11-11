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


def read(path: str) -> list[dict]:
    """Notes from a Standard MIDI File as [{pitch, start, duration, velocity}] in beats (quarter notes)."""
    data = open(path, "rb").read()
    if data[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    ntracks, division = struct.unpack(">HH", data[10:14])
    if division & 0x8000:
        raise ValueError("SMPTE time division is not supported")
    pos = 14
    notes = []
    for _ in range(ntracks):
        if data[pos:pos + 4] != b"MTrk":
            break
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        p, end = pos + 8, pos + 8 + length
        tick, status, open_ = 0, 0, {}
        while p < end:
            delta = 0
            while True:
                b = data[p]
                p += 1
                delta = (delta << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            tick += delta
            b = data[p]
            if b & 0x80:
                status = b
                p += 1
            kind = status & 0xF0
            if status == 0xFF:
                p += 1  # meta type
                ln = 0
                while True:
                    c = data[p]
                    p += 1
                    ln = (ln << 7) | (c & 0x7F)
                    if not c & 0x80:
                        break
                p += ln
            elif status in (0xF0, 0xF7):
                ln = 0
                while True:
                    c = data[p]
                    p += 1
                    ln = (ln << 7) | (c & 0x7F)
                    if not c & 0x80:
                        break
                p += ln
            elif kind in (0x80, 0x90):
                pitch, vel = data[p], data[p + 1]
                p += 2
                key = (status & 0x0F, pitch)
                if kind == 0x90 and vel > 0:
                    open_.setdefault(key, []).append((tick, vel))
                elif open_.get(key):
                    t0, v0 = open_[key].pop(0)
                    notes.append({"pitch": pitch, "start": t0 / division, "duration": max(1, tick - t0) / division, "velocity": v0})
            elif kind in (0xC0, 0xD0):
                p += 1
            else:
                p += 2
        pos = end
    notes.sort(key=lambda n: (n["start"], n["pitch"]))
    return notes
