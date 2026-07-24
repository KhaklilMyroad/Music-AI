# Music-AI

## OmniRoute — AI gateway

This repo uses [OmniRoute](https://github.com/diegosouzapw/OmniRoute), an
open-source AI gateway that aggregates 290+ AI providers (90+ free models)
behind a single OpenAI-compatible endpoint, with auto-routing, fallback on
quota exhaustion, and token compression.

### Install

Requires Node.js 18+.

```bash
./scripts/install-omniroute.sh
```

Or manually:

```bash
npm install -g omniroute
```

### Run

```bash
omniroute
```

- Dashboard: <http://localhost:20128>
- OpenAI-compatible API: `http://localhost:20128/v1`

Keyless free providers work out of the box with zero configuration. To use it
from any OpenAI-compatible tool (Claude Code, Cursor, Cline, etc.), point the
tool's base URL at `http://localhost:20128/v1` and use an API key generated in
the dashboard. Docker alternative:

```bash
docker run -p 127.0.0.1:20128:20128 diegosouzapw/omniroute:latest
```

## Claude Code: caveman plugin

This repo is configured to use the [caveman](https://github.com/JuliusBrussee/caveman)
Claude Code plugin — an ultra-compressed communication mode that cuts ~75% of
output tokens while keeping full technical accuracy ("why use many token when
few token do trick").

The setup lives in [`.claude/settings.json`](.claude/settings.json), which
registers the marketplace and enables the plugin at the **project scope** so it
applies to everyone who works in this repo:

```json
{
  "extraKnownMarketplaces": {
    "caveman": {
      "source": { "source": "github", "repo": "JuliusBrussee/caveman" }
    }
  },
  "enabledPlugins": {
    "caveman@caveman": true
  }
}
```

When you open this repo in Claude Code and trust the folder, you'll be prompted
to install the `caveman` marketplace and plugin. After install, run
`/reload-plugins` (or restart) and trigger it with `/caveman`, or just say
"caveman mode".

### Manual install (equivalent)

```bash
claude plugin marketplace add JuliusBrussee/caveman
claude plugin install caveman@caveman
```

Or the upstream one-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.sh | bash
```
