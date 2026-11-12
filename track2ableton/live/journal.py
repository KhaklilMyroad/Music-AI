"""A record of every change sent to Live: when, what, with which arguments, and how it ended.

One JSON line per change, in a file per day, in ~/.track2ableton/journal (T2A_JOURNAL_DIR to move it, T2A_JOURNAL=0
to turn it off). Rows hold what was sent: track and clip names and file paths among them. Files are private to the
user where the system allows it, and files older than KEEP_DAYS are removed.

`ok` is true or false when Live answered, and null when no answer came in time: the change may still have been
carried out, and the row says so.
"""
from __future__ import annotations

import datetime
import json
import os
import time

KEEP_DAYS = 60
MAX_ROW = 4000                                   # characters of arguments kept per row
SESSION = f"{os.getpid()}-{int(time.time())}"    # one per process: "what did this session change"


def folder() -> str | None:
    if os.environ.get("T2A_JOURNAL", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    return os.path.expanduser(os.environ.get("T2A_JOURNAL_DIR") or os.path.join("~", ".track2ableton", "journal"))


def brief(v, depth: int = 0):
    """Arguments short enough to read back: a long list becomes its length, a long text keeps its two ends."""
    if isinstance(v, dict):
        return {str(k): brief(x, depth + 1) for k, x in list(v.items())[:40]} if depth < 4 else "<...>"
    if isinstance(v, (list, tuple)):
        return f"<{len(v)} items>" if len(v) > 8 or depth >= 4 else [brief(x, depth + 1) for x in v]
    if isinstance(v, str) and len(v) > 400:
        return v[:190] + " ... " + v[-190:]      # a long path keeps its file name
    return v


def record(cmd: str, args: dict, ok: bool | None, error: str | None = None) -> None:
    d = folder()
    if d is None:
        return
    try:                                          # the journal must never be the reason a command fails
        os.makedirs(d, mode=0o700, exist_ok=True)
        now = datetime.datetime.now()
        shown = brief(args)
        text = json.dumps(shown, ensure_ascii=False, default=str)
        if len(text) > MAX_ROW:
            shown = {"shortened": text[:MAX_ROW] + " ..."}
        row = {"time": now.isoformat(timespec="seconds"), "session": SESSION, "cmd": cmd, "args": shown, "ok": ok}
        if ok is None:
            row["outcome"] = "unknown: no answer in time, the change may still have been carried out"
        if error:
            row["error"] = str(error)[:300]
        path = os.path.join(d, f"journal-{now:%Y%m%d}.jsonl")
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        if new:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            limit = f"journal-{now - datetime.timedelta(days=KEEP_DAYS):%Y%m%d}.jsonl"
            for old in os.listdir(d):
                if old.startswith("journal-") and old.endswith(".jsonl") and old < limit:
                    os.remove(os.path.join(d, old))
    except Exception:
        pass


def read(last: int = 30, this_session: bool = True, days: int = 3) -> dict:
    """The newest `last` rows of this session (or of every session) from the last `days` days."""
    d = folder()
    if d is None:
        return {"journal": "off (T2A_JOURNAL=0)", "entries": []}
    out = {"folder": d, "session": SESSION, "entries": [], "unreadable_lines": 0}
    if not os.path.isdir(d):
        out["note"] = ("Nothing has been recorded: the journal folder does not exist. If changes were made in this session, "
                       "the folder could not be created and they were NOT recorded.")
        return out
    if not os.access(d, os.W_OK):
        out["note"] = "The journal folder is not writable: changes are NOT being recorded."
    since = f"journal-{datetime.datetime.now() - datetime.timedelta(days=max(1, days) - 1):%Y%m%d}.jsonl"
    rows = []
    for f in sorted(x for x in os.listdir(d) if x.startswith("journal-") and x.endswith(".jsonl") and x >= since):
        path = os.path.join(d, f)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        out["unreadable_lines"] += 1
        except OSError:
            out["unreadable_lines"] += 1
    if this_session:
        rows = [r for r in rows if r.get("session") == SESSION]
    out["total"] = len(rows)
    out["entries"] = rows[-int(last):] if int(last) > 0 else []
    return out
