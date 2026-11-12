"""Copy the T2A_Bridge Remote Script into Ableton's User Library.

Usage: python tools/install_bridge.py [--user-library "<path to User Library>"]

The usual places are tried in turn (on Windows the Documents folder is often inside OneDrive):
  macOS   ~/Music/Ableton/User Library
  Windows %OneDrive%\\Documents\\Ableton\\User Library, then %USERPROFILE%\\Documents\\Ableton\\User Library
Then restart Live and choose Control Surface 'T2A_Bridge' in Settings > Link, Tempo & MIDI.
The same as: python -m track2ableton.doctor --install-bridge
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from track2ableton.doctor import main as doctor  # noqa: E402


def main(argv=None):
    return doctor(["--install-bridge"] + list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
