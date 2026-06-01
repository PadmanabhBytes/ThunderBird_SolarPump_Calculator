import './Steps.css'

const PIPE_MATERIALS = ['PVC', 'HDPE', 'Galvanized Steel', 'Steel', 'Copper']

export default function Step1Flow({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })

  return (
    <div className="step-section">
      <h2 className="step-title">Production & TDH</h2>
      <p className="step-subtitle">How much water you need and the total head the pump must overcome.</p>

      {/* ── a) Production ──────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">a) Production Requirements</h3>
      <div className="field-grid">
        <div className="field-group">
          <label>Gallons Per Minute (GPM) <span className="req">*</span></label>
          <input type="number" min="0.1" step="0.5" placeholder="e.g. 12"
            value={data.requiredFlowGpm || ''} onChange={e => set('requiredFlowGpm', e.target.value)} />
          <span className="hint">Required instantaneous flow rate at the pump outlet</span>
        </div>

        <div className="field-group">
          <label>Gallons Per Day (GPD)</label>
          <input type="number" min="1" placeholder="Unknown — auto-calculated"
            value={data.dailyDemandGallons || ''} onChange={e => set('dailyDemandGallons', e.target.value)} />
          <span className="hint">Leave blank — derived from GPM × 6.5 hrs × 60 × 1.1 buffer</span>
        </div>
      </div>

      <div className="divider" />

      {/* ── b) TDH ─────────────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">b) TDH Components</h3>
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
          <span className="hint">Additional drop when the pump is running</span>
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

      {/* Pumping level preview */}
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
          <label>Pipe Material <span className="req">*</span></label>
          <select value={data.pipeMaterial || 'PVC'} onChange={e => set('pipeMaterial', e.target.value)}>
            {PIPE_MATERIALS.map(m => <option key={m}>{m}</option>)}
          </select>
        </div>

        <div className="field-group">
          <label>Nominal Pipe Diameter (inches) <span className="req">*</span></label>
          <input type="number" min="0.5" step="0.25" placeholder='e.g. 1.25 for 1-1/4"'
            value={data.pipeDiameter || ''} onChange={e => set('pipeDiameter', e.target.value)} />
        </div>

        <div className="field-group">
          <label>Pipe Run Length (ft) <span className="req">*</span></label>
          <input type="number" min="1" placeholder="e.g. 300"
            value={data.pipeLength || ''} onChange={e => set('pipeLength', e.target.value)} />
          <span className="hint">Total pipe length from pump to delivery point.</span>
        </div>
      </div>
    </div>
  )
}
