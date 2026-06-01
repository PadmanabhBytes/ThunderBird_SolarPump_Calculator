# Pump Performance Dataset Format

This directory holds one CSV file per pump SKU.

**Filename convention:** `<pump_id>.csv` — the stem must exactly match the  
`pump_id` field in `pump_catalog.csv` (e.g. `P001.csv` for pump `P001`).

Files whose name begins with `_` (e.g. `_template.csv`) are ignored by the  
loader and may be used freely as templates or documentation.

---

## Required CSV format

```
head_ft,<watts_1>,<watts_2>,...,<watts_n>
<value>, <gpm>,   <gpm>,  ..., <gpm>
<value>, <gpm>,   <gpm>,  ..., <gpm>
...
```

| Element | Description |
|---|---|
| `head_ft` | Required first column. Operating head in **US feet** (float). |
| `<watts_N>` | Remaining column headers. Each is a **power level in watts** (numeric string, e.g. `100`, `250`, `400`). |
| Cell values | Achievable flow in **US GPM** at that (head, power) combination. Use `0.0` for no-flow / shutoff conditions. |

---

## Rules

1. **At least 2 head rows are required** — the engine uses piecewise-linear  
   interpolation and cannot operate on a single-point dataset.

2. **All cells must be filled.** Do not leave blank cells. Use `0.0` where  
   the pump delivers no flow.

3. **GPM must be ≥ 0.** Negative values will cause the file to be rejected.

4. **Power column headers must be strictly numeric** (integer or float watts).  
   Do not include units in the header (write `400` not `400W`).

5. **Rows may be in any order** — the loader sorts by `head_ft` ascending  
   before use.

6. **Lines beginning with `#` are treated as comments** and are ignored.

7. **Power levels must be > 0 W.**

---

## Validation warnings (non-fatal)

The loader emits warnings for the following — the dataset is still used:

- GPM that increases as head increases in a given power column  
  *(typical pump behaviour is GPM decreases as head rises)*
- GPM that decreases as power increases at a fixed head  
  *(typical behaviour is more power → more flow)*
- Duplicate `head_ft` values
- Power levels ≤ 0 W (data quality issue)

Warnings are visible in startup logs and in the  
`evaluation_warnings` field of the API response.

---

## Out-of-range queries

When a requested TDH is outside the dataset's `head_ft` range:

- The result is **clamped to the boundary** (no extrapolation).
- An `evaluation_warnings` entry is added to the API response.
- The evaluation is still performed and returned.

To avoid clamping, ensure the dataset covers the full expected operating  
range plus a margin above the expected TDH.

---

## Example (minimal valid dataset)

```csv
# Pump P001 — Example Brand, Model XYZ
# Datasheet: [reference URL or document name]
# Units: head_ft (US ft), power columns (W), GPM (US gal/min)
head_ft,100,200,400
20.0,2.5,4.8,8.1
60.0,2.1,4.0,6.9
100.0,1.4,2.8,4.8
140.0,0.5,1.2,2.1
180.0,0.0,0.0,0.3
```

---

## Catalog optional columns

`pump_catalog.csv` accepts the following optional columns for AC/DC  
compatibility filtering. They are not required — the loader uses safe  
defaults when absent:

| Column | Type | Default | Description |
|---|---|---|---|
| `voltage_class` | string | auto-inferred | `dc`, `ac`, `hybrid`, or `unknown` |
| `requires_inverter` | bool (0/1) | `False` | Set `1` if pump requires an AC inverter when driven by PV |
| `mppt_compatible` | bool (0/1) | `False` | Set `1` if pump accepts direct MPPT controller input |

---

## What happens when no dataset file exists

If a pump has no `.csv` in this directory, the evaluation engine falls back  
to **catalog envelope bounds** (`max_head_ft`, `max_flow_gpm` from the catalog).

In envelope mode:
- Operating wattage is **unknown** (`null` in the API response)
- `curve_based_evaluation` = `false`
- An `evaluation_warnings` entry explains the degraded result
- Solar panel count is estimated from a hydraulic power formula (not measured data)

Envelope mode is useful for initial catalog browsing but **should not be used  
for final system specification.** Add a real dataset for each pump that will  
be specified in a delivered system.
