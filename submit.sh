#!/usr/bin/env bash
# Bundle a strategy into a single submission-ready file.
# Usage: ./submit.sh strategies/my_strat.py
#
# Output: submissions/my_strat.py (ready to upload to prosperity.imc.com)
#
# Behavior:
#   - Rewrites `from backtester.datamodel` -> `from datamodel` (IMC runtime).
#   - Strips local-only imports (backtester.*, strategies.*).
#   - Only injects Logger + extra datamodel imports if the strategy actually
#     references `logger.print(` or `logger.flush(`. Otherwise keeps the file
#     minimal (matches the format of working submissions).
set -e

if [ -z "$1" ]; then
    echo "Usage: ./submit.sh strategies/my_strat.py"
    exit 1
fi

STRAT="$1"
NAME=$(basename "$STRAT")
mkdir -p submissions
OUT="submissions/$NAME"

USES_LOGGER=0
if grep -qE "logger\.(print|flush)\(" "$STRAT"; then
    USES_LOGGER=1
fi

# Strip local imports + standalone `logger = Logger()` lines.
# Rewrite `from backtester.datamodel` to `from datamodel`.
# IMC bans `import os` (matches forbidden pattern 'import\s*os'), so we:
#   - drop `import os` lines
#   - replace `os.environ.get(...)` with `None` (live-mode fallback)
STRATEGY=$(sed \
    -e 's|^from backtester\.datamodel|from datamodel|' \
    -e 's|os\.environ\.get([^)]*)|None|g' \
    -e 's|^_TTE_SCHEDULE_DAYS = \[8\.0, 7\.0, 6\.0, 5\.0, 4\.0, 3\.0, 2\.0, 1\.0\]|_TTE_SCHEDULE_DAYS = [5.0, 4.0, 3.0, 2.0, 1.0]|' \
    "$STRAT" \
    | grep -v "^from backtester\.\|^from strategies\.\|^logger = Logger()\|^import os$")

if [ "$USES_LOGGER" -eq 1 ]; then
    LOGGER=$(grep -v "^import \|^from " strategies/logger.py)
    cat > "$OUT" << PYEOF
import json
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

$LOGGER

logger = Logger()

$STRATEGY
PYEOF
    echo "Submission ready (with Logger): $OUT"
else
    printf '%s\n' "$STRATEGY" > "$OUT"
    echo "Submission ready (clean, no Logger): $OUT"
fi
