"""
network_model.py
-----------------
Mixed-Integer Programming formulation of the 4-echelon network design problem:

    Plant -> RDC -> LDC -> Customer Zone

Decisions:
    - open_rdc[r]        binary, RDC r is open this planning cycle
    - open_ldc[l]         binary, LDC l is open this planning cycle
    - flow_plant_rdc[p,r,t]   units shipped plant -> RDC in week t
    - flow_rdc_ldc[r,l,t]     units shipped RDC -> LDC in week t
    - flow_ldc_zone[l,z,t]    units shipped LDC -> zone in week t
    - inv_rdc[r,t], inv_ldc[l,t]   end-of-week inventory
    - shortage[z,t]           unmet demand at zone z in week t

Objective: minimize
    transportation cost + handling cost + holding cost
    + facility opening cost + facility operating/residual cost
    + shortage penalty cost

Constraints:
    - Flow conservation / inventory balance at RDC and LDC
    - Plant weekly production capacity
    - RDC / LDC weekly throughput capacity (only if open)
    - RDC / LDC storage capacity (only if open)
    - No flow through a closed facility
    - Demand satisfaction: LDC->zone delivery + shortage = demand
    - Optional service guardrail: segment-level fill rate floor
    - Optional disruption: force a named RDC closed
"""

import pulp as pl
import pandas as pd


