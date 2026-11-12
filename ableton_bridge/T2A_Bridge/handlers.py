# T2A_Bridge command handlers. Runs inside Ableton Live's embedded Python.
# Kept free of Live imports at module level so it can be unit-tested with a fake Live Object Model.
# Python 3.7-compatible syntax on purpose (no walrus, no builtin generics).
from __future__ import absolute_import, division, print_function

import os
import re

VERSION = "0.2"

try:  # only available inside Live
    import Live  # noqa: F401
except Exception:  # pragma: no cover
    Live = None


class CommandError(Exception):
    pass


# Commands that only look. `kind_of` is the one place that says what a command does to the Live Set; the client
# keeps a copy (track2ableton/live/guard.py) and a test holds the two together.
READS = frozenset(["ping", "list_commands", "get_session", "list_tracks", "get_track", "get_routing", "get_notes",
                   "get_device", "browse", "search_browser", "get_audio_files", "get_meters"])
OFF_WORDS = ("", "0", "false", "no", "off")


def kind_of(cmd, args=None):
    """'read': only looks. 'playback': starts, stops or moves playback without editing anything.
    'write': changes the Live Set."""
    args = args or {}
    action = str(args.get("action", "list")).lower()
    if cmd in READS:
        return "read"
    if cmd in ("cue", "scene") and action == "list":
        return "read"
    if cmd == "set_sidechain" and args.get("source") is None and args.get("channel") is None:
        return "read"                      # no source given: it lists the options
    if cmd == "transport" or (cmd == "cue" and action in ("next", "prev", "jump")):
        return "playback"
    return "write"


def read_only_flag():
    return os.path.join(os.path.expanduser("~"), ".track2ableton", "read_only")


def read_only():
    """Has the user switched read-only on? Either the flag file exists (python -m track2ableton.doctor --read-only on),
    or T2A_READ_ONLY is set to anything that is not plainly off: a value this code does not know means on."""
    v = os.environ.get("T2A_READ_ONLY")
    if v is not None and v.strip().strip("\"'").strip().lower() not in OFF_WORDS:
        return True
    try:
        return os.path.exists(read_only_flag())
    except Exception:
        return False


def _num(s):
    if "-inf" in str(s).lower():
        return float("-inf")
    m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", "."))
    if not m:
        return None
    v = float(m.group(0))
    txt = str(s)
    if re.search(r"\d\s*k(hz)?\b", txt.lower()):
        v *= 1000.0
    return v


def _has(obj, name):
    try:
        return hasattr(obj, name)
    except Exception:
        return False


