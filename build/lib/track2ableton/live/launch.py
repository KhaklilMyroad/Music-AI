"""Start the MCP server, or say plainly what is missing. The console script points here, so a missing `mcp`
package gives one clear line instead of a traceback from an import."""
from __future__ import annotations

import importlib.util
import sys


def main(argv=None) -> int:
    if importlib.util.find_spec("mcp") is None:
        print('track2ableton-mcp needs the "mcp" package: pip install "track2ableton[live]"  (from a checkout: pip install -e ".[live]")',
              file=sys.stderr)
        return 1
    from .mcp_server import main as serve
    return serve(argv) or 0


if __name__ == "__main__":
    raise SystemExit(main())
