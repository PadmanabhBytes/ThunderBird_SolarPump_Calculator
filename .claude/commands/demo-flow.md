# Demo Flow

Print the step-by-step walkthrough for demoing the solar pump calculator to Corey & Cody (Thunderbird/POP).

---

Do NOT run any commands. Just print the following guide for the user:

---

## Thunderbird Solar Pump Calculator — Demo Walkthrough

### Before the demo
1. Start the backend: `cd solar_pump_calculator && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Open http://localhost:5173 in your browser
4. Run `/check-servers` to confirm everything is up

---

### Step 1 — Production & TDH
Show the first form step. Walk through each field:
- **Required Flow (GPM):** How much water the system must deliver per minute
- **Static Water Level (ft):** Depth to resting water (from ground surface)
- **Drawdown (ft):** Additional depth depression when pump is running
- **Pipe Diameter & Length:** Affects friction loss calculation
- Point out that TDH is computed from these inputs automatically on the results page

**Use Scenario 2 as a live example:** 150 ft static, 30 ft drawdown, 15 GPM, 1.5" PVC, 700 ft pipe

---

### Step 2 — Well
- **Well Casing Diameter:** Filters out incompatible pumps (e.g., <4.5" excludes 4" pumps)
- **Recovery Rate:** If well can't keep up with pump, system warns about dry-run risk
- Explain: "If recovery is unknown, we flag it and recommend a dry-run sensor"

---

### Step 3 — Solar & Location
- **Panel source:** Default TBS 116-1038 (370W) or bring-your-own specs
- **ZIP Code lookup:** Hits NREL API to get annual average solar irradiance → determines zone coefficient (how many extra panels to add for cloudy days)
- **Operating season:** Year-round vs summer/winter only → affects effective daily production

**Enter ZIP 88310** (Alamogordo NM) and hit "Look up" to show the live GPS resolution

---

### Step 4 — Controls
- **Float switch:** Adds to equipment list; stops pump when tank is full
- **Pressure switch:** Adds pressure switch to parts list with the selected PSI range (30-50, 40-60, etc.)
- **Generator backup:** Changes solar sizing (uses zone coefficient instead of 1×) and wire sizing method

---

### Results page
Walk through the output sections:
1. **TDH Breakdown** — shows each component (pumping level, elevation, friction, pressure head, safety factor)
2. **Solar Sizing** — panel count and governing path (production vs deadhead)
3. **Pump Recommendation** — 15TBS-4C-AC, achievable GPM, daily GPD
4. **Wire Sizing** — AWG recommendation with voltage drop calculation
5. **Equipment List** — TBS and non-TBS items, SKUs where available

Show the **Edit Inputs** button — user can go back and tweak numbers without losing their place.

---

### Key talking points for Corey & Cody
- All 5 reference scenarios match the client-provided PDF to within ±5% on TDH, panels, GPM, and AWG
- The 7.5% STC efficiency derating is applied consistently (they confirmed this in the May 29 meeting)
- Friction calculation uses the Goulds Pump table they provided
- Location-based solar sizing via NREL is live (not a hardcoded number)
- Generator backup correctly uses zone-based array sizing now (previously was 1× — fixed)

---

### What's NOT in Phase 1 yet (don't demo these)
- Multiple pump SKUs (waiting for equipment-rules doc from Corey)
- PDF quote export
- Saved calculation history
- Racking/pipe-length calculation from panel dimensions
