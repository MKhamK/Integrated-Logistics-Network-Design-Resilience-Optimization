"""
run_scenarios.py
-----------------
Runs the three scenarios described in the executive report and writes a
comparison table to ../results/scenario_comparison.csv

    1. Base Case          - unconstrained cost minimization
    2. Service Guardrail  - Premium fill rate >= 98%, Standard >= 95%
    3. Disruption Case    - RDC02 forced closed, guardrails still active

Run:
    python run_scenarios.py
(requires ../data/*.csv to already exist - run data/generate_data.py first)
"""

import sys
import os
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "model"))
from network_model import NetworkModel  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

SCENARIOS = {
    "Base Case": {},
    "Service Guardrail": {
        "service_guardrail": {"Premium": 0.98, "Standard": 0.95},
    },
    "Disruption Case": {
        "service_guardrail": {"Premium": 0.98, "Standard": 0.95},
        "force_closed_rdcs": ["RDC02"],
    },
}


def run_all():
    rows = []
    for name, cfg in SCENARIOS.items():
        print(f"\n=== Solving scenario: {name} ===")
        nm = NetworkModel(data_dir=DATA_DIR)
        nm.build(scenario_config=cfg)
        status = nm.solve(msg=False)
        print(f"Solver status: {status}")

        summary = nm.summarize()
        print(f"Total cost: {summary['total_cost']:,.0f}")
        print(f"Open RDCs: {summary['n_open_rdcs']}/{summary['n_total_rdcs']}  "
              f"Open LDCs: {summary['n_open_ldcs']}/{summary['n_total_ldcs']}")
        print(f"Premium shortage: {summary['premium_shortage_pct']:.2f}%  "
              f"Standard shortage: {summary['standard_shortage_pct']:.2f}%")

        rows.append({
            "scenario": name,
            "status": status,
            "total_cost": round(summary["total_cost"], 0),
            "open_rdcs": f"{summary['n_open_rdcs']}/{summary['n_total_rdcs']}",
            "open_ldcs": f"{summary['n_open_ldcs']}/{summary['n_total_ldcs']}",
            "premium_shortage_pct": round(summary["premium_shortage_pct"], 2),
            "standard_shortage_pct": round(summary["standard_shortage_pct"], 2),
        })

    df = pd.DataFrame(rows)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "scenario_comparison.csv")
    df.to_csv(out_path, index=False)

    print("\n\n=== Scenario Comparison ===")
    print(df.to_string(index=False))
    print(f"\nSaved to {out_path}")
    return df


if __name__ == "__main__":
    run_all()
