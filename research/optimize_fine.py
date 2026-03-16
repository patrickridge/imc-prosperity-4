"""Fine parameter sweep around best region. Run: python3 research/optimize_fine.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.optimize import eval_params
from itertools import product as iterproduct


def main():
    take_edges = [0.5, 1.0, 1.5, 2.0]
    quote_offsets = [1, 2, 3, 4]
    inv_skews = [0.02, 0.05, 0.08, 0.10, 0.15]
    emerald_fvs = [10000]  # insensitive, fix it

    results = []
    total = len(take_edges) * len(quote_offsets) * len(inv_skews) * len(emerald_fvs)
    print(f"Running {total} fine-grained combos...")

    for i, (te, qo, inv, efv) in enumerate(iterproduct(take_edges, quote_offsets, inv_skews, emerald_fvs)):
        profit = eval_params(te, qo, inv, efv)
        results.append((profit, te, qo, inv, efv))
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{total} done...")

    results.sort(reverse=True)

    print(f"\n{'Profit':>10}  {'TakeEdge':>8}  {'QuoteOff':>8}  {'InvSkew':>8}")
    print("-" * 45)
    for profit, te, qo, inv, efv in results[:20]:
        print(f"{profit:>10,.0f}  {te:>8.1f}  {qo:>8}  {inv:>8.2f}")


if __name__ == "__main__":
    main()
