"""Build a single-file submission bundle from r5_combined.py.

submit.sh strips `from strategies.X import` lines, so the multi-file combined
runner can't be uploaded directly. This script reads each sub-strategy
referenced by r5_combined.py, embeds their source as base64-encoded strings,
and writes a single-file bundle that loads them at runtime via exec into
isolated module namespaces. No name collisions, no manual surgery.

Output: submissions/r5_combined.py (ready to upload).

Run as: python3 research/round5_build_submission.py
"""
from __future__ import annotations

import base64
import re
import textwrap
from pathlib import Path

REPO = Path(__file__).parent.parent
STRATEGIES = REPO / "strategies"
OUT = REPO / "submissions" / "r5_combined.py"

SUB_MODULES = [
    ("snackpack", "r5_snackpack_mm.py"),
    ("robot_dishes", "r5_robot_dishes_mr.py"),
    ("panel_spread", "r5_panel_spread.py"),
    ("galaxy_oxygen", "galaxy_oxygen.py"),
    ("microchip", "r5_microchip_lead_lag.py"),
    ("fallback_mm", "r5_fallback_mm.py"),
    ("pebbles", "pebbles.py"),
]

LOGGER_PATH = STRATEGIES / "logger.py"


def strip_imports(src: str) -> str:
    """Remove backtester/strategies imports, the try/except datamodel fallback
    block (some sub-strategies use it), and standalone `logger = Logger()`."""
    lines = src.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith(("from backtester.", "import backtester",
                                "from strategies.", "import strategies",
                                "from datamodel", "import datamodel")):
            i += 1
            continue
        if stripped == "logger = Logger()":
            i += 1
            continue
        if stripped == "try:":
            block = [line]
            j = i + 1
            while j < len(lines):
                l = lines[j]
                if l.startswith((" ", "\t")) or not l.strip() or \
                   l.strip().startswith(("except", "finally", "else:")):
                    block.append(l)
                    j += 1
                else:
                    break
            block_text = "\n".join(block)
            if "datamodel" in block_text:
                while block and not block[-1].strip():
                    block.pop()
                    j -= 1
                i = j
                continue
            out.append(line)
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def encode_source(path: Path) -> str:
    raw = path.read_text()
    cleaned = strip_imports(raw)
    return base64.b64encode(cleaned.encode("utf-8")).decode("ascii")


def read_logger() -> str:
    src = LOGGER_PATH.read_text()
    out = []
    for line in src.splitlines():
        if line.startswith("import ") or line.startswith("from "):
            continue
        out.append(line)
    return "\n".join(out).strip()


BUNDLE_TEMPLATE = '''# Auto-generated submission bundle for r5_combined.
# Built by research/round5_build_submission.py — do not edit by hand.
import base64
import json
import math
import types
from typing import Any, Dict, List, Optional, Tuple

try:
    from datamodel import (
        Listing, Observation, Order, OrderDepth, ProsperityEncoder,
        Symbol, Trade, TradingState,
    )
except ImportError:
    from backtester.datamodel import (
        Listing, Observation, Order, OrderDepth, ProsperityEncoder,
        Symbol, Trade, TradingState,
    )


{logger_block}


logger = Logger()


class _Quiet:
    def print(self, *args, **kwargs):
        pass

    def flush(self, *args, **kwargs):
        pass


_SUB_SOURCES = {{
{sources_block}
}}


def _load_sub(name):
    mod = types.ModuleType("sub_" + name)
    mod.__dict__.update({{
        "Order": Order, "OrderDepth": OrderDepth, "TradingState": TradingState,
        "Listing": Listing, "Observation": Observation, "Trade": Trade,
        "Symbol": Symbol, "ProsperityEncoder": ProsperityEncoder,
        "Logger": Logger, "logger": _Quiet(),
        "json": json, "math": math,
        "Any": Any, "Dict": Dict, "List": List,
        "Optional": Optional, "Tuple": Tuple,
    }})
    src = base64.b64decode(_SUB_SOURCES[name]).decode("utf-8")
    exec(src, mod.__dict__)
    return mod


_SUBS = [(name, _load_sub(name).Trader()) for name in _SUB_SOURCES]


class _ProxyState:
    def __init__(self, state, sub_trader_data):
        object.__setattr__(self, "_state", state)
        object.__setattr__(self, "traderData", sub_trader_data)

    def __getattr__(self, name):
        return getattr(self._state, name)


def _load_combined(raw):
    if not raw:
        return {{}}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {{}}
    return loaded if isinstance(loaded, dict) else {{}}


class Trader:
    def run(self, state):
        combined = _load_combined(state.traderData)
        merged_orders = {{}}
        new_combined = {{}}

        for name, sub_trader in _SUBS:
            sub_td = combined.get(name, "")
            proxy = _ProxyState(state, sub_td)
            try:
                orders, _, new_td = sub_trader.run(proxy)
            except Exception:
                orders = {{}}
                new_td = sub_td
            merged_orders.update(orders)
            new_combined[name] = new_td if isinstance(new_td, str) else ""

        trader_data = json.dumps(new_combined)
        logger.flush(state, merged_orders, 0, trader_data)
        return merged_orders, 0, trader_data
'''


def build_bundle() -> str:
    sources = {name: encode_source(STRATEGIES / file) for name, file in SUB_MODULES}
    sources_block = ",\n".join(
        f'    "{name}": "{src}"' for name, src in sources.items()
    )
    logger_block = read_logger()
    return BUNDLE_TEMPLATE.format(logger_block=logger_block, sources_block=sources_block)


def main():
    bundle = build_bundle()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(bundle)
    print(f"wrote {OUT}  ({len(bundle):,} bytes)")
    print(f"  embedded modules: {[name for name, _ in SUB_MODULES]}")


if __name__ == "__main__":
    main()
