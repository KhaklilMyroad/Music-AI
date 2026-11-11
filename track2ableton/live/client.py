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


class LiveError(RuntimeError):
    pass


class LiveClient:
    def __init__(self, host: str | None = None, port: int | None = None, timeout: float = 15.0):
        self.host = host or os.environ.get("T2A_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("T2A_PORT", 9877))
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
                except (ConnectionError, BrokenPipeError, socket.timeout, OSError) as exc:
                    self.close()
                    if attempt == 1 or isinstance(exc, socket.timeout):
                        raise LiveError(f"'{cmd}' failed: {exc}") from exc
        if not resp.get("ok"):
            raise LiveError(resp.get("error", "unknown error"))
        return resp.get("result")
