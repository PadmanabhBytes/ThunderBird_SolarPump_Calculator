# Thunderbird Solar Pumps — Calculator Project

## What this is

A solar pump sizing calculator for **Thunderbird Solar / POP** (client: Corey Pratt & Cody Burgdorff).
Given well depth, flow requirement, pipe specs, and location, it outputs: TDH, panel count, achievable GPM,
daily GPD, wire AWG, and a full parts/equipment list.

**Phase 1 constraint:** One pump SKU only — **15TBS-4C-AC**. Do not add new pumps until Corey sends the
equipment-inclusion rules document and both sides sign off (next milestone: Jun 12 meeting).

---

## Architecture

```
frontend/          (React + Vite, port 5173)
  └─ src/
      ├─ App.jsx                  ← top-level routing (form → results)
      ├─ CalculatorForm.jsx       ← 4-step wizard with validation
      ├─ ResultsPage.jsx          ← output display, equipment list, wire sizing
      ├─ steps/
      │   ├─ Step1Flow.jsx        ← GPM, TDH inputs (static level, drawdown, pipe)
      │   ├─ Step2Well.jsx        ← well casing, recovery rate
      │   ├─ Step3Solar.jsx       ← panel specs, ZIP/GPS location, operating season
      │   └─ Step4Controls.jsx   ← float switch, pressure switch (range select/custom)
      └─ api/
          └─ calculator.js        ← POST to /api/v1/calculations/calculate

solar_pump_calculator/    (FastAPI, port 8000)
  ├─ app/
  │   ├─ main.py                  ← FastAPI app entry, CORS, router mount
  │   ├─ controllers/
  │   │   └─ calculation_controller.py  ← full pipeline (TDH→solar→pump→wire)
  │   ├─ services/
  │   │   ├─ tdh_service.py       ← TDH = pumping level + elevation + friction + pressure head
  │   │   ├─ friction_service.py  ← Goulds table lookup + interpolation
  │   │   ├─ solar_service.py     ← panel count via production & deadhead paths
  │   │   ├─ nrel_service.py      ← NREL API → GHI → solar zone coefficient
  │   │   ├─ ranking_service.py   ← bilinear pump curve → panels, achievable GPM
  │   │   ├─ wire_sizing_service.py  ← AWG via voltage-drop, min 12 AWG floor
  │   │   └─ pump_eval_service.py ← pump curve interpolation
  │   └─ models/
  │       ├─ calculation_request.py   ← Pydantic request model
  │       └─ calculation_response.py  ← Pydantic response model
  ├─ data/
  │   ├─ pumps/
  │   │   ├─ pump_catalog.csv         ← pump specs (rated_power_w, voltage, etc.)
  │   │   └─ performance/
  │   │       └─ 15TBS-4C-AC.csv      ← bilinear pump curve (head vs wattage → GPM)
  │   └─ friction/
  │       └─ pvc.csv                  ← Goulds Sch 40 PVC friction table (ft/100ft)
  └─ test_validation_scenarios.py     ← 5 reference scenarios; must all PASS
```

---

## How to run

