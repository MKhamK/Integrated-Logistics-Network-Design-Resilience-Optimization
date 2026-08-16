"""
generate_data.py
-----------------
Builds the synthetic dataset for the 4-Echelon Integrated Logistics Network
Optimization project:

    Plant -> Regional DC (RDC) -> Local DC (LDC) -> Customer Zone

Scope (matches the executive report):
    4 plants | 7 RDCs | 14 LDCs | 35 customer zones (Premium/Standard)
    10-week planning horizon

Note on product detail: the executive report models 20 product groups.
For this open-source reference implementation, demand is aggregated to a
single flow unit (cases) per zone/week/segment to keep the MIP tractable
on a laptop-grade solver (CBC). The model and data schema are written so
a product dimension can be re-introduced by adding a `product_id` column
and looping the flow/inventory variables over products.

Run:
    python generate_data.py
Outputs CSVs into this same `data/` folder.
"""

import numpy as np
import pandas as pd
import os

SEED = 42
rng = np.random.default_rng(SEED)

N_PLANTS = 4
N_RDCS = 7
N_LDCS = 14
N_ZONES = 35
N_WEEKS = 10

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def rand_coords(n, x_range=(0, 1000), y_range=(0, 1000)):
    x = rng.uniform(*x_range, n)
    y = rng.uniform(*y_range, n)
    return x, y


def euclid(x1, y1, x2, y2):
    return np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


# ---------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------

def build_plants():
    x, y = rand_coords(N_PLANTS)
    df = pd.DataFrame({
        "plant_id": [f"PLANT{i+1:02d}" for i in range(N_PLANTS)],
        "x": x, "y": y,
        "weekly_capacity": rng.integers(9000, 14000, N_PLANTS),
        "production_cost_per_unit": rng.uniform(2.5, 4.0, N_PLANTS).round(2),
    })
    return df


def build_rdcs():
    x, y = rand_coords(N_RDCS)
    df = pd.DataFrame({
        "rdc_id": [f"RDC{i+1:02d}" for i in range(N_RDCS)],
        "x": x, "y": y,
        # capacities are intentionally tight relative to demand so the model
        # is forced to open several RDCs/LDCs, mirroring the report's 5/7 RDC
        # and 13-14/14 LDC footprint rather than collapsing to a single hub
        "throughput_capacity": rng.integers(3800, 6500, N_RDCS),
        "storage_capacity": rng.integers(6000, 11000, N_RDCS),
        "opening_cost": rng.integers(800_000, 1_600_000, N_RDCS),
        "operating_cost_per_week": rng.integers(18_000, 32_000, N_RDCS),
        "handling_cost_per_unit": rng.uniform(0.35, 0.65, N_RDCS).round(2),
        "holding_cost_per_unit_per_week": rng.uniform(0.08, 0.15, N_RDCS).round(3),
    })
    # residual lease cost if closed = 40% of operating cost per week (per report assumption)
    df["residual_cost_per_week_if_closed"] = (df["operating_cost_per_week"] * 0.40).round(0)
    df["operating_cost_per_week_if_open"] = (df["operating_cost_per_week"] * 0.60).round(0)
    return df


def build_ldcs():
    x, y = rand_coords(N_LDCS)
    df = pd.DataFrame({
        "ldc_id": [f"LDC{i+1:02d}" for i in range(N_LDCS)],
        "x": x, "y": y,
        "throughput_capacity": rng.integers(1500, 3000, N_LDCS),
        "storage_capacity": rng.integers(2500, 5000, N_LDCS),
        "opening_cost": rng.integers(150_000, 400_000, N_LDCS),
        "operating_cost_per_week": rng.integers(4_000, 9_000, N_LDCS),
        "handling_cost_per_unit": rng.uniform(0.25, 0.50, N_LDCS).round(2),
        "holding_cost_per_unit_per_week": rng.uniform(0.06, 0.12, N_LDCS).round(3),
    })
    df["residual_cost_per_week_if_closed"] = (df["operating_cost_per_week"] * 0.40).round(0)
    df["operating_cost_per_week_if_open"] = (df["operating_cost_per_week"] * 0.60).round(0)
    return df


