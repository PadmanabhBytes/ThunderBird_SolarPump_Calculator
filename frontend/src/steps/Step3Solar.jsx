import { useState } from 'react'
import './Steps.css'

const DEFAULT_PANEL = { wattage: '370', voc: '48', vmp: '40' }

export default function Step3Solar({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })
  const ownPanels = data.ownPanels !== false
  const [locMode, setLocMode]     = useState(data.latitude && !data.zipCode ? 'coords' : 'zip')
  const [zipLookup, setZipLookup] = useState({ loading: false, error: null })

  function handleOwnPanels(yes) {
    if (yes) {
      onChange({ ...data, ownPanels: true, panelWattage: '', panelVocV: '', panelVmpV: '' })
    } else {
      onChange({
        ...data,
        ownPanels: false,
        panelWattage: DEFAULT_PANEL.wattage,
        panelVocV:    DEFAULT_PANEL.voc,
        panelVmpV:    DEFAULT_PANEL.vmp,
      })
    }
  }

  function handleLocMode(mode) {
    setLocMode(mode)
    if (mode === 'zip') {
      onChange({ ...data, latitude: '', longitude: '' })
    } else {
      onChange({ ...data, peakSunHours: '', zipCode: '' })
    }
  }

  async function lookupZip() {
    const zip = (data.zipCode || '').trim()
    if (!zip) return
    setZipLookup({ loading: true, error: null })
    try {
      const res = await fetch(`https://api.zippopotam.us/us/${encodeURIComponent(zip)}`)
      if (!res.ok) throw new Error('ZIP code not found')
      const result = await res.json()
      const place = result.places?.[0]
      if (!place) throw new Error('ZIP code not found')
      const label = `${place['place name']}, ${place['state abbreviation']} ${zip}`
      onChange({
        ...data,
        latitude:  parseFloat(place.latitude).toFixed(4),
        longitude: parseFloat(place.longitude).toFixed(4),
        zipCode:   zip,
        zipLabel:  label,
      })
      setZipLookup({ loading: false, error: null })
    } catch (e) {
      setZipLookup({ loading: false, error: e.message })
    }
  }

  return (
    <div className="step-section">
      <h2 className="step-title">Solar & Location</h2>
      <p className="step-subtitle">Panel specs and site location for accurate solar sizing.</p>

      {/* ── d) Solar Panel Data ───────────────────────────────────────────────── */}
      <h3 className="subsection-title">d) Solar Panel Data</h3>

      <div className="field-row">
        <div className="radio-group" style={{ flexDirection: 'row', gap: '1.5rem' }}>
          <label className="radio-label">
            <input type="radio" name="ownPanels" value="yes"
              checked={ownPanels} onChange={() => handleOwnPanels(true)} />
            Yes — I'm providing my own panels
          </label>
          <label className="radio-label">
            <input type="radio" name="ownPanels" value="no"
              checked={!ownPanels} onChange={() => handleOwnPanels(false)} />
            No — use Thunderbird default panels (370W)
          </label>
        </div>
      </div>

      {ownPanels ? (
        <>
          <div className="field-grid">
            <div className="field-group">
              <label>Power Rating (W) per Panel <span className="req">*</span></label>
              <input type="number" min="50" step="5" placeholder="e.g. 400"
                value={data.panelWattage || ''} onChange={e => set('panelWattage', e.target.value)} />
            </div>
            <div className="field-group">
              <label>Voc (Vdc) per Panel</label>
              <input type="number" min="1" step="0.1" placeholder="e.g. 49.5"
                value={data.panelVocV || ''} onChange={e => set('panelVocV', e.target.value)} />
              <span className="hint">Open-circuit voltage from spec sheet</span>
            </div>
            <div className="field-group">
              <label>Vmp (Vdc) per Panel</label>
              <input type="number" min="1" step="0.1" placeholder="e.g. 41.2"
                value={data.panelVmpV || ''} onChange={e => set('panelVmpV', e.target.value)} />
              <span className="hint">Max power point voltage — used for wire sizing</span>
            </div>
          </div>

          <h3 className="subsection-title" style={{ marginTop: '1rem' }}>Panel Dimensions</h3>
          <div className="field-grid">
            <div className="field-group">
              <label>Length (inches)</label>
              <input type="number" min="1" step="0.1" placeholder='e.g. 79.5"'
                value={data.panelL || ''} onChange={e => set('panelL', e.target.value)} />
            </div>
            <div className="field-group">
              <label>Width (inches)</label>
              <input type="number" min="1" step="0.1" placeholder='e.g. 40"'
                value={data.panelW || ''} onChange={e => set('panelW', e.target.value)} />
            </div>
            <div className="field-group">
              <label>Thickness (inches)</label>
              <input type="number" min="0.1" step="0.01" placeholder='e.g. 1.38"'
                value={data.panelH || ''} onChange={e => set('panelH', e.target.value)} />
            </div>
          </div>
        </>
      ) : (
        <div className="info-box">
          Default panel: <strong>370W · Voc 48V · Vmp 40V · 80" × 40" × 1.5"</strong> — Thunderbird stock panel (SKU 116-1038)
        </div>
      )}

      <div className="divider" />

      {/* ── e) Location ──────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">e) Location</h3>

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
                  onClick={lookupZip} disabled={zipLookup.loading}>
                  {zipLookup.loading ? '…' : 'Look up'}
                </button>
              </div>
              {zipLookup.error && <span className="hint error">{zipLookup.error}</span>}
            </div>
          </div>

          {data.latitude && data.longitude && (
            <div className="info-box success">
              <strong>{data.zipLabel || data.zipCode}</strong>
              <span style={{ marginLeft: '1rem', opacity: 0.7 }}>
                {data.latitude}°, {data.longitude}°
              </span>
            </div>
          )}
          {(!data.latitude || !data.longitude) && (
            <div className="info-box">
              Enter a 5-digit US ZIP code and click "Look up" to automatically retrieve GPS coordinates for the NREL solar resource lookup.
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
          <div className="info-box">
            Coordinates are sent to NREL's Solar Resource Database to retrieve annual average solar irradiance for your location.
          </div>
        </>
      )}

      <div className="divider" />

      {/* ── f) System Operating Window ───────────────────────────────────────── */}
      <h3 className="subsection-title">f) System Operating Window</h3>
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
    </div>
  )
}
