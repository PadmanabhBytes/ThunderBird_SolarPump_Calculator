# Thunderbird Solar × POP — Solar Pump Calculator: Project Status

**Last updated:** June 22, 2026
**Client:** Corey Pratt & Cody Burgdorff (Thunderbird Solar / POP)
**Developer:** Padmanabh Wanikar (ConsultAdd)
**Phase:** 1 — Single SKU (15TBS-4C-AC). No new pumps until equipment-inclusion rules doc received and signed off.

---

## Live Deployment

| Service | URL | Platform |
|---|---|---|
| Frontend (React + Vite) | https://sparkling-reflection-production-22a7.up.railway.app | Railway |
| Backend (FastAPI) | Internal Railway service | Railway |
| Auto-deploy trigger | Push to `main` branch on GitHub → Railway redeploys both services automatically | GitHub → Railway |
| Source repository | https://github.com/PadmanabhBytes/ThunderBird_SolarPump_Calculator | GitHub |

> **Security note:** NREL API key (`NREL_API_KEY`) is set as a Railway environment variable. It is NOT in the GitHub repository. The `.env` file is in `.gitignore`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, React Router v7, html2pdf.js |
| Backend | Python, FastAPI, Pydantic v2, httpx (async NREL calls) |
| Data | CSV files (Goulds friction table, pump catalog, pump performance curves) |
| Deployment | Railway (RAILPACK builder), `npx serve` for frontend static serving |
| External API | NREL Solar Resource API (GHI lookup → solar zone coefficient) |

---

## Project Architecture

```
Thunderbird-SolarPumps/
├── frontend/                          React + Vite
│   └── src/
│       ├── App.jsx                    Top-level routing (form → results)
│       ├── CalculatorForm.jsx         4-step wizard with validation
│       ├── ResultsPage.jsx            Output display, equipment list, wire sizing, PDF
│       ├── steps/
│       │   ├── Step1Flow.jsx          GPM, TDH inputs (water level, drawdown, pipe)
│       │   ├── Step2Well.jsx          Well casing diameter, recovery rate, water quality
│       │   ├── Step3Solar.jsx         Panel specs (W, Voc, Vmp, dims), GPS location
│       │   └── Step4Controls.jsx     Float switch, pressure switch + range selection
│       ├── data/
│       │   └── accessories.js         Equipment list logic (SKUs, quantities, conditions)
│       └── api/
│           └── calculator.js          POST to /api/v1/calculations/calculate
│
└── solar_pump_calculator/             FastAPI backend
    ├── app/
    │   ├── main.py                    App factory, lifespan, CORS, /health
    │   ├── config.py                  Pydantic-Settings, env vars
    │   ├── controllers/
    │   │   └── calculation_controller.py   Full pipeline: TDH→NREL→pump→wire
    │   ├── services/
    │   │   ├── tdh_service.py         TDH = pumping level + elevation + friction + pressure head
    │   │   ├── friction_service.py    Goulds table lookup, ceiling GPM, Hazen-Williams fallback
    │   │   ├── nrel_service.py        NREL GHI API → solar zone (1–7) → coefficient
    │   │   ├── solar_service.py       Panel count via production + deadhead paths
    │   │   ├── pump_eval_service.py   Pump curve bilinear interpolation, eligibility check
    │   │   ├── pump_filter_service.py Removes DC-only pumps when generator backup required
    │   │   ├── ranking_service.py     3-category engine (economical/precise/premium)
    │   │   ├── wire_sizing_service.py AWG via voltage-drop formula, min floor by system type
    │   │   └── interpolation.py       Power-law interpolation utilities
    │   ├── repositories/
    │   │   ├── friction_repository.py CSV loader, indexed by (material, diameter)
    │   │   └── pump_repository.py     CSV loader, pump catalog + performance curve datasets
    │   ├── models/
    │   │   ├── calculation_request.py  Pydantic v2 input model (all fields, validators)
    │   │   ├── calculation_response.py Pydantic v2 output model (TDH breakdown, recommendations)
    │   │   └── pump.py                Pump data model
    │   └── utils/
    │       ├── logger.py              Centralized logging setup
    │       └── exceptions.py          Custom exception types
    ├── data/
    │   ├── friction/
    │   │   ├── pvc.csv                Goulds Sch 40 PVC friction table (ft/100ft by GPM + diameter)
    │   │   └── steel.csv              Steel friction table
    │   └── pumps/
    │       ├── pump_catalog.csv        21 pumps with specs (power, head, flow, voltage, price)
    │       └── performance/
    │           └── 15TBS-4C-AC.csv    Bilinear pump curve: head_ft × wattage → GPM
    └── test_validation_scenarios.py   5 reference scenarios; all must PASS before any client share
```

