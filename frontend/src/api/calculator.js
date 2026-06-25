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
  // TDH mode: default is "Help Me Calculate" (sub-fields visible)
  const helpMeCalculate = f.helpMeCalculate !== false

  // Static level + drawdown — direct TDH encodes as static=TDH, drawdown=0
  let staticLevel, drawdown, elevationGain, pressurePsi
  if (helpMeCalculate) {
    staticLevel  = num(f.staticWaterLevel)
    drawdown     = num(f.drawdown, 0)
    elevationGain = num(f.elevationGain, 0)
    pressurePsi  = num(f.pressurePsi, 0)
  } else {
    const tdh    = num(f.directTdh, 0)
    staticLevel  = tdh
    drawdown     = 0
    elevationGain = 0
    pressurePsi  = 0
  }

  // Pipe run: only include when user checked "Is there a pipe run?"
  const hasPipeRun = f.hasPipeRun === true
  const pipeDia    = hasPipeRun ? num(f.pipeDiameter, 0) : 0
  const pipeLen    = hasPipeRun ? num(f.pipeLength, 0)   : 0
  const noPipe     = !pipeDia || !pipeLen

  const body = {
    static_water_level_ft:    staticLevel,
    dynamic_water_level_ft:   staticLevel + drawdown,
    discharge_head_ft:        elevationGain,
    required_flow_gpm:        num(f.requiredFlowGpm),
    pipe_material:            f.pipeMaterial || 'PVC',
    nominal_pipe_diameter_in: noPipe ? 4.0 : pipeDia,
    pipe_length_ft:           noPipe ? 1   : pipeLen,
    discharge_pressure_psi:   pressurePsi + (f.systemType === 'floatPressure' ? 15 : 0),
    panel_wattage_w:          num(f.panelWattage, 370),
    solar_coefficient:        1.0,
    float_switch:             f.floatSwitch === true,
    pressure_switch:          f.pressureSwitch === true,
    generator_backup_required: f.generatorBackup === true,
    grid_backup_required:     f.gridBackup === true,
    poor_water_quality:       f.waterQuality === 'poor',
    operating_window:         f.operatingWindow || 'year_round',
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

  // Panel Voc
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

export async function runDualCalculation(formData) {
  const zoneCoeff  = formData.gpdZoneCoeff || 1.0
  const desiredGpd = parseFloat(formData.desiredGpd)
  const derivedGpm = desiredGpd / (6.5 * 60 * 1.1 * zoneCoeff)

  // Category 1: original GPM, no daily demand override
  const body1 = buildRequestBody({ ...formData, gpdAccepted: true, desiredGpd: '' })

  // Category 2: derived GPM + keep desiredGpd as daily_water_demand_gallons override
  const body2 = buildRequestBody({ ...formData, requiredFlowGpm: String(derivedGpm) })

  const opts = body => ({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  const parse = async r => {
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(Array.isArray(err.detail)
        ? err.detail.map(e => typeof e === 'string' ? e : `${e.loc?.slice(-1)[0]}: ${e.msg}`).join(' | ')
        : err.detail || `HTTP ${r.status}`)
    }
    return r.json()
  }

  const [r1, r2] = await Promise.all([
    fetch(`${BASE}/calculate`, opts(body1)),
    fetch(`${BASE}/calculate`, opts(body2)),
  ])

  const [result1, result2] = await Promise.all([parse(r1), parse(r2)])

  return {
    mode:        'dual',
    category1:   result1,
    category2:   result2,
    originalGpm: parseFloat(formData.requiredFlowGpm),
    desiredGpd,
    derivedGpm:  parseFloat(derivedGpm.toFixed(1)),
  }
}
