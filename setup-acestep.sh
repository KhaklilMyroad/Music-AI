#!/usr/bin/env bash
# Install ACE-Step 1.5 (open-source music generation) into this project.
# Usage: ./setup-acestep.sh
set -euo pipefail

cd "$(dirname "$0")"

# 1. Install uv (Python package manager) if missing
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Clone ACE-Step 1.5 if not already present
if [ ! -d ACE-Step-1.5 ]; then
    git clone https://github.com/ACE-Step/ACE-Step-1.5.git
fi

# 3. Install all Python dependencies (PyTorch, transformers, gradio, etc.)
cd ACE-Step-1.5
uv sync

echo ""
echo "ACE-Step 1.5 installed successfully."
echo ""
echo "To launch the Gradio web UI (models auto-download on first run):"
echo "  cd ACE-Step-1.5 && uv run acestep      # http://localhost:7860"
echo ""
echo "To launch the REST API server:"
echo "  cd ACE-Step-1.5 && uv run acestep-api  # http://localhost:8001"
