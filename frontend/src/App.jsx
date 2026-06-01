import { useState } from 'react'
import CalculatorForm from './CalculatorForm'
import ResultsPage    from './ResultsPage'
import './App.css'

export default function App() {
  const [page, setPage]         = useState('form')   // 'form' | 'results'
  const [results, setResults]   = useState(null)
  const [formData, setFormData] = useState(null)

  function handleResults(result, data) {
    setResults(result)
    setFormData(data)
    setPage('results')
  }

  function handleEdit() {
    setPage('form')
    setResults(null)
    // formData preserved — form will pre-fill with previous values
  }

  function handleReset() {
    setPage('form')
    setResults(null)
    setFormData(null)
  }

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="brand">
            <span className="brand-icon">☀</span>
            <div>
              <div className="brand-name">Thunderbird Solar Supply</div>
              <div className="brand-tagline">Solar Pump Sizing Calculator</div>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="app-main">
        <div className="app-container">
          {page === 'form' ? (
            <>
              <div className="page-intro">
                <h1 className="page-title">Solar Water Pump Sizing</h1>
                <p className="page-desc">
                  Enter your site parameters to get pump recommendations, solar array sizing, and a complete equipment list.
                </p>
              </div>
              <CalculatorForm onResults={handleResults} initialData={formData} />
            </>
          ) : (
            <>
              <div className="page-intro">
                <h1 className="page-title">Sizing Results</h1>
                <p className="page-desc">
                  Three tiers ranked by cost, precision, and capacity — select the one that fits your project.
                </p>
              </div>
              <ResultsPage result={results} formData={formData} onReset={handleReset} onEdit={handleEdit} />
            </>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="app-footer">
      </footer>
    </div>
  )
}
