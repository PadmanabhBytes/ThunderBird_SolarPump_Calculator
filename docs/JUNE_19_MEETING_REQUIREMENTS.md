# June 19, 2026 — Client Requirements & Changes

**Source:** "Solar Calculator Comments - 6.19.25.pdf" + meeting transcript  
**Clients:** Corey Pratt & Cody Burgdorff (Thunderbird Solar / POP)  
**Status:** Requirements captured — implementation pending  

---

## Overview

This document captures all change requests and new requirements from the June 19 meeting. This represents a substantial Phase 2 expansion of the calculator. Items marked **[PENDING FROM TBS]** require additional materials from the client before implementation.

---

## 1. Location / System Operating Window — Move to Step 1

**Request:** Shift the location/operating window input to the **top of the calculator** so it is the first user input. It must be available early to drive the GPD calculation in subsequent steps.

**Operating Window options (unchanged):**
- Year Round: annual average data
- Summer Use Only: April–September average
- Winter Use Only: October–March average

**Impact:** Location (lat/lng or ZIP) and operating season must be captured in Step 1, before pipe, well, or flow inputs. This is a UX reordering, not a calculation change.

---

## 2. Production Calculation — New GPD Logic with Accept/Reject Flow

### Step 1: Calculate Proposed GPD

After the customer enters their required GPM, the calculator computes a proposed GPD using the TBS production formula:

```
GPD = GPM_INPUT × 6.5 × 60 × 1.1 × SOLAR_ZONE_COEFF
```

**Solar Zone Coefficient table** (derived from location data entered in Step 1):

| Zone | Coefficient |
|------|------------|
| 5    | 1.08       |
| 4    | 1.00       |
| 3    | 0.92       |
| 2    | 0.85       |
| 1    | 0.78       |

> **Note:** These zone coefficients are different from the NREL-derived zone coefficients used internally for panel count sizing. These are TBS-specific GPD production coefficients.

### Step 2: Present GPD to Customer

Display: _"Based on your requested flow rate, the estimated daily water production is **X GPD**. Is this acceptable?"_

Options: **Yes** / **No**

### Step 2A: Customer Accepts GPD (Yes)

- Calculated GPD becomes the production target.
- Calculator proceeds to system sizing.
- **Single results category** displayed.
- Results prioritized per prioritization logic (Section 9).

### Step 2B: Customer Rejects GPD (No)

- Prompt customer to enter a desired GPD value.
- Calculator generates **two independent result categories**:
  - **Category 1 — Closest to Requested GPM**: systems optimized to match the customer's originally requested flow rate.
  - **Category 2 — Closest to Requested GPD**: systems optimized to match the customer-entered GPD target.
- Each category independently applies all sizing, filtering, and prioritization logic.

**Implementation note:** The existing `daily_gallons_per_day` field in the response and the GPD formula in `ranking_service.py` must be replaced with this new formula and flow.

---

## 3. TDH Calculator — Direct Input + "Help Me Calculate" Mode

**Request:** Offer the customer the ability to input TDH directly. If they don't know it, a checkbox opens the sub-fields.

### UI Change

- **TDH field**: direct numeric input (primary field, always visible).
- **Checkbox**: "Help Me Calculate" — when checked, reveals sub-fields below.
- If TDH is entered directly: use that number as-is; skip sub-field calculations.
- If "Help Me Calculate" is checked: use existing sub-fields to compute TDH.

### Sub-fields (shown when "Help Me Calculate" is checked) — all **required**:

| Field | Notes |
|-------|-------|
| Static water level (ft) | Currently required |
| Expected drawdown (ft) | Currently required |
| Vertical elevation (ft) | Make required (currently optional; user enters 0 if not needed) |
| System pressure (psi) | Make required (currently optional; user enters 0 if not needed) |

### Friction Loss Sub-section (within "Help Me Calculate")

Add a checkbox: _"Is there a pipe run between the well head and the destination?"_

- **If No:** friction = 0; pipe fields hidden.
- **If Yes:** show required fields:
  - Pipe material
  - Nominal pipe diameter (in)
  - Pipe run length — horizontal/linear (ft)

> **Note:** The current Step 1 always shows pipe fields. This becomes a conditional block under the "Help Me Calculate" checkbox.

---

## 4. Recovery Rate — Required with Unknown Fallback

**Change:** Recovery rate must be a **required field** unless the customer checks an "Unknown" checkbox.

### Logic:

```
If "Unknown" is NOT checked:
    Recovery rate is required numeric input.
    Apply recovery rate filters per pump category (Section 9).

If "Unknown" IS checked:
    Show question: "Is there any concern of the well running dry?"
    
    If No:
        Exclude recovery rate filters from sizing logic.
    
    If Yes:
        Apply recovery rate filter as if rate were very low.
        Display all applicable warnings.
```