def build_zones():
    x, y = rand_coords(N_ZONES)
    # ~40% Premium, 60% Standard, matching a typical enterprise customer mix
    segment = rng.choice(["Premium", "Standard"], size=N_ZONES, p=[0.4, 0.6])
    df = pd.DataFrame({
        "zone_id": [f"ZONE{i+1:02d}" for i in range(N_ZONES)],
        "x": x, "y": y,
        "segment": segment,
    })
    return df


# ---------------------------------------------------------------------
# Demand
# ---------------------------------------------------------------------

def build_demand(zones_df):
    rows = []
    for _, z in zones_df.iterrows():
        base = rng.integers(300, 1200) if z["segment"] == "Premium" else rng.integers(200, 900)
        for week in range(1, N_WEEKS + 1):
            # mild week-to-week variation
            noise = rng.normal(1.0, 0.08)
            demand = max(0, int(base * noise))
            rows.append({
                "zone_id": z["zone_id"],
                "segment": z["segment"],
                "week": week,
                "demand": demand,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Costs (distance-based transportation cost tables)
# ---------------------------------------------------------------------

def build_transport_costs(from_df, to_df, from_id_col, to_id_col, base_rate):
    rows = []
    for _, f in from_df.iterrows():
        for _, t in to_df.iterrows():
            dist = euclid(f["x"], f["y"], t["x"], t["y"])
            cost = round(base_rate * (1 + dist / 1000), 3)
            rows.append({from_id_col: f[from_id_col], to_id_col: t[to_id_col], "cost_per_unit": cost})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Shortage penalties (per-unit, per-week) - the key service-policy lever
# ---------------------------------------------------------------------

def build_shortage_penalties():
    return pd.DataFrame([
        {"segment": "Premium", "shortage_penalty_per_unit": 45.0},
        {"segment": "Standard", "shortage_penalty_per_unit": 12.0},
    ])


def main():
    plants = build_plants()
    rdcs = build_rdcs()
    ldcs = build_ldcs()
    zones = build_zones()
    demand = build_demand(zones)

    plant_rdc_cost = build_transport_costs(plants, rdcs, "plant_id", "rdc_id", base_rate=1.2)
    rdc_ldc_cost = build_transport_costs(rdcs, ldcs, "rdc_id", "ldc_id", base_rate=0.9)
    ldc_zone_cost = build_transport_costs(ldcs, zones, "ldc_id", "zone_id", base_rate=0.6)

    shortage_penalty = build_shortage_penalties()

    plants.to_csv(f"{OUT_DIR}/plants.csv", index=False)
    rdcs.to_csv(f"{OUT_DIR}/rdcs.csv", index=False)
    ldcs.to_csv(f"{OUT_DIR}/ldcs.csv", index=False)
    zones.to_csv(f"{OUT_DIR}/zones.csv", index=False)
    demand.to_csv(f"{OUT_DIR}/demand.csv", index=False)
    plant_rdc_cost.to_csv(f"{OUT_DIR}/cost_plant_rdc.csv", index=False)
    rdc_ldc_cost.to_csv(f"{OUT_DIR}/cost_rdc_ldc.csv", index=False)
    ldc_zone_cost.to_csv(f"{OUT_DIR}/cost_ldc_zone.csv", index=False)
    shortage_penalty.to_csv(f"{OUT_DIR}/shortage_penalty.csv", index=False)

    print("Synthetic dataset generated:")
    for f in ["plants", "rdcs", "ldcs", "zones", "demand", "cost_plant_rdc",
              "cost_rdc_ldc", "cost_ldc_zone", "shortage_penalty"]:
        print(f"  - {f}.csv")


if __name__ == "__main__":
    main()
