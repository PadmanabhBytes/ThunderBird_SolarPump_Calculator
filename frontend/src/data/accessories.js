// ── Solar Racking Matrix (from client deliverable, 2026-06-22) ───────────────
// Inputs:
//   A: use2_5Racking — customer wants 2.5" (TOPM-2.5IN) pipe racking
//   B: panelExceeds35 — panel width > 35"
//   n: panel count (rounds up to next table entry if not exact)
//
// Matrix 1 → A=Y, B=Y   Matrix 2 → A=Y, B=N
// Matrices 3 & 4 → A=N  (identical for both B values)

const RACK_M1 = {  // A=Y, B=Y (wants 2.5", large panels)
  1:  [{ sku: '1TOPM-2.5IN', desc: '2.5" Nominal (2.875" OD) 1 Panel Solar Rack Kit',  qty: 1 }],
  2:  [{ sku: '2TOPM-2.5IN', desc: '2.5" Nominal (2.875" OD) 2 Panel Solar Rack Kit',  qty: 1 }],
  3:  [{ sku: '203-1003',    desc: '4" Nominal (4.5" OD) 3 Panel Solar Rack Kit',       qty: 1 }],
  4:  [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 1 }],
  5:  [{ sku: '205-1003',    desc: '4" Nominal (4.5" OD) 5 Panel Solar Rack Kit',       qty: 1 }],
  6:  [{ sku: '206-1003',    desc: '4" Nominal (4.5" OD) 6 Panel Solar Rack Kit',       qty: 1 }],
  7:  [{ sku: '203-1003',    desc: '4" Nominal (4.5" OD) 3 Panel Solar Rack Kit',       qty: 1 },
       { sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 1 }],
  8:  [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 }],
  10: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 },
       { sku: '202-1003',    desc: '4" Nominal (4.5" OD) 2 Panel Solar Rack Kit',       qty: 1 }],
  12: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 3 }],
  14: [{ sku: '203-1003',    desc: '4" Nominal (4.5" OD) 3 Panel Solar Rack Kit',       qty: 2 },
       { sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 }],
  16: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 4 }],
}

const RACK_M2 = {  // A=Y, B=N (wants 2.5", small panels ≤ 35")
  1:  [{ sku: '1TOPM-2.5IN', desc: '2.5" Nominal (2.875" OD) 1 Panel Solar Rack Kit',  qty: 1 }],
  2:  [{ sku: '2TOPM-2.5IN', desc: '2.5" Nominal (2.875" OD) 2 Panel Solar Rack Kit',  qty: 1 }],
  3:  [{ sku: '3TOPM-2.5IN', desc: '2.5" Nominal (2.875" OD) 3 Panel Solar Rack Kit',  qty: 1 }],
  4:  [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 1 }],
  5:  [{ sku: '207-1003',    desc: '4" Nominal (4.5" OD) 5 Panel Solar Rack Kit - Single Post', qty: 1 }],
  6:  [{ sku: '206-1003',    desc: '4" Nominal (4.5" OD) 6 Panel Solar Rack Kit',       qty: 1 }],
  7:  [{ sku: '203-1003',    desc: '4" Nominal (4.5" OD) 3 Panel Solar Rack Kit',       qty: 1 },
       { sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 1 }],
  8:  [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 }],
  10: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 },
       { sku: '202-1003',    desc: '4" Nominal (4.5" OD) 2 Panel Solar Rack Kit',       qty: 1 }],
  12: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 3 }],
  14: [{ sku: '203-1003',    desc: '4" Nominal (4.5" OD) 3 Panel Solar Rack Kit',       qty: 2 },
       { sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 }],
  16: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 4 }],
}

const RACK_M34 = {  // A=N — no 2.5" preference (same for B=Y and B=N)
  1:  [{ sku: '201-1003',    desc: '4" Nominal (4.5" OD) 1 Panel Solar Rack Kit',       qty: 1 }],
  2:  [{ sku: '202-1003',    desc: '4" Nominal (4.5" OD) 2 Panel Solar Rack Kit',       qty: 1 }],
  3:  [{ sku: '203-1003',    desc: '4" Nominal (4.5" OD) 3 Panel Solar Rack Kit',       qty: 1 }],
  4:  [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 1 }],
  5:  [{ sku: '207-1003',    desc: '4" Nominal (4.5" OD) 5 Panel Solar Rack Kit - Single Post', qty: 1 }],
  6:  [{ sku: '206-1003',    desc: '4" Nominal (4.5" OD) 6 Panel Solar Rack Kit',       qty: 1 }],
  7:  [{ sku: '203-1003',    desc: '4" Nominal (4.5" OD) 3 Panel Solar Rack Kit',       qty: 1 },
       { sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 1 }],
  8:  [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 }],
  10: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 },
       { sku: '202-1003',    desc: '4" Nominal (4.5" OD) 2 Panel Solar Rack Kit',       qty: 1 }],
  12: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 3 }],
  14: [{ sku: '203-1003',    desc: '4" Nominal (4.5" OD) 3 Panel Solar Rack Kit',       qty: 2 },
       { sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 2 }],
  16: [{ sku: '204-1003',    desc: '4" Nominal (4.5" OD) 4 Panel Solar Rack Kit',       qty: 4 }],
}

const RACK_VALID_COUNTS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16]

function rackSkuLookup(n, use2_5, panelExceeds35) {
  if (!n || n <= 0) return []
  const key = RACK_VALID_COUNTS.find(k => n <= k)
  if (!key) return []
  if (use2_5) return (panelExceeds35 ? RACK_M1 : RACK_M2)[key] || []
  return RACK_M34[key] || []
}