**Backend** (from `solar_pump_calculator/`):
```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend** (from `frontend/`):
```bash
npm run dev
```

**Run validation tests** (from `solar_pump_calculator/`):
```bash
.venv/bin/python test_validation_scenarios.py
```

**Public URL via ngrok** (in a separate terminal):
```bash
ngrok http 5173
```

---

## Key engineering formulas

### TDH (Total Dynamic Head)
```
TDH = (Static Water Level + Drawdown + Discharge Elevation + Friction Loss + Pressure Head) × Safety Factor
Pressure Head (ft) = PSI × 2.31
```

### Friction loss
- Goulds Sch 40 PVC table: `data/friction/pvc.csv` (ft per 100 ft)
- Service rounds the lookup GPM UP to the next table breakpoint (ceiling lookup, not interpolation down)
- **Known quirk:** 14 GPM row for 1.25" PVC was missing from the official table; reference value 2.56 ft/100ft has been added

### Friction GPM rule — TBS methodology (critical)
- **Solar-only systems:** friction is calculated at `max(required_gpm, 15.0)` — the pump's rated output (15TBS-4C-AC rated flow). The pipe must handle full pump output in good solar.
- **Generator-backup systems:** friction is calculated at `required_gpm` only. AC backup controls output.
- Implemented in `tdh_service.py` → `calculate()` as `_TBS_RATED_FLOW_GPM = 15.0`.
- Effect: S1 solar-only 12 GPM required → friction @ 15 GPM → 11.2 ft → TDH = 291 ft ✓

### STC efficiency derating — dual-rate design (intentional)
- **Panel COUNT sizing** (`stc_efficiency_loss` field, default 0.04): uses **4%** derating in `size_panels_for_pump` loop to find minimum n panels. Conservative — ensures the panel count is sufficient.
- **Achievable GPM display** (`_DISPLAY_STC_LOSS = 0.075` in `ranking_service.py`): always uses **7.5%** derating. Shows realistic real-world output after typical losses.
- Do NOT change either value without re-running all 5 validation scenarios. Changing panel-count derating from 4% to 7.5% shifts S4 from 7 → 8 panels (wrong).

### Solar panel count
```
Production path:  panels = ceil(pump_input_watts × solar_zone_coefficient / panel_wattage)
Deadhead path:    panels = ceil(deadhead_watts / 0.35 / panel_wattage)
Final:            max(production_panels, deadhead_panels)
```
- Zone coefficient from NREL GHI lookup: Zone 1=2.00×, 2=1.75×, 3=1.55×, 4=1.40×, 5=1.30×, 6=1.20×, 7=1.10×

### Wire AWG sizing
Two strategies based on system type:
- **Solar-only (no generator backup):** current = pump `rated_power_w` / system Vmp, voltage drop ≤ 5%, min floor **10 AWG**
- **With generator backup:** current = (n_panels × panel_wattage) / system Vmp, voltage drop ≤ 10%, min floor **12 AWG**
- System Vmp = n_panels × panel_vmp_v

---

## Pump curve data (15TBS-4C-AC)

`data/pumps/performance/15TBS-4C-AC.csv` — rows are head_ft breakpoints, columns are wattage levels.
Values are achievable GPM at that (head, wattage) operating point.
The ranking service uses bilinear interpolation to find:
- minimum wattage to achieve required GPM at TDH → number of panels
- achievable GPM at full array wattage after 7.5% STC derating

---

## Default panel (TBS stock, SKU 116-1038)
- Wattage: 370 W
- Voc: 48 V
- Vmp: 40 V  *(actual measured ≈ 32.4 V — confirm exact value with Corey/Cody)*
- Dimensions: 80" × 40" × 1.5"

---

## Validation test status

All 5 reference scenarios from the client PDF **must pass** before any demo or client share.
Run `/run-tests` or `cd solar_pump_calculator && .venv/bin/python test_validation_scenarios.py`.

Verified reference outputs (from "15TBS SYSTEM INPUT SCENARIOS FINAL.pdf" — source of truth):

| Scenario | Location | TDH (ft) | Friction (ft) | Panels | Achievable GPM | Wire AWG |
|---|---|---|---|---|---|---|
| S1 — Deep Well, solar-only | Fort Davis TX 79835 | 291 | 11.2 @ 15 GPM | 5 × 400W | 14.8 | 10 AWG |
| S2 — Medium Well, solar-only | Alamogordo NM 88310 | 217 | 12.2 @ 15 GPM | 5 × 370W | 17.8 | 10 AWG |
| S3 — Pressure switch + gen backup | Monte Vista CO 81132 | 339 | 6.4 @ 14 GPM | 6 × 370W | 14.1 | 12 AWG |
| S4 — Shallow well, gen backup | Monte Vista CO 81132 | 125 | 0 | 7 × 235W | 20.1 | 12 AWG |
| S5 — Very deep, gen backup | Cottonwood CA 96022 | 480 | 0 | 7 × 370W | 10.2 | 10 AWG |

Notes on reference PDF typos (do NOT "fix" these in our output — they are errors in the source doc):
- S2: reference text says "300 ft pipe" but inputs are 700 ft; friction is correctly calculated at 700 ft
- S3: reference text says "friction @ 15 GPM" but it is actually @ 14 GPM (required flow, gen-backup rule); the text is a copy-paste error
- S3: reference text says "Pressure Head: 0'" but TDH=339 requires 92.4 ft of pressure head (40 PSI × 2.31); the "0'" is an error

Verified panel Vmp values (from reference PDF, not from default spec sheet):
- S1: 5 × 41.2 V = 206 V system Vmp (400W panels)
- S4: 7 × 31.6 V = 221.2 V system Vmp (235W panels)
- S5: 7 × 32.4 V = 226.8 V system Vmp (370W panels — actual measured Vmp, not nominal 40V)

---

## Client context

- **Client:** Corey Pratt & Cody Burgdorff (Thunderbird Solar / POP)
- **Next meeting:** June 12, 2026
- **Pending from client:** Equipment-inclusion rules doc (which SKUs appear under which scenario)
- **Do NOT:** Add new pump SKUs, change accessories logic, or push major changes without client sign-off
- **Open questions:** Exact Vmp/Voc for TBS 116-1038 panel; 3W vs 2W drop cable convention for solar-only systems

---

## Code conventions

- Backend: Python, Pydantic v2, FastAPI. Async where needed (NREL API calls).
- Frontend: React functional components, hooks only, no Redux. CSS modules per component (`Component.css`).
- No TypeScript (plain JSX).
- No comments unless the WHY is non-obvious. No docstrings on obvious functions.
- Do not add features beyond what the current task requires.
