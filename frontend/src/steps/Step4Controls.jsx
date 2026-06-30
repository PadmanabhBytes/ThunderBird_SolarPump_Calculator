import { useState } from 'react'
import './Steps.css'
import './Step4Controls.css'

const PRESSURE_RANGES = [
  '20-40 PSI', '30-50 PSI', '40-60 PSI',
  '50-70 PSI', '60-80 PSI', '80-100 PSI',
]

function parseTopEndPsi(range) {
  if (!range) return null
  const nums = range.match(/\d+/g)
  return nums && nums.length >= 2 ? parseInt(nums[nums.length - 1]) : null
}

function roundUpTo10(x) {
  return Math.ceil(x / 10) * 10
}

// ── System Diagrams ───────────────────────────────────────────────────────────

const DIAGRAMS = {
  float: {
    title: 'Electrical Float System',
    content: (
      <div className="diagram-wrap">
        <div className="diag-row"><div className="diag-box solar">☀ Solar Array</div></div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row"><div className="diag-box ctrl">TBS Monitor / Controller</div></div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row"><div className="diag-box pump">Pump Motor</div></div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row">
          <div className="diag-box tank">Storage Tank</div>
        </div>
        <div className="diag-arrow">↕</div>
        <div className="diag-row">
          <div className="diag-box switch float-sw">Float Switch<br/><span className="diag-note">Cuts pump when tank full</span></div>
        </div>
        <div className="diag-desc">
          The float switch is wired to the TBS Monitor. When the storage tank reaches the set level,
          the float cuts power to the pump automatically.
        </div>
      </div>
    ),
  },
  pressure: {
    title: 'Pressure System',
    content: (
      <div className="diagram-wrap">
        <div className="diag-row"><div className="diag-box solar">☀ Solar Array</div></div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row"><div className="diag-box ctrl">TBS Monitor / Controller</div></div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row"><div className="diag-box pump">Pump Motor</div></div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row">
          <div className="diag-box tank">Pressure Tank</div>
          <div className="diag-side">
            <div className="diag-box switch pres-sw">Pressure Switch<br/><span className="diag-note">Starts pump on pressure drop</span></div>
          </div>
        </div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row"><div className="diag-box dist">Distribution<br/><span className="diag-note">Irrigation / Cabin / House</span></div></div>
        <div className="diag-desc">
          The pressure switch monitors tank pressure. When demand drops system pressure below the cut-in
          setting, the pump activates. The TDH calculation includes the system delivery pressure.
        </div>
      </div>
    ),
  },
  floatPressure: {
    title: 'Pressure Switch + Mechanical Float System',
    content: (
      <div className="diagram-wrap">
        <div className="diag-row"><div className="diag-box solar">☀ Solar Array</div></div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row">
          <div className="diag-box ctrl">TBS Monitor / Controller</div>
          <div className="diag-side">
            <div className="diag-box switch float-sw">Mechanical Float<br/><span className="diag-note">Tank-full shutoff</span></div>
          </div>
        </div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row"><div className="diag-box pump">Pump Motor</div></div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row">
          <div className="diag-box tank">Pressure Tank</div>
          <div className="diag-side">
            <div className="diag-box switch pres-sw">Pressure Switch<br/><span className="diag-note">On-demand control</span></div>
          </div>
        </div>
        <div className="diag-arrow">↓</div>
        <div className="diag-row"><div className="diag-box dist">Distribution</div></div>
        <div className="diag-desc">
          The mechanical float stops the pump when the holding tank is full. The pressure switch
          starts the pump on demand. A shutoff PSI is recommended to ensure adequate head from the switch to the tank.
        </div>
      </div>
    ),
  },
}

