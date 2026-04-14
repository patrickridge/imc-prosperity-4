# Colors
BID_COLOR = "#2196F3"
BID_COLORS = ["#2196F3", "#64B5F6", "#BBDEFB"]
ASK_COLOR = "#F44336"
ASK_COLORS = ["#F44336", "#E57373", "#FFCDD2"]
BUY_COLOR = "#4CAF50"
SELL_COLOR = "#E53935"
OWN_TRADE_COLOR = "#FF9800"
MID_COLOR = "#333333"
PNL_COLOR = "#7C4DFF"
POSITION_COLOR = "#00BCD4"

# Marker shapes
BUY_MARKER = "triangle-up"
SELL_MARKER = "triangle-down"
OWN_MARKER = "x"

# Sizing
TRADE_SIZE_SCALE = 3
DOT_SIZE_BASE = 4
DOT_OPACITY_BY_LEVEL = [0.9, 0.5, 0.25]

# LOB
LOB_LEVELS = 3

# CSV format
CSV_SEPARATOR = ";"

# Price columns per level
PRICE_BID_COLS = ["bid_price_1", "bid_price_2", "bid_price_3"]
PRICE_ASK_COLS = ["ask_price_1", "ask_price_2", "ask_price_3"]
VOLUME_BID_COLS = ["bid_volume_1", "bid_volume_2", "bid_volume_3"]
VOLUME_ASK_COLS = ["ask_volume_1", "ask_volume_2", "ask_volume_3"]

# Downsample
DOWNSAMPLE_OPTIONS = [1, 2, 5, 10]
DEFAULT_DOWNSAMPLE = 1

# Normalization modes
NORM_RAW = "Raw"
NORM_RELATIVE_MID = "Relative to Mid"
NORMALIZATION_OPTIONS = [NORM_RAW, NORM_RELATIVE_MID]

# Layout
SIDEBAR_WIDTH = "260px"
CHART_HEIGHT = 350
SMALL_CHART_HEIGHT = 200
