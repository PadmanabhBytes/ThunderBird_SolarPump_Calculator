import { useState } from 'react'
import Step1Flow    from './steps/Step1Flow'
import Step2Well    from './steps/Step2Well'
import Step3Solar   from './steps/Step3Solar'
import Step4Controls from './steps/Step4Controls'
import { runCalculation } from './api/calculator'
import './CalculatorForm.css'

const STEPS = [
  { label: 'Production & TDH', short: '1' },
  { label: 'Well',             short: '2' },
  { label: 'Solar',            short: '3' },
  { label: 'Controls',         short: '4' },
]

const REQUIRED_FIELDS = {
  0: ['requiredFlowGpm', 'staticWaterLevel', 'drawdown', 'pipeDiameter', 'pipeLength'],
  1: [],
  2: [], // lat/long OR peakSunHours — validated in component
  3: [],
}

function validate(step, data) {
  const missing = REQUIRED_FIELDS[step].filter(k => {
    const v = data[k]
    return v === undefined || v === null || v === ''
  })
  if (missing.length) return `Please fill in: ${missing.join(', ')}`

  if (step === 0) {
    if (parseFloat(data.requiredFlowGpm) <= 0) return 'GPM must be greater than 0'
    if (parseFloat(data.staticWaterLevel) <= 0) return 'Static water level must be greater than 0'
    // pipe diameter / length of 0 means "no pipe run" — allowed
  }

  if (step === 2) {
    const hasCoords = data.latitude && data.longitude
    const hasPSH    = data.peakSunHours
    if (!hasCoords && !hasPSH) return 'Enter a ZIP code and click "Look up", enter GPS coordinates, or enter peak sun hours manually.'
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
    setError(null)
    setLoading(true)
    try {
      const result = await runCalculation(data)
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
