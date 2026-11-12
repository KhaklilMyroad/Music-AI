"""Client for the T2A_Bridge Remote Script running inside Ableton Live.

Protocol: one JSON object per line over TCP (default 127.0.0.1:9877).
  request : {"id": 1, "cmd": "set_tempo", "args": {"bpm": 124}}
  response: {"id": 1, "ok": true, "result": ...}   or   {"id": 1, "ok": false, "error": "..."}
"""
from __future__ import annotations

import itertools
import json
import os
import socket
import threading

from . import guard, journal


class LiveError(RuntimeError):
    pass


class LiveTimeout(LiveError):
    """No answer in time. The command was sent: Live may still carry it out."""


class LiveClient:
    def __init__(self, host: str | None = None, port: int | None = None, timeout: float = 30.0):
        """timeout must be longer than the 20 s the Remote Script waits for Live's main thread: a shorter one
        gives up on a change that Live then makes."""
        self.host = host or os.environ.get("T2A_HOST", "127.0.0.1")
        try:
            self.port = int(port or os.environ.get("T2A_PORT") or 9877)
        except ValueError:
            raise LiveError(f"T2A_PORT must be a number, not {os.environ.get('T2A_PORT')!r}") from None
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def _connect(self):
        if self._sock is None:
            try:
                self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            except OSError as exc:
                raise LiveError(
                    f"Cannot reach Ableton Live at {self.host}:{self.port} ({exc}). Is Live running with the "
                    "'T2A_Bridge' control surface selected in Settings > Link, Tempo & MIDI?") from exc
            self._sock.settimeout(self.timeout)

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
                self._buf = b""

    def call(self, cmd: str, **args):
        """Send one command. Anything that changes the Live Set is refused when read-only mode is on, and is
        written to the journal otherwise, whoever the caller is."""
        kind = guard.kind_of(cmd, args)
        if kind != "read" and guard.read_only():
            raise LiveError(f"Read-only mode is on: '{cmd}' was not sent to Live. Looking and measuring still work. "
                            "Switch it off with: python -m track2ableton.doctor --read-only off")
        try:
            result = self._send(cmd, args)
        except LiveTimeout as exc:
            if kind == "write":
                journal.record(cmd, args, None, str(exc))
            raise
        except LiveError as exc:
            if kind == "write":
                journal.record(cmd, args, False, str(exc))
            raise
        if kind == "write":
            journal.record(cmd, args, True)
        return result

    def _send(self, cmd: str, args: dict):
        with self._lock:
            for attempt in (0, 1):  # one reconnect, e.g. after Live restarted
                try:
                    self._connect()
                    rid = next(self._ids)
                    self._sock.sendall((json.dumps({"id": rid, "cmd": cmd, "args": args}) + "\n").encode("utf-8"))
                    while b"\n" not in self._buf:
                        chunk = self._sock.recv(65536)
                        if not chunk:
                            raise ConnectionError("connection closed by Live")
                        self._buf += chunk
                    line, self._buf = self._buf.split(b"\n", 1)
                    resp = json.loads(line.decode("utf-8"))
                    break
                except socket.timeout as exc:
                    self.close()
                    raise LiveTimeout(f"'{cmd}': no answer from Live within {self.timeout:g} s. The command was sent and may "
                                      "still be carried out: look at the Set (live_session) before sending it again.") from exc
                except ValueError as exc:      # not our protocol: something else is listening on this port
                    self.close()
                    raise LiveError(f"'{cmd}': the answer on {self.host}:{self.port} is not from T2A_Bridge ({exc}). Another "
                                    "program may be using this port.") from exc
                except (ConnectionError, BrokenPipeError, OSError) as exc:
                    self.close()
                    if attempt == 1:
                        raise LiveError(f"'{cmd}' failed: {exc}") from exc
        if not isinstance(resp, dict):
            raise LiveError(f"'{cmd}': the answer on {self.host}:{self.port} is not from T2A_Bridge. Another program may be using this port.")
        if not resp.get("ok"):
            raise LiveError(resp.get("error", "unknown error"))
        return resp.get("result")
