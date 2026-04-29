"""Combined Round 5 strategy runner.

Delegates each product to the sub-strategy that owns it. Sub-strategies'
loggers are suppressed; this runner flushes one log line per tick.

Sub-state is namespaced inside traderData (JSON dict with one key per
sub-strategy) so each sub-strategy reads/writes its own state without
clobbering siblings.

Coverage:
  SNACKPACKs (5)     -> r5_snackpack_mm
  ROBOT_DISHES (1)   -> r5_robot_dishes_mr
  PANEL_1X4 + 2X2    -> r5_panel_spread
  PEBBLES (5)        -> pebbles
  Everything else (~30 unclaimed) -> r5_fallback_mm
"""
import json

from backtester.datamodel import TradingState
from strategies.logger import Logger

from strategies import (
    r5_snackpack_mm,
    r5_robot_dishes_mr,
    r5_panel_spread,
    r5_fallback_mm,
    galaxy_oxygen,
    r5_microchip_lead_lag as r5_microchip,
)

try:
    from strategies import pebbles as pebbles_mod
    PEBBLES_OK = True
except Exception:
    pebbles_mod = None
    PEBBLES_OK = False


class _Quiet:
    def print(self, *args, **kwargs):
        pass

    def flush(self, *args, **kwargs):
        pass


r5_snackpack_mm.logger = _Quiet()
r5_robot_dishes_mr.logger = _Quiet()
r5_panel_spread.logger = _Quiet()
r5_fallback_mm.logger = _Quiet()
r5_microchip.logger = _Quiet()
if hasattr(galaxy_oxygen, "logger"):
    galaxy_oxygen.logger = _Quiet()
if PEBBLES_OK and hasattr(pebbles_mod, "logger"):
    pebbles_mod.logger = _Quiet()

logger = Logger()


def build_sub_strategies():
    subs = [
        ("snackpack", r5_snackpack_mm.Trader()),
        ("robot_dishes", r5_robot_dishes_mr.Trader()),
        ("panel_spread", r5_panel_spread.Trader()),
        ("galaxy_oxygen", galaxy_oxygen.Trader()),
        ("microchip", r5_microchip.Trader()),
        ("fallback_mm", r5_fallback_mm.Trader()),
    ]
    if PEBBLES_OK:
        subs.append(("pebbles", pebbles_mod.Trader()))
    return subs


SUB_STRATEGIES = build_sub_strategies()


class ProxyState:
    """Wraps a TradingState, overriding traderData for the sub-strategy."""
    def __init__(self, state, sub_trader_data):
        object.__setattr__(self, "_state", state)
        object.__setattr__(self, "traderData", sub_trader_data)

    def __getattr__(self, name):
        return getattr(self._state, name)


def load_combined_state(raw):
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


class Trader:
    def run(self, state: TradingState):
        combined = load_combined_state(state.traderData)
        merged_orders = {}
        new_combined = {}

        for name, sub_trader in SUB_STRATEGIES:
            sub_td = combined.get(name, "")
            proxy = ProxyState(state, sub_td)
            try:
                orders, _, new_td = sub_trader.run(proxy)
            except Exception:
                orders = {}
                new_td = sub_td
            merged_orders.update(orders)
            new_combined[name] = new_td if isinstance(new_td, str) else ""

        new_trader_data = json.dumps(new_combined)
        logger.flush(state, merged_orders, 0, new_trader_data)
        return merged_orders, 0, new_trader_data
