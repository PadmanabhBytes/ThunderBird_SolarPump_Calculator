import { useState } from 'react'
import Step1Flow    from './steps/Step1Flow'
import Step2Well    from './steps/Step2Well'
import Step3Solar   from './steps/Step3Solar'
import Step4Controls from './steps/Step4Controls'
import { runCalculation, runDualCalculation } from './api/calculator'
import './CalculatorForm.css'

const STEPS = [
  { label: 'Location & Flow', short: '1' },
  { label: 'Well',            short: '2' },
  { label: 'Solar Panels',    short: '3' },
  { label: 'Controls',        short: '4' },
]

function _topEndPsi(range) {
  if (!range) return null
  const nums = range.match(/\d+/g)
  return nums && nums.length >= 2 ? parseInt(nums[nums.length - 1]) : null
}

function validate(step, data) {
  if (step === 0) {
    // Location
    const hasCoords = data.latitude && data.longitude
    const hasPSH    = data.peakSunHours
    if (!hasCoords && !hasPSH) {
      return 'Enter a ZIP code and click "Look up", or enter GPS coordinates, to determine your solar zone before proceeding.'
    }
    // GPM
    if (!data.requiredFlowGpm) return 'Please enter the required flow rate (GPM).'
    if (parseFloat(data.requiredFlowGpm) <= 0) return 'GPM must be greater than 0'
    // TDH
    const helpMeCalculate = data.helpMeCalculate !== false
    if (!helpMeCalculate) {
      if (!data.directTdh) return 'Please enter the Total Dynamic Head (TDH).'
      if (parseFloat(data.directTdh) <= 0) return 'TDH must be greater than 0'
    } else {
      if (!data.staticWaterLevel) return 'Please enter the Static Water Level.'
      if (parseFloat(data.staticWaterLevel) <= 0) return 'Static water level must be greater than 0'
      const empty = v => v === '' || v === undefined || v === null
      if (empty(data.drawdown))      return 'Please enter Expected Drawdown (0 if unknown).'
      if (empty(data.elevationGain)) return 'Please enter Vertical Elevation Gain (0 if none).'
      if (empty(data.pressurePsi))   return 'Please enter System Pressure (0 if none).'
    }
    // Pipe run
    if (data.hasPipeRun) {
      if (!data.pipeDiameter) return 'Please enter the pipe diameter.'
      if (!data.pipeLength)   return 'Please enter the pipe run length.'
    }
    return null
  }

  if (step === 1) {
    if (!data.recoveryUnknown && !data.recoveryRate) {
      return 'Please enter the well recovery rate, or check "Recovery rate unknown".'
    }
    return null
  }

  if (step === 2) {
    if (data.ownPanels !== false) {
      if (!data.panelWattage) return 'Please enter the panel power rating (W).'
      if (!data.panelW)       return 'Please enter the panel width (inches) — required for racking matrix selection.'
    }
    return null
  }

  if (step === 3) {
    const systemType         = data.systemType || 'none'
    const showPressureFields = systemType === 'pressure' || systemType === 'floatPressure'
    if (showPressureFields && !data.pressureSwitchRange) {
      return 'Please select a pressure switch range for the pressure switch.'
    }
    // PSI mismatch blocks — matches requirement: "customer must update system pressure before proceeding"
    const topEnd   = _topEndPsi(data.pressureSwitchRange)
    const sysPsi   = parseFloat(data.pressurePsi)
    const helpMode = data.helpMeCalculate !== false
    if (
      showPressureFields && helpMode &&
      topEnd != null && !isNaN(sysPsi) && sysPsi > 0 &&
      Math.abs(topEnd - sysPsi) > 0.01
    ) {
      return `PSI Mismatch: System pressure (${sysPsi} PSI) does not match the pressure switch shutoff (${topEnd} PSI). Update the System Pressure field in Step 1 to ${topEnd} PSI before proceeding.`
    }
    return null
  }

  return null
}

export default function CalculatorForm({ onResults, initialData }) {
  const [step, setStep]   = useState(0)
  const [data, setData]   = useState(initialData || { pipeMaterial: 'PVC', panelWattage: '400' })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [maxVisited, setMaxVisited] = useState(initialData ? STEPS.length - 1 : 0)

  function goTo(i) {
    setError(null)
    setStep(i)
    setMaxVisited(v => Math.max(v, i))
  }

  function goNext() {
    const err = validate(step, data)
    if (err) { setError(err); return }
    setError(null)
    const next = step + 1
    setStep(next)
    setMaxVisited(v => Math.max(v, next))
  }

  function goBack() {
    setError(null)
    setStep(s => s - 1)
  }

  async function submit() {
    const err = validate(3, data)
    if (err) { setError(err); return }
    setError(null)
    setLoading(true)
    try {
      const result = (data.gpdAccepted === false && data.desiredGpd)
        ? await runDualCalculation(data)
        : await runCalculation(data)
      onResults(result, data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const stepComponents = [
    <Step1Flow    key="s1" data={data} onChange={setData} />,
    <Step2Well    key="s2" data={data} onChange={setData} />,
    <Step3Solar   key="s3" data={data} onChange={setData} />,
    <Step4Controls key="s4" data={data} onChange={setData} />,
  ]

  return (
    <div className="calc-form">
      {/* Step indicator */}
      <div className="step-indicator">
        {STEPS.map((s, i) => {
          const clickable = i <= maxVisited && i !== step
          return (
          <div key={i} className={`step-dot ${i < step ? 'done' : i === step ? 'active' : ''}`}>
            <div
              className={`dot-circle${clickable ? ' clickable' : ''}`}
              onClick={() => clickable && goTo(i)}
            >
              {i < step ? <CheckIcon /> : <span>{i + 1}</span>}
            </div>
            <span
              className={`dot-label${clickable ? ' clickable' : ''}`}
              onClick={() => clickable && goTo(i)}
            >{s.label}</span>
            {i < STEPS.length - 1 && <div className="dot-line" />}
          </div>
          )
        })}
      </div>

      {/* Step content */}
      <div className="step-body">
        {stepComponents[step]}
      </div>

      {/* Error */}
      {error && (
        <div className="form-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Nav */}
      <div className="form-nav">
        {step > 0 && (
          <button className="btn-secondary" onClick={goBack} disabled={loading}>
            ← Back
          </button>
        )}
        <div style={{ flex: 1 }} />
        {step < STEPS.length - 1 ? (
          <button className="btn-primary" onClick={goNext} disabled={loading}>
            Next →
          </button>
        ) : (
          <button className="btn-gold" onClick={submit} disabled={loading}>
            {loading ? 'Calculating…' : 'Calculate →'}
          </button>
        )}
      </div>
    </div>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2.5 7L5.5 10L11.5 4" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
