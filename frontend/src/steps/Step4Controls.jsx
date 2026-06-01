import { useState } from 'react'
import './Steps.css'

const PRESSURE_RANGES = [
  '20-40 PSI', '30-50 PSI', '40-60 PSI',
  '50-70 PSI', '60-80 PSI', '80-100 PSI',
]

export default function Step4Controls({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })
  const [rangeMode, setRangeMode] = useState(
    data.pressureSwitchRange && !PRESSURE_RANGES.includes(data.pressureSwitchRange)
      ? 'custom' : 'select'
  )

  function handleRangeMode(mode) {
    setRangeMode(mode)
    set('pressureSwitchRange', '')
  }

  return (
    <div className="step-section">
      <h2 className="step-title">System Controls</h2>
      <p className="step-subtitle">Switches, protection devices, and electrical run details.</p>

      <h3 className="subsection-title">Control Switches</h3>

      <div className="field-row">
        <label className="checkbox-label">
          <input type="checkbox" checked={data.floatSwitch || false}
            onChange={e => set('floatSwitch', e.target.checked)} />
          Float switch required — stops pump when storage tank is full
        </label>
      </div>

      <div className="field-row">
        <label className="checkbox-label">
          <input type="checkbox" checked={data.pressureSwitch || false}
            onChange={e => set('pressureSwitch', e.target.checked)} />
          Pressure switch required — activates pump on demand pressure drop
        </label>
      </div>

      {data.pressureSwitch && (
        <div className="field-grid">
          <div className="field-group">
            <label>Pressure Switch Range</label>
            <div className="radio-group" style={{ flexDirection: 'row', gap: '1.5rem', marginBottom: '0.5rem' }}>
              <label className="radio-label">
                <input type="radio" name="rangeMode" value="select"
                  checked={rangeMode === 'select'} onChange={() => handleRangeMode('select')} />
                Select from list
              </label>
              <label className="radio-label">
                <input type="radio" name="rangeMode" value="custom"
                  checked={rangeMode === 'custom'} onChange={() => handleRangeMode('custom')} />
                Enter custom
              </label>
            </div>
            {rangeMode === 'select' ? (
              <select value={data.pressureSwitchRange || ''} onChange={e => set('pressureSwitchRange', e.target.value)}>
                <option value="">Select range</option>
                {PRESSURE_RANGES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            ) : (
              <input type="text" placeholder="e.g. 45-65 PSI"
                value={data.pressureSwitchRange || ''} onChange={e => set('pressureSwitchRange', e.target.value)} />
            )}
          </div>
        </div>
      )}

      <div className="divider" />
      <h3 className="subsection-title">Electrical Run</h3>

      <div className="field-grid">
        <div className="field-group">
          <label>Wire Distance (ft)</label>
          <input type="number" min="0" placeholder="e.g. 300"
            value={data.wireDistance || ''} onChange={e => set('wireDistance', e.target.value)} />
          <span className="hint">One-way distance from panels/controller to pump. Wire sizing uses round-trip (2×).</span>
        </div>

      </div>

      <div className="info-box">
        Wire sizing is calculated to NEC standards targeting ≤ 3% voltage drop. AWG recommendation is included in the results.
      </div>
    </div>
  )
}
