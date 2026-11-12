"""What a command does to the Live Set, and whether the user has switched read-only on.

The Remote Script inside Live has the same two functions and enforces read-only itself; it cannot import this
package, so the rules are written twice and a test holds them together. Checking here as well means a command is
refused before it is sent, also against an older Remote Script.
"""
from __future__ import annotations

import os

READS = frozenset(["ping", "list_commands", "get_session", "list_tracks", "get_track", "get_routing", "get_notes",
                   "get_device", "browse", "search_browser", "get_audio_files", "get_meters"])
OFF_WORDS = ("", "0", "false", "no", "off")


def kind_of(cmd: str, args: dict | None = None) -> str:
    """'read': only looks. 'playback': starts, stops or moves playback without editing anything.
    'write': changes the Live Set."""
    args = args or {}
    action = str(args.get("action", "list")).lower()
    if cmd in READS:
        return "read"
    if cmd in ("cue", "scene") and action == "list":
        return "read"
    if cmd == "set_sidechain" and args.get("source") is None and args.get("channel") is None:
        return "read"
    if cmd == "transport" or (cmd == "cue" and action in ("next", "prev", "jump")):
        return "playback"
    return "write"


def read_only_flag() -> str:
    return os.path.join(os.path.expanduser("~"), ".track2ableton", "read_only")


def read_only() -> bool:
    """On when the flag file exists (python -m track2ableton.doctor --read-only on) or T2A_READ_ONLY is set to
    anything that is not plainly off. A value this code does not recognise means on: a safety switch fails closed."""
    v = os.environ.get("T2A_READ_ONLY")
    if v is not None and v.strip().strip("\"'").strip().lower() not in OFF_WORDS:
        return True
    return os.path.exists(read_only_flag())


def set_read_only(on: bool) -> str:
    """Create or remove the flag file. Both this package and the Remote Script inside Live look at it for every
    command, so it takes effect at once, without restarting anything."""
    flag = read_only_flag()
    if on:
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        with open(flag, "w", encoding="utf-8") as fh:
            fh.write("Read-only mode for track2ableton: nothing that changes the Live Set is carried out while this file exists.\n")
    elif os.path.exists(flag):
        os.remove(flag)
    return flag
