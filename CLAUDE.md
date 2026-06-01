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
- Service interpolates between GPM breakpoints (power-law, not linear)
- **Known quirk:** 14 GPM row for 1.25" PVC was missing from the official table; reference value 2.56 ft/100ft has been added

### Solar panel count
```
Production path:  panels = ceil(pump_input_watts × solar_zone_coefficient / panel_wattage)
Deadhead path:    panels = ceil(deadhead_watts / 0.35 / panel_wattage)
Final:            max(production_panels, deadhead_panels)
```
- Zone coefficient from NREL GHI lookup: Zone 1=2.00×, 2=1.75×, 3=1.55×, 4=1.40×, 5=1.30×, 6=1.20×, 7=1.10×

### Wire AWG sizing
Two strategies based on system type:
- **Solar-only (no generator backup):** current = pump `rated_power_w` / system Vmp, voltage drop ≤ 5%
- **With generator backup:** current = (n_panels × panel_wattage) / system Vmp, voltage drop ≤ 10%
- Minimum floor: 12 AWG (NEC standard for submersible pump drop cables)
- System Vmp = n_panels × panel_vmp_v

### STC efficiency derating
Always 7.5% (previously conditional on generator backup — now fixed to always use 7.5%).

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

| Scenario | Location | Key inputs | Status |
|---|---|---|---|
| S1 | Fort Davis TX | 220 ft static, 12 GPM, 1.25" PVC 300 ft | PASS |
| S2 | Alamogordo NM | 150 ft static, 15 GPM, 1.5" PVC 700 ft | PASS |
| S3 | Monte Vista CO | 180 ft static, 14 GPM, generator backup, pressure switch 30/50 psi | PASS |
| S4 | Monte Vista CO | 80 ft static, 20 GPM, generator backup, 235W panels | PASS |
| S5 | Cottonwood CA | 460 ft static, 10 GPM, generator backup, 600 ft wire | PASS |

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
