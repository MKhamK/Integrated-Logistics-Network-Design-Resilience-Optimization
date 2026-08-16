# 4-Echelon Integrated Logistics Network Optimization

**Strategic Network Design, Service Policy Trade-offs, and Disruption Resilience Analysis**

*Role perspective: Supply Chain Solution Architect*

A Mixed-Integer Programming (MIP) model that turns network design into a quantified management decision — balancing facility footprint, cost-to-serve, customer service policy, and disruption resilience across a 4-echelon distribution network.

---

## 🎯 Objective

Build a mathematical optimization model to support decisions on:

- Which Regional DCs (RDCs) and Local DCs (LDCs) to open or close
- How product flows through a 4-echelon network
- The cost trade-off between operating efficiency and customer service level
- How resilient the network is to the loss of a major hub

**Network structure:** `Plant → Regional DC → Local DC → Customer Zone`

---

## 📐 Scope & Assumptions

| Parameter | Value |
|---|---|
| Plants | 4 |
| Regional DCs (RDCs) | 7 |
| Local DCs (LDCs) | 14 |
| Customer zones | 35 (Premium / Standard segments) |
| Product groups | 20 |
| Planning horizon | 10 weeks |

**Key modeling assumptions:**
- Closed facilities still retain 40% of residual lease cost; open facilities carry the remaining 60% as operating cost
- Opening a facility incurs a one-time Opening Cost
- Customers are segmented into **Premium** and **Standard**, each with distinct shortage penalty costs
- Unmet demand is allowed but penalized — the model makes the commercial cost of shortage explicit rather than forcing 100% service artificially
- No echelon-skipping: flow must pass through every tier in sequence

---

## 🧪 Why Mixed-Integer Programming

The problem combines **discrete facility decisions** (open/close) with **continuous flow, inventory, capacity, and shortage decisions**. MIP finds a network configuration and allocation plan that minimizes total cost while respecting physical capacity limits and policy constraints.

> This is a strategic decision-support asset, not a deterministic forecast of operating performance. It is designed for footprint, policy, and resilience choices — not for daily routing, labor scheduling, or real-time inventory control.

---

## 🧩 Scenario Architecture

Three scenarios form a decision ladder — separating economic efficiency, commercial acceptability, and resilience investment into distinct, comparable choices.

| # | Scenario | Description |
|---|---|---|
| 1 | **Base Case** | Unconstrained cost minimization. Exposes what the model does when free to trade shortage penalties for operating savings. |
| 2 | **Service Guardrail** | Policy-constrained. Imposes Premium fill rate ≥98% and Standard fill rate ≥95% as hard requirements. |
| 3 | **Disruption Case** | Resilience stress test. Forces RDC02 closed while keeping service guardrails active, to test whether the network can hold acceptable service through backup capacity. |

---

## 📊 Results

**Original study (executive report), proprietary dataset:**

| Scenario | Total Cost | Open RDCs | Open LDCs | Premium Shortage | Standard Shortage |
|---|---|---|---|---|---|
| Base Case | $78.1M | 5/7 | 13/14 | 0.38% | 13.31% |
| Service Guardrail | $84.0M | 5/7 | 14/14 | 1.77% | 5.00% |
| Disruption (RDC02 closed) | $88.8M | 6/7 | 14/14 | 1.86% | 5.00% |

- Enforcing the service policy adds **+$5.9M** vs. the Base Case
- Recovering from the RDC02 disruption adds a further **+$4.8M**
- The network expands first at the LDC tier, then at the RDC tier when a major hub is lost

**This repo's reference run**, on the included synthetic, randomly-seeded dataset (`data/generate_data.py`, seed 42) — reproducible by anyone who clones the repo:

| Scenario | Total Cost | Open RDCs | Open LDCs | Premium Shortage | Standard Shortage |
|---|---|---|---|---|---|
| Base Case | $5.80M | 1/7 | 2/14 | 37.28% | 100.00% |
| Service Guardrail | $8.88M | 4/7 | 9/14 | 0.00% | 4.84% |
| Disruption (RDC02 closed) | $8.96M | 4/7 | 9/14 | 0.00% | 4.84% |

> The absolute numbers differ from the original study because the underlying dataset is synthetic and generated at a smaller scale — but the **pattern is the same and is the actual point of the model**: an unconstrained cost objective sacrifices service (especially for the lower-penalty segment), a service guardrail buys back service at a quantifiable cost premium, and losing a major RDC is recoverable but not free. Regenerate with a different seed or swap in your own cost/demand data to reproduce the original report's scale.

