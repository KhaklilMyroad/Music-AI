# T2A_Bridge: Ableton Live MIDI Remote Script that exposes the Live Object Model over a local
# TCP socket (127.0.0.1 only). Every command is executed on Live's main thread: the socket thread
# only queues work; the queue is drained from schedule_message callbacks and from update_display().
from __future__ import absolute_import, division, print_function

import json
import socket
import threading
import traceback

try:
    import Queue as queue  # noqa: N813  (Python 2, very old Live)
except ImportError:
    import queue

import Live
from _Framework.ControlSurface import ControlSurface

from .handlers import CommandError, Handlers

HOST = "127.0.0.1"
PORT = 9877
TIMEOUT = 20.0


class T2ABridge(ControlSurface):
    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._jobs = queue.Queue()
        self._running = True
        self._handlers = Handlers(self.song(), Live.Application.get_application(), self.log_message)
        self._server = None
        self._thread = threading.Thread(target=self._serve, name="T2A_Bridge")
        self._thread.daemon = True
        self._thread.start()

    # ---------------------------------------------------------------- main-thread side
    def _drain(self):
        while True:
            try:
                cmd, args, box = self._jobs.get_nowait()
            except queue.Empty:
                return
            try:
                box.put({"ok": True, "result": self._handlers.handle(cmd, args)})
            except CommandError as exc:
                box.put({"ok": False, "error": str(exc)})
            except Exception as exc:  # report, never crash Live
                self.log_message("T2A error in %s: %s" % (cmd, traceback.format_exc()))
                box.put({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)})

    def update_display(self):
        ControlSurface.update_display(self)
        if getattr(self, "_jobs", None) is not None:  # may be called before __init__ finished
            self._drain()

    def disconnect(self):
        self._running = False
        try:
            if self._server is not None:
                self._server.close()
        except Exception:
            pass
        ControlSurface.disconnect(self)

    def _say(self, text):
        try:                                   # called from the socket thread: must never take it down
            self.show_message(text)
        except Exception:
            self.log_message(text)

    # ---------------------------------------------------------------- socket side
    def _serve(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # On Windows SO_REUSEADDR lets a second program listen on a port that is taken, and the two then steal
            # each other's connections (another Ableton bridge uses 9877 too). Ask for the port exclusively there.
            exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
            if exclusive is not None:
                srv.setsockopt(socket.SOL_SOCKET, exclusive, 1)
            else:
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((HOST, PORT))
            srv.listen(4)
            srv.settimeout(1.0)
            self._server = srv
        except Exception as exc:
            self.log_message("T2A could not listen on %s:%d: %s" % (HOST, PORT, exc))
            self._say("T2A Bridge could NOT listen on %s:%d (is another bridge using the port?)" % (HOST, PORT))
            return
        self._say("T2A Bridge listening on %s:%d" % (HOST, PORT))
        while self._running:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            t = threading.Thread(target=self._client, args=(conn,))
            t.daemon = True
            t.start()

    def _client(self, conn):
        buf = b""
        conn.settimeout(None)
        try:
            while self._running:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        conn.sendall((json.dumps(self._run(line), default=str) + "\n").encode("utf-8"))
        except Exception as exc:
            self.log_message("T2A client error: %s" % exc)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _run(self, line):
        try:
            req = json.loads(line.decode("utf-8"))
        except Exception as exc:
            return {"id": None, "ok": False, "error": "bad JSON: %s" % exc}
        box = queue.Queue()
        self._jobs.put((req.get("cmd"), req.get("args") or {}, box))
        try:
            self.schedule_message(1, self._drain)
        except Exception:
            pass  # update_display() drains as well
        try:
            res = box.get(timeout=TIMEOUT)
        except queue.Empty:
            res = {"ok": False, "error": "timed out waiting for Live's main thread"}
        res["id"] = req.get("id")
        return res
