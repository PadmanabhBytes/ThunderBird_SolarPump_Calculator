import { useState } from 'react'
import './Steps.css'

const CASING_SIZES  = ['3.5', '4.0', '4.5', '5.0']
const WATER_QUALITY = [
  { value: 'none',    label: 'Clean Water' },
  { value: 'unknown', label: 'Unknown' },
  { value: 'minor',   label: 'Minor sand or sediment' },
  { value: 'poor',    label: 'Poor — heavy solids or iron bacteria (excludes helical rotor pumps)' },
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

function RackingInfoModal({ onClose }) {
  return (
    <div className="popup-overlay" onClick={onClose}>
      <div className="popup-box" onClick={e => e.stopPropagation()}>
        <button className="popup-close" onClick={onClose}>✕</button>
        <h3 className="popup-title">TBS Racking Kit — 2.5" vs 4" Pipe</h3>
        <p className="popup-body">
          TBS offers two racking configurations based on panel count and site conditions:
        </p>
        <ul className="popup-body" style={{ paddingLeft: '1.2rem', margin: '0.5rem 0' }}>
          <li><strong>2.5" Schedule 40 pipe</strong> — used for both the ground post and crossbeam on smaller arrays. Lighter and easier to install.</li>
          <li><strong>4" Schedule 40 pipe</strong> — required for larger panel counts or wider panel widths where structural load demands it.</li>
        </ul>
        <p className="popup-body" style={{ marginTop: '0.5rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Diagrams coming soon — Corey / Cody to provide racking layout images.
        </p>
        <button className="btn-primary" style={{ marginTop: '0.75rem' }} onClick={onClose}>
          Got it
        </button>
      </div>
    </div>
  )
}

export default function Step2Well({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })
  const recoveryUnknown = data.recoveryUnknown === true

  const [backupPopup, setBackupPopup] = useState(null)
  const [showRackingInfo, setShowRackingInfo] = useState(false)

  function handleUseTbsRacking(useTbs) {
    onChange({
      ...data,
      useTbsRacking: useTbs,
      tbsRackingKit: useTbs ? data.tbsRackingKit : false,
    })
  }

  function handleGeneratorToggle(checked) {
    onChange({ ...data, generatorBackup: checked, gridBackup: checked ? false : data.gridBackup })
    if (checked) setBackupPopup('generator')
  }

  function handleGridToggle(checked) {
    onChange({ ...data, gridBackup: checked, generatorBackup: checked ? false : data.generatorBackup })
    if (checked) setBackupPopup('grid')
  }

  const show4inWarning = data.wellCasing === '4.0'

  return (
    <div className="step-section">
      {backupPopup && <BackupPopup type={backupPopup} onClose={() => setBackupPopup(null)} />}
      {showRackingInfo && <RackingInfoModal onClose={() => setShowRackingInfo(false)} />}

      <h2 className="step-title">Well Characteristics</h2>
      <p className="step-subtitle">Well recovery, casing, and water quality.</p>

      {/* ── Recovery Rate ──────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">c) Recovery Rate</h3>

      <div className="field-row">
        <label className="checkbox-label">
          <input type="checkbox" checked={recoveryUnknown}
            onChange={e => {
              const checked = e.target.checked
              onChange({
                ...data,
                recoveryUnknown: checked,
                recoveryRate: checked ? '' : data.recoveryRate,
                dryRunConcern: checked ? data.dryRunConcern : undefined,
              })
            }} />
          Recovery rate unknown
        </label>
      </div>

      {!recoveryUnknown && (
        <div className="field-grid" style={{ marginTop: '0.5rem' }}>
          <div className="field-group">
            <label>Recovery Rate of the Well (GPM) <span className="req">*</span></label>
            <input
              type="number" min="0.1" step="0.1" placeholder="e.g. 20"
              value={data.recoveryRate || ''}
              onChange={e => set('recoveryRate', e.target.value)}
            />
            <span className="hint">How fast the well refills under pumping.</span>
          </div>
        </div>
      )}

      {recoveryUnknown && (
        <div style={{ marginTop: '0.75rem', paddingLeft: '1.5rem' }}>
          <span className="field-label-inline">Is there any concern of the well running dry?</span>
          <div className="radio-group" style={{ flexDirection: 'row', gap: '1.5rem', marginTop: '0.5rem' }}>
            <label className="radio-label">
              <input type="radio" name="dryRunConcern" value="no"
                checked={data.dryRunConcern === 'no'}
                onChange={() => set('dryRunConcern', 'no')} />
              No — recovery filters will not apply
            </label>
            <label className="radio-label">
              <input type="radio" name="dryRunConcern" value="yes"
                checked={data.dryRunConcern === 'yes'}
                onChange={() => set('dryRunConcern', 'yes')} />
              Yes — add dry-run protection recommendation
            </label>
          </div>
        </div>
      )}

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

      {show4inWarning && (
        <div className="info-box" style={{ background: '#FFF7ED', borderColor: '#F97316', marginTop: '0.75rem' }}>
          <strong>⚠ 4" Casing Notice:</strong> A 4" inner diameter casing is selected with an AC/DC 4" pump option.
          Ensure the actual inner casing diameter meets minimum clearance requirements for the selected pump before installation.
        </div>
      )}

      <div className="divider" />

      {/* ── Generator / Grid Backup ───────────────────────────────────────────── */}
      <h3 className="subsection-title">Generator / Grid Backup</h3>
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

      {/* ── Solar Racking ─────────────────────────────────────────────────────── */}
      <h3 className="subsection-title">Solar Racking</h3>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
        Will you be using TBS racking, or do you have your own?
      </p>

      <div className="radio-group" style={{ flexDirection: 'row', gap: '1.5rem' }}>
        <label className="radio-label">
          <input
            type="radio"
            name="useTbsRacking"
            value="tbs"
            checked={data.useTbsRacking !== false}
            onChange={() => handleUseTbsRacking(true)}
          />
          Use TBS Racking
        </label>
        <label className="radio-label">
          <input
            type="radio"
            name="useTbsRacking"
            value="own"
            checked={data.useTbsRacking === false}
            onChange={() => handleUseTbsRacking(false)}
          />
          I have my own racking
        </label>
      </div>

      {data.useTbsRacking !== false && (
        <div style={{ marginTop: '0.85rem', paddingLeft: '0.25rem' }}>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={data.tbsRackingKit !== false}
              onChange={e => set('tbsRackingKit', e.target.checked)}
            />
            If viable, prefer the{' '}
            <strong>2.5" pipe option</strong>{' '}
            <button
              type="button"
              className="sys-diag-link"
              style={{ fontSize: '0.8rem', padding: 0, background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
              onClick={() => setShowRackingInfo(true)}
            >
              What is this?
            </button>
          </label>
          {data.tbsRackingKit === false && (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.3rem', paddingLeft: '1.75rem' }}>
              4" pipe option will be used when 2.5" is not viable.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
