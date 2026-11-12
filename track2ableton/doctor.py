"""Is everything in place? One command that checks the installation and says exactly what to do about what is not.

    python -m track2ableton.doctor                  check
    python -m track2ableton.doctor --install-bridge copy the Remote Script into Ableton's User Library

Connecting an assistant to Live has several parts on one computer: this package, the Remote Script inside Ableton's
User Library (which Windows often keeps under OneDrive), Live running with the control surface selected, and the MCP
server registered with the assistant. Each check names its own fix.
"""
from __future__ import annotations

import filecmp
import importlib.util
import json
import os
import platform
import shutil
import sys
import sysconfig

from . import __version__, separation
from .live.client import LiveClient, LiveError

BRIDGE = "T2A_Bridge"


def bridge_source() -> str | None:
    """The Remote Script that ships with this checkout (next to the package), or None when it is not there."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(here, "ableton_bridge", BRIDGE)
    return src if os.path.isdir(src) else None


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


def _same_tree(a: str, b: str) -> bool:
    names = lambda d: sorted(f for f in os.listdir(d) if f.endswith(".py"))
    return names(a) == names(b) and all(filecmp.cmp(os.path.join(a, f), os.path.join(b, f), shallow=False) for f in names(a))


def bridge_state(library: str) -> str:
    """'current', 'differs' (another version is installed) or 'missing', for one User Library."""
    dst = os.path.join(library, "Remote Scripts", BRIDGE)
    src = bridge_source()
    if not os.path.isdir(dst):
        return "missing"
    if src is None:
        return "current"                # nothing to compare with: installed is all that can be said
    return "current" if _same_tree(src, dst) else "differs"


def install_bridge(library: str | None = None) -> str:
    """Copy the Remote Script into the User Library (the given one, else the first that exists). Returns the folder."""
    src = bridge_source()
    if src is None:
        raise FileNotFoundError("the ableton_bridge folder is not next to the package: run this from a checkout of the repository")
    if library is None:
        library = next((p for p in user_library_candidates() if os.path.isdir(p)), None)
        if library is None:
            raise FileNotFoundError("no Ableton User Library found in: " + "; ".join(user_library_candidates())
                                    + ". Pass --user-library with the path shown in Live > Settings > Library.")
    if not os.path.isdir(library):
        raise FileNotFoundError(f"User Library not found: {library}")
    dst = os.path.join(library, "Remote Scripts", BRIDGE)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


def check(host: str | None = None, port: int | None = None) -> list[dict]:
    """Every check as {name, state: ok | problem | optional, detail, fix}."""
    out: list[dict] = []

    def add(name, state, detail, fix=""):
        out.append({"name": name, "state": state, "detail": detail, "fix": fix})

    v = sys.version_info
    add("Python", "ok" if v >= (3, 10) else "problem", f"{v.major}.{v.minor}.{v.micro}", "" if v >= (3, 10) else "Install Python 3.10 or newer.")
    add("track2ableton", "ok", __version__)
    has_mcp = importlib.util.find_spec("mcp") is not None
    add("MCP server package", "ok" if has_mcp else "problem", "installed" if has_mcp else "not installed",
        "" if has_mcp else 'pip install -e ".[live]"')
    exe = shutil.which("track2ableton-mcp")
    scripts = os.path.join(sysconfig.get_path("scripts"), "track2ableton-mcp" + (".exe" if platform.system() == "Windows" else ""))
    if exe:
        add("MCP server command", "ok", exe)
    elif os.path.isfile(scripts):
        add("MCP server command", "ok", f"{scripts} (its folder is not on PATH: register it by its full path)",
            f'claude mcp add ableton -- "{scripts}"')
    else:
        add("MCP server command", "problem", "track2ableton-mcp was not found", 'pip install -e ".[live]"')
    src = bridge_source()
    libs = [p for p in user_library_candidates() if os.path.isdir(p)]
    if not libs:
        add("Ableton User Library", "problem", "not found in: " + "; ".join(user_library_candidates()),
            'Find the path in Live > Settings > Library, then: python -m track2ableton.doctor --install-bridge --user-library "<path>"')
    for lib in libs:
        state = bridge_state(lib)
        add("Remote Script in " + lib, "ok" if state == "current" else "problem",
            {"current": "installed, same as this version", "differs": "installed, but not this version", "missing": "not installed"}[state],
            "" if state == "current" else "python -m track2ableton.doctor --install-bridge" + ("" if src else " (from a checkout of the repository)")
            + ", then restart Live")
    client = LiveClient(host, port, timeout=2.0)
    try:
        pong = client.call("ping")
        add("Ableton Live", "ok", f"answering on {client.host}:{client.port}, {pong.get('commands', '?')} commands")
    except LiveError as exc:
        add("Ableton Live", "problem", f"no answer on {client.host}:{client.port}",
            "Start Live, then Settings > Link, Tempo & MIDI > Control Surface: T2A_Bridge (Input and Output: None). "
            f"({str(exc)[:120]})")
    finally:
        client.close()
    py = separation.demucs_python()
    named = os.environ.get("T2A_DEMUCS_PYTHON", "").strip()
    add("Demucs (neural stem splitting)", "ok" if py else "optional",
        (f"runs with {py}" if py else (f"T2A_DEMUCS_PYTHON names {named}, which does not exist" if named else "not installed: the rough built-in split is used")),
        "" if py else "See docs/VOCAL_IN_LIVE.md, 'Demucs, in its own environment'.")
    for mod, what, extra in (("cmudict", "English pronunciation (vocal scores)", "vocal"), ("pyphen", "Hyphenation (vocal scores)", "vocal"),
                             ("basic_pitch", "Neural note transcription", "transcription")):
        ok = importlib.util.find_spec(mod) is not None
        add(what, "ok" if ok else "optional", "installed" if ok else "not installed", "" if ok else f'pip install -e ".[{extra}]"')
    return out


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="track2ableton-doctor", description="Check the installation and say what to do about what is missing.")
    ap.add_argument("--install-bridge", action="store_true", help="copy the Remote Script into Ableton's User Library")
    ap.add_argument("--user-library", help="the User Library path, if it is not in one of the usual places")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.install_bridge:
        try:
            dst = install_bridge(args.user_library)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Installed to {dst}\nRestart Live, then Settings > Link, Tempo & MIDI > Control Surface: T2A_Bridge (Input/Output: None).")
        return 0
    rows = check()
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
