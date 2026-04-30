import json
from typing import Dict, List, Tuple

from backtester.datamodel import Order, OrderDepth, TradingState


# ---------------------------------------------------------------------------
# Round 5 v2 — fixes two v1 failures:
#   1. Anchor drift: live SNACKPACK was +140 vs hist; OXYGEN was -493 vs hist.
#      Hardcoded anchors never triggered. Fix: track anchor as live EMA.
#   2. PEBBLES bid-ask cost: v1 fired on mid-deviation but filled at bid/ask,
#      so deviation was eaten by the spread. Fix: trigger on TRADEABLE arb
#      (sum_of_bids > anchor when selling, sum_of_asks < anchor when buying).
# ---------------------------------------------------------------------------

POSITION_LIMIT = 100


PEBBLES_VARIANTS = ("PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL")
SNACKPACK_VARIANTS = (
    "SNACKPACK_CHOCOLATE", "SNACKPACK_PISTACHIO", "SNACKPACK_RASPBERRY",
    "SNACKPACK_STRAWBERRY", "SNACKPACK_VANILLA",
)
OXYGEN_VARIANTS = (
    "OXYGEN_SHAKE_CHOCOLATE", "OXYGEN_SHAKE_EVENING_BREATH", "OXYGEN_SHAKE_GARLIC",
    "OXYGEN_SHAKE_MINT", "OXYGEN_SHAKE_MORNING_BREATH",
)

# PEBBLES has a hard invariant — keep static anchor. Soft baskets use live EMA.
_PEBBLES_HARD_ANCHOR = 50_000.0

# EMA alpha for soft-basket anchors. 0.001 = ~1000 tick half-life,
# enough memory to dampen noise but quick enough to track regime shifts.
_ANCHOR_EMA_ALPHA = 0.001

_GROUP_CONFIG = {
    "PEBBLES":   {"variants": PEBBLES_VARIANTS,   "trigger": 1.0,   "lot": 30, "static": True},
    # soft baskets disabled — day 4 anchor drift = -301k loss
}


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result: Dict[str, List[Order]] = {}
        data = _load_data(state.traderData)
        for group, cfg in _GROUP_CONFIG.items():
            _trade_basket(result, state, group, cfg, data)
        return result, 0, json.dumps(data, separators=(",", ":"))


def _load_data(raw: str) -> dict:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _trade_basket(
    result: Dict[str, List[Order]],
    state: TradingState,
    group: str,
    cfg: dict,
    data: dict,
) -> None:
    legs = _collect_legs(state, cfg["variants"])
    if legs is None:
        return
    sum_bids = sum(bid for _, _, bid, _ in legs)
    sum_asks = sum(ask for _, _, _, ask in legs)
    sum_mid = (sum_bids + sum_asks) / 2.0

    anchor = _resolve_anchor(group, cfg, sum_mid, data)

    # Trigger on TRADEABLE arb: only fire when we can actually capture edge
    # net of bid-ask spread.
    sell_edge = sum_bids - anchor       # selling each at bid earns this
    buy_edge = anchor - sum_asks        # buying each at ask earns this

    if sell_edge > cfg["trigger"]:
        _sell_each_variant(result, state, legs, cfg["lot"])
    elif buy_edge > cfg["trigger"]:
        _buy_each_variant(result, state, legs, cfg["lot"])


def _resolve_anchor(group: str, cfg: dict, sum_mid: float, data: dict) -> float:
    if cfg["static"]:
        return _PEBBLES_HARD_ANCHOR
    key = f"anchor_{group}"
    prev = data.get(key, sum_mid)
    new = (1.0 - _ANCHOR_EMA_ALPHA) * prev + _ANCHOR_EMA_ALPHA * sum_mid
    data[key] = new
    return new


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