---

## What Is Built

### Backend — Fully Functional

#### TDH Calculation (`tdh_service.py`)
```
TDH = (Dynamic Water Level + Discharge Elevation + Friction Loss + Pressure Head) × Safety Factor
    = (Static Water Level + Drawdown + Discharge Elevation + Friction Loss + PSI × 2.31) × SF
```
- Safety factor default: 1.0 (no safety margin — client uses raw physics)
- Pressure head conversion: 1 PSI = 2.31 ft of water head (exact per ASPE)

#### Friction Loss (`friction_service.py`)
- Source: Goulds Sch 40 PVC table (`data/friction/pvc.csv`) — ft loss per 100 ft of pipe
- Lookup method: **ceiling GPM** — rounds required GPM UP to next table breakpoint (not interpolated down)
- Fallback: Hazen-Williams formula when GPM is outside table range (e.g. very large pipes)
- Known addition: 14 GPM row for 1.25" PVC (2.56 ft/100ft) was missing from Goulds official table; added from reference PDF reverse-engineering

#### TBS Friction-GPM Rule — Critical Methodology
| System type | Friction sized at |
|---|---|
| Solar-only (no generator backup) | `max(required_gpm, 15.0)` — pump's rated output. Pipe must handle full pump flow in good solar. |
| Generator backup | `required_gpm` only — AC controls output, pipe sized to requirement only |

Implemented in `tdh_service.py` → `calculate()` as `_TBS_RATED_FLOW_GPM = 15.0`.

#### NREL Solar Lookup (`nrel_service.py`)
- Calls NREL Solar Resource API with lat/lon from user input
- Returns annual GHI (kWh/m²/day) → maps to one of 7 solar zones

| Zone | Coefficient |
|---|---|
| 1 (lowest GHI) | 2.00× |
| 2 | 1.75× |
| 3 | 1.55× |
| 4 | 1.40× |
| 5 | 1.30× |
| 6 | 1.20× |
| 7 (highest GHI) | 1.10× |

#### Panel Count Sizing (`solar_service.py` + `ranking_service.py`)
```
Production path:  panels = ceil(pump_input_watts × zone_coefficient / panel_wattage)
Deadhead path:    panels = ceil(deadhead_watts / 0.35 / panel_wattage)
Final:            max(production_panels, deadhead_panels)
```

**Dual STC derating design (intentional — do NOT change without re-running all 5 validation tests):**

| Purpose | Rate | Where |
|---|---|---|
| Panel COUNT sizing | **4%** (`stc_efficiency_loss=0.04` in `calculation_request.py`) | `size_panels_for_pump()` loop |
| Achievable GPM display | **7.5%** (`_DISPLAY_STC_LOSS=0.075` in `ranking_service.py`) | Display output only |

Changing the 4% to 7.5% shifts S4 from 7 panels → 8 panels (wrong per reference PDF).

#### Wire Sizing (`wire_sizing_service.py`)

| System type | Current basis | Max voltage drop | Min AWG floor |
|---|---|---|---|
| Solar-only | pump `rated_power_w` / system Vmp | 5% | **10 AWG** |
| Generator backup | `n_panels × panel_wattage` / system Vmp | 10% | **12 AWG** |

System Vmp = n_panels × panel_vmp_v (user-entered per-panel Vmp)

#### Pump Filtering (`pump_filter_service.py`)
- Generator backup required → removes all DC-only pump SKUs (21 → 8 remaining)
- Poor water quality → removes helical rotor pumps
- Well casing diameter → removes pumps that don't fit casing

#### Pump Ranking (`ranking_service.py`)
Three recommendation categories — all currently resolve to 15TBS-4C-AC (only Phase 1 pump with a curve):
- **Economical** — fewest panels
- **Precise** — best power utilisation ratio (operating watts vs array output)
- **Premium** — highest efficiency + head margin

---

### Frontend — Fully Functional

#### Step 1 — Production & TDH
- Required flow (GPM) — required
- Daily demand (GPD) — optional, auto-calculated if blank: `GPM × 6.5 × 60 × 1.1`
- Static water level (ft), Drawdown (ft) — required; live preview shows Pumping Level
- Vertical elevation gain (ft), System pressure (PSI) — optional
- Pipe material (PVC/HDPE/Galvanized Steel/Steel/Copper), diameter (in), length (ft)