def _get(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


class Handlers(object):
    """Every public method `cmd_<name>(**args)` is a protocol command."""

    def __init__(self, song, application=None, log=None):
        self.song = song
        self.app = application
        self.log = log or (lambda *a: None)

    # ------------------------------------------------------------------ dispatch
    def commands(self):
        return sorted(n[4:] for n in dir(self) if n.startswith("cmd_"))

    def handle(self, cmd, args):
        fn = getattr(self, "cmd_" + str(cmd), None)
        if fn is None:
            raise CommandError("unknown command '%s'. Available: %s" % (cmd, ", ".join(self.commands())))
        if kind_of(cmd, args) != "read" and read_only():
            # Enforced here, inside Live, so that it holds for anything that talks to this bridge.
            raise CommandError("Read-only mode is on: '%s' was not carried out. Looking and measuring still work. "
                               "Switch it off with: python -m track2ableton.doctor --read-only off" % cmd)
        return fn(**(args or {}))

    # ------------------------------------------------------------------ lookup helpers
    def _all_tracks(self):
        return list(self.song.tracks)

    def _track(self, track):
        """track: index (int), 'master', 'return:<i>' / 'A'..'L', or exact/partial track name."""
        if track is None:
            sel = _get(self.song.view, "selected_track")
            if sel is None:
                raise CommandError("no track given and none selected")
            return sel
        if isinstance(track, int):
            tracks = self._all_tracks()
            if not 0 <= track < len(tracks):
                raise CommandError("track index %d out of range (0..%d)" % (track, len(tracks) - 1))
            return tracks[track]
        s = str(track).strip()
        if s.lower() in ("master", "main"):
            return self.song.master_track
        rets = list(self.song.return_tracks)
        m = re.match(r"^return[:\s]*(\d+)$", s.lower())
        if m:
            i = int(m.group(1))
            if i >= len(rets):
                raise CommandError("return track %d does not exist" % i)
            return rets[i]
        if len(s) == 1 and s.isalpha() and ord(s.upper()) - 65 < len(rets):
            return rets[ord(s.upper()) - 65]
        if s.isdigit():
            return self._track(int(s))
        cands = self._all_tracks() + rets
        for t in cands:
            if t.name == s:
                return t
        low = [t for t in cands if s.lower() in t.name.lower()]
        if len(low) == 1:
            return low[0]
        if len(low) > 1:
            raise CommandError("track name '%s' is ambiguous: %s" % (s, [t.name for t in low]))
        raise CommandError("no track named '%s'" % s)

    def _track_index(self, t):
        tracks = self._all_tracks()
        for i, x in enumerate(tracks):
            if x == t:
                return i
        return None

    def _slot(self, track, slot):
        t = self._track(track)
        slots = list(_get(t, "clip_slots", []) or [])
        if not 0 <= int(slot) < len(slots):
            raise CommandError("clip slot %s out of range (track has %d)" % (slot, len(slots)))
        return t, slots[int(slot)]

    def _clip(self, track, slot=None, arrangement_index=None):
        t = self._track(track)
        if arrangement_index is not None:
            clips = list(_get(t, "arrangement_clips", []) or [])
            if not 0 <= int(arrangement_index) < len(clips):
                raise CommandError("arrangement clip %s out of range (%d clips)" % (arrangement_index, len(clips)))
            return clips[int(arrangement_index)]
        _, s = self._slot(track, slot)
        if not s.has_clip:
            raise CommandError("slot %s on '%s' is empty" % (slot, t.name))
        return s.clip

    def _device(self, track, device, chain_path=None):
        t = self._track(track)
        devs = list(t.devices)
        for step in (chain_path or []):  # [[device_index, chain_index], ...] to reach nested rack devices
            d = devs[int(step[0])]
            devs = list(d.chains[int(step[1])].devices)
        if isinstance(device, int) or str(device).isdigit():
            i = int(device)
            if not 0 <= i < len(devs):
                raise CommandError("device %d out of range (%d devices)" % (i, len(devs)))
            return devs[i]
        for d in devs:
            if d.name == device or _get(d, "class_name") == device:
                return d
        low = [d for d in devs if str(device).lower() in d.name.lower()]
        if low:
            return low[0]
        raise CommandError("no device '%s' on '%s'" % (device, t.name))

    def _param(self, dev, parameter):
        ps = list(dev.parameters)
        if isinstance(parameter, int) or str(parameter).isdigit():
            return ps[int(parameter)]
        for p in ps:
            if p.name == parameter:
                return p
        low = [p for p in ps if str(parameter).lower() in p.name.lower()]
        if len(low) == 1:
            return low[0]
        if len(low) > 1:
            exact_word = [p for p in low if p.name.lower().split()[-1] == str(parameter).lower()]
            if len(exact_word) == 1:
                return exact_word[0]
            raise CommandError("parameter '%s' is ambiguous on %s: %s" % (parameter, dev.name, [p.name for p in low]))
        raise CommandError("no parameter '%s' on %s. Parameters: %s" % (parameter, dev.name, [p.name for p in ps]))

    # ------------------------------------------------------------------ serialisers
    def _param_info(self, p, i=None):
        d = {"name": p.name, "value": p.value, "min": p.min, "max": p.max,
             "is_quantized": bool(_get(p, "is_quantized", False)), "display": self._display(p, p.value)}
        if i is not None:
            d["index"] = i
        items = _get(p, "value_items")
        if items:
            d["value_items"] = [str(x) for x in items]
        return d

    @staticmethod
    def _display(p, v):
        try:
            return str(p.str_for_value(v))
        except Exception:
            return str(v)

    def _device_info(self, d, i=None, deep=False):
        info = {"name": d.name, "class_name": _get(d, "class_name"), "is_active": bool(_get(d, "is_active", True))}
        if i is not None:
            info["index"] = i
        if _get(d, "can_have_chains", False):
            info["chains"] = [{"name": c.name, "devices": [self._device_info(x, j) for j, x in enumerate(c.devices)]}
                              for c in d.chains]
        if deep:
            info["parameters"] = [self._param_info(p, j) for j, p in enumerate(d.parameters)]
        sample = _get(d, "sample")
        if sample is not None:
            info["sample"] = self._sample_info(sample)
        return info

    @staticmethod
    def _sample_info(s):
        out = {}
        for k in ("file_path", "length", "sample_rate", "start_marker", "end_marker", "gain", "warping"):
            v = _get(s, k)
            if v is not None:
                out[k] = v if isinstance(v, (int, float, str, bool)) else str(v)
        return out

    def _clip_info(self, c):
        out = {"name": c.name, "length": c.length, "is_midi": bool(_get(c, "is_midi_clip", False)),
               "is_audio": bool(_get(c, "is_audio_clip", False)), "looping": bool(_get(c, "looping", False))}
        for k in ("start_time", "loop_start", "loop_end", "start_marker", "end_marker", "color_index", "is_playing",
                  "warping", "warp_mode", "gain", "pitch_coarse", "pitch_fine", "file_path", "sample_length", "sample_rate"):
            v = _get(c, k)
            if v is not None and isinstance(v, (int, float, str, bool)):
                out[k] = v
        return out

    def _track_info(self, t, i=None, deep=False):
        mix = t.mixer_device
        out = {"name": t.name, "mute": bool(_get(t, "mute", False)), "solo": bool(_get(t, "solo", False)),
               "arm": bool(_get(t, "arm", False)) if _get(t, "can_be_armed", False) else None,
               "midi": bool(_get(t, "has_midi_input", False)), "audio": bool(_get(t, "has_audio_input", False)),
               "volume": self._display(mix.volume, mix.volume.value), "pan": self._display(mix.panning, mix.panning.value),
               "sends": [self._display(s, s.value) for s in _get(mix, "sends", [])],
               "devices": [d.name for d in t.devices], "color_index": _get(t, "color_index")}
        if i is not None:
            out["index"] = i
        if deep:
            out["devices"] = [self._device_info(d, j) for j, d in enumerate(t.devices)]
            out["clip_slots"] = [self._clip_info(s.clip) if s.has_clip else None for s in _get(t, "clip_slots", [])]
            out["arrangement_clips"] = [self._clip_info(c) for c in (_get(t, "arrangement_clips", []) or [])]
            out["routing"] = self.cmd_get_routing(t.name) if _has(t, "output_routing_type") else None
        return out

    # ------------------------------------------------------------------ parameter setting by display value
    def _set_param(self, p, value=None, display_value=None, normalized=None):
        if normalized is not None:
            v = p.min + float(normalized) * (p.max - p.min)
        elif display_value is not None:
            v = self._solve_display(p, display_value)
        else:
            v = value
            if isinstance(v, str):
                items = [str(x) for x in (_get(p, "value_items") or [])]
                if v in items:
                    v = items.index(v)
                else:
                    raise CommandError("value '%s' not in %s" % (v, items))
        v = max(p.min, min(p.max, float(v)))
        if _get(p, "is_quantized", False):
            v = round(v)
        p.value = v
        return {"name": p.name, "value": p.value, "display": self._display(p, p.value)}

    def _solve_display(self, p, target):
        """Find the raw value whose displayed text (e.g. '-6.0 dB', '1.20 kHz') equals `target`, by
        bisection on Live's own str_for_value(). Assumes the display is monotonic in the raw value."""
        target = float(target)
        lo, hi = float(p.min), float(p.max)
        f_lo, f_hi = _num(self._display(p, lo)), _num(self._display(p, hi))
        if f_lo is None or f_hi is None:
            raise CommandError("parameter '%s' has no numeric display; use value=" % p.name)
        increasing = (f_hi if f_hi != float("-inf") else -1e9) >= (f_lo if f_lo != float("-inf") else -1e9)
        for _ in range(60):
            mid = (lo + hi) / 2.0
            f = _num(self._display(p, mid))
            if f is None:
                break
            if f == float("-inf"):
                f = -1e9
            if (f < target) == increasing:
                lo = mid
            else:
                hi = mid
        # invariant: display(lo) < target <= display(hi) when increasing (mirrored when decreasing);
        # return the side whose displayed value has reached the target.
        return hi if increasing else lo

    # ================================================================== SESSION / TRANSPORT
    def cmd_ping(self):
        return {"pong": True, "bridge": "T2A_Bridge", "version": VERSION, "commands": len(self.commands()), "read_only": read_only()}

    def cmd_list_commands(self):
        return self.commands()

    def cmd_get_session(self):
        s = self.song
        out = {"tempo": s.tempo, "is_playing": s.is_playing, "current_song_time": s.current_song_time,
               "signature": "%d/%d" % (s.signature_numerator, s.signature_denominator),
               "loop": {"on": s.loop, "start": s.loop_start, "length": s.loop_length},
               "metronome": s.metronome, "record_mode": _get(s, "record_mode"), "session_record": _get(s, "session_record"),
               "tracks": [self._track_info(t, i) for i, t in enumerate(s.tracks)],
               "returns": [self._track_info(t, i) for i, t in enumerate(s.return_tracks)],
               "master": self._track_info(s.master_track),
               "scenes": [{"index": i, "name": sc.name} for i, sc in enumerate(s.scenes)],
               "cue_points": [{"name": c.name, "time": c.time} for c in (_get(s, "cue_points", []) or [])]}
        for k in ("root_note", "scale_name", "song_length"):
            v = _get(s, k)
            if v is not None:
                out[k] = v
        sel = _get(s.view, "selected_track")
        out["selected_track"] = sel.name if sel is not None else None
        return out

    def cmd_transport(self, action):
        s = self.song
        acts = {"play": s.start_playing, "stop": s.stop_playing, "continue": s.continue_playing,
                "stop_all_clips": s.stop_all_clips}
        if action not in acts:
            raise CommandError("action must be one of %s" % sorted(acts))
        acts[action]()
        return {"is_playing": s.is_playing}

    def cmd_set_song(self, tempo=None, time=None, loop=None, loop_start=None, loop_length=None, metronome=None,
                     record_mode=None, session_record=None, numerator=None, denominator=None, root_note=None, scale_name=None,
                     overdub=None):
        s = self.song
        changed = {}
        for name, val, attr in (("tempo", tempo, "tempo"), ("time", time, "current_song_time"), ("loop", loop, "loop"),
                                ("loop_start", loop_start, "loop_start"), ("loop_length", loop_length, "loop_length"),
                                ("metronome", metronome, "metronome"), ("record_mode", record_mode, "record_mode"),
                                ("session_record", session_record, "session_record"), ("numerator", numerator, "signature_numerator"),
                                ("denominator", denominator, "signature_denominator"), ("root_note", root_note, "root_note"),
                                ("scale_name", scale_name, "scale_name"), ("overdub", overdub, "arrangement_overdub")):
            if val is None:
                continue
            if not _has(s, attr):
                raise CommandError("this Live version has no Song.%s" % attr)
            setattr(s, attr, val)
            changed[name] = _get(s, attr)
        return changed

    def cmd_undo(self):
        self.song.undo()
        return True

    def cmd_redo(self):
        self.song.redo()
        return True

    def cmd_cue(self, action="list", name=None):
        s = self.song
        if action == "add":
            s.set_or_delete_cue()
        elif action == "next":
            s.jump_to_next_cue()
        elif action == "prev":
            s.jump_to_prev_cue()
        elif action == "jump":
            for c in s.cue_points:
                if c.name == name:
                    c.jump()
                    break
            else:
                raise CommandError("no locator named '%s'" % name)
        return [{"name": c.name, "time": c.time} for c in s.cue_points]

    # ================================================================== TRACKS
    def cmd_list_tracks(self):
        return {"tracks": [self._track_info(t, i) for i, t in enumerate(self.song.tracks)],
                "returns": [self._track_info(t, i) for i, t in enumerate(self.song.return_tracks)]}

    def cmd_get_track(self, track):
        t = self._track(track)
        return self._track_info(t, self._track_index(t), deep=True)

    def cmd_create_track(self, kind="midi", index=-1, name=None):
        s = self.song
        if kind == "midi":
            s.create_midi_track(int(index))
        elif kind == "audio":
            s.create_audio_track(int(index))
        elif kind == "return":
            s.create_return_track()
            t = list(s.return_tracks)[-1]
            if name:
                t.name = name
            return {"name": t.name, "return_index": len(s.return_tracks) - 1}
        else:
            raise CommandError("kind must be midi, audio or return")
        tracks = list(s.tracks)
        i = len(tracks) - 1 if int(index) < 0 else int(index)
        if name:
            tracks[i].name = name
        return {"index": i, "name": tracks[i].name}

    def cmd_delete_track(self, track):
        t = self._track(track)
        i = self._track_index(t)
        if i is not None:
            self.song.delete_track(i)
        else:
            rets = list(self.song.return_tracks)
            if t in rets:
                self.song.delete_return_track(rets.index(t))
            else:
                raise CommandError("cannot delete the master track")
        return True

    def cmd_duplicate_track(self, track):
        i = self._track_index(self._track(track))
        if i is None:
            raise CommandError("only regular tracks can be duplicated")
        self.song.duplicate_track(i)
        return {"index": i + 1}

    def cmd_set_track(self, track, name=None, mute=None, solo=None, arm=None, color_index=None,
                      volume_db=None, volume=None, pan=None, select=None, fold=None):
        t = self._track(track)
        if name is not None:
            t.name = name
        if mute is not None:
            t.mute = bool(mute)
        if solo is not None:
            t.solo = bool(solo)
        if arm is not None:
            if not _get(t, "can_be_armed", False):
                raise CommandError("'%s' cannot be armed" % t.name)
            t.arm = bool(arm)
        if color_index is not None:
            t.color_index = int(color_index)
        if volume_db is not None:
            self._set_param(t.mixer_device.volume, display_value=volume_db)
        elif volume is not None:
            self._set_param(t.mixer_device.volume, value=volume)
        if pan is not None:  # -1 (L) .. +1 (R) raw
            self._set_param(t.mixer_device.panning, value=pan)
        if fold is not None and _get(t, "is_foldable", False):
            t.fold_state = 1 if fold else 0
        if select:
            self.song.view.selected_track = t
        return self._track_info(t, self._track_index(t))

    def cmd_set_send(self, track, send, level_db=None, value=None):
        t = self._track(track)
        sends = list(t.mixer_device.sends)
        if isinstance(send, str) and not send.isdigit():
            i = ord(send.strip().upper()[0]) - 65
        else:
            i = int(send)
        if not 0 <= i < len(sends):
            raise CommandError("send %s out of range (%d sends)" % (send, len(sends)))
        if level_db is not None:
            return self._set_param(sends[i], display_value=level_db)
        return self._set_param(sends[i], value=value)

    # ------------------------------------------------------------------ routing
    def cmd_get_routing(self, track):
        t = self._track(track)

        def names(attr):
            return [x.display_name for x in (_get(t, attr, []) or [])]

        def cur(attr):
            x = _get(t, attr)
            return x.display_name if x is not None else None

        if not _has(t, "available_output_routing_types"):
            raise CommandError("routing API not available in this Live version")
        return {"input_type": cur("input_routing_type"), "input_channel": cur("input_routing_channel"),
                "output_type": cur("output_routing_type"), "output_channel": cur("output_routing_channel"),
                "available_input_types": names("available_input_routing_types"),
                "available_input_channels": names("available_input_routing_channels"),
                "available_output_types": names("available_output_routing_types"),
                "available_output_channels": names("available_output_routing_channels"),
                "monitoring": _get(t, "current_monitoring_state")}

    def cmd_set_routing(self, track, input_type=None, input_channel=None, output_type=None, output_channel=None, monitoring=None):
        t = self._track(track)

        def pick(avail_attr, wanted):
            opts = list(_get(t, avail_attr, []) or [])
            for o in opts:
                if o.display_name == wanted:
                    return o
            low = [o for o in opts if wanted.lower() in o.display_name.lower()]
            if len(low) == 1:
                return low[0]
            raise CommandError("'%s' not in %s" % (wanted, [o.display_name for o in opts]))

        if input_type is not None:
            t.input_routing_type = pick("available_input_routing_types", input_type)
        if input_channel is not None:
            t.input_routing_channel = pick("available_input_routing_channels", input_channel)
        if output_type is not None:
            t.output_routing_type = pick("available_output_routing_types", output_type)
        if output_channel is not None:
            t.output_routing_channel = pick("available_output_routing_channels", output_channel)
        if monitoring is not None:  # 0 In, 1 Auto, 2 Off
            t.current_monitoring_state = {"in": 0, "auto": 1, "off": 2}.get(str(monitoring).lower(), monitoring)
        return self.cmd_get_routing(t.name)

    # ================================================================== CLIPS & NOTES
    def cmd_create_clip(self, track, slot, length=4.0, name=None):
        t, s = self._slot(track, slot)
        if s.has_clip:
            raise CommandError("slot %s on '%s' already has a clip" % (slot, t.name))
        s.create_clip(float(length))
        if name:
            s.clip.name = name
        return self._clip_info(s.clip)

    def cmd_create_audio_clip(self, track, file_path, slot=None, position=None):
        t = self._track(track)
        if slot is not None:
            _, s = self._slot(track, slot)
            if not _has(s, "create_audio_clip"):
                raise CommandError("ClipSlot.create_audio_clip is not available in this Live version")
            s.create_audio_clip(file_path)
            return self._clip_info(s.clip)
        if not _has(t, "create_audio_clip"):
            raise CommandError("Track.create_audio_clip is not available in this Live version")
        t.create_audio_clip(file_path, float(position or 0.0))
        return {"arrangement_clips": len(t.arrangement_clips)}

    def cmd_create_arrangement_midi_clip(self, track, start, length):
        t = self._track(track)
        if not _has(t, "create_midi_clip"):
            raise CommandError("Track.create_midi_clip is not available in this Live version")
        t.create_midi_clip(float(start), float(length))
        return {"arrangement_clips": len(t.arrangement_clips)}

    def cmd_delete_clip(self, track, slot):
        _, s = self._slot(track, slot)
        s.delete_clip()
        return True

    def cmd_clip_action(self, track, slot, action, target_track=None, target_slot=None, time=None):
        t, s = self._slot(track, slot)
        if action == "fire":
            s.fire()
        elif action == "stop":
            s.stop()
        elif action == "duplicate_to":
            _, dst = self._slot(target_track if target_track is not None else track, target_slot)
            s.duplicate_clip_to(dst)
        elif action == "to_arrangement":
            if not s.has_clip:
                raise CommandError("slot is empty")
            if not _has(t, "duplicate_clip_to_arrangement"):
                raise CommandError("Track.duplicate_clip_to_arrangement is not available in this Live version")
            t.duplicate_clip_to_arrangement(s.clip, float(time or 0.0))
        elif action == "duplicate_loop":
            s.clip.duplicate_loop()
        else:
            raise CommandError("action must be fire, stop, duplicate_to, to_arrangement or duplicate_loop")
        return True

    def cmd_set_clip(self, track, slot=None, arrangement_index=None, name=None, looping=None, loop_start=None, loop_end=None,
                     start_marker=None, end_marker=None, color_index=None, gain=None, pitch_coarse=None, pitch_fine=None,
                     warping=None, warp_mode=None, muted=None):
        c = self._clip(track, slot, arrangement_index)
        for attr, val in (("name", name), ("looping", looping), ("loop_end", loop_end), ("loop_start", loop_start),
                          ("end_marker", end_marker), ("start_marker", start_marker), ("color_index", color_index),
                          ("gain", gain), ("pitch_coarse", pitch_coarse), ("pitch_fine", pitch_fine),
                          ("warping", warping), ("warp_mode", warp_mode), ("muted", muted)):
            if val is not None:
                if not _has(c, attr):
                    raise CommandError("clip has no '%s' (audio-only or not in this Live version)" % attr)
                setattr(c, attr, val)
        return self._clip_info(c)

    def cmd_get_notes(self, track, slot=None, arrangement_index=None, from_time=0.0, time_span=None, from_pitch=0, pitch_span=128):
        c = self._clip(track, slot, arrangement_index)
        if not _get(c, "is_midi_clip", False):
            raise CommandError("not a MIDI clip")
        span = float(time_span) if time_span is not None else max(float(c.length), float(_get(c, "loop_end", 0) or 0)) + 1
        if _has(c, "get_notes_extended"):
            notes = c.get_notes_extended(from_pitch=int(from_pitch), pitch_span=int(pitch_span), from_time=float(from_time), time_span=span)
            return [{"pitch": n.pitch, "start": n.start_time, "duration": n.duration, "velocity": n.velocity,
                     "mute": bool(_get(n, "mute", False)), "note_id": _get(n, "note_id")} for n in notes]
        notes = c.get_notes(float(from_time), int(from_pitch), span, int(pitch_span))  # legacy (Live <= 10)
        return [{"pitch": n[0], "start": n[1], "duration": n[2], "velocity": n[3], "mute": bool(n[4])} for n in notes]

    def cmd_add_notes(self, track, notes, slot=None, arrangement_index=None, replace=False):
        """notes: [{pitch, start, duration, velocity?, mute?}] in beats."""
        c = self._clip(track, slot, arrangement_index)
        if not _get(c, "is_midi_clip", False):
            raise CommandError("not a MIDI clip")
        if replace:
            self.cmd_clear_notes(track, slot, arrangement_index)
        clean = [(int(n["pitch"]), float(n["start"]), float(n.get("duration", 0.25)), float(n.get("velocity", 100)),
                  bool(n.get("mute", False))) for n in notes]
        if _has(c, "add_new_notes") and Live is not None and _has(Live.Clip, "MidiNoteSpecification"):
            specs = tuple(Live.Clip.MidiNoteSpecification(pitch=p, start_time=s, duration=d, velocity=v, mute=m)
                          for p, s, d, v, m in clean)
            c.add_new_notes(specs)
        elif _has(c, "add_new_notes") and Live is None:  # test double
            c.add_new_notes(clean)
        else:
            c.set_notes(tuple(clean))  # legacy API
        return {"added": len(clean)}

    def cmd_clear_notes(self, track, slot=None, arrangement_index=None):
        c = self._clip(track, slot, arrangement_index)
        span = max(float(c.length), float(_get(c, "loop_end", 0) or 0)) + 1000
        if _has(c, "remove_notes_extended"):
            c.remove_notes_extended(from_pitch=0, pitch_span=128, from_time=-1000.0, time_span=span + 1000)
        else:
            c.remove_notes(-1000.0, 0, span + 1000, 128)
        return True

    def cmd_quantize_clip(self, track, slot=None, arrangement_index=None, grid="1/16", amount=1.0):
        # Values of Live.Song.RecordingQuantization (names verified against the Live 12.4 API dump).
        names = {"1/4": "rec_q_quarter", "1/8": "rec_q_eight", "1/8T": "rec_q_eight_triplet",
                 "1/8+T": "rec_q_eight_eight_triplet", "1/16": "rec_q_sixtenth", "1/16T": "rec_q_sixtenth_triplet",
                 "1/16+T": "rec_q_sixtenth_sixtenth_triplet", "1/32": "rec_q_thirtysecond"}
        if grid not in names:
            raise CommandError("grid must be one of %s" % sorted(names))
        c = self._clip(track, slot, arrangement_index)
        q = getattr(Live.Song.RecordingQuantization, names[grid]) if Live is not None else names[grid]
        c.quantize(q, float(amount))
        return True

    # ================================================================== SCENES
    def cmd_scene(self, action="list", index=None, name=None, tempo=None, color_index=None):
        s = self.song
        if action == "create":
            s.create_scene(int(index if index is not None else -1))
        elif action == "delete":
            s.delete_scene(int(index))
        elif action == "duplicate":
            s.duplicate_scene(int(index))
        elif action == "fire":
            s.scenes[int(index)].fire()
        elif action == "capture":
            s.capture_and_insert_scene()
        elif action == "set":
            sc = s.scenes[int(index)]
            if name is not None:
                sc.name = name
            if tempo is not None:
                sc.tempo = float(tempo)
            if color_index is not None:
                sc.color_index = int(color_index)
        elif action != "list":
            raise CommandError("action must be list, create, delete, duplicate, fire, capture or set")
        return [{"index": i, "name": sc.name, "tempo": _get(sc, "tempo"), "is_empty": _get(sc, "is_empty")}
                for i, sc in enumerate(s.scenes)]

    # ================================================================== DEVICES
    def cmd_get_device(self, track, device, chain_path=None):
        return self._device_info(self._device(track, device, chain_path), deep=True)

    def cmd_set_parameter(self, track, device, parameter, value=None, display_value=None, normalized=None, chain_path=None):
        d = self._device(track, device, chain_path)
        return self._set_param(self._param(d, parameter), value, display_value, normalized)

    def cmd_set_parameters(self, track, device, values, chain_path=None):
        """values: {parameter_name: number_or_item} or [{parameter, value|display_value|normalized}]"""
        d = self._device(track, device, chain_path)
        out = []
        items = values.items() if isinstance(values, dict) else [(v["parameter"], v) for v in values]
        for name, v in items:
            if isinstance(v, dict):
                out.append(self._set_param(self._param(d, name), v.get("value"), v.get("display_value"), v.get("normalized")))
            else:
                out.append(self._set_param(self._param(d, name), value=v))
        return out

    def cmd_device_action(self, track, device, action, chain_path=None):
        t = self._track(track)
        d = self._device(track, device, chain_path)
        if action in ("on", "off"):
            on = self._param(d, "Device On")
            on.value = 1 if action == "on" else 0
        elif action == "delete":
            devs = list(t.devices)
            t.delete_device(devs.index(d))
        elif action == "select":
            self.song.view.select_device(d)
        else:
            raise CommandError("action must be on, off, delete or select")
        return [x.name for x in t.devices]

    def cmd_insert_device(self, track, name, index=None):
        """Insert a native Live device by name (Live 12.x Track.insert_device); falls back to the browser."""
        t = self._track(track)
        if _has(t, "insert_device"):  # Track.insert_device(DeviceName, DeviceIndex=-1), Live 12.3+
            try:
                t.insert_device(name, -1 if index is None else int(index))
                return [x.name for x in t.devices]
            except Exception as exc:
                self.log("insert_device failed (%s); trying the browser" % exc)
        return self.cmd_load_from_browser(track=track, query=name, category=None)

    def cmd_set_sidechain(self, track, device, source=None, channel=None):
        """Sidechain input of a Compressor (CompressorDevice routing, Live 12.4 API). source = display name of a
        routing type (usually a track name, e.g. 'Kick'); no source -> list the options."""
        d = self._device(track, device)
        if not _has(d, "available_input_routing_types"):
            raise CommandError("'%s' has no sidechain routing in this Live version's API (needs a Compressor in Live 12.4+); "
                               "set Audio From by hand" % d.name)

        def opts(attr):
            return list(_get(d, attr, []) or [])

        if source is None:
            return {"types": [o.display_name for o in opts("available_input_routing_types")],
                    "channels": [o.display_name for o in opts("available_input_routing_channels")],
                    "current": _get(_get(d, "input_routing_type"), "display_name")}
        for attr, cur, wanted in (("available_input_routing_types", "input_routing_type", source),
                                  ("available_input_routing_channels", "input_routing_channel", channel)):
            if wanted is None:
                continue
            o = opts(attr)
            hit = [x for x in o if x.display_name == wanted] or [x for x in o if str(wanted).lower() in x.display_name.lower()]
            if not hit:
                raise CommandError("'%s' not in %s" % (wanted, [x.display_name for x in o]))
            setattr(d, cur, hit[0])
        # switch the sidechain section on if a matching parameter exists (name differs by device version)
        enabled = None
        for p in d.parameters:
            if p.name.lower() in ("s/c on", "sidechain on", "sidechain"):
                p.value = p.max
                enabled = p.name
        return {"source": _get(_get(d, "input_routing_type"), "display_name"), "enabled_parameter": enabled,
                "note": None if enabled else "enable the sidechain switch on the device if it is not on"}

    # ================================================================== BROWSER
    def _browser(self):
        if self.app is None:
            raise CommandError("browser not available")
        return self.app.browser

    def _roots(self):
        b = self._browser()
        out = []
        for attr in ("sounds", "drums", "instruments", "audio_effects", "midi_effects", "max_for_live", "plugins",
                     "clips", "samples", "packs", "user_library", "current_project"):
            item = _get(b, attr)
            if item is not None:
                out.append((attr, item))
        return out

    @staticmethod
    def _item_info(it, path):
        return {"name": it.name, "path": path, "is_loadable": bool(_get(it, "is_loadable", False)),
                "is_folder": bool(_get(it, "is_folder", False)), "uri": _get(it, "uri")}

    def _resolve_path(self, path):
        parts = [p for p in str(path).split("/") if p]
        roots = dict(self._roots())
        if not parts or parts[0] not in roots:
            raise CommandError("path must start with one of %s" % sorted(roots))
        it = roots[parts[0]]
        for p in parts[1:]:
            nxt = [c for c in it.children if c.name == p]
            if not nxt:
                raise CommandError("'%s' not found under '%s'" % (p, it.name))
            it = nxt[0]
        return it

    def cmd_browse(self, path=None, limit=200):
        if not path:
            return [{"name": n, "path": n} for n, _ in self._roots()]
        it = self._resolve_path(path)
        return [self._item_info(c, path.rstrip("/") + "/" + c.name) for c in list(it.children)[:int(limit)]]

    def cmd_search_browser(self, query, category=None, limit=30, max_nodes=20000):
        q = str(query).lower()
        roots = [(n, i) for n, i in self._roots() if category is None or n == category]
        hits, visited = [], 0
        stack = [(it, name) for name, it in roots][::-1]
        exact = []
        while stack and len(hits) < int(limit) and visited < int(max_nodes):
            it, path = stack.pop()
            visited += 1
            nm = it.name.lower()
            if q in nm and (_get(it, "is_loadable", False) or _get(it, "is_device", False)):
                info = self._item_info(it, path)
                (exact if nm.split(".")[0] == q else hits).append(info)
            kids = list(_get(it, "children", []) or [])
            stack.extend((c, path + "/" + c.name) for c in reversed(kids))
        return {"results": (exact + hits)[:int(limit)], "visited": visited, "truncated": visited >= int(max_nodes)}

    def cmd_load_from_browser(self, track, path=None, query=None, category=None):
        """Loads onto `track` (selects it first). Device -> appended; sample -> Simpler / clip per Live's rules."""
        t = self._track(track)
        if path:
            it = self._resolve_path(path)
        elif query:
            res = self.cmd_search_browser(query, category, limit=1)["results"]
            if not res:
                raise CommandError("nothing loadable matches '%s'" % query)
            it = self._resolve_path(res[0]["path"])
        else:
            raise CommandError("give path= or query=")
        if not _get(it, "is_loadable", False):
            raise CommandError("'%s' is not loadable" % it.name)
        self.song.view.selected_track = t
        self._browser().load_item(it)
        return {"loaded": it.name, "track": t.name, "devices": [d.name for d in t.devices]}

    # ================================================================== SAMPLES / FILES FOR ANALYSIS
    def cmd_get_audio_files(self, track=None):
        """Source file paths of audio clips (session + arrangement) and Simpler samples, for analysis."""
        tracks = [self._track(track)] if track is not None else list(self.song.tracks)
        out = []
        for t in tracks:
            for i, s in enumerate(_get(t, "clip_slots", []) or []):
                if s.has_clip and _get(s.clip, "is_audio_clip", False):
                    out.append({"track": t.name, "slot": i, "clip": s.clip.name, "file_path": _get(s.clip, "file_path")})
            for i, c in enumerate(_get(t, "arrangement_clips", []) or []):
                if _get(c, "is_audio_clip", False):
                    out.append({"track": t.name, "arrangement_index": i, "clip": c.name, "start_time": _get(c, "start_time"),
                                "file_path": _get(c, "file_path")})
            for d in t.devices:
                smp = _get(d, "sample")
                if smp is not None and _get(smp, "file_path"):
                    out.append({"track": t.name, "device": d.name, "file_path": smp.file_path})
        return out

    def cmd_get_meters(self, track=None):
        tracks = [self._track(track)] if track is not None else list(self.song.tracks) + [self.song.master_track]
        return [{"track": t.name, "left": _get(t, "output_meter_left"), "right": _get(t, "output_meter_right")} for t in tracks]