---

## 🔍 Key Findings

1. **Without an explicit service policy**, the model economically deprioritizes Standard customers — Standard shortage reaches 13.31% vs. just 0.38% for Premium, because Standard penalties are materially lower. Mathematically optimal, but commercially risky.
2. **Adding Service Guardrails** (Premium ≥98%, Standard ≥95%) shifts the allocation frontier rather than simply adding cost — Standard shortage drops to 5.00%, Premium shortage rises only modestly to 1.77%.
3. **When a major RDC is forced offline**, the network activates a 6th RDC and holds Standard shortage at 5.00%, with Premium shortage rising only marginally to 1.86% — proving backup capacity *can* preserve service, but only if it's deliberately funded. Resilience is not automatic.
4. The **$5.9M policy premium** and **$4.8M resilience premium** put a real number on two things leadership usually treats as intangible: commercial acceptability and structural flexibility.

---

## 🏗️ Solution Architecture Implications

This model sits at the top of the planning hierarchy:

**Strategic Network Design → Tactical Planning → Operational Execution**

| Area | Application |
|---|---|
| Network & Capacity | Informs warehouse footprint, throughput requirements, and contingency capacity |
| Service Policy | Formalizes segment-level fill-rate targets owned by commercial leadership |
| Transportation & Inventory | Guides lane strategy and inventory positioning between RDCs/LDCs |
| Enterprise Integration | Feeds Integrated Business Planning (IBP); passes parameters downstream to TMS/WMS |

---

## ✅ Recommendations

1. **Adopt the Service Guardrail case** as the management baseline (Premium ≥98%, Standard ≥95% fill rate)
2. **Treat the $5.9M policy premium** as a deliberate commercial investment, built into the business case — not a model artifact to be optimized away
3. **Pre-approve the $4.8M resilience premium** as planned capacity investment, budgeted in advance of a disruption — not discovered during a crisis
4. Institutionalize disruption scenarios and refresh assumptions on a recurring planning cadence — this model is a repeatable decision asset, not a one-off study

---

## 🚀 Quickstart

```bash
git clone <your-repo-url>
cd logistics-network-optimization
pip install -r requirements.txt

# 1. Generate the synthetic dataset
cd data && python generate_data.py && cd ..

# 2. Solve all three scenarios and compare
cd scenarios && python run_scenarios.py
```

Output: a solved status, cost, and shortage summary for each of the three scenarios printed to console, plus `results/scenario_comparison.csv`.

To point the model at your own data, replace the CSVs in `data/` (same schema) and re-run `scenarios/run_scenarios.py`.

---

## 🛠️ What Was Done

- Designed the data structure and built a synthetic dataset (4 plants, 7 RDCs, 14 LDCs, 35 zones, 20 products, 10-week horizon)
- Formulated and implemented the MIP model using **PuLP** (Python)
- Solved and validated feasibility across all three scenarios
- Ran comparative scenario analysis (Base → Guardrail → Disruption)
- Interpreted results from a Supply Chain Solution Architect lens (strategic → tactical → operational)
- Produced an 11-page executive report translating model output into management decisions

---

## 🧰 Tech Stack

- **Python** — data generation, orchestration
- **PuLP** (CBC solver) — MIP formulation and solving
- **Pandas / NumPy** — data generation, wrangling, results analysis

---

## 📁 Repository Structure

```
.
├── data/
│   ├── generate_data.py          # builds the synthetic dataset (edit params here)
│   └── *.csv                     # plants, RDCs, LDCs, zones, demand, costs, penalties
├── model/
│   └── network_model.py          # MIP formulation (PuLP) — NetworkModel class
├── scenarios/
│   └── run_scenarios.py          # builds + solves all 3 scenarios, saves comparison
├── results/
│   └── scenario_comparison.csv   # output of the last run_scenarios.py run
├── report/
│   └── Integrated_Logistics_Network_Design_and_Resilience_Optimization.pdf
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 📄 Full Report

See [`report/Integrated_Logistics_Network_Design_and_Resilience_Optimization.pdf`](./report/) for the full 11-page executive report (original study, proprietary dataset).

---

## 👤 Author

**K. Anuwat**
