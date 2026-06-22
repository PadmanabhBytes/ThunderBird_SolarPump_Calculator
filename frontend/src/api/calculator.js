const BASE = (import.meta.env.VITE_API_URL || '') + '/api/v1/calculations'

export async function runCalculation(formData) {
  const body = buildRequestBody(formData)
  const res = await fetch(`${BASE}/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    let message
    if (Array.isArray(err.detail)) {
      message = err.detail
        .map(e => {
          if (typeof e === 'string') return e
          const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : 'field'
          return `${field}: ${e.msg || JSON.stringify(e)}`
        })
        .join(' | ')
    } else {
      message = err.detail || `HTTP ${res.status}`
    }
    throw new Error(message)
  }
  return res.json()
}

function num(val, fallback) {
  const n = parseFloat(val)
  if (!isNaN(n)) return n
  if (fallback !== undefined) return fallback
  return undefined
}

function buildRequestBody(f) {
  /** @type {Record<string, unknown>} */
  const staticLevel = num(f.staticWaterLevel)
  const drawdown    = num(f.drawdown, 0)

  // 0 or missing pipe fields mean "no pipe run" — use a large-diameter short run
  // so the backend gets a valid gt=0 value and friction ≈ 0
  const pipeDia = num(f.pipeDiameter, 0)
  const pipeLen = num(f.pipeLength, 0)
  const noPipe  = !pipeDia || !pipeLen

  const body = {
    static_water_level_ft:    staticLevel,
    dynamic_water_level_ft:   staticLevel + drawdown,
    discharge_head_ft:        num(f.elevationGain, 0),
    required_flow_gpm:        num(f.requiredFlowGpm),
    pipe_material:            f.pipeMaterial || 'PVC',
    nominal_pipe_diameter_in: noPipe ? 4.0 : pipeDia,
    pipe_length_ft:           noPipe ? 1   : pipeLen,
    discharge_pressure_psi:   num(f.pressurePsi, 0),
    panel_wattage_w:          num(f.panelWattage, 370),
    solar_coefficient:        1.0,
    float_switch:             f.floatSwitch === true,
    pressure_switch:          f.pressureSwitch === true,
    generator_backup_required: f.generatorBackup === true,
    grid_backup_required:     f.gridBackup === true,
    poor_water_quality:       f.waterQuality === 'poor',
  }

  // Daily demand: use desired GPD when user rejected the calculated value
  if (f.gpdAccepted === false && f.desiredGpd) {
    body.daily_water_demand_gallons = parseFloat(f.desiredGpd)
  } else if (f.dailyDemandGallons) {
    body.daily_water_demand_gallons = parseFloat(f.dailyDemandGallons)
  }

  // Well casing
  if (f.wellCasing) body.well_casing_diameter_in = parseFloat(f.wellCasing)

  // Recovery rate — required unless Unknown is checked
  if (f.recoveryUnknown) {
    body.well_recovery_unknown = true
    // Pass dry concern flag when unknown: true=concern, false=no concern, null=not answered
    if (f.dryRunConcern === 'yes') body.well_recovery_dry_concern = true
    else if (f.dryRunConcern === 'no') body.well_recovery_dry_concern = false
  } else {
    body.well_recovery_unknown = false
    if (f.recoveryRate) body.recovery_rate_gpm = parseFloat(f.recoveryRate)
  }

  // Pressure switch range
  if (f.pressureSwitch && f.pressureSwitchRange) body.pressure_switch_range = f.pressureSwitchRange

  // Wire distance
  if (f.wireDistance) body.wire_distance_ft = parseFloat(f.wireDistance)

  // Panel Vmp — required for accurate wire sizing
  if (f.panelVmpV) body.panel_vmp_v = parseFloat(f.panelVmpV)

  // Panel Voc — used to compute system open-circuit voltage display
  if (f.panelVocV) body.panel_voc_v = parseFloat(f.panelVocV)

  // Location — prefer coords over manual peak_sun_hours
  if (f.latitude && f.longitude) {
    body.latitude  = parseFloat(f.latitude)
    body.longitude = parseFloat(f.longitude)
  } else {
    body.peak_sun_hours = parseFloat(f.peakSunHours || 5.0)
  }

  return body
}