---

## 5. Well Casing — 4" Warning (not exclusion)

**Change:** When customer selects a 4" inner diameter casing with an AC/DC 4" pump option:

> Add a **warning** (not a hard exclusion): _"Warning: This pump is designed for 4" casing. Ensure actual inner casing diameter meets minimum clearance requirements."_

Do **not** prevent the customer from proceeding; only display the warning.

---

## 6. Generator / Grid Backup — Separate Checkboxes + Popups

### Current state
Single checkbox for "generator backup required."

### New state
Split into **two separate, mutually exclusive checkboxes**:
- `[ ] Generator backup`
- `[ ] Grid (utility) backup`

### Generator backup popup

When generator is checked, show popup:

> _"AC/DC TBS Solar Products require 1ph 230VAC power backup for optimal performance."_

### Grid backup popup

When grid is checked, show **two** messages in popup:

> _"AC/DC TBS Solar Products require 1ph 230VAC power backup for optimal performance."_
>
> _"An AC surge protector is required for grid use — this SKU will be added to your final system selections."_

**AND** automatically add **SKU 344-1001** (300VAC AC Surge Protection Device) to the output parts list for any grid-backup system.

---

## 7. Solar Racking / Panel Data

### 2.5" Pipe Racking Checkbox

Add checkbox: _"If viable, would you like to use our racking kit designed around 2.5" schedule 40 pipe (used for both ground post and crossbeam)?"_

- **Yes** or **No** answer qualifies which racking matrix to use.

### Panel Width — Racking Matrix Qualifier

Panel width (from customer input or TBS default) determines which racking matrix applies:

- Width > 35": use wide-panel racking matrix
- Width ≤ 35": use narrow-panel racking matrix

### Racking Matrices

**[PENDING FROM TBS]** — Corey/Cody to supply the actual racking selection matrices. The matrices determine:
- Crossbeam length
- Number of ground posts required (single vs. two post rack, etc.)
- Additional rack configurations

The racking result feeds into the **racking complexity adjustment** in the prioritization logic (Section 9.5).

---

## 8. System Controls — Diagrams + Updated Logic

### Diagram Links

For each system control option, add a clickable link that opens a diagram popup/modal.

**[PENDING FROM TBS]** — Three main system diagrams to be supplied by Corey/Cody.

### Float Switch (Electrical Float)

When selected, insert informational comment:

> _"All AC/DC TBS products can accept pump-up or pump-down 2-wire floats. DC ONLY TBS products will include a 3-wire float switch as part of the sales package."_

### Pressure Switch (Irrigation / Cabin / House)

When selected:
- Show existing PSI dropdown — make it **required**.
- Cross-validate with "System Pressure" field in TDH inputs:
  - If top-end shutoff PSI ≠ System Pressure field (and TDH was not entered directly):
    - Flag the mismatch with warning: _"These fields must match. Ex: System pressure field = 40 psi; pressure switch selection = 30/50 psi — you must update the system pressure field to equal 50 psi before proceeding."_
  - Customer must resolve before continuing.

### Pressure Switch + Mechanical Float

When **both** pressure switch AND mechanical float are selected:

1. **Add 15 PSI to the TDH calculation.**
2. **PSI replaces downstream head** in TDH: deadhead TDH includes PSI, subtract downstream head from pressure-switch-to-tank path.
3. Use downstream head without pressure switch cutoff to calculate GPM and GPD for system sizing.

**Shutoff PSI Recommendation:**

- If customer entered TDH directly:
  > _"Shutoff PSI must exceed the PSI required to move water from the pressure switch location to the tank. Please select a PSI rating that meets this requirement and include that rating below."_

- If customer used "Help Me Calculate" sub-fields, suggest:
  ```
  Shutoff PSI Rating = ROUNDUP(Elevation_Gain + Friction_Loss + 10 PSI, -1)
  ```

---

## 9. Wire Sizing — New Formulas

Replace current wire sizing logic with the following TBS formulas.

### Core Formulas

**Operating array voltage:**
```
Vmp_Array = Panel_Count_Series × Panel_Vmp × 0.95
```
(0.95 is a temperature/operating derate factor)

**System power (capped at pump max watts):**
```
System_Power = MIN(Panel_Count_Total × Panel_Watts, Pump_Max_Watts)
```

**Pump max wattage caps by SKU:**

| SKU | Max Watts |
|-----|-----------|
| 3TBS-4H-AC | 900 W |
| 6TBS-4H-AC | 1,200 W |
| 12TBS-4H-AC | 1,400 W |
| 7TBS-4C-AC | 1,800 W |
| 13TBS-4C-AC | 600 W |
| 15TBS-4C-AC | 3,000 W |
| 25TBS-4C-AC | 1,200 W |
| 40TBS-4C-AC | 1,800 W |

