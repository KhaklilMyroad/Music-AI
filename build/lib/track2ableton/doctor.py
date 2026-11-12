"""Is everything in place? One command that checks the installation and says exactly what to do about what is not.

    python -m track2ableton.doctor                          check
    python -m track2ableton.doctor --install-bridge         copy the Remote Script into Ableton's User Library
    python -m track2ableton.doctor --read-only on | off     switch read-only mode

Connecting an assistant to Live has several parts on one computer: this package, the Remote Script inside Ableton's
User Library (which Windows often keeps under OneDrive), Live running with the control surface selected, and the MCP
server registered with the assistant. Each check names what to run for it.

What this cannot know: which User Library Live itself is set to use (that is in Live > Settings > Library). When it
finds more than one it says so.
"""
from __future__ import annotations

import filecmp
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile

from . import __version__, separation
from .live import guard
from .live.client import LiveClient, LiveError

BRIDGE = "T2A_Bridge"
BRIDGE_VERSION = "0.2"                       # what the Remote Script of this version answers to ping
LIBRARY_FOLDERS = ("Remote Scripts", "Presets", "Clips", "Samples", "Defaults", "Grooves", "Templates")


def _py() -> str:
    return "py" if platform.system() == "Windows" else "python"


def _config_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".track2ableton", "config.json")


