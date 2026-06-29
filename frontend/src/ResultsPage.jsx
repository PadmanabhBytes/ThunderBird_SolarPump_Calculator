import { useState, useRef } from 'react'
import html2pdf from 'html2pdf.js'
import { getAccessories, getSystemFeatures } from './data/accessories'
import './ResultsPage.css'

const TIER_LABELS = { economical: 'Economical', precise: 'Precise', premium: 'Premium' }
const TIER_COLORS = { economical: 'green', precise: 'gold', premium: 'purple' }

// ── Helpers ───────────────────────────────────────────────────────────────────

function pumpTypeLabel(type) {
  const m = { submersible: 'Submersible', surface: 'Surface Pump', helical_rotor: 'Helical Rotor' }
  return m[type] || type?.replace(/_/g, ' ')
}

function voltageLabel(cls) {
  const m = { ac: 'AC', dc: 'DC', hybrid: 'AC/DC' }
  return m[cls] || cls?.toUpperCase()
}

function buildWhyItems(pump, tier, tdh, gpm, panels, formData) {
  if (!pump) return []
  const items = []
  const peakFlow = tier?.achievable_gpm ?? pump.max_flow_gpm

  if (tdh)      items.push({ bold: 'Handles your TDH',  text: `Operates efficiently at ${tdh.toFixed(0)} ft` })
  if (peakFlow) items.push({ bold: 'Meets flow needs',  text: `Delivers ${peakFlow} GPM (need: ${gpm} GPM)` })

  const vCls = pump.voltage_class
  if (vCls === 'hybrid' || vCls === 'ac') {
    items.push({ bold: 'Hybrid power', text: 'Solar primary with AC grid backup' })
  } else if (vCls === 'dc') {
    items.push({ bold: 'Solar direct', text: 'Runs directly off panels — no inverter losses' })
  }

  if (pump.max_flow_gpm > parseFloat(gpm) * 1.1) {
    items.push({ bold: 'Flow headroom', text: `Up to ${pump.max_flow_gpm} GPM max capacity` })
  }

  if (panels) items.push({ bold: 'Optimized panels', text: `${panels} panels for your solar zone` })
  items.push({ bold: 'Proven reliability', text: 'Professional-grade with warranty' })

  if (formData.poorWaterQuality)  items.push({ bold: 'Note', text: 'Helical rotor pumps excluded — poor water quality.', warn: true })
  if (formData.generatorBackup)   items.push({ bold: 'Note', text: 'DC-only pumps excluded — generator backup required.', warn: true })
  if (formData.recoveryUnknown)   items.push({ bold: 'Note', text: 'Add dry-run protection — well recovery unknown.', warn: true })

  return items
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ResultsPage({ result, formData, onReset, onEdit }) {
  const [activeTier, setActiveTier]       = useState('precise')
  const [showEquipment, setShowEquipment] = useState(true)
  const [showRacking, setShowRacking]     = useState(true)
  const [showWire, setShowWire]           = useState(false)
  const [showTdh, setShowTdh]             = useState(false)
  const pdfRef = useRef(null)

  const isDual = result.mode === 'dual'
  const [activeCategory, setActiveCategory] = useState('category1')
  const activeResult = isDual ? result[activeCategory] : result

  const tier       = activeResult.recommendations?.[activeTier]
  const pump       = tier?.pump
  const panels     = tier?.solar_panels
  const accessories = pump ? getAccessories(pump.pump_id, panels, {
    ownPanels:        formData.ownPanels !== false,
    ownRacking:       formData.ownRacking === true,
    use2_5Racking:    formData.tbsRackingKit !== false,
    dryRunConcern:    formData.dryRunConcern === 'yes',
    panelWattage:     parseFloat(formData.panelWattage) || 370,
    floatSwitch:      formData.floatSwitch === true,
    pressureSwitch:   formData.pressureSwitch === true,
    pressureSwitchRange: formData.pressureSwitchRange || '',
    panelDims:        (formData.panelL || formData.panelW)
      ? { l: formData.panelL, w: formData.panelW, h: formData.panelH }
      : null,
    staticWaterLevel: parseFloat(formData.staticWaterLevel) || 0,
  }) : []
  const tbsItems      = accessories.filter(a => a.category === 'tbs' && !a.isRacking)
  const customerItems = accessories.filter(a => a.category === 'customer' && !a.isRacking)
  const tbsRacking    = accessories.filter(a => a.isRacking && a.category === 'tbs')
  const custRacking   = accessories.filter(a => a.isRacking && a.category === 'customer')

  // Racking summary line for card stat row + collapsible subtitle
  const rackSummary = tbsRacking.length > 0
    ? tbsRacking.map(r => `(${r.qty}×) ${r.sku}`).join(' + ')
    : null

  // Matrix selection context for display
  const panelWidthIn   = formData.panelW ? parseFloat(formData.panelW) : (formData.ownPanels === false ? 40 : null)
  const panelExceeds35 = panelWidthIn != null ? panelWidthIn > 35 : true
  const rackMatrixLabel = formData.tbsRackingKit !== false
    ? (panelExceeds35 ? 'Matrix 1 — 2.5" preferred, panel > 35"' : 'Matrix 2 — 2.5" preferred, panel ≤ 35"')
    : (panelExceeds35 ? 'Matrix 3 — 4" standard, panel > 35"'   : 'Matrix 4 — 4" standard, panel ≤ 35"')

  const tdh        = activeResult.head_breakdown?.total_dynamic_head_ft
  const tdhStr     = tdh != null ? tdh.toFixed(1) : null
  const gpm        = isDual && activeCategory === 'category2'
    ? String(result.derivedGpm)
    : formData.requiredFlowGpm
  const gpd        = activeResult.daily_water_demand_gallons
  const frictionFt = activeResult.head_breakdown?.friction_loss_ft
  const pressureHd = activeResult.head_breakdown?.pressure_head_ft
  const pumpingLvl = formData.staticWaterLevel && formData.drawdown
    ? parseFloat(formData.staticWaterLevel) + parseFloat(formData.drawdown)
    : null
  const wireRes    = activeResult.wire_sizing
  const warnings   = (activeResult.warnings || []).filter(
    w => !w.startsWith('Solar resource lookup unavailable') && !w.startsWith('NREL lookup failed')
  )
  const opWatts    = tier?.operating_wattage_w
  const panelWatt  = parseFloat(formData.panelWattage) || 400

  const headMarginPct = tier?.head_margin_percent
  const headMarginFt  = tdh != null && headMarginPct != null ? (headMarginPct / 100) * tdh : null

  const peakFlow   = tier?.achievable_gpm ?? pump?.max_flow_gpm
  // Use zone-adjusted GPD from backend (GPM × 6.5 × 60 × 1.1 × solar_zone_coeff)
  const dailyOut   = activeResult.daily_water_demand_gallons
    ? Math.round(activeResult.daily_water_demand_gallons)
    : (peakFlow != null ? Math.round(peakFlow * 6.5 * 60 * 1.1) : null)

  // Solar system voltages
  const panelVoc   = parseFloat(formData.panelVocV) || null
  const panelVmp   = parseFloat(formData.panelVmpV) || null
  const sysVoc     = panels != null && panelVoc ? Math.round(panels * panelVoc * 10) / 10 : null
  const sysVmp     = panels != null && panelVmp ? Math.round(panels * panelVmp * 10) / 10 : null

  const isPerfectMatch  = tier?.meets_head_requirement && tier?.meets_flow_requirement
  const systemFeatures  = pump ? getSystemFeatures(pump.pump_id) : []

  const whyItems = buildWhyItems(pump, tier, tdh, gpm, panels, formData)

  const equipSubtitle = panels != null ? `${panels} Panel System — Complete Parts List` : 'Complete Parts List'
  const wireSubtitle  = wireRes
    ? `Recommended: ${wireRes.recommended_awg} (${wireRes.voltage_drop_percent?.toFixed(1)}% loss)`
    : null

  function handlePrint() {
    const el = pdfRef.current
    if (!el) return
    const opt = {
      margin:       [10, 10, 10, 10],
      filename:     'TBS-Solar-Quote.pdf',
      image:        { type: 'jpeg', quality: 0.97 },
      html2canvas:  { scale: 2, useCORS: true, scrollY: 0 },
      jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' },
      pagebreak:    { mode: ['avoid-all', 'css'] },
    }
    html2pdf().set(opt).from(el).save()
  }

  return (
    <div className="results-page" ref={pdfRef}>
      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="warnings-bar">
          {warnings.map((w, i) => <WarningChip key={i} text={w} />)}
        </div>
      )}

      {/* Dual category tabs */}
      {isDual && (
        <div className="dual-category-tabs">
          <button
            className={`dual-tab ${activeCategory === 'category1' ? 'active' : ''}`}
            onClick={() => setActiveCategory('category1')}>
            Category 1 — Optimized for {result.originalGpm} GPM
          </button>
          <button
            className={`dual-tab ${activeCategory === 'category2' ? 'active' : ''}`}
            onClick={() => setActiveCategory('category2')}>
            Category 2 — Optimized for {result.desiredGpd?.toLocaleString()} GPD
          </button>
        </div>
      )}

      {/* Tier tabs */}
      <div className="tier-tabs">
        {Object.keys(TIER_LABELS).map(t => (
          activeResult.recommendations?.[t] && (
            <button key={t}
              className={`tier-tab ${activeTier === t ? 'active' : ''} color-${TIER_COLORS[t]}`}
              onClick={() => setActiveTier(t)}>
              {TIER_LABELS[t]}
            </button>
          )
        ))}
      </div>

      {/* ── 1. Gold hero banner ─────────────────────────────────────────────── */}
      {pump && (
        <div className="pump-hero">
          <div className="pump-hero-left">
            <div className="pump-hero-name">{pump.pump_id}</div>
            <div className="pump-hero-sub">
              {pump.min_casing_diameter_in != null ? `${pump.min_casing_diameter_in}" ` : ''}{pumpTypeLabel(pump.pump_type)} · {voltageLabel(pump.voltage_class)}
            </div>
          </div>
          {isPerfectMatch && (
            <span className="perfect-match-badge">Perfect Match</span>
          )}
        </div>
      )}

      {/* ── System Features ─────────────────────────────────────────────────── */}
      {systemFeatures.length > 0 && (
        <div className="system-features">
          <div className="system-features-title">System Features</div>
          <ul className="system-features-list">
            {systemFeatures.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}

      {/* ── 3-column results layout ─────────────────────────────────────────── */}
      <div className="results-grid">
        {/* Col 1: Requirements (unchanged — skip #2) */}
        <div className="result-card req-card">
          <h3 className="card-dot-title gray">YOUR REQUIREMENTS</h3>
          <dl className="stat-list">
            <StatRow label="Flow Rate"          value={`${gpm} GPM`} />
            <StatRow label="Daily Demand"       value={gpd ? `${Math.round(gpd).toLocaleString()} GPD` : '—'} />
            <StatRow label="Total Head (TDH)"   value={tdhStr ? `${tdhStr} ft` : '—'} highlight />
            <StatRow label="Static Water Level" value={formData.staticWaterLevel ? `${formData.staticWaterLevel} ft` : '—'} />
            <StatRow label="Drawdown"           value={formData.drawdown ? `${formData.drawdown} ft` : '—'} />
            <StatRow label="Elevation Gain"     value={formData.elevationGain ? `${formData.elevationGain} ft` : '0 ft'} />
            <StatRow label="Pressure"           value={formData.pressurePsi != null && formData.pressurePsi !== '' ? `${formData.pressurePsi} PSI` : '0 PSI'} />
            <StatRow label="Pipe"
              value={formData.pipeMaterial
                ? `${formData.pipeDiameter}" ${formData.pipeMaterial} / ${formData.pipeLength} ft`
                : '—'} />
            <StatRow label="Panel Power"        value={formData.panelWattage ? `${formData.panelWattage} W` : '—'} />
            {formData.panelVocV && <StatRow label="Panel Voc"  value={`${formData.panelVocV} Vdc`} />}
            {formData.panelVmpV && <StatRow label="Panel Vmp"  value={`${formData.panelVmpV} Vdc`} />}
          </dl>
        </div>

        {/* ── 3. Col 2: Recommended system — green border, new fields ───────── */}
        <div className="result-card rec-card">
          <div className="card-title-row">
            <h3 className="card-dot-title green">RECOMMENDED SYSTEM</h3>
            <span className="rec-badge">RECOMMENDED</span>
          </div>

          {pump ? (
            <>
              <div className="pump-name">{pump.model || pump.pump_id}</div>

              <dl className="stat-list rec-stats">
                <StatRow label="Operating TDH"  value={tdhStr ? `${tdhStr} ft` : '—'}   highlight />
                <StatRow label="Solar Panels"    value={panels != null ? `${panels}` : '—'}           highlight />
                {opWatts != null && <StatRow label="Operating Power" value={`${opWatts.toFixed(0)} W`} />}
                {pump?.rated_power_w != null && <StatRow label="Deadhead Power" value={`${pump.rated_power_w.toFixed(0)} W`} />}
                <StatRow label="Solar Array"     value={panels != null ? `${(panels * panelWatt).toLocaleString()} W` : '—'} />
                {sysVoc != null && <StatRow label="Sys Voc (@STC)"  value={`${sysVoc} Vdc`} />}
                {sysVmp != null && <StatRow label="Sys Vmp (@STC)"  value={`${sysVmp} Vdc`} />}
                {panels != null && <StatRow label="Connections"      value={`1x series string — ${panels} panels`} />}
                {rackSummary    && <StatRow label="Solar Racking"    value={rackSummary} highlight />}
              </dl>

              {headMarginFt != null && headMarginFt > 0 && (
                <div className="margin-pill">
                  Head margin: +{headMarginFt.toFixed(0)} ft ({headMarginPct.toFixed(0)}%)
                </div>
              )}
            </>
          ) : (
            <div className="no-match">No pump matched for this tier.</div>
          )}
        </div>

        {/* ── 4. Col 3: Why This Works — gold dot, bold bullets ─────────────── */}
        <div className="result-card why-card">
          <h3 className="card-dot-title gold">WHY THIS WORKS</h3>
          <ul className="why-list">
            {whyItems.map((item, i) => (
              <WhyBullet key={i} bold={item.bold} text={item.text} warn={item.warn} />
            ))}
            {!pump && <li className="why-item muted">No pump matched — adjust requirements.</li>}
          </ul>
        </div>
      </div>

      {/* ── TDH Breakdown — collapsible, matches PDF system overview ─────────── */}
      <Collapsible
        open={showTdh}
        onToggle={() => setShowTdh(v => !v)}
        title="TDH Breakdown"
        subtitle={tdhStr ? `Total: ${tdhStr} ft` : null}>
        <dl className="stat-list inline">
          <StatRow label="Static Water Level"  value={formData.staticWaterLevel ? `${formData.staticWaterLevel} ft` : '—'} />
          <StatRow label="Drawdown"            value={formData.drawdown ? `${formData.drawdown} ft` : '—'} />
          <StatRow label="Pumping Level"       value={pumpingLvl != null ? `${pumpingLvl.toFixed(0)} ft` : '—'} highlight />
          <StatRow label="Elevation Gain"      value={formData.elevationGain ? `${formData.elevationGain} ft` : '0 ft'} />
          <StatRow label="Friction Loss"
            value={frictionFt != null
              ? (formData.hasPipeRun && formData.pipeDiameter && formData.pipeLength
                  ? `${frictionFt.toFixed(2)} ft (${formData.pipeDiameter}" ${formData.pipeMaterial} × ${formData.pipeLength} ft @ ${activeResult.head_breakdown?.friction_flow_gpm ?? gpm} GPM)`
                  : `${frictionFt.toFixed(2)} ft`)
              : '—'} />
          <StatRow label="Pressure Head"      value={pressureHd != null ? `${pressureHd.toFixed(2)} ft` : '0 ft'} />
          <StatRow label="Total TDH"          value={tdhStr ? `${tdhStr} ft` : '—'} highlight />
        </dl>
      </Collapsible>

      {/* ── True Production banner ───────────────────────────────────────────── */}
      {peakFlow != null && (
        <div className="true-production-banner">
          <div className="tp-label">True Production <span className="tp-note">(assuming 7.5% efficiency loss from STC)</span></div>
          <ul className="tp-list">
            <li>{peakFlow} GPM</li>
            {dailyOut != null && <li>{dailyOut.toLocaleString()} GPD</li>}
          </ul>
        </div>
      )}

      {/* ── Solar Racking Recommendation ─────────────────────────────────────── */}
      {tbsRacking.length > 0 && (
        <Collapsible
          open={showRacking}
          onToggle={() => setShowRacking(v => !v)}
          title="Solar Racking Recommendation"
          subtitle={rackSummary}>
          <div className="racking-matrix-info">
            <div className="racking-matrix-badge">{rackMatrixLabel}</div>
            <dl className="stat-list inline" style={{ marginTop: '0.75rem' }}>
              <StatRow label="Panel Count"      value={panels != null ? `${panels}` : '—'} />
              <StatRow label="Panel Width"      value={panelWidthIn != null ? `${panelWidthIn}"` : 'Not entered (assumed > 35")'} />
              <StatRow label={'Exceeds 35"'}     value={panelExceeds35 ? 'Yes' : 'No'} />
              <StatRow label={'2.5" Preference'} value={formData.tbsRackingKit !== false ? 'Yes' : 'No'} />
            </dl>
          </div>

          <div className="acc-section-header" style={{ marginTop: '1rem' }}>TBS Rack Kits</div>
          <div className="accessories-list" style={{ marginTop: '0.5rem' }}>
            {tbsRacking.map((r, i) => <AccessoryCard key={r.sku || i} item={r} />)}
          </div>

          {custRacking.length > 0 && (
            <>
              <div className="acc-section-header customer" style={{ marginTop: '0.75rem' }}>Customer-Provided Materials</div>
              <div className="accessories-list" style={{ marginTop: '0.5rem' }}>
                {custRacking.map((r, i) => <AccessoryCard key={i} item={r} />)}
              </div>
            </>
          )}
        </Collapsible>
      )}

      {/* ── 6. Wire Sizing — collapsible with inline subtitle ─────────────────── */}
      {wireRes && (
        <Collapsible
          open={showWire}
          onToggle={() => setShowWire(v => !v)}
          title="Wire Sizing Calculator"
          subtitle={wireSubtitle}>
          <dl className="stat-list inline">
            <StatRow label="Recommended AWG"        value={wireRes.recommended_awg} highlight />
            <StatRow label="Vmp_Array (×0.95)"      value={wireRes.vmp_array_v != null ? `${wireRes.vmp_array_v} V` : `${wireRes.system_voltage} V`} />
            <StatRow label="System Power"           value={wireRes.system_power_w != null ? `${wireRes.system_power_w} W` : `${wireRes.operating_watts} W`} />
            <StatRow label="Amp Draw (×1.05, ≤12A)" value={wireRes.amp_draw_a != null ? `${wireRes.amp_draw_a?.toFixed(2)} A` : `${wireRes.operating_current_a?.toFixed(2)} A`} />
            <StatRow label="Wire Resistance"        value={`${wireRes.resistance_per_1000ft} Ω/kft`} />
            <StatRow label="Voltage Drop"           value={`${wireRes.voltage_drop_percent?.toFixed(1)}%`} />
            <StatRow label="One-Way Distance"       value={`${wireRes.wire_distance_ft} ft`} />
          </dl>
          {wireRes.max_length_by_gauge && Object.keys(wireRes.max_length_by_gauge).length > 0 && (
            <div style={{ marginTop: '0.75rem' }}>
              <div className="acc-section-header" style={{ marginBottom: '0.4rem' }}>Max Wire Length by Gauge</div>
              <dl className="stat-list inline">
                {Object.entries(wireRes.max_length_by_gauge).map(([awg, len]) => (
                  <StatRow key={awg} label={awg} value={`${len} ft`} highlight={awg === wireRes.recommended_awg} />
                ))}
              </dl>
            </div>
          )}
          {wireRes.note && <div className="wire-warning">{wireRes.note}</div>}
        </Collapsible>
      )}

      {/* ── 5 & 6. Equipment Breakdown — (qty) SKU format, gold primary ────── */}
      <Collapsible
        open={showEquipment}
        onToggle={() => setShowEquipment(v => !v)}
        title="Equipment Breakdown"
        subtitle={equipSubtitle}>
        {accessories.length > 0 ? (
          <div className="accessories-list">
            {tbsItems.length > 0 && (
              <>
                <div className="acc-section-header">TBS Equipment</div>
                {tbsItems.map((a, i) => <AccessoryCard key={a.sku || i} item={a} />)}
              </>
            )}
            {customerItems.length > 0 && (
              <>
                <div className="acc-section-header customer">Customer Provided</div>
                {customerItems.map((a, i) => <AccessoryCard key={i} item={a} />)}
              </>
            )}
          </div>
        ) : (
          <p className="muted-note">
            {pump
              ? <>No accessories configured for pump <strong>{pump.pump_id}</strong>.</>
              : 'No pump matched your requirements — adjust well casing, TDH, or flow to see the equipment list.'}
          </p>
        )}
      </Collapsible>

      {/* Action buttons */}
      <div className="results-actions">
        <button className="btn-outline" onClick={onReset}>← New Calculation</button>
        <button className="btn-secondary" onClick={onEdit}>Edit Inputs</button>
        <button className="btn-print" onClick={handlePrint}>Print Quote</button>
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatRow({ label, value, highlight }) {
  return (
    <>
      <dt className="stat-label">{label}</dt>
      <dd className={`stat-value ${highlight ? 'highlight' : ''}`}>{value ?? '—'}</dd>
    </>
  )
}

// ── 4. Bold-label bullet item ─────────────────────────────────────────────────
function WhyBullet({ bold, text, warn }) {
  return (
    <li className={`why-item ${warn ? 'warn' : ''}`}>
      · <strong>{bold}:</strong> {text}
    </li>
  )
}

function WarningChip({ text }) {
  return <div className="warning-chip">{text}</div>
}

// ── 5. Equipment card: (qty) SKU title, green In Stock text, gold primary bg ──
function AccessoryCard({ item }) {
  return (
    <div className={`accessory-card ${item.highlight ? 'acc-primary' : ''} ${item.warn ? 'acc-warn' : ''}`}>
      <div className="acc-title">({item.qty}x) {item.sku}</div>
      <div className="acc-desc">{item.description}</div>
      {item.inStock && !item.warn && <div className="acc-in-stock">In Stock</div>}
    </div>
  )
}

// ── 6. Collapsible with subtitle + +/− toggle ─────────────────────────────────
function Collapsible({ open, onToggle, title, subtitle, children }) {
  return (
    <div className="collapsible">
      <button className="collapsible-header" onClick={onToggle}>
        <div className="collapsible-header-text">
          <span className="collapsible-title">{title}</span>
          {subtitle && <span className="collapsible-subtitle">{subtitle}</span>}
        </div>
        <span className="collapsible-toggle">{open ? '−' : '+'}</span>
      </button>
      {open && <div className="collapsible-body">{children}</div>}
    </div>
  )
}