**Amp draw (capped at 12A):**
```
Amp_Draw = MIN((System_Power / Vmp_Array) × 1.05, 12)
```
(1.05 = safety factor; 12A = maximum current cap)

**Wire resistance constants:**

| Gauge | Ohm/ft |
|-------|--------|
| #14 AWG | 0.002525 |
| #12 AWG | 0.001588 |
| #10 AWG | 0.000999 |
| #8 AWG  | 0.0006282 |
| #6 AWG  | 0.0003951 |

**Max wire length per gauge:**
```
Max_Length_ft = ROUNDDOWN((Allowed_Voltage_Drop × Vmp_Array) / (2 × Amp_Draw × Wire_Resistance_Ohm_Per_Ft), -1)
```
(÷2 accounts for round-trip conductor distance; result rounded down to nearest 10 ft)

### Parallel Panel Connections

When panels are wired in parallel strings:
```
Total_Panel_Count = Series_Count × Parallel_Strings
Vmp_Array = Series_Count × Panel_Vmp × 0.95
System_Power = MIN(Total_Panel_Count × Panel_Watts, Pump_Max_Watts)
Amp_Draw = MIN((System_Power / Vmp_Array) × 1.05, 12)
```

---

## 10. Pump System Sizing — Categories, Filters, Prioritization

### 10.1 Three Product Categories

All qualifying systems are grouped into one of three categories:

| Category | Type | Examples |
|----------|------|---------|
| **A** | Stacked Impeller Pump + **External Drive** | TBS AC/DC Systems, VFD-Controlled Systems |
| **B** | Stacked Impeller Pump + **Internal Motor Drive** | Integrated Controller Motor Systems |
| **C** | **Helical Rotor Pump** | Helical w/ External Drive, Helical w/ Internal Drive |

For prioritization, all helical designs are treated as a single category regardless of drive type.

### 10.2 Candidate System Generation

Before prioritization, the calculator generates **all systems** capable of meeting:
1. TDH requirement
2. Production requirement (GPD)
3. Applicable electrical requirements

Only after all viable systems are identified is prioritization applied.

### 10.3 Primary Prioritization Logic

Priorities are based on **pump category** and **solar panel count**. Goal: prefer External Drive, but not at the cost of more than 2 extra panels over Helical.

#### External Drive (A) vs. Helical (C)

External Drive is preferred when:
```
External_Panels ≤ Helical_Panels + 2
```

| External | Helical | Selected |
|----------|---------|----------|
| 8 panels | 7 panels | External ✓ |
| 9 panels | 7 panels | External ✓ |
| 10 panels | 7 panels | Helical ✓ |

#### External Drive (A) vs. Internal Drive (B)

External Drive is preferred **only when panel counts are equal**:
```
External_Panels = Internal_Panels → External wins
External_Panels > Internal_Panels → Internal wins (any advantage)
```

| External | Internal | Selected |
|----------|----------|----------|
| 8 panels | 8 panels | External ✓ |
| 9 panels | 8 panels | Internal ✓ |
| 8 panels | 7 panels | Internal ✓ |

#### Internal Drive (B) vs. Helical (C)

Internal Drive is preferred when:
```
Internal_Panels ≤ Helical_Panels + 1
```

| Internal | Helical | Selected |
|----------|---------|----------|
| 8 panels | 8 panels | Internal ✓ |
| 9 panels | 8 panels | Internal ✓ |
| 10 panels | 8 panels | Helical ✓ |

### 10.4 Racking Complexity Adjustment

If a Helical solution requires **fewer ground posts** than both External Drive and Internal Drive candidates:

- **External vs. Helical** threshold reduced by 1 panel:
  - Normal: External ≤ Helical + 2
  - Adjusted: External ≤ Helical + 1

- **Internal vs. Helical** threshold reduced by 1 panel:
  - Normal: Internal ≤ Helical + 1
  - Adjusted: Internal ≤ Helical + 0 (equal panel count only)

**Goal:** give additional credit to solutions that reduce ground posts, rack complexity, installation labor, and material cost.

### 10.5 Wire Gauge Feasibility Filter

**Purpose:** Prevent recommending systems that require unusually large conductors on short runs.

```
IF Required_Wire_Size = 8 AWG AND Wire_Run_Distance < 300 ft
    THEN Exclude system
```

8 AWG systems remain valid when `Wire_Run ≥ 300 ft`.

### 10.6 Recovery Rate Filters (per category)

Applied after the recovery rate logic in Section 4.