#### Step 2 — Well Characteristics
- Well casing diameter (in) — used to filter incompatible pumps
- Recovery rate (GPM) — triggers over-pumping warning if below required GPM
- Recovery unknown checkbox — triggers dry-run protection recommendation
- Poor water quality checkbox — excludes helical rotor pumps

#### Step 3 — Solar Parameters
- Panel wattage (W), Voc (Vdc), Vmp (Vdc), dimensions (L × W × H inches)
- GPS location input (lat/lon) → triggers NREL API lookup
- Own panels / own racking toggle — controls which SKUs appear in equipment list

#### Step 4 — System Controls
- Float switch checkbox
- Pressure switch checkbox + range selector (20/40, 30/50, 40/60, 50/70, 60/80, 80/100 PSI or custom)
- Generator backup checkbox
- Wire distance (ft) — for AWG calculation
- Dry-run concern toggle

#### Results Page
- **3-column layout:** Your Requirements | Recommended System | Why This Works
- **Tier tabs:** Economical / Precise / Premium (all currently resolve to 15TBS-4C-AC)
- **TDH Breakdown** — collapsible: pumping level, elevation, friction (with GPM used), pressure head, total
- **True Production banner** — achievable GPM and GPD at 7.5% STC derating
- **Wire Sizing** — collapsible: recommended AWG, voltage drop %, system voltage, operating current
- **Equipment Breakdown** — collapsible, split into TBS Equipment and Customer Provided sections
- **Action buttons:** New Calculation | Edit Inputs | Print Quote (PDF via html2pdf.js)

#### Equipment List Logic (`data/accessories.js`)

**Always included — TBS Equipment:**
| SKU | Qty | Description |
|---|---|---|
| 15TBS-4C-AC | 1 | 15GPM Stacked Impeller ACDC Solar Pump |
| TBS-4ACM | 1 | ACDC Solar Monitor (AC↔DC switching + system ON/OFF) |
| 300-1002 | 1 | 16A DC Disconnect |
| 301-1001 | 2 | 30ft PV Extension Cables (10AWG, MC4 connectors) |

**Conditional — TBS Equipment:**
| Item | Condition |
|---|---|
| `116-1038` × n panels | Only if customer does not supply own panels |
| Rack SKU (`201-1003` through `206-1003` for 1–6 panels; `203-1003` + `204-1003` for 7+) | Only if customer does not supply own racking |
| Pressure switch | When pressure switch selected (with PSI range in description) |
| `701-1003` dry well sensor | When dry-run concern checked |

**Always included — Customer Provided:**
| Item | Logic |
|---|---|
| Drop cable | 10AWG if static water level > 300 ft, else 12AWG. Always 2W+G. |
| Float switch | When float switch selected |

**Conditional — Customer Provided (only when TBS racking is used):**
| Item | Logic |
|---|---|
| Schedule 40 pipe for racking | Length = `(panelCount × panelWidth + 254) / 12` ft for 7+ panels; `panelCount × (panelWidth + 56) / 12` for 1–6 |
| Concrete for groundposts | Always when TBS racking |
| Mounting channel for TBS-4ACM + DC disconnect | Always when TBS racking |

---

## Validation Status — All 5/5 Pass

Reference: "15TBS SYSTEM INPUT SCENARIOS FINAL.pdf" (client-provided, source of truth)
Run: `cd solar_pump_calculator && .venv/bin/python test_validation_scenarios.py`

### S1 — Deep Well, Fort Davis TX 79835 (Solar-only)
**Inputs:** Static=220 ft, Drawdown=45 ft, Elevation=15 ft, Required=12 GPM, 1.25" PVC 300 ft, 400W panels Vmp=41.2V, No gen backup

| | Expected (ref PDF) | Actual | |
|---|---|---|---|
| TDH | 291 ft | 291.2 ft | ✅ |
| Friction | 11.2 ft @ 15 GPM | 11.25 ft | ✅ |
| Panels | 5 × 400W | 5 | ✅ |
| Achievable GPM | 14.8 | 14.9 | ✅ |
| Wire AWG | 10 AWG | 10 AWG | ✅ |

### S2 — Medium Well, Alamogordo NM 88310 (Solar-only)
**Inputs:** Static=150 ft, Drawdown=30 ft, Elevation=25 ft, Required=15 GPM, 1.5" PVC 700 ft, 370W panels Vmp=39.6V, No gen backup

