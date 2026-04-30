"""Build bundled submission from sub-strategy source files."""
import base64
import sys
from pathlib import Path

SUB_DIR = Path(__file__).parent / "r5_baseline"
TEMPLATE = Path(__file__).parent.parent / "strategies" / "bundle_template.py"
PLACEHOLDER = "# === _SUB_SOURCES PLACEHOLDER ==="

SUB_NAMES = [
    "snackpack", "galaxy_oxygen", "robot_dishes",
    "panel_spread", "microchip", "uv_visor",
    "fallback_mm", "pebbles",
]

def build(output_path: str):
    template = TEMPLATE.read_text()
    lines = []
    lines.append("_SUB_SOURCES = {")
    for name in SUB_NAMES:
        src_path = SUB_DIR / f"sub_{name}.py"
        src = src_path.read_text()
        encoded = base64.b64encode(src.encode()).decode()
        lines.append(f'    "{name}": "{encoded}",')
    lines.append("}")
    sub_block = "\n".join(lines)
    output = template.replace(PLACEHOLDER, sub_block)
    Path(output_path).write_text(output)
    print(f"Built {output_path} ({len(output):,} bytes, {len(SUB_NAMES)} subs)")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "strategies/round5_v10.py"
    build(out)
