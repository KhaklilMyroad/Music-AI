#!/usr/bin/env bash
# Install and start OmniRoute (https://github.com/diegosouzapw/OmniRoute) —
# an open-source AI gateway exposing 290+ providers behind a single
# OpenAI-compatible endpoint.
set -euo pipefail

if ! command -v node >/dev/null 2>&1; then
  echo "error: Node.js 18+ is required (https://nodejs.org)" >&2
  exit 1
fi

NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "error: Node.js 18+ is required, found $(node --version)" >&2
  exit 1
fi

echo "Installing omniroute globally via npm..."
npm install -g omniroute

echo
echo "Installed: omniroute $(omniroute --version 2>/dev/null | tail -1)"
echo
echo "Start it with:  omniroute"
echo "Dashboard:      http://localhost:20128"
echo "API endpoint:   http://localhost:20128/v1 (OpenAI-compatible)"