class NetworkModel:
    def __init__(self, data_dir="../data"):
        self.plants = pd.read_csv(f"{data_dir}/plants.csv")
        self.rdcs = pd.read_csv(f"{data_dir}/rdcs.csv")
        self.ldcs = pd.read_csv(f"{data_dir}/ldcs.csv")
        self.zones = pd.read_csv(f"{data_dir}/zones.csv")
        self.demand = pd.read_csv(f"{data_dir}/demand.csv")
        self.cost_plant_rdc = pd.read_csv(f"{data_dir}/cost_plant_rdc.csv")
        self.cost_rdc_ldc = pd.read_csv(f"{data_dir}/cost_rdc_ldc.csv")
        self.cost_ldc_zone = pd.read_csv(f"{data_dir}/cost_ldc_zone.csv")
        self.shortage_penalty = pd.read_csv(f"{data_dir}/shortage_penalty.csv")

        self.P = self.plants["plant_id"].tolist()
        self.R = self.rdcs["rdc_id"].tolist()
        self.L = self.ldcs["ldc_id"].tolist()
        self.Z = self.zones["zone_id"].tolist()
        self.T = sorted(self.demand["week"].unique().tolist())

        self.zone_segment = dict(zip(self.zones["zone_id"], self.zones["segment"]))
        self.demand_lookup = {
            (row.zone_id, row.week): row.demand for row in self.demand.itertuples()
        }
        self.c_pr = {(r.plant_id, r.rdc_id): r.cost_per_unit for r in self.cost_plant_rdc.itertuples()}
        self.c_rl = {(r.rdc_id, r.ldc_id): r.cost_per_unit for r in self.cost_rdc_ldc.itertuples()}
        self.c_lz = {(r.ldc_id, r.zone_id): r.cost_per_unit for r in self.cost_ldc_zone.itertuples()}
        self.penalty = dict(zip(self.shortage_penalty["segment"], self.shortage_penalty["shortage_penalty_per_unit"]))

        self.rdc_row = self.rdcs.set_index("rdc_id")
        self.ldc_row = self.ldcs.set_index("ldc_id")
        self.plant_row = self.plants.set_index("plant_id")

    def build(self, scenario_config=None):
        """
        scenario_config: dict, optional keys:
            - service_guardrail: {"Premium": 0.98, "Standard": 0.95}  min fill rate by segment
            - force_closed_rdcs: ["RDC02"]   RDCs forced closed for the whole horizon
        """
        cfg = scenario_config or {}
        guardrail = cfg.get("service_guardrail")
        forced_closed = set(cfg.get("force_closed_rdcs", []))

        m = pl.LpProblem("NetworkDesign", pl.LpMinimize)

        # --- Decision variables -------------------------------------------------
        open_rdc = pl.LpVariable.dicts("open_rdc", self.R, cat="Binary")
        open_ldc = pl.LpVariable.dicts("open_ldc", self.L, cat="Binary")

        flow_pr = pl.LpVariable.dicts("flow_pr", (self.P, self.R, self.T), lowBound=0)
        flow_rl = pl.LpVariable.dicts("flow_rl", (self.R, self.L, self.T), lowBound=0)
        flow_lz = pl.LpVariable.dicts("flow_lz", (self.L, self.Z, self.T), lowBound=0)

        inv_rdc = pl.LpVariable.dicts("inv_rdc", (self.R, self.T), lowBound=0)
        inv_ldc = pl.LpVariable.dicts("inv_ldc", (self.L, self.T), lowBound=0)

        shortage = pl.LpVariable.dicts("shortage", (self.Z, self.T), lowBound=0)

        # --- Forced-closed RDCs (disruption scenario) ---------------------------
        for r in forced_closed:
            m += open_rdc[r] == 0

        # --- Objective ------------------------------------------------------------
        transport_cost = (
            pl.lpSum(flow_pr[p][r][t] * self.c_pr[(p, r)] for p in self.P for r in self.R for t in self.T)
            + pl.lpSum(flow_rl[r][l][t] * self.c_rl[(r, l)] for r in self.R for l in self.L for t in self.T)
            + pl.lpSum(flow_lz[l][z][t] * self.c_lz[(l, z)] for l in self.L for z in self.Z for t in self.T)
        )

        handling_cost = (
            pl.lpSum(flow_rl[r][l][t] * self.rdc_row.loc[r, "handling_cost_per_unit"]
                     for r in self.R for l in self.L for t in self.T)
            + pl.lpSum(flow_lz[l][z][t] * self.ldc_row.loc[l, "handling_cost_per_unit"]
                       for l in self.L for z in self.Z for t in self.T)
        )

        holding_cost = (
            pl.lpSum(inv_rdc[r][t] * self.rdc_row.loc[r, "holding_cost_per_unit_per_week"]
                     for r in self.R for t in self.T)
            + pl.lpSum(inv_ldc[l][t] * self.ldc_row.loc[l, "holding_cost_per_unit_per_week"]
                       for l in self.L for t in self.T)
        )

        facility_cost = (
            pl.lpSum(open_rdc[r] * self.rdc_row.loc[r, "opening_cost"] for r in self.R)
            + pl.lpSum(open_ldc[l] * self.ldc_row.loc[l, "opening_cost"] for l in self.L)
            + pl.lpSum(
                (open_rdc[r] * self.rdc_row.loc[r, "operating_cost_per_week_if_open"]
                 + (1 - open_rdc[r]) * self.rdc_row.loc[r, "residual_cost_per_week_if_closed"])
                for r in self.R
              ) * len(self.T)
            + pl.lpSum(
                (open_ldc[l] * self.ldc_row.loc[l, "operating_cost_per_week_if_open"]
                 + (1 - open_ldc[l]) * self.ldc_row.loc[l, "residual_cost_per_week_if_closed"])
                for l in self.L
              ) * len(self.T)
        )

        shortage_cost = pl.lpSum(
            shortage[z][t] * self.penalty[self.zone_segment[z]] for z in self.Z for t in self.T
        )

        m += transport_cost + handling_cost + holding_cost + facility_cost + shortage_cost

        # --- Constraints -----------------------------------------------------------

        # Plant weekly capacity
        for p in self.P:
            for t in self.T:
                m += pl.lpSum(flow_pr[p][r][t] for r in self.R) <= self.plant_row.loc[p, "weekly_capacity"]

        # RDC inventory balance: inbound (from plants) = outbound (to LDCs) + delta inventory
        for r in self.R:
            for t in self.T:
                inflow = pl.lpSum(flow_pr[p][r][t] for p in self.P)
                outflow = pl.lpSum(flow_rl[r][l][t] for l in self.L)
                prev_inv = inv_rdc[r][t - 1] if t > self.T[0] else 0
                m += prev_inv + inflow - outflow == inv_rdc[r][t]
                # throughput & storage capacity, only usable if open
                m += inflow <= self.rdc_row.loc[r, "throughput_capacity"] * open_rdc[r]
                m += inv_rdc[r][t] <= self.rdc_row.loc[r, "storage_capacity"] * open_rdc[r]

        # LDC inventory balance
        for l in self.L:
            for t in self.T:
                inflow = pl.lpSum(flow_rl[r][l][t] for r in self.R)
                outflow = pl.lpSum(flow_lz[l][z][t] for z in self.Z)
                prev_inv = inv_ldc[l][t - 1] if t > self.T[0] else 0
                m += prev_inv + inflow - outflow == inv_ldc[l][t]
                m += inflow <= self.ldc_row.loc[l, "throughput_capacity"] * open_ldc[l]
                m += inv_ldc[l][t] <= self.ldc_row.loc[l, "storage_capacity"] * open_ldc[l]

        # Demand satisfaction at each zone/week
        for z in self.Z:
            for t in self.T:
                d = self.demand_lookup.get((z, t), 0)
                m += pl.lpSum(flow_lz[l][z][t] for l in self.L) + shortage[z][t] == d

        # Optional service guardrail: segment fill rate floor over the full horizon
        if guardrail:
            for segment, min_fill in guardrail.items():
                seg_zones = [z for z in self.Z if self.zone_segment[z] == segment]
                total_demand = pl.lpSum(self.demand_lookup.get((z, t), 0) for z in seg_zones for t in self.T)
                total_shortage = pl.lpSum(shortage[z][t] for z in seg_zones for t in self.T)
                # shortage <= (1 - min_fill) * total demand  ->  fill rate >= min_fill
                m += total_shortage <= (1 - min_fill) * total_demand

        self.model = m
        self.vars = {
            "open_rdc": open_rdc, "open_ldc": open_ldc,
            "flow_pr": flow_pr, "flow_rl": flow_rl, "flow_lz": flow_lz,
            "inv_rdc": inv_rdc, "inv_ldc": inv_ldc, "shortage": shortage,
        }
        return m

    def solve(self, msg=False):
        solver = pl.PULP_CBC_CMD(msg=msg)
        self.model.solve(solver)
        return pl.LpStatus[self.model.status]

    def summarize(self):
        v = self.vars
        total_cost = pl.value(self.model.objective)

        open_rdcs = [r for r in self.R if pl.value(v["open_rdc"][r]) > 0.5]
        open_ldcs = [l for l in self.L if pl.value(v["open_ldc"][l]) > 0.5]

        results = {}
        for segment in ["Premium", "Standard"]:
            seg_zones = [z for z in self.Z if self.zone_segment[z] == segment]
            total_demand = sum(self.demand_lookup.get((z, t), 0) for z in seg_zones for t in self.T)
            total_shortage = sum(pl.value(v["shortage"][z][t]) for z in seg_zones for t in self.T)
            shortage_pct = 100 * total_shortage / total_demand if total_demand else 0
            results[segment] = {"demand": total_demand, "shortage": total_shortage, "shortage_pct": shortage_pct}

        return {
            "total_cost": total_cost,
            "open_rdcs": open_rdcs,
            "open_ldcs": open_ldcs,
            "n_open_rdcs": len(open_rdcs),
            "n_total_rdcs": len(self.R),
            "n_open_ldcs": len(open_ldcs),
            "n_total_ldcs": len(self.L),
            "premium_shortage_pct": results["Premium"]["shortage_pct"],
            "standard_shortage_pct": results["Standard"]["shortage_pct"],
        }
