#!/usr/bin/env python3
import subprocess
import json
from pathlib import Path
from datetime import datetime

REPO_PATH = "/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4"
STRATEGY_TEMPLATE = "/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/strategies/round3_tuned.py"
RESULTS_FILE = "/sessions/amazing-upbeat-volta/mnt/imc-prosperity-4/research/sweep_results_hydrogel.json"

BASELINE = {
    "HYDROGEL_POST_EDGE": 2,
    "HYDROGEL_MAX_TAKE_SIZE": 10,
    "HYDROGEL_TARGET_SCALE": 40,
    "HYDROGEL_FAIR_VALUE": 9_991.0,
}

SWEEPS = {
    "HYDROGEL_POST_EDGE": [1, 2, 3, 4, 5],
    "HYDROGEL_MAX_TAKE_SIZE": [5, 10, 15, 20, 30, 50],
    "HYDROGEL_TARGET_SCALE": [10, 20, 40, 80, 120, 200],
    "HYDROGEL_FAIR_VALUE": [9989, 9990, 9991, 9992, 9993],
}

def read_strategy_template():
    with open(STRATEGY_TEMPLATE) as f:
        return f.read()

def create_test_strategy(params):
    template = read_strategy_template()

    for key, value in params.items():
        old = f"{key} = "
        if isinstance(value, float):
            new = f"{key} = {value}"
        else:
            new = f"{key} = {value}"

        lines = template.split('\n')
        for i, line in enumerate(lines):
            if line.startswith(old):
                lines[i] = new
                template = '\n'.join(lines)
                break

    return template

def run_backtest(strategy_code, test_name):
    test_file = f"{REPO_PATH}/strategies/test_{test_name}.py"

    with open(test_file, 'w') as f:
        f.write(strategy_code)

    try:
        result = subprocess.run(
            ["bash", "-c", f"cd {REPO_PATH} && ./backtest.sh strategies/test_{test_name}.py 3 2>&1"],
            capture_output=True,
            text=True,
            timeout=300
        )

        output = result.stdout + result.stderr
        pnl_lines = [l for l in output.split('\n') if 'Total profit:' in l]

        if pnl_lines:
            total_line = pnl_lines[-1]
            total_pnl = int(total_line.split(':')[1].replace(',', '').strip())

            hydrogel_line = [l for l in output.split('\n') if 'HYDROGEL_PACK:' in l]
            if hydrogel_line:
                hydrogel_pnl_str = hydrogel_line[-1].split(':')[1].replace(',', '').strip()
                hydrogel_pnl = int(hydrogel_pnl_str)
            else:
                hydrogel_pnl = 0

            return total_pnl, hydrogel_pnl
        else:
            return None, None
    except Exception as e:
        print(f"Error running {test_name}: {e}")
        return None, None
    finally:
        Path(test_file).unlink(missing_ok=True)

def main():
    results = {}

    for param_name, param_values in SWEEPS.items():
        print(f"\n{'='*70}")
        print(f"Sweeping {param_name}")
        print(f"{'='*70}")

        param_results = []

        for value in param_values:
            params = dict(BASELINE)
            params[param_name] = value

            test_name = f"hydro_{param_name}_{value}".replace('.', 'p').replace('_', '')
            print(f"Testing {param_name}={value}...", end=" ", flush=True)

            strategy_code = create_test_strategy(params)
            total_pnl, hydrogel_pnl = run_backtest(strategy_code, test_name)

            if total_pnl is not None:
                param_results.append({
                    "value": value,
                    "total_pnl": total_pnl,
                    "hydrogel_pnl": hydrogel_pnl,
                })
                print(f"Total={total_pnl:,} Hydrogel={hydrogel_pnl:,}")
            else:
                print("FAILED")

        results[param_name] = param_results

        if param_results:
            best = max(param_results, key=lambda x: x["total_pnl"])
            print(f"\nBest for {param_name}: {best['value']} (Total={best['total_pnl']:,})")

    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Results saved to {RESULTS_FILE}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