def _config() -> dict:
    try:
        with open(_config_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _remember(library: str) -> None:
    try:
        os.makedirs(os.path.dirname(_config_path()), exist_ok=True)
        with open(_config_path(), "w", encoding="utf-8") as fh:
            json.dump(dict(_config(), user_library=library), fh, ensure_ascii=False, indent=1)
    except OSError:
        pass


def bridge_source() -> str | None:
    """The Remote Script that ships with this version: installed beside the package (a wheel), or in the checkout."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(here, "ableton_bridge", BRIDGE)
    if os.path.isdir(src):
        return src
    try:
        spec = importlib.util.find_spec(BRIDGE)
    except (ImportError, ValueError):
        spec = None
    if spec is not None and spec.origin and os.path.isfile(os.path.join(os.path.dirname(spec.origin), "handlers.py")):
        return os.path.dirname(spec.origin)
    return None


def user_library_candidates(system: str | None = None, env: dict | None = None, home: str | None = None) -> list[str]:
    """Where Ableton's User Library usually is, the likeliest first. On Windows the Documents folder is often moved
    into OneDrive, and the library moves with it."""
    system = system or platform.system()
    env = os.environ if env is None else env
    home = home or os.path.expanduser("~")
    if system == "Windows":
        roots = [env.get(k) for k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")] + [os.path.join(home, "OneDrive"), home]
        out = []
        for r in roots:
            p = os.path.join(r, "Documents", "Ableton", "User Library") if r else None
            if p and p not in out:
                out.append(p)
        return out
    if system == "Darwin":
        return [os.path.join(home, "Music", "Ableton", "User Library")]
    return [os.path.join(home, "Ableton", "User Library")]


def libraries(extra: str | None = None) -> list[str]:
    """The User Libraries that exist: one named now, the one remembered from an earlier install, then the usual places."""
    out: list[str] = []
    for p in [extra, _config().get("user_library")] + user_library_candidates():
        if p and os.path.isdir(p) and os.path.normpath(p) not in [os.path.normpath(x) for x in out]:
            out.append(p)
    return out


def looks_like_library(path: str) -> str | None:
    """None if the folder can be a User Library, else why not."""
    name = os.path.basename(os.path.normpath(path))
    if name in ("Remote Scripts", BRIDGE):
        return f"that is the {name} folder itself: give the User Library that contains 'Remote Scripts'"
    if name != "User Library" and not any(os.path.isdir(os.path.join(path, f)) for f in LIBRARY_FOLDERS):
        return "it is not named 'User Library' and has none of the folders a User Library has (Presets, Clips, Samples, Remote Scripts)"
    return None


def _same_tree(a: str, b: str) -> bool:
    names = lambda d: sorted(f for f in os.listdir(d) if f.endswith(".py"))
    return names(a) == names(b) and all(filecmp.cmp(os.path.join(a, f), os.path.join(b, f), shallow=False) for f in names(a))


def bridge_state(library: str) -> str:
    """'current', 'differs' (another version is installed), 'missing', or 'unknown' when there is nothing here to
    compare an installed script with."""
    dst = os.path.join(library, "Remote Scripts", BRIDGE)
    src = bridge_source()
    if not os.path.isdir(dst):
        return "missing"
    if src is None:
        return "unknown"
    return "current" if _same_tree(src, dst) else "differs"


def install_bridge(library: str | None = None, force: bool = False) -> str:
    """Copy the Remote Script into the User Library (the given one, else the first that exists). The copy that was
    there is put back if the new one cannot be written. Returns the folder."""
    src = bridge_source()
    if src is None:
        raise FileNotFoundError("the Remote Script is not part of this installation. Reinstall the package, or run from a "
                                "checkout of the repository.")
    if library is None:
        library = next(iter(libraries()), None)
        if library is None:
            raise FileNotFoundError("no Ableton User Library found in: " + "; ".join(user_library_candidates())
                                    + ". Pass --user-library with the path shown in Live > Settings > Library.")
    if not os.path.isdir(library):
        raise FileNotFoundError(f"User Library not found: {library}")
    why = looks_like_library(library)
    if why and not force:
        raise ValueError(f"{library} does not look like an Ableton User Library: {why}. Add --force if it really is one.")
    dst = os.path.join(library, "Remote Scripts", BRIDGE)
    if os.path.islink(dst) or (os.path.exists(dst) and not os.path.isdir(dst)):
        raise ValueError(f"{dst} is a link or a file, not the folder this installer writes. Remove it by hand first.")
    backup = None
    try:
        if os.path.isdir(dst):
            backup = os.path.join(tempfile.mkdtemp(prefix="t2a_bridge_backup_"), BRIDGE)
            shutil.copytree(dst, backup)
            shutil.rmtree(dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    except OSError as exc:
        if backup is not None:                     # put back what was there
            shutil.rmtree(dst, ignore_errors=True)
            try:
                shutil.copytree(backup, dst)
            except OSError:
                pass
        raise OSError(f"could not write {dst} ({exc}). If Live is running, close it and try again.") from exc
    finally:
        if backup is not None:
            shutil.rmtree(os.path.dirname(backup), ignore_errors=True)
    _remember(library)
    return dst


def _mcp_command() -> str | None:
    exe = shutil.which("track2ableton-mcp")
    if exe:
        return exe
    name = "track2ableton-mcp" + (".exe" if platform.system() == "Windows" else "")
    places = [sysconfig.get_path("scripts")]
    try:                                           # where `pip install --user` puts commands
        places.append(sysconfig.get_path("scripts", sysconfig.get_preferred_scheme("user")))
    except Exception:
        pass
    return next((os.path.join(p, name) for p in places if p and os.path.isfile(os.path.join(p, name))), None)


def _demucs() -> tuple[str, str]:
    """(state, detail). The interpreter is really asked whether it can import demucs."""
    named = os.environ.get("T2A_DEMUCS_PYTHON", "").strip().strip("\"'")
    if named and os.path.isdir(os.path.expanduser(named)):
        return "problem", f"T2A_DEMUCS_PYTHON names {named}, which is a folder: it must be the python program inside it"
    py = separation.demucs_python()
    if py is None:
        return ("problem", f"T2A_DEMUCS_PYTHON names {named}, which does not exist") if named else \
               ("optional", "not installed: the rough built-in split is used")
    try:
        run = subprocess.run([py, "-c", "import demucs"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "problem", f"{py} could not be run ({type(exc).__name__})"
    if run.returncode != 0:
        return "problem", f"{py} runs, but cannot import demucs"
    return "ok", f"runs with {py}"


def check(host: str | None = None, port: int | None = None, user_library: str | None = None) -> list[dict]:
    """Every check as {name, state: ok | problem | optional, detail, fix}."""
    out: list[dict] = []
    me = f"{_py()} -m track2ableton.doctor"

    def add(name, state, detail, fix=""):
        out.append({"name": name, "state": state, "detail": detail, "fix": fix})

    v = sys.version_info
    add("Python", "ok" if v >= (3, 10) else "problem", f"{v.major}.{v.minor}.{v.micro}", "" if v >= (3, 10) else "Install Python 3.10 or newer.")
    add("track2ableton", "ok", __version__)
    has_mcp = importlib.util.find_spec("mcp") is not None
    add("MCP server package", "ok" if has_mcp else "problem", "installed" if has_mcp else "not installed",
        "" if has_mcp else f'{_py()} -m pip install "mcp>=1.2"')
    exe = _mcp_command()
    if exe is None:
        add("MCP server command", "problem", "track2ableton-mcp was not found", "Reinstall the package with pip, then run this check again.")
    elif shutil.which("track2ableton-mcp"):
        add("MCP server command", "ok", exe)
    else:
        add("MCP server command", "ok", f"{exe} (its folder is not on PATH: register it by its full path)", f'claude mcp add ableton -- "{exe}"')

    src = bridge_source()
    libs = libraries(user_library)
    if user_library and not os.path.isdir(user_library):
        add("Ableton User Library", "problem", f"{user_library} does not exist", "Take the path from Live > Settings > Library.")
    if not libs:
        add("Ableton User Library", "problem", "not found in: " + "; ".join(user_library_candidates()),
            f'Find the path in Live > Settings > Library, then: {me} --install-bridge --user-library "<path>"')
    states = {lib: bridge_state(lib) for lib in libs}
    have = any(s in ("current", "unknown") for s in states.values())
    for lib, state in states.items():
        fix = f'{me} --install-bridge --user-library "{lib}", then restart Live'
        if state == "current":
            add("Remote Script in " + lib, "ok", "installed, same as this version")
        elif state == "unknown":
            add("Remote Script in " + lib, "ok", "installed (this installation has no copy to compare it with)")
        elif have:
            add("Remote Script in " + lib, "optional",
                ("not installed here" if state == "missing" else "another version is installed here")
                + ". Another library has it: this one matters only if it is the one Live uses (Live > Settings > Library)", fix)
        else:
            add("Remote Script in " + lib, "problem", "not installed" if state == "missing" else "installed, but not this version", fix)
    if len(libs) > 1:
        add("Which library Live uses", "optional", f"{len(libs)} User Libraries exist; this check cannot see which one Live is set to",
            "Live > Settings > Library shows it.")

    try:
        client = LiveClient(host, port, timeout=2.0)
        where = f"{client.host}:{client.port}"
        try:
            pong = client.call("ping")
        finally:
            client.close()
        if not isinstance(pong, dict) or not pong.get("pong"):
            raise LiveError("the answer is not from T2A_Bridge")
        if pong.get("version") != BRIDGE_VERSION:
            add("Ableton Live", "problem", f"answering on {where}, but with an older Remote Script",
                f"{me} --install-bridge, then restart Live")
        else:
            add("Ableton Live", "ok", f"answering on {where}, {pong.get('commands', '?')} commands")
    except Exception as exc:
        text = str(exc)
        if "not from T2A_Bridge" in text or "no answer from Live within" in text:
            add("Ableton Live", "problem", "something answers on the port, but it is not this tool's Remote Script",
                "Another Ableton bridge uses the same port (9877). In Live > Settings > Link, Tempo & MIDI leave only "
                "T2A_Bridge selected as Control Surface, then restart Live.")
        else:
            add("Ableton Live", "problem", "no answer" + (f" ({text[:110]})" if "T2A_PORT" in text else ""),
                "Start Live, then Settings > Link, Tempo & MIDI > Control Surface: T2A_Bridge (Input and Output: None).")
    add("Read-only mode", "ok", "ON: nothing that changes the Live Set is carried out" if guard.read_only() else "off",
        f"{me} --read-only off" if guard.read_only() else "")

    state, detail = _demucs()
    add("Demucs (neural stem splitting)", state, detail, "" if state == "ok" else "See docs/VOCAL_IN_LIVE.md, 'Demucs, in its own environment'.")
    for mod, what, fix in (("cmudict", "English pronunciation (vocal scores)", f"{_py()} -m pip install cmudict"),
                           ("pyphen", "Hyphenation (vocal scores)", f"{_py()} -m pip install pyphen"),
                           ("basic_pitch", "Neural note transcription",
                            f"{_py()} -m pip install basic-pitch (it pins an old TensorFlow and may not install on a recent Python)")):
        ok = importlib.util.find_spec(mod) is not None
        add(what, "ok" if ok else "optional", "installed" if ok else "not installed", "" if ok else fix)
    if src is None:
        add("Remote Script source", "problem", "this installation does not contain the Remote Script", "Reinstall the package.")
    return out


def main(argv=None) -> int:
    from ._console import safe_output
    safe_output()
    import argparse

    ap = argparse.ArgumentParser(prog="track2ableton-doctor", description="Check the installation and say what to do about what is missing.")
    ap.add_argument("--install-bridge", action="store_true", help="copy the Remote Script into Ableton's User Library")
    ap.add_argument("--user-library", help="the User Library path, if it is not in one of the usual places (it is remembered)")
    ap.add_argument("--force", action="store_true", help="install even if the folder does not look like a User Library")
    ap.add_argument("--read-only", choices=["on", "off"], help="switch read-only mode: nothing that changes the Live Set is carried out")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.read_only:
        try:
            flag = guard.set_read_only(args.read_only == "on")
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        still = args.read_only == "off" and guard.read_only()
        print(f"Read-only mode is {'ON' if guard.read_only() else 'off'} ({flag})."
              + (" T2A_READ_ONLY is still set in the environment: remove that variable too." if still else ""))
        return 0
    if args.install_bridge:
        try:
            dst = install_bridge(args.user_library, args.force)
        except (OSError, ValueError) as exc:       # FileNotFoundError and PermissionError are OSErrors
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Installed to {dst}\nRestart Live, then Settings > Link, Tempo & MIDI > Control Surface: T2A_Bridge (Input/Output: None).")
        return 0
    rows = check(user_library=args.user_library)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        mark = {"ok": "OK      ", "problem": "PROBLEM ", "optional": "optional"}
        for r in rows:
            print(f"{mark[r['state']]}  {r['name']}: {r['detail']}")
            if r["fix"]:
                print(f"            -> {r['fix']}")
        bad = sum(r["state"] == "problem" for r in rows)
        print(f"\n{'Everything needed is in place.' if not bad else f'{bad} thing(s) to fix, see the arrows.'}")
    return 1 if any(r["state"] == "problem" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