| | Expected | Actual | |
|---|---|---|---|
| TDH | 217 ft | 217.2 ft | ✅ |
| Friction | 12.2 ft @ 15 GPM | 12.18 ft | ✅ |
| Panels | 5 × 370W | 5 | ✅ |
| Achievable GPM | 17.8 | 17.3 | ✅ (2.8% — within 10% tolerance) |
| Wire AWG | 10 AWG | 10 AWG | ✅ |

### S3 — Pressure Switch + Generator, Monte Vista CO 81132
**Inputs:** Static=180 ft, Drawdown=50 ft, Elevation=10 ft, Required=14 GPM, 1.25" PVC 250 ft, 40 PSI (30/50 switch), 370W panels Vmp=40V, Gen backup

| | Expected | Actual | |
|---|---|---|---|
| TDH | 339 ft | 338.8 ft | ✅ |
| Friction | 6.4 ft @ 14 GPM | 6.40 ft | ✅ |
| Panels | 6 × 370W | 6 | ✅ |
| Achievable GPM | 14.1 | 14.3 | ✅ (1.4%) |
| Wire AWG | 12 AWG | 12 AWG | ✅ |

### S4 — Shallow Well High Flow, Monte Vista CO 81132 (Generator backup)
**Inputs:** Static=80 ft, Drawdown=35 ft, Elevation=10 ft, Required=20 GPM, 2.0" PVC 1 ft, 235W panels Vmp=31.6V, Gen backup

| | Expected | Actual | |
|---|---|---|---|
| TDH | 125 ft | 125.0 ft | ✅ |
| Friction | 0 ft | 0.01 ft | ✅ |
| Panels | 7 × 235W | 7 | ✅ |
| Achievable GPM | 20.1 | 19.4 | ✅ (3.5%) |
| Wire AWG | 12 AWG | 12 AWG | ✅ |

### S5 — Very Deep Well, Cottonwood CA 96022 (Generator backup)
**Inputs:** Static=460 ft, Drawdown=10 ft, Elevation=10 ft, Required=10 GPM, 2.0" PVC 1 ft, 370W panels Vmp=32.4V, Gen backup, Wire=600 ft

| | Expected | Actual | |
|---|---|---|---|
| TDH | 480 ft | 480.0 ft | ✅ |
| Friction | 0 ft | 0.00 ft | ✅ |
| Panels | 7 × 370W | 7 | ✅ |
| Achievable GPM | 10.2 | 10.7 | ✅ (4.9%) |
| Wire AWG | 10 AWG | 10 AWG | ✅ |

> **Note on GPM tolerance:** Achievable GPM differences of up to ~5% are expected — bilinear interpolation on our pump curve CSV vs the manufacturer's exact curve equation. Panels, TDH, friction, and wire AWG all match exactly.

> **Reference PDF typos (do NOT fix in our output):**
> - S2: PDF says "300 ft pipe" — actual input is 700 ft; our calculation correctly uses 700 ft
> - S3: PDF says "friction @ 15 GPM" — actually @ 14 GPM (gen-backup rule); copy-paste error in PDF
> - S3: PDF says "Pressure Head: 0'" — TDH=339 requires 92.4 ft pressure head (40 PSI × 2.31); PDF error

---

## Default Panel Spec (TBS Stock, SKU 116-1038)

| Parameter | Nominal spec sheet | Measured (from reference PDF) |
|---|---|---|
| Wattage | 370W | — |
| Voc | 48V | — |
| Vmp | 40V | **32.4V** (S5) / **31.6V** (S4) — discrepancy unresolved |
| Dimensions | 80" × 40" × 1.5" | — |

> The reference PDF uses measured Vmp values (32.4V, 31.6V) that differ significantly from the nominal 40V. This affects wire AWG output across all scenarios. Needs Corey/Cody confirmation (Q2 below).

---

## Open Questions (Sent to Client — Awaiting Answers)

