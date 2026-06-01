import './Steps.css'

const CASING_SIZES  = ['3.5', '4.0', '4.5', '5.0']
const WATER_QUALITY = [
  { value: 'none',    label: 'Clean Water' },
  { value: 'unknown', label: 'Unknown' },
  { value: 'minor',   label: 'Minor sand or sediment' },
  { value: 'poor',    label: 'Poor — heavy solids or iron bacteria (excludes helical rotor pumps)' },
]

export default function Step2Well({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })
  const dryRunConcern = data.dryRunConcern === 'yes'

  return (
    <div className="step-section">
      <h2 className="step-title">Well Characteristics</h2>
      <p className="step-subtitle">Well recovery, casing, water quality, and system configuration.</p>

      {/* ── c) Recovery Rate ──────────────────────────────────────────────────── */}
      <h3 className="subsection-title">c) Recovery Rate</h3>

      <div className="field-row">
        <span className="field-label-inline">Is there any concern with the well running dry?</span>
        <div className="radio-group" style={{ flexDirection: 'row', gap: '1.5rem', marginTop: '0.5rem' }}>
          <label className="radio-label">
            <input type="radio" name="dryRunConcern" value="no"
              checked={!dryRunConcern} onChange={() => set('dryRunConcern', 'no')} />
            No
          </label>
          <label className="radio-label">
            <input type="radio" name="dryRunConcern" value="yes"
              checked={dryRunConcern} onChange={() => set('dryRunConcern', 'yes')} />
            Yes — add dry-run protection recommendation
          </label>
        </div>
      </div>

      <div className="field-grid" style={{ marginTop: '1rem' }}>
        <div className="field-group">
          <label>Recovery Rate of the Well (GPM)</label>
          <input type="number" min="0" placeholder="e.g. 20"
            value={data.recoveryRate || ''} onChange={e => set('recoveryRate', e.target.value)} />
          <span className="hint">How fast the well refills under pumping. Leave blank if unknown.</span>
        </div>
      </div>

      <div className="divider" />

      {/* ── Well Casing ───────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">Well Casing</h3>
      <div className="field-grid">
        <div className="field-group">
          <label>Well Casing Inner Diameter</label>
          <select value={data.wellCasing || ''} onChange={e => set('wellCasing', e.target.value)}>
            <option value="">Unknown / Not sure</option>
            {CASING_SIZES.map(s => <option key={s} value={s}>{s}"</option>)}
            <option value="5.1">5"+</option>
            <option value="5.5">5.5"+</option>
          </select>
          <span className="hint">Used to filter out incompatible pump sizes</span>
        </div>
      </div>

      <div className="divider" />

      {/* ── Water Quality ─────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">Water Quality</h3>
      <div className="field-grid">
        <div className="field-group">
          <label>Water Quality</label>
          <select value={data.waterQuality || 'none'} onChange={e => set('waterQuality', e.target.value)}>
            {WATER_QUALITY.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      <div className="divider" />

      {/* ── System Configuration ─────────────────────────────────────────────── */}
      <h3 className="subsection-title">System Configuration</h3>

      <div className="field-row">
        <label className="checkbox-label">
          <input type="checkbox" checked={data.generatorBackup || false}
            onChange={e => set('generatorBackup', e.target.checked)} />
          Generator or grid backup required — excludes DC-only pumps
        </label>
      </div>

      <div className="divider" />

      {/* ── Solar Racking ─────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">Solar Racking</h3>

      <div className="field-row">
        <span className="field-label-inline">Do you wish to use your own racking solution?</span>
        <div className="radio-group" style={{ flexDirection: 'row', gap: '1.5rem', marginTop: '0.5rem' }}>
          <label className="radio-label">
            <input type="radio" name="ownRacking" value="no"
              checked={!data.ownRacking} onChange={() => set('ownRacking', false)} />
            No — include TBS racking in equipment list
          </label>
          <label className="radio-label">
            <input type="radio" name="ownRacking" value="yes"
              checked={data.ownRacking === true} onChange={() => set('ownRacking', true)} />
            Yes — I'll provide my own racking
          </label>
        </div>
      </div>
    </div>
  )
}
