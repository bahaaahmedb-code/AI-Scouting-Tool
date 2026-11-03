import { useEffect, useState } from 'react'
import { getGlobalImportance, getDependence } from '../api'
import { fmtNum } from '../utils'
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell,
  ScatterChart, Scatter, CartesianGrid,
} from 'recharts'
import { PageLoading, ErrorBox, Disclaimer, DataCaveat, SectionHead } from '../components/UI'

const POSITIONS = [
  { value: '',  label: 'All players' },
  { value: 'D', label: 'Defenders' },
  { value: 'M', label: 'Midfielders' },
  { value: 'F', label: 'Forwards' },
]

const COLORS_POS = { D: '#3b82f6', M: '#10b981', F: '#ef4444', '': '#3b82f6' }

export default function Explain() {
  const [pos, setPos] = useState('')
  const [importance, setImportance] = useState(null)
  const [loadingImp, setLoadingImp] = useState(true)
  const [errorImp, setErrorImp] = useState(null)

  const [selectedFeature, setSelectedFeature] = useState(null)
  const [depData, setDepData] = useState(null)
  const [loadingDep, setLoadingDep] = useState(false)

  useEffect(() => {
    setLoadingImp(true)
    setErrorImp(null)
    getGlobalImportance(pos || undefined)
      .then(d => { setImportance(d); setLoadingImp(false) })
      .catch(e => { setErrorImp(e.message); setLoadingImp(false) })
  }, [pos])

  function loadDependence(feature) {
    setSelectedFeature(feature)
    setLoadingDep(true)
    getDependence(feature)
      .then(d => { setDepData(d); setLoadingDep(false) })
      .catch(() => setLoadingDep(false))
  }

  const barColor = COLORS_POS[pos]

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <h1>🧠 Model Explanations</h1>
          <p className="text-muted">
            SHAP global feature importance shows which stats drive estimated values most. Click a bar to see a dependence plot.
          </p>
        </div>

        {/* ── Position filter ──────────────────────────────────── */}
        <div className="flex gap-8 mb-32">
          {POSITIONS.map(p => (
            <button
              key={p.value}
              id={`explain-pos-${p.value || 'all'}`}
              className={`btn ${pos === p.value ? 'btn-primary' : 'btn-secondary'} btn-sm`}
              onClick={() => setPos(p.value)}
              aria-pressed={pos === p.value}
            >
              {p.label}
            </button>
          ))}
        </div>

        {errorImp && <ErrorBox message={errorImp} />}
        {loadingImp && <PageLoading />}

        {!loadingImp && !errorImp && importance && (
          <div className="grid-2" style={{ gap: 24, alignItems: 'start' }}>
            {/* Global importance bar chart */}
            <div className="card">
              <h3 className="mb-4">Mean |SHAP| by Feature</h3>
              <p className="text-muted mb-20" style={{ fontSize: '0.85rem' }}>
                Average absolute SHAP value across all players. Longer bar = larger impact on valuations.
              </p>
              <div style={{ height: 420 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={importance.merged}
                    layout="vertical"
                    margin={{ left: 16, right: 32, top: 8, bottom: 8 }}
                  >
                    <XAxis
                      type="number"
                      tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
                      tickFormatter={v => v.toFixed(3)}
                    />
                    <YAxis
                      type="category" dataKey="label" width={160}
                      tick={{ fill: 'var(--c-text)', fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{ background: 'var(--c-card2)', border: '1px solid var(--c-border2)', borderRadius: 8 }}
                      formatter={(v, name) => [v.toFixed(4) + ' (log units)', 'Mean |SHAP|']}
                      cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                    />
                    <Bar
                      dataKey="mean_abs"
                      radius={[0, 4, 4, 0]}
                      cursor="pointer"
                      onClick={(d) => loadDependence(d.feature)}
                    >
                      {(importance.merged ?? []).map((entry, index) => (
                        <Cell
                          key={index}
                          fill={entry.feature === selectedFeature ? '#f59e0b' : barColor}
                          opacity={entry.feature === selectedFeature ? 1 : 0.75}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-subtle mt-12" style={{ fontSize: '0.78rem' }}>
                Click a bar to see the dependence plot →
              </p>
            </div>

            {/* Dependence plot */}
            <div className="card" style={{ minHeight: 300 }}>
              {!selectedFeature && (
                <div className="empty-state" style={{ padding: 60 }}>
                  <div className="empty-state-icon">👆</div>
                  <h3>Click a feature</h3>
                  <p>Select a bar on the left to see how that stat affects valuations across all players.</p>
                </div>
              )}

              {selectedFeature && loadingDep && <PageLoading />}

              {selectedFeature && !loadingDep && depData && (
                <div className="animate-fade">
                  <h3 className="mb-4">{depData.label ?? selectedFeature}</h3>
                  <p className="text-muted mb-20" style={{ fontSize: '0.85rem' }}>
                    Each dot is a player. X-axis = raw stat value; Y-axis = SHAP contribution (£). Upward slope = stat boosts value.
                  </p>
                  <div style={{ height: 340 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 16 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border)" />
                        <XAxis
                          dataKey="x" type="number" name={depData.label ?? selectedFeature}
                          tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
                          label={{ value: depData.label ?? selectedFeature, position: 'insideBottom', offset: -8, fill: 'var(--c-muted)', fontSize: 11 }}
                        />
                        <YAxis
                          dataKey="shap" type="number" name="SHAP"
                          tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
                          tickFormatter={v => v.toFixed(3)}
                        />
                        <Tooltip
                          cursor={{ strokeDasharray: '3 3' }}
                          contentStyle={{ background: 'var(--c-card2)', border: '1px solid var(--c-border2)', borderRadius: 8, fontSize: '0.82rem' }}
                          formatter={(v, name) => [
                            name === 'SHAP' ? v.toFixed(4) : fmtNum(v),
                            name,
                          ]}
                        />
                        <Scatter
                          data={depData.points.map(p => ({ ...p, y: p.shap }))}
                          fill={barColor}
                          opacity={0.65}
                          r={4}
                        />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                  {depData.tooltip && (
                    <div className="alert alert-info mt-16" style={{ fontSize: '0.82rem' }}>
                      ℹ️ <strong>{depData.label}:</strong> {depData.tooltip}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── How SHAP works ────────────────────────────────────── */}
        <div className="card mt-32">
          <h3 className="mb-16">📖 How SHAP works (in plain English)</h3>
          <div className="grid-3" style={{ gap: 20 }}>
            {SHAP_EXPLAINERS.map((e, i) => (
              <div key={i} style={{ padding: 16, background: 'var(--c-surface)', borderRadius: 8 }}>
                <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>{e.icon}</div>
                <div style={{ fontWeight: 600, marginBottom: 6, fontSize: '0.95rem' }}>{e.title}</div>
                <p className="text-muted" style={{ fontSize: '0.85rem', lineHeight: 1.6 }}>{e.text}</p>
              </div>
            ))}
          </div>
        </div>

        <DataCaveat />
        <Disclaimer />
      </div>
    </main>
  )
}

const SHAP_EXPLAINERS = [
  {
    icon: '🎯',
    title: 'What is a SHAP value?',
    text: 'A SHAP value tells you how much a specific stat pushed the model\'s estimate up or down, compared to the average player. Positive = increased value; negative = decreased value.',
  },
  {
    icon: '📊',
    title: 'Why do the bars differ by player?',
    text: 'SHAP is computed individually per player. A high xG score matters more for a striker than for a centre-back. The waterfall on each player profile shows their personal breakdown.',
  },
  {
    icon: '🧪',
    title: 'Correlation ≠ causation',
    text: 'The model finds statistical patterns, not football causes. A high assist count correlates with high value, but it doesn\'t mean assisting alone makes a player expensive.',
  },
]
