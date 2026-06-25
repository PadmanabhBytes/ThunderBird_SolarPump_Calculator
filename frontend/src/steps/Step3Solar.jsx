import './Steps.css'

const DEFAULT_PANEL = { wattage: '370', voc: '48', vmp: '40', width: '40' }
const TBS_DEFAULT_WIDTH = 40  // TBS stock panel 116-1038: 80" × 40" × 1.5"

function WidthBadge({ widthStr }) {
  const w = parseFloat(widthStr)
  if (isNaN(w) || w <= 0) return null
  const over = w > 35
  return (
    <span style={{
      display: 'inline-block',
      marginLeft: '0.5rem',
      padding: '0.1rem 0.45rem',
      borderRadius: '4px',
      fontSize: '0.75rem',
      fontWeight: 600,
      background: over ? '#EFF6FF' : '#F0FDF4',
      color: over ? '#1D4ED8' : '#15803D',
      border: `1px solid ${over ? '#BFDBFE' : '#BBF7D0'}`,
    }}>
      {over ? '> 35" matrix' : '≤ 35" matrix'}
    </span>
  )
}

export default function Step3Solar({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v })
  const ownPanels = data.ownPanels !== false

  const displayWidth = ownPanels
    ? (data.panelW || '')
    : String(TBS_DEFAULT_WIDTH)

  function handleOwnPanels(yes) {
    if (yes) {
      onChange({ ...data, ownPanels: true, panelWattage: '', panelVocV: '', panelVmpV: '', panelW: '' })
    } else {
      onChange({
        ...data,
        ownPanels: false,
        panelWattage: DEFAULT_PANEL.wattage,
        panelVocV:    DEFAULT_PANEL.voc,
        panelVmpV:    DEFAULT_PANEL.vmp,
        panelW:       DEFAULT_PANEL.width,
      })
    }
  }

  return (
    <div className="step-section">
      <h2 className="step-title">Solar Panels</h2>
      <p className="step-subtitle">Panel specifications for array sizing.</p>

      {/* ── Solar Panel Data ──────────────────────────────────────────────────── */}
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
              <label>
                Width (inches) <span className="req">*</span>
                <WidthBadge widthStr={data.panelW} />
              </label>
              <input type="number" min="1" step="0.1" placeholder='e.g. 40"'
                value={data.panelW || ''} onChange={e => set('panelW', e.target.value)} />
              <span className="hint">
                Determines racking matrix: panels &gt; 35" wide use a different crossbeam configuration than narrower panels.
              </span>
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
          <div style={{ marginTop: '0.4rem' }}>
            Panel width: <strong>40"</strong>
            <WidthBadge widthStr="40" />
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
              — crossbeam racking configuration for panels wider than 35"
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
