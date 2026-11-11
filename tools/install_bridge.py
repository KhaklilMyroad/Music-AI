"""Copy the T2A_Bridge Remote Script into Ableton's User Library.

Usage: python tools/install_bridge.py [--user-library "<path to User Library>"]

Default locations (Ableton's standard User Library; change it if you moved yours in Live's settings):
  macOS   ~/Music/Ableton/User Library
  Windows %USERPROFILE%\\Documents\\Ableton\\User Library
Then restart Live and choose Control Surface 'T2A_Bridge' in Settings > Link, Tempo & MIDI.
"""
import argparse
import os
import platform
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "ableton_bridge", "T2A_Bridge")


def default_user_library():
    home = os.path.expanduser("~")
    if platform.system() == "Windows":
        return os.path.join(home, "Documents", "Ableton", "User Library")
    return os.path.join(home, "Music", "Ableton", "User Library")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user-library", default=default_user_library())
    a = ap.parse_args(argv)
    if not os.path.isdir(a.user_library):
        print(f"User Library not found at {a.user_library}. Pass --user-library (see Live > Settings > Library).", file=sys.stderr)
        return 1
    dst = os.path.join(a.user_library, "Remote Scripts", "T2A_Bridge")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"Installed to {dst}\nRestart Live, then Settings > Link, Tempo & MIDI > Control Surface: T2A_Bridge (Input/Output: None).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