// Pipe length for ground mount racking.
// Formula: each panel contributes its width (in) plus 56" of post stock per rack section;
// split rack (7+ panels = 3+4) adds 254" fixed overhead.
function rackingPipeFt(panelCount, panelWidthIn = 34) {
  const w = Number(panelWidthIn) || 34
  if (panelCount >= 7) return Math.round((panelCount * w + 254) / 12 * 10) / 10
  return Math.round(panelCount * (w + 56) / 12 * 10) / 10
}

const SYSTEM_FEATURES = {
  '15TBS-4C-AC': [
    'Stainless Steel Stacked Impeller Design – equipped to handle variable water quality',
    'Direct solar and 1ph 230VAC compatible for generator/grid backup capability',
  ],
}

export function getSystemFeatures(pumpId) {
  return SYSTEM_FEATURES[pumpId] || []
}

export function getAccessories(pumpId, panelCount, opts = {}) {
  const {
    ownPanels           = true,
    ownRacking          = false,
    use2_5Racking       = false,
    dryRunConcern       = false,
    panelWattage        = 370,
    floatSwitch         = false,
    pressureSwitch      = false,
    pressureSwitchRange = '',
    panelDims           = null,   // { l, w, h } in inches
    staticWaterLevel    = 0,      // ft — used to choose drop cable AWG
  } = opts

  if (pumpId !== '15TBS-4C-AC') return []

  const tbs      = []
  const customer = []

  // ── TBS: core pump equipment ─────────────────────────────────────────────────
  tbs.push({
    sku: '15TBS-4C-AC', qty: 1,
    description: '15GPM Stacked Impeller ACDC Solar Pump — compatible with direct solar and 1ph 230VAC',
    inStock: true, highlight: true, category: 'tbs',
  })
  tbs.push({
    sku: 'TBS-4ACM', qty: 1,
    description: 'ACDC Solar Monitor — power switching (AC↔DC) and system ON/OFF control',
    inStock: true, category: 'tbs',
  })
  tbs.push({
    sku: '300-1002', qty: 1,
    description: '16A DC Disconnect for solar power disconnect',
    inStock: true, category: 'tbs',
  })
  tbs.push({
    sku: '301-1001', qty: 2,
    description: '30ft Extension PV Cables (10AWG solar shielded, MC4 connectors)',
    inStock: true, category: 'tbs',
  })

  // ── TBS: panels — only when customer doesn't supply own ──────────────────────
  if (!ownPanels && panelCount != null) {
    tbs.push({
      sku: '116-1038', qty: panelCount,
      description: `${panelWattage}W Solar Panels (TBS stock)`,
      inStock: true, category: 'tbs',
    })
  }

  // ── TBS: racking hardware — client matrix lookup ──────────────────────────────
  if (!ownRacking && panelCount != null) {
    // Default panel width: TBS 116-1038 is 40" wide (> 35" → B=Y)
    // Custom panels use entered width; unknown → assume 40"
    const panelWidthIn   = panelDims?.w ? Number(panelDims.w) : 40
    const panelExceeds35 = panelWidthIn > 35
    const rackItems      = rackSkuLookup(panelCount, use2_5Racking, panelExceeds35)

    rackItems.forEach(r =>
      tbs.push({ sku: r.sku, qty: r.qty, description: r.desc, inStock: true, category: 'tbs', isRacking: true })
    )

    // ── Customer Provided: pipe, concrete, mounting ──────────────────────────
    const pipeFt   = rackingPipeFt(panelCount, panelDims?.w)
    const uses2_5  = rackItems.some(r => r.sku?.includes('TOPM-2.5IN'))
    const pipeSpec = uses2_5 ? '2.5" Nominal (2.875" OD)' : '4" Nominal (4.5" OD)'
    customer.push({
      sku: null, qty: 1,
      description: `${pipeFt}' ${pipeSpec} Schedule 40 Pipe for Solar Racking`,
      category: 'customer', isRacking: true,
    })
    customer.push({
      sku: null, qty: 1,
      description: 'Concrete for Setting Groundposts',
      category: 'customer', isRacking: true,
    })
    customer.push({
      sku: null, qty: 1,
      description: 'Mounting Channel for TBS-4ACM and 300-1002 - DC Disconnect',
      category: 'customer', isRacking: false,
    })
  }

  // ── TBS: pressure switch ─────────────────────────────────────────────────────
  if (pressureSwitch) {
    const rangeNote = pressureSwitchRange ? ` (${pressureSwitchRange})` : ''
    tbs.push({
      sku: null, qty: 1,
      description: `Pressure Switch${rangeNote}`,
      inStock: true, category: 'tbs',
    })
  }

  // ── TBS: dry-run protection ───────────────────────────────────────────────────
  if (dryRunConcern) {
    tbs.push({
      sku: '701-1003', qty: 1,
      description: 'Dry Well Sensor — OPTIONAL (see warning: production near well recovery rate)',
      inStock: true, warn: true, category: 'tbs',
    })
  }

  // ── Customer Provided: drop cable ────────────────────────────────────────────
  // AWG by depth: > 300 ft → 10AWG, ≤ 300 ft → 12AWG
  const dropAwg = staticWaterLevel > 300 ? '10AWG' : '12AWG'
  customer.push({
    sku: null, qty: 1,
    description: `${dropAwg} 2W+G Drop Cable for run from TBS-4ACM Monitor to Motor`,
    category: 'customer',
  })

  // ── Customer Provided: float switch ──────────────────────────────────────────
  if (floatSwitch) {
    customer.push({
      sku: null, qty: 1,
      description: 'Pump Up or Pump Down Float Switch – 2 wire',
      category: 'customer',
    })
  }

  return [...tbs, ...customer]
}
