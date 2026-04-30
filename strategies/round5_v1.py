import json
from typing import Dict, List, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


# ---------------------------------------------------------------------------
# Round 5 baskets — sum-of-5-variants is anchored per group (cointegrated).
# PEBBLES is structurally pinned (sd $2.8 around 50,000). The other two
# soft-anchor groups support stat-arb at wider thresholds.
# ---------------------------------------------------------------------------

POSITION_LIMIT = 100  # TODO(Kieran): confirm from R5 wiki, may be 50 or 100


PEBBLES_VARIANTS = ("PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL")
SNACKPACK_VARIANTS = (
    "SNACKPACK_CHOCOLATE", "SNACKPACK_PISTACHIO", "SNACKPACK_RASPBERRY",
    "SNACKPACK_STRAWBERRY", "SNACKPACK_VANILLA",
)
OXYGEN_VARIANTS = (
    "OXYGEN_SHAKE_CHOCOLATE", "OXYGEN_SHAKE_EVENING_BREATH", "OXYGEN_SHAKE_GARLIC",
    "OXYGEN_SHAKE_MINT", "OXYGEN_SHAKE_MORNING_BREATH",
)

# Per-group anchor (sum of all 5 variants) and trigger thresholds.
# Trigger threshold = 2× the historical SD of the group-sum, so we only fire
# on real dislocations rather than noise.
_GROUP_CONFIG = {
    "PEBBLES":   {"variants": PEBBLES_VARIANTS,   "anchor": 50_000.0, "trigger": 5.0,   "lot": 30},
    "SNACKPACK": {"variants": SNACKPACK_VARIANTS, "anchor": 50_041.0, "trigger": 320.0, "lot": 10},
    "OXYGEN":    {"variants": OXYGEN_VARIANTS,    "anchor": 50_076.0, "trigger": 800.0, "lot": 5},
}


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result: Dict[str, List[Order]] = {}
        for group, cfg in _GROUP_CONFIG.items():
            _trade_basket(result, state, cfg)
        return result, 0, state.traderData or ""


def _trade_basket(
    result: Dict[str, List[Order]],
    state: TradingState,
    cfg: dict,
) -> None:
    legs = _collect_legs(state, cfg["variants"])
    if legs is None:
        return
    sum_mid = sum((bid + ask) / 2.0 for _, _, bid, ask in legs)
    deviation = sum_mid - cfg["anchor"]
    if abs(deviation) < cfg["trigger"]:
        return
    if deviation > 0:
        _sell_each_variant(result, state, legs, cfg["lot"])
    else:
        _buy_each_variant(result, state, legs, cfg["lot"])


def _collect_legs(
    state: TradingState, variants: tuple,
) -> List[Tuple[str, OrderDepth, int, int]] | None:
    legs = []
    for v in variants:
        od = state.order_depths.get(v)
        if od is None or not od.buy_orders or not od.sell_orders:
            return None
        legs.append((v, od, max(od.buy_orders), min(od.sell_orders)))
    return legs


def _sell_each_variant(
    result: Dict[str, List[Order]],
    state: TradingState,
    legs: list,
    lot: int,
) -> None:
    for v, od, bid, _ in legs:
        position = state.position.get(v, 0)
        sell_room = POSITION_LIMIT + position
        depth = od.buy_orders[bid]
        qty = min(lot, depth, sell_room)
        if qty > 0:
            result.setdefault(v, []).append(Order(v, bid, -qty))


def _buy_each_variant(
    result: Dict[str, List[Order]],
    state: TradingState,
    legs: list,
    lot: int,
) -> None:
    for v, od, _, ask in legs:
        position = state.position.get(v, 0)
        buy_room = POSITION_LIMIT - position
        depth = abs(od.sell_orders[ask])
        qty = min(lot, depth, buy_room)
        if qty > 0:
            result.setdefault(v, []).append(Order(v, ask, qty))
