#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
uv venv --allow-existing .venv
uv pip install --python .venv/bin/python -e .
exec .venv/bin/python -m ipad_usb_monitor.install "$@"
