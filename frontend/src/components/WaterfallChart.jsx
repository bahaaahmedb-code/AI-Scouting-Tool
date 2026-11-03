import { fmtValue } from '../utils'
import { Tip } from './UI'

/**
 * SHAP waterfall chart.
 * API response shape (from store.waterfall):
 *   { rows: [{label, contribution, pct, value, group, tooltip}],
 *     base_eur, prediction_eur, base_log, prediction_log }
 * shap values are log-scale contributions; bars are proportional to contribution magnitude.
 */
export default function WaterfallChart({ data }) {
  // Accept both old shape {features, base_value, predicted} and new API shape {rows, base_eur, prediction_eur}
  const rows     = data?.rows     ?? data?.features ?? []
  const baseEur  = data?.base_eur ?? data?.base_value ?? 0
  const predEur  = data?.prediction_eur ?? data?.predicted ?? 0

  if (!data || !rows.length) return (
    <div className="empty-state" style={{ padding: 40 }}>
      <div className="empty-state-icon">📊</div>
      <p>No SHAP data available for this player.</p>
    </div>
  )

  // Each row has .contribution (log-scale), .label, .tooltip, .pct (% of base)
  const maxAbs = Math.max(...rows.map(r => Math.abs(r.contribution ?? r.shap ?? 0)), 0.001)
  const BAR_MAX = 60   // max bar width %

  // Format SHAP contribution as EUR delta.
  // The API gives contribution in log-EUR space and pct as % of prediction.
  // We use: delta_EUR ≈ predEur * pct / 100  (pct field from the API)
  // Euro effect per row comes from the API (`eur`): sequential steps in log space that sum exactly to
  // (estimate - base). Fall back to the old approximation only if an older API response lacks it.
  function fmtContrib(r) {
    const contrib = r?.contribution ?? r?.shap ?? 0
    if (contrib == null || contrib === 0) return '±£0'
    let eur = r?.eur
    if (eur == null) eur = (contrib >= 0 ? 1 : -1) * Math.abs((r?.pct ?? 0) / 100) * predEur
    const sign = eur >= 0 ? '+' : '-'
    const a = Math.abs(eur)
    if (a >= 1e6) return `${sign}£${(a / 1e6).toFixed(1)}m`
    if (a >= 1e3) return `${sign}£${(a / 1e3).toFixed(0)}k`
    return `${sign}£${a.toFixed(0)}`
  }

  return (
    <div className="animate-slide">
      {/* Header */}
      <div className="waterfall-row" style={{ borderBottom: '2px solid var(--c-border2)', paddingBottom: 12, marginBottom: 8 }}>
        <div className="waterfall-label label">Feature</div>
        <div style={{ flex: 1 }}>
          <div className="label">Impact on estimated value</div>
        </div>
        <div className="waterfall-val label">SHAP</div>
      </div>

      {/* Base value row */}
      <div className="waterfall-row" style={{ opacity: 0.6 }}>
        <div className="waterfall-label text-muted" style={{ fontSize: '0.8rem' }}>Base (avg player)</div>
        <div className="waterfall-bar-wrap">
          <div
            className="waterfall-bar"
            style={{
              width: '50%', left: 0,
              background: 'rgba(255,255,255,0.05)',
              border: '1px dashed var(--c-border2)',
              color: 'var(--c-muted)', fontSize: '0.75rem',
            }}
          >
            {fmtValue(baseEur)}
          </div>
        </div>
        <div className="waterfall-val text-subtle">{fmtValue(baseEur)}</div>
      </div>

      {/* Feature rows */}
      {rows.map((r, i) => {
        const contrib = r.contribution ?? r.shap ?? 0
        const pct     = (Math.abs(contrib) / maxAbs) * BAR_MAX
        const isPos   = contrib >= 0
        const label   = r.label ?? r.name ?? r.feature ?? `Feature ${i}`
        const tooltip = r.tooltip ?? ''
        return (
          <div key={i} className="waterfall-row" style={{ animationDelay: `${i * 30}ms` }}>
            <div className="waterfall-label" title={tooltip || label}>
              {tooltip ? (
                <Tip text={tooltip}>
                  <span>{label}</span>
                </Tip>
              ) : label}
            </div>

            <div className="waterfall-bar-wrap">
              {/* Centre line */}
              <div style={{ position: 'absolute', left: '50%', width: 1, height: '100%', background: 'var(--c-border)' }} />
              <div
                className={`waterfall-bar ${isPos ? 'pos' : 'neg'}`}
                style={{
                  width: `${pct}%`,
                  [isPos ? 'left' : 'right']: '50%',
                }}
                aria-label={`${label}: ${fmtContrib(r)}`}
              />
            </div>

            <div className={`waterfall-val ${isPos ? 'text-green' : 'text-red'}`}>
              {fmtContrib(r)}
            </div>
          </div>
        )
      })}

      {/* Total row */}
      <div className="waterfall-row" style={{ borderTop: '2px solid var(--c-border2)', marginTop: 8, paddingTop: 12 }}>
        <div className="waterfall-label" style={{ fontWeight: 700 }}>Model Estimate</div>
        <div className="waterfall-bar-wrap">
          <div style={{ flex: 1 }} />
        </div>
        <div className="waterfall-val val-medium" style={{ fontSize: '1.2rem' }}>
          {fmtValue(predEur)}
        </div>
      </div>
    </div>
  )
}
