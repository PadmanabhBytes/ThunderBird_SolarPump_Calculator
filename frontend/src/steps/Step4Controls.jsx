import { useState } from 'react'
import './Steps.css'

const PRESSURE_RANGES = [
  '20-40 PSI', '30-50 PSI', '40-60 PSI',
  '50-70 PSI', '60-80 PSI', '80-100 PSI',
]

function BackupPopup({ type, onClose }) {
  const isGrid = type === 'grid'
  return (
    <div className="popup-overlay" onClick={onClose}>
      <div className="popup-box" onClick={e => e.stopPropagation()}>
        <button className="popup-close" onClick={onClose}>✕</button>
        <h3 className="popup-title">{isGrid ? 'Grid Backup' : 'Generator Backup'}</h3>
        <p className="popup-body">
          AC/DC TBS Solar Products require <strong>1ph 230VAC power backup</strong> for optimal performance.
        </p>
        {isGrid && (
          <p className="popup-body">
            An <strong>AC surge protector</strong> is required for grid use — SKU 344-1001 (300VAC AC Surge Protection Device) will be added to your final system selections.
          </p>
        )}
        <button className="btn-primary" style={{ marginTop: '0.75rem' }} onClick={onClose}>
          Got it
        </button>
      </div>
    </div>
  )
}

export default function Step4Controls({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })
  const [rangeMode, setRangeMode] = useState(
    data.pressureSwitchRange && !PRESSURE_RANGES.includes(data.pressureSwitchRange)
      ? 'custom' : 'select'
  )
  const [backupPopup, setBackupPopup] = useState(null) // 'generator' | 'grid' | null

  function handleRangeMode(mode) {
    setRangeMode(mode)
    set('pressureSwitchRange', '')
  }

  function handleGeneratorToggle(checked) {
    onChange({ ...data, generatorBackup: checked, gridBackup: checked ? false : data.gridBackup })
    if (checked) setBackupPopup('generator')
  }

  function handleGridToggle(checked) {
    onChange({ ...data, gridBackup: checked, generatorBackup: checked ? false : data.generatorBackup })
    if (checked) setBackupPopup('grid')
  }

  return (
    <div className="step-section">
      {backupPopup && (
        <BackupPopup type={backupPopup} onClose={() => setBackupPopup(null)} />
      )}

      <h2 className="step-title">System Controls</h2>
      <p className="step-subtitle">Switches, protection devices, and electrical run details.</p>

      <h3 className="subsection-title">Control Switches</h3>

      <div className="field-row">
        <label className="checkbox-label">
          <input type="checkbox" checked={data.floatSwitch || false}
            onChange={e => set('floatSwitch', e.target.checked)} />
          Float switch (electrical) — stops pump when storage tank is full
        </label>
        {data.floatSwitch && (
          <div className="info-box" style={{ marginTop: '0.5rem' }}>
            All AC/DC TBS products can accept pump-up or pump-down 2-wire floats.
            DC ONLY TBS products include a 3-wire float switch as part of the sales package.
          </div>
        )}
      </div>

      <div className="field-row" style={{ marginTop: '0.75rem' }}>
        <label className="checkbox-label">
          <input type="checkbox" checked={data.pressureSwitch || false}
            onChange={e => set('pressureSwitch', e.target.checked)} />
          Pressure switch (irrigation / cabin / house) — activates pump on demand pressure drop
        </label>
      </div>

      {data.pressureSwitch && (
        <div className="field-grid">
          <div className="field-group">
            <label>Pressure Switch Range <span className="req">*</span></label>
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

      <h3 className="subsection-title">AC Backup Power</h3>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
        Select if this system will have an AC power backup source. Only one may be selected.
      </p>

      <div className="field-row">
        <label className="checkbox-label">
          <input type="checkbox" checked={data.generatorBackup || false}
            onChange={e => handleGeneratorToggle(e.target.checked)} />
          Generator backup — excludes DC-only pump designs
        </label>
      </div>

      <div className="field-row" style={{ marginTop: '0.5rem' }}>
        <label className="checkbox-label">
          <input type="checkbox" checked={data.gridBackup || false}
            onChange={e => handleGridToggle(e.target.checked)} />
          Grid (utility) backup — adds AC surge protector SKU 344-1001 to parts list
        </label>
      </div>

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
        Wire gauge is calculated using Thunderbird Solar formulas: Vmp_Array = n_panels × Vmp × 0.95, with a 12A current cap and ROUNDDOWN to nearest 10 ft. AWG recommendation is included in the results.
      </div>
    </div>
  )
}