| # | Question | Why It Matters | Status |
|---|---|---|---|
| 1 | **Minimum well casing diameter for 15TBS-4C-AC** | Currently pump appears for any casing size. Need actual min inner diameter to show incompatibility warnings. | ⏳ Pending |
| 2 | **TBS 116-1038 panel exact Vmp and Voc** | Reference PDF implies Vmp ≈ 32.4V but spec sheet says 40V. Directly affects wire AWG on every calculation. | ⏳ Pending |
| 3 | **GPD formula — is ~3 GPD difference acceptable?** | Formula: `GPM × 6.5 × 60 × 1.1`. Some scenarios differ from reference by ~3 GPD. Raised May 29 — not formally accepted yet. | ⏳ Pending |
| 4 | **Full official Goulds Sch 40 PVC friction table** | 14 GPM row for 1.25" PVC (2.56 ft/100ft) was reverse-engineered from S3 reference, not taken from official Goulds table. | ⏳ Pending |
| 5 | **Equipment-inclusion rules document** | Corey to send doc defining which SKUs appear under which input combination. All accessories logic held until received. | ⏳ Pending (Corey to send) |
| 6 | **Drop cable AWG cutoff — is 300 ft the TBS rule?** | We switch 12AWG → 10AWG drop cable when static water level > 300 ft. Derived from voltage-drop physics, not a TBS published spec. | ⏳ Pending |
| 7 | **Racking for 8+ panels — split logic** | For 7 panels: 3+4 split. What at 8, 9, 10+ panels — 4+4, 4+5? Do rack SKUs change above 7? | ⏳ Pending |
| 8 | **Rack SKUs for 1-panel and 2-panel systems** | Generating SKU 201-1003 (1-panel) and 202-1003 (2-panel). Do these exist in TBS inventory? | ⏳ Pending |
| 9 | **Mounting channel — always required or only with TBS racking?** | TBS-4ACM mounting channel currently appears only when TBS supplies racking. Should it always appear? | ⏳ Pending |
| 10 | **Solar window — 6.5 hrs/day fixed or zone-dependent?** | GPD formula uses 6.5 hrs/day fixed for all locations. Should it vary by NREL solar zone? | ⏳ Pending |
| 11 | **Deep-well gen backup — fallback panel sizing approach** | When pump can't reach nameplate flow at very high TDH (e.g. S5 at 480 ft), panels are sized to deliver customer's required GPM. Correct approach? | ⏳ Pending |
| 12 | **Voc/Vmp — STC only or NEC 690 temperature-derated?** | Currently showing STC values (25°C). Should these be derated for local minimum temperature per NEC 690.7? Needs a design temperature input if yes. | ⏳ Pending |

---

## Meeting History

### May 29, 2026 — First Client Demo (Google Meet, ~13 min)
- Recording: https://fathom.video/share/WyiWtGxEgX_7meoD43EvviMxNHgy27W-
- TDH for S4 (125 ft) — exact match, accepted
- Voc/Vmp 0.2V difference — accepted as close enough
- GPD ~3 gallon difference — flagged, needs formal sign-off at Jun 12
- Phase 1 constraint confirmed: 15TBS-4C-AC only until equipment-inclusion doc received
- Cody out of town June 2–6
- **Action (client):** Corey to send equipment-inclusion rules doc
- **Action (dev):** Share live link by June 1 ✅

### June 12, 2026 — Follow-up Meeting
> _To be filled in — awaiting updates_

---

## Usage Log (Railway)

| Date | Activity |
|---|---|
| June 1, 17:23–17:38 | Developer ran all 5 reference scenarios manually — 5/5 correct |
| June 1, 17:37–18:13 | Developer opened UI to visually verify results |
| June 7, 17:13 | Someone opened the frontend — no calculation submitted |
| June 8 onwards | No further calculations recorded |

> As of June 22: Corey and Cody have not yet submitted a calculation through the live site.

---

## Known Issues / Notes

| Issue | Detail |
|---|---|
| No request-level logging | When `/calculate` is hit, inputs are not logged. Mid-pipeline logs (TDH, friction, NREL, wire) all present. If a production bug occurs, the user would need to repeat it. |
| Achievable GPM ~5% variance | Inherent to bilinear interpolation vs manufacturer curve. Not a bug. Within engineering tolerance. All 5 scenarios pass. |
| Pump catalog has 21 pumps, only 1 has a performance curve | 20 other pumps are envelope-only. If ever selected, they'd use a hydraulic estimate. Only 15TBS-4C-AC has a bilinear curve dataset. |
| Racking logic above 7 panels unverified | SKU split for 8+ panels has not been confirmed by client (open question Q7). |
| GPD uses fixed 6.5 hrs/day | Not NREL-zone-adjusted. Pending client confirmation (open question Q10). |

---

## Next Steps

> _To be filled in after June 12 meeting updates_