function DiagramModal({ type, onClose }) {
  const d = DIAGRAMS[type]
  if (!d) return null
  return (
    <div className="popup-overlay" onClick={onClose}>
      <div className="popup-box diagram-popup" onClick={e => e.stopPropagation()}>
        <button className="popup-close" onClick={onClose}>✕</button>
        <h3 className="popup-title">{d.title}</h3>
        {d.content}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Step4Controls({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })

  const systemType = data.systemType || 'none'

  const [rangeMode, setRangeMode] = useState(
    data.pressureSwitchRange && !PRESSURE_RANGES.includes(data.pressureSwitchRange)
      ? 'custom' : 'select'
  )
  const [diagramType, setDiagramType] = useState(null)

  function handleSystemType(type) {
    onChange({
      ...data,
      systemType:    type,
      floatSwitch:   type === 'float' || type === 'floatPressure',
      pressureSwitch: type === 'pressure' || type === 'floatPressure',
      // clear PSI range when deselecting pressure options
      ...(type === 'float' || type === 'none' ? { pressureSwitchRange: '' } : {}),
    })
  }

  function handleRangeMode(mode) {
    setRangeMode(mode)
    onChange({ ...data, pressureSwitchRange: '', pressureCutIn: '', pressureCutOut: '' })
  }

  // ── PSI mismatch warning (pressure / floatPressure only) ──────────────────
  const showPressureFields = systemType === 'pressure' || systemType === 'floatPressure'
  const topEndPsi  = parseTopEndPsi(data.pressureSwitchRange)
  const systemPsi  = parseFloat(data.pressurePsi)
  const helpMode   = data.helpMeCalculate !== false  // true = subfields, false = direct TDH
  const psiMismatch = (
    showPressureFields &&
    helpMode &&
    topEndPsi != null &&
    !isNaN(systemPsi) &&
    systemPsi > 0 &&
    Math.abs(topEndPsi - systemPsi) > 0.01
  )

  // ── Shutoff PSI recommendation (floatPressure only) ────────────────────────
  const elev    = parseFloat(data.elevationGain) || 0
  const elevPsi = roundUpTo10(elev + 10)

  return (
    <div className="step-section">
      {diagramType && <DiagramModal type={diagramType} onClose={() => setDiagramType(null)} />}

      <h2 className="step-title">System Controls</h2>
      <p className="step-subtitle">Select your system type, then configure controls and backup power.</p>

      {/* ── System Type Cards ─────────────────────────────────────────────────── */}
      <h3 className="subsection-title">System Type</h3>
      <div className="sys-type-grid">

        {/* Electrical Float */}
        <div
          className={`sys-card ${systemType === 'float' ? 'sys-card--active color-blue' : ''}`}
          onClick={() => handleSystemType(systemType === 'float' ? 'none' : 'float')}
        >
          <div className="sys-card-icon">💧</div>
          <div className="sys-card-title">Electrical Float</div>
          <div className="sys-card-desc">Stops pump when storage tank is full</div>
          <button className="sys-diag-link" onClick={e => { e.stopPropagation(); setDiagramType('float') }}>
            View Diagram →
          </button>
        </div>

        {/* Pressure System */}
        <div
          className={`sys-card ${systemType === 'pressure' ? 'sys-card--active color-gold' : ''}`}
          onClick={() => handleSystemType(systemType === 'pressure' ? 'none' : 'pressure')}
        >
          <div className="sys-card-icon">⚡</div>
          <div className="sys-card-title">Pressure System</div>
          <div className="sys-card-desc">On-demand for irrigation, cabin, or house</div>
          <button className="sys-diag-link" onClick={e => { e.stopPropagation(); setDiagramType('pressure') }}>
            View Diagram →
          </button>
        </div>

        {/* Float + Pressure */}
        <div
          className={`sys-card ${systemType === 'floatPressure' ? 'sys-card--active color-purple' : ''}`}
          onClick={() => handleSystemType(systemType === 'floatPressure' ? 'none' : 'floatPressure')}
        >
          <div className="sys-card-icon">🔄</div>
          <div className="sys-card-title">Float + Pressure</div>
          <div className="sys-card-desc">Tank storage with on-demand pressure delivery</div>
          <button className="sys-diag-link" onClick={e => { e.stopPropagation(); setDiagramType('floatPressure') }}>
            View Diagram →
          </button>
        </div>

      </div>

      {/* ── Electrical Float: info note ────────────────────────────────────────── */}
      {systemType === 'float' && (
        <div className="info-box" style={{ marginTop: '0.75rem' }}>
          All AC/DC TBS products can accept pump-up or pump-down <strong>2-wire floats</strong>.
          DC ONLY TBS products include a <strong>3-wire float switch</strong> as part of the sales package.
        </div>
      )}

      {/* ── Pressure fields (pressure + floatPressure) ────────────────────────── */}
      {showPressureFields && (
        <div style={{ marginTop: '1rem' }}>
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
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end' }}>
                  <div className="field-group" style={{ flex: 1, marginBottom: 0 }}>
                    <label style={{ fontSize: '0.8rem', marginBottom: '0.25rem' }}>Cut-in PSI</label>
                    <input type="number" min="0" placeholder="e.g. 30"
                      value={data.pressureCutIn || ''}
                      onChange={e => {
                        const cutIn = e.target.value
                        const cutOut = data.pressureCutOut || ''
                        onChange({ ...data, pressureCutIn: cutIn,
                          pressureSwitchRange: cutIn && cutOut ? `${cutIn}/${cutOut} PSI` : '' })
                      }} />
                  </div>
                  <span style={{ paddingBottom: '0.5rem', color: '#6B7280' }}>—</span>
                  <div className="field-group" style={{ flex: 1, marginBottom: 0 }}>
                    <label style={{ fontSize: '0.8rem', marginBottom: '0.25rem' }}>Cut-out PSI</label>
                    <input type="number" min="0" placeholder="e.g. 50"
                      value={data.pressureCutOut || ''}
                      onChange={e => {
                        const cutOut = e.target.value
                        const cutIn = data.pressureCutIn || ''
                        onChange({ ...data, pressureCutOut: cutOut,
                          pressureSwitchRange: cutIn && cutOut ? `${cutIn}/${cutOut} PSI` : '' })
                      }} />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* PSI mismatch warning */}
          {psiMismatch && (
            <div className="psi-mismatch-warn">
              ⚠ <strong>PSI Mismatch:</strong> System pressure in Step 1 is <strong>{systemPsi} PSI</strong> but
              the pressure switch shutoff is <strong>{topEndPsi} PSI</strong>.
              Update the System Pressure field in Step 1 to <strong>{topEndPsi} PSI</strong> before proceeding.
            </div>
          )}

          {/* Float+Pressure: +15 PSI note and shutoff recommendation */}
          {systemType === 'floatPressure' && (
            <div className="info-box" style={{ marginTop: '0.75rem', background: '#EFF6FF', borderColor: '#3B82F6' }}>
              <strong>Recommended Shutoff PSI:</strong>
              {helpMode ? (
                elev > 0 ? (
                  <>
                    {' '}<strong>{elevPsi} PSI minimum</strong> (based on {elev} ft elevation gain + 10 PSI buffer,
                    rounded to nearest 10). Note: friction loss will increase this — check TDH breakdown after first calculation.
                  </>
                ) : (
                  ' Enter elevation gain in Step 1 to get a PSI recommendation.'
                )
              ) : (
                ' Shutoff PSI must exceed the PSI required to move water from the pressure switch location to the tank. Select a PSI rating that meets this requirement and enter it in the pressure switch range above.'
              )}
            </div>
          )}
        </div>
      )}

      <div className="divider" />

      {/* ── Electrical Run ────────────────────────────────────────────────────── */}
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
