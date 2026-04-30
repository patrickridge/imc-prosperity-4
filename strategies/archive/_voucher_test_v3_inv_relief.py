"""
Test strategy: VEV v3 with inventory relief MM and passive bidding.
Merge template: call vev_init_state(), then vev_compute_orders() per tick.
"""

import json
from typing import Dict, List

from backtester.datamodel import Order, OrderDepth, TradingState
from round3_voucher_v3 import vev_init_state, vev_compute_orders

VELVETFRUIT_EXTRACT = "VELVETFRUIT_EXTRACT"
_VEV_ACTIVE_SYMBOLS = ("VEV_4000", "VEV_5200", "VEV_5300", "VEV_5400")


class Trader:
    def __init__(self):
        self.vev_trader = None

    def run(
        self, state: TradingState
    ) -> tuple[Dict[str, List[Order]], int, str]:
        # Init VEV trader once per run
        if self.vev_trader is None:
            self.vev_trader = vev_init_state()

        result: Dict[str, List[Order]] = {}
        spot_depth = state.order_depths.get(VELVETFRUIT_EXTRACT)
        spot_mid = None
        if spot_depth is not None:
            bid = max(spot_depth.buy_orders) if spot_depth.buy_orders else None
            ask = min(spot_depth.sell_orders) if spot_depth.sell_orders else None
            if bid is not None and ask is not None:
                spot_mid = (bid + ask) / 2.0

        # Get VEV orders
        vev_orders_dict = vev_compute_orders(
            self.vev_trader,
            _VEV_ACTIVE_SYMBOLS,
            state.order_depths,
            state.position,
            spot_mid,
            state.timestamp,
        )

        # Convert internal format to Order objects
        for sym, order_list in vev_orders_dict.items():
            result[sym] = []
            for symbol, price, qty in order_list:
                result[sym].append(Order(symbol, price, qty))

        return result, 0, json.dumps({}, separators=(",", ":"))
