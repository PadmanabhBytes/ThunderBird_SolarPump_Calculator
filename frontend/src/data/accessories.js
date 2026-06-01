// Rack SKU lookup by panel count
function rackSku(panelCount) {
  if (panelCount <= 5) return [{ sku: `20${panelCount}-1003`, qty: 1, description: `${panelCount} Panel TOPM Solar Rack` }]
  if (panelCount === 6) return [{ sku: '206-1003', qty: 1, description: '6 Panel TOPM Solar Rack' }]
  // 7+ panels: split into 3+4 racks
  return [
    { sku: '203-1003', qty: 1, description: '3 Panel TOPM Solar Rack' },
    { sku: '204-1003', qty: 1, description: '4 Panel TOPM Solar Rack' },
  ]
}

// Pipe length for ground mount racking.
// Formula derived from TOPM rack geometry: each panel contributes its width (in) plus 56" of
// post stock for a single rack section; split rack (7+ panels = 3+4) adds a fixed 254" overhead.
// Default panel width 34" reproduces the legacy 7.5 ft/panel (34+56=90"=7.5 ft) figure.
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
    ownPanels         = true,
    ownRacking        = false,
    dryRunConcern     = false,
    panelWattage      = 370,
    floatSwitch       = false,
    pressureSwitch    = false,
    pressureSwitchRange = '',
    panelDims         = null,   // { l, w, h } in inches
    staticWaterLevel  = 0,      // ft — used to choose drop cable AWG
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

  // ── TBS: racking hardware — only when customer doesn't supply own ─────────────
  if (!ownRacking && panelCount != null) {
    rackSku(panelCount).forEach(r =>
      tbs.push({ ...r, inStock: true, category: 'tbs' })
    )
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

  // ── Customer Provided ─────────────────────────────────────────────────────────

  // Racking materials (pipe + concrete + mounting channel) when TBS rack is used
  if (!ownRacking && panelCount != null) {
    const panelWidthIn = panelDims?.w ? Number(panelDims.w) : 34
    const pipeFt = rackingPipeFt(panelCount, panelWidthIn)
    customer.push({
      sku: null, qty: 1,
      description: `${pipeFt}' 4" Nominal (4.5" OD) Schedule 40 Pipe for Solar Racking`,
      category: 'customer',
    })
    customer.push({
      sku: null, qty: 1,
      description: 'Concrete for Setting Groundposts',
      category: 'customer',
    })
    customer.push({
      sku: null, qty: 1,
      description: 'Mounting Channel for TBS-4ACM and 300-1002 - DC Disconnect',
      category: 'customer',
    })
  }

  // Drop cable — always required, always 2W+G (single-phase 230VAC motor).
  // AWG determined by drop cable length ≈ static water level:
  //   > 300 ft → 10AWG (keeps voltage drop < 5% at 10.9A over 460+ ft)
  //   ≤ 300 ft → 12AWG (sufficient for shallower installations)
  const dropAwg = staticWaterLevel > 300 ? '10AWG' : '12AWG'
  customer.push({
    sku: null, qty: 1,
    description: `${dropAwg} 2W+G Drop Cable for run from TBS-4ACM Monitor to Motor`,
    category: 'customer',
  })

  // Float switch — when requested
  if (floatSwitch) {
    customer.push({
      sku: null, qty: 1,
      description: 'Pump Up or Pump Down Float Switch – 2 wire',
      category: 'customer',
    })
  }

  return [...tbs, ...customer]
}