| Category | Rule | Example (Recovery = 5 GPM) |
|----------|------|---------------------------|
| **C — Helical** | Pump GPM ≤ Recovery Rate | Allow ≤ 5.0; Reject > 5.0 |
| **B — Internal Drive** | Pump GPM ≤ Recovery Rate + 2.5 | Allow ≤ 7.5; Reject > 7.5 |
| **A — External Drive** | Pump GPM ≤ Recovery Rate × 2.4 | Allow ≤ 12.0; Reject > 12.0 |

### 10.7 Recovery Rate Warnings

Passing the filter does not eliminate warnings. A warning is shown when `Pump GPM > Recovery Rate`:

**Helical (C):**
> _"Pump output exceeds the reported well recovery rate. Continuous operation may result in the well being pumped down."_

**Internal Drive (B):**
> _"Pump output exceeds the reported well recovery rate. This system may require storage capacity, timer controls, or additional well recovery evaluation."_

**External Drive (A):**
> _"Pump output exceeds the reported well recovery rate. Variable speed operation may allow successful operation; however, storage capacity and well recovery characteristics should be reviewed before installation."_

---

## 11. Recommended Selection Process (Execution Order)

The calculator shall execute in this order:

1. Receive customer inputs.
2. Calculate proposed GPD.
3. Determine single-output vs. dual-output workflow (Section 2).
4. Generate all candidate systems meeting TDH and production requirements.
5. Apply wire gauge feasibility filter (Section 10.5).
6. Apply recovery rate filter (Section 10.6).
7. Apply panel count prioritization (Section 10.3).
8. Apply racking complexity adjustment (Section 10.4).
9. Select highest-priority system(s).
10. Apply recovery rate warnings where applicable (Section 10.7).
11. Present final recommendation(s) to customer.

---

## 12. Pending Items (Blocked on TBS)

| Item | Section | Status |
|------|---------|--------|
| Racking matrices (2.5" pipe + panel width variants) | §7 | Awaiting from Corey/Cody |
| Three main system control diagrams | §8 | Awaiting from Corey/Cody |
| Full Phase 2 pump catalog (new SKUs beyond 15TBS-4C-AC) | §10 | Awaiting from Corey/Cody |

Do not implement racking matrix logic or system control diagram links until these materials are received.

---

## 13. Summary of Backend Changes Required

| Area | Change |
|------|--------|
| GPD formula | Replace current formula with `GPM × 6.5 × 60 × 1.1 × zone_coeff` using new zone coefficients |
| GPD accept/reject flow | New dual-output path in calculation_controller.py |
| TDH direct input | Accept raw TDH; bypass sub-field calc if provided |
| Friction conditional | Only calculate if pipe-run checkbox = Yes |
| Recovery rate | Required field; Unknown checkbox → dry-well concern logic |
| Generator/Grid | Split into two flags; SKU 344-1001 auto-add for grid |
| Pressure switch + float | +15 PSI to TDH; downstream head handling |
| Wire sizing | Full formula replacement (Vmp_Array, System_Power, Amp_Draw, Max_Length) |
| Pump categories | Implement A/B/C categorization in pump catalog and ranking_service |
| Prioritization logic | New multi-category comparison with panel-count thresholds |
| Racking adjustment | Ground-post count modifies prioritization thresholds |
| Wire feasibility filter | Exclude 8 AWG systems on runs < 300 ft |
| Recovery filters | Per-category thresholds (×1.0, +2.5, ×2.4) |
| Pump max watts | Add `max_watts` field to pump catalog CSV |
| SKU 344-1001 | Add to parts catalog; auto-include for grid systems |

## 14. Summary of Frontend Changes Required

| Area | Change |
|------|--------|
| Step ordering | Location/operating window moves to Step 1 |
| GPD accept/reject | New UI prompt + Yes/No + conditional GPD input field |
| TDH field | Direct input + "Help Me Calculate" checkbox that reveals sub-fields |
| Friction conditional | Checkbox gating pipe-run fields |
| Recovery rate | Required + Unknown checkbox + dry-well question |
| Well casing | 4" warning display |
| Generator vs Grid | Two separate checkboxes with popup dialogs |
| Solar racking | 2.5" pipe checkbox |
| System controls | Diagram links/popups per control type |
| Pressure switch validation | Cross-validate PSI fields; block on mismatch |
| Pressure switch + float | Show +15 PSI notice and shutoff PSI recommendation |
| Wire sizing output | Display new wire sizing output fields (Vmp_Array, Amp_Draw, Max_Length per gauge) |
| Dual results display | Two result categories when customer rejects GPD |
| Recovery warnings | Per-category warnings on results page |
| Grid SKU | Show SKU 344-1001 in parts list for grid systems |
