import { useState } from 'react'
import './Steps.css'

const PIPE_MATERIALS = ['PVC', 'HDPE', 'Galvanized Steel', 'Steel', 'Copper']
const API_BASE = (import.meta.env.VITE_API_URL || '') + '/api/v1/calculations'

export default function Step1Flow({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })
  const [locMode, setLocMode] = useState(
    data.latitude && !data.zipCode ? 'coords' : 'zip'
  )
  const [lookup, setLookup] = useState({ loading: false, error: null })

  function handleLocMode(mode) {
    setLocMode(mode)
    if (mode === 'zip') {
      onChange({ ...data, latitude: '', longitude: '', solarZone: undefined, gpdZoneCoeff: undefined })
    } else {
      onChange({ ...data, peakSunHours: '', zipCode: '', solarZone: undefined, gpdZoneCoeff: undefined })
    }
  }

  async function applyZone(lat, lon, base) {
    try {
      const res = await fetch(`${API_BASE}/solar-zone?lat=${lat}&lon=${lon}`)
      if (res.ok) {
        const z = await res.json()
        onChange({ ...base, gpdZoneCoeff: z.gpd_coeff, solarZone: z.solar_zone })
        return
      }
    } catch (_) {}
    onChange(base)
  }

  async function lookupZip() {
    const zip = (data.zipCode || '').trim()
    if (!zip) return
    setLookup({ loading: true, error: null })
    try {
      const res = await fetch(`https://api.zippopotam.us/us/${encodeURIComponent(zip)}`)
      if (!res.ok) throw new Error('ZIP code not found')
      const result = await res.json()
      const place = result.places?.[0]
      if (!place) throw new Error('ZIP code not found')
      const lat = parseFloat(place.latitude).toFixed(4)
      const lon = parseFloat(place.longitude).toFixed(4)
      const label = `${place['place name']}, ${place['state abbreviation']} ${zip}`
      await applyZone(lat, lon, { ...data, latitude: lat, longitude: lon, zipCode: zip, zipLabel: label })
      setLookup({ loading: false, error: null })
    } catch (e) {
      setLookup({ loading: false, error: e.message })
    }
  }

  async function lookupCoordsZone() {
    const { latitude: lat, longitude: lon } = data
    if (!lat || !lon) return
    setLookup({ loading: true, error: null })
    try {
      const res = await fetch(`${API_BASE}/solar-zone?lat=${lat}&lon=${lon}`)
      if (!res.ok) throw new Error('Solar zone lookup failed')
      const z = await res.json()
      onChange({ ...data, gpdZoneCoeff: z.gpd_coeff, solarZone: z.solar_zone })
      setLookup({ loading: false, error: null })
    } catch (e) {
      setLookup({ loading: false, error: e.message })
    }
  }

  const gpm = parseFloat(data.requiredFlowGpm)
  const hasZone = !!data.solarZone
  const proposedGpd = (hasZone && !isNaN(gpm) && gpm > 0)
    ? Math.round(gpm * 6.5 * 60 * 1.1 * (data.gpdZoneCoeff || 1.0))
    : null

  return (
    <div className="step-section">
      <h2 className="step-title">Location & Production</h2>
      <p className="step-subtitle">Site location, daily demand, and total head the pump must overcome.</p>

      {/* ── a) Location ──────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">a) Location <span className="req">*</span></h3>

      <div className="field-row">
        <div className="radio-group" style={{ flexDirection: 'row', gap: '1.5rem' }}>
          <label className="radio-label">
            <input type="radio" name="locMode" value="zip"
              checked={locMode === 'zip'} onChange={() => handleLocMode('zip')} />
            ZIP code (recommended)
          </label>
          <label className="radio-label">
            <input type="radio" name="locMode" value="coords"
              checked={locMode === 'coords'} onChange={() => handleLocMode('coords')} />
            GPS coordinates
          </label>
        </div>
      </div>

      {locMode === 'zip' && (
        <>
          <div className="field-grid">
            <div className="field-group">
              <label>ZIP Code <span className="req">*</span></label>
              <div className="input-with-btn">
                <input type="text" maxLength={5} placeholder="e.g. 88310"
                  value={data.zipCode || ''}
                  onChange={e => set('zipCode', e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && lookupZip()} />
                <button type="button" className="btn-lookup"
                  onClick={lookupZip} disabled={lookup.loading}>
                  {lookup.loading ? '…' : 'Look up'}
                </button>
              </div>
              {lookup.error && <span className="hint error">{lookup.error}</span>}
            </div>
          </div>

          {data.latitude && data.longitude ? (
            <div className="info-box success">
              <strong>{data.zipLabel || data.zipCode}</strong>
              <span style={{ marginLeft: '1rem', opacity: 0.7 }}>
                {data.latitude}°, {data.longitude}°
              </span>
              {data.solarZone && (
                <span style={{ marginLeft: '1rem', fontWeight: 600 }}>
                  · Solar Zone {data.solarZone}
                </span>
              )}
            </div>
          ) : (
            <div className="info-box">
              Enter a 5-digit US ZIP code and click "Look up" to retrieve GPS coordinates and solar zone for daily production estimates.
            </div>
          )}
        </>
      )}

      {locMode === 'coords' && (
        <>
          <div className="field-grid">
            <div className="field-group">
              <label>Latitude <span className="req">*</span></label>
              <input type="number" min="-90" max="90" step="0.0001" placeholder="e.g. 32.8950"
                value={data.latitude || ''} onChange={e => set('latitude', e.target.value)} />
            </div>
            <div className="field-group">
              <label>Longitude <span className="req">*</span></label>
              <input type="number" min="-180" max="180" step="0.0001" placeholder="e.g. -105.9600"
                value={data.longitude || ''} onChange={e => set('longitude', e.target.value)} />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <button type="button" className="btn-lookup"
              onClick={lookupCoordsZone}
              disabled={lookup.loading || !data.latitude || !data.longitude}>
              {lookup.loading ? '…' : 'Get Solar Zone'}
            </button>
            {lookup.error && <span className="hint error">{lookup.error}</span>}
            {data.solarZone && !lookup.loading && (
              <span className="info-box success" style={{ padding: '0.35rem 0.75rem', display: 'inline-block' }}>
                Solar Zone {data.solarZone}
              </span>
            )}
          </div>
          {!data.latitude && !data.longitude && (
            <div className="info-box">
              Enter coordinates then click "Get Solar Zone" to retrieve solar resource data for your location.
            </div>
          )}
        </>
      )}

      <div className="divider" />

      {/* ── b) System Operating Window ───────────────────────────────────────── */}
      <h3 className="subsection-title">b) System Operating Window</h3>
      <div className="field-grid">
        <div className="field-group">
          <label>Operating Season</label>
          <select value={data.operatingWindow || 'year_round'} onChange={e => set('operatingWindow', e.target.value)}>
            <option value="year_round">Year Round</option>
            <option value="summer">Summer Only (Mar – Oct)</option>
            <option value="winter">Winter Only (Nov – Feb)</option>
          </select>
        </div>
      </div>

      <div className="divider" />

      {/* ── c) Production Requirements ───────────────────────────────────────── */}
      <h3 className="subsection-title">c) Production Requirements</h3>
      <div className="field-grid">
        <div className="field-group">
          <label>Gallons Per Minute (GPM) <span className="req">*</span></label>
          <input type="number" min="0.1" step="0.5" placeholder="e.g. 12"
            value={data.requiredFlowGpm || ''} onChange={e => set('requiredFlowGpm', e.target.value)} />
          <span className="hint">Required instantaneous flow rate at the pump outlet</span>
        </div>
      </div>

      {!hasZone && data.requiredFlowGpm && (
        <div className="info-box">
          Enter your location above and click "Look up" to see the estimated daily GPD for your solar zone.
        </div>
      )}

      {proposedGpd !== null && (
        <div className="gpd-proposal">
          <p className="gpd-proposal-text">
            Based on Solar Zone {data.solarZone} and {gpm.toFixed(1)} GPM, the estimated daily water production is{' '}
            <strong>{proposedGpd.toLocaleString()} GPD</strong>.
            Is this sufficient for your needs?
          </p>
          <div className="radio-group" style={{ flexDirection: 'row', gap: '1.5rem', marginTop: '0.5rem' }}>
            <label className="radio-label">
              <input type="radio" name="gpdAccepted" value="yes"
                checked={data.gpdAccepted !== false}
                onChange={() => onChange({ ...data, gpdAccepted: true, desiredGpd: '' })} />
              Yes — {proposedGpd.toLocaleString()} GPD is sufficient
            </label>
            <label className="radio-label">
              <input type="radio" name="gpdAccepted" value="no"
                checked={data.gpdAccepted === false}
                onChange={() => onChange({ ...data, gpdAccepted: false })} />
              No — I need a different daily volume
            </label>
          </div>
          {data.gpdAccepted === false && (
            <div className="field-grid" style={{ marginTop: '0.75rem' }}>
              <div className="field-group">
                <label>Required Daily Volume (GPD) <span className="req">*</span></label>
                <input type="number" min="1" placeholder={`e.g. ${proposedGpd}`}
                  value={data.desiredGpd || ''}
                  onChange={e => set('desiredGpd', e.target.value)} />
                <span className="hint">Your actual daily water demand in gallons per day.</span>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="divider" />

      {/* ── d) TDH Components ────────────────────────────────────────────────── */}
      <h3 className="subsection-title">d) TDH Components</h3>
      <div className="field-grid">
        <div className="field-group">
          <label>Static Water Level (ft) <span className="req">*</span></label>
          <input type="number" min="0" placeholder="e.g. 220"
            value={data.staticWaterLevel || ''} onChange={e => set('staticWaterLevel', e.target.value)} />
          <span className="hint">Depth from ground surface to resting water level</span>
        </div>

        <div className="field-group">
          <label>Expected Drawdown (ft) <span className="req">*</span></label>
          <input type="number" min="0" placeholder="e.g. 45"
            value={data.drawdown || ''} onChange={e => set('drawdown', e.target.value)} />
          <span className="hint">Additional drop when the pump is running (0 if unknown)</span>
        </div>

        <div className="field-group">
          <label>Vertical Elevation Gain (ft)</label>
          <input type="number" min="0" placeholder="e.g. 15"
            value={data.elevationGain || ''} onChange={e => set('elevationGain', e.target.value)} />
          <span className="hint">Height from wellhead to highest delivery point</span>
        </div>

        <div className="field-group">
          <label>System Pressure (PSI)</label>
          <input type="number" min="0" placeholder="e.g. 0"
            value={data.pressurePsi || ''} onChange={e => set('pressurePsi', e.target.value)} />
          <span className="hint">Required delivery pressure (0 if none)</span>
        </div>
      </div>

      {data.staticWaterLevel && data.drawdown && (
        <div className="calc-preview">
          <span>Pumping Level:</span>
          <strong>{(parseFloat(data.staticWaterLevel) + parseFloat(data.drawdown)).toFixed(0)} ft</strong>
        </div>
      )}

      <div className="divider" />

      {/* ── Friction loss — pipe run ─────────────────────────────────────────── */}
      <h3 className="subsection-title">Friction Loss — Pipe Line Run</h3>
      <div className="field-grid">
        <div className="field-group">
          <label>Pipe Material</label>
          <select value={data.pipeMaterial || 'PVC'} onChange={e => set('pipeMaterial', e.target.value)}>
            {PIPE_MATERIALS.map(m => <option key={m}>{m}</option>)}
          </select>
        </div>

        <div className="field-group">
          <label>Nominal Pipe Diameter (inches)</label>
          <input type="number" min="0.5" step="0.25" placeholder='e.g. 1.25 for 1-1/4"'
            value={data.pipeDiameter || ''} onChange={e => set('pipeDiameter', e.target.value)} />
          <span className="hint">Leave blank if no pipe run</span>
        </div>

        <div className="field-group">
          <label>Pipe Run Length (ft)</label>
          <input type="number" min="1" placeholder="e.g. 300"
            value={data.pipeLength || ''} onChange={e => set('pipeLength', e.target.value)} />
          <span className="hint">Total pipe length from pump to delivery point</span>
        </div>
      </div>
    </div>
  )
}
