/** Inline loading spinner */
export function Spinner({ size = 40 }) {
  return (
    <div
      style={{ width: size, height: size }}
      className="spinner"
      role="status"
      aria-label="Loading"
    />
  )
}

/** Full-page centered loading */
export function PageLoading() {
  return (
    <div className="loading-center">
      <Spinner />
    </div>
  )
}

/** Position chip: D / M / F */
export function PosChip({ pos }) {
  return <span className={`pos-chip pos-${pos}`}>{pos}</span>
}

/** Value band badge */
export function ValueBadge({ estimated, market }) {
  if (!estimated) return null
  let label, cls
  if (!market) {
    label = 'Est.'; cls = 'badge-blue'
  } else {
    const r = estimated / market
    if (r < 0.75)      { label = 'Undervalued'; cls = 'badge-green' }
    else if (r > 1.3)  { label = 'Overvalued';  cls = 'badge-red' }
    else               { label = 'Fair value';   cls = 'badge-yellow' }
  }
  return <span className={`badge ${cls}`}>{label}</span>
}

/** Tooltip wrapper */
export function Tip({ text, children }) {
  return (
    <span className="tooltip-wrap">
      {children}
      <span className="tooltip-box" role="tooltip">{text}</span>
    </span>
  )
}

/** Disclaimer box shown on every valuation */
export function Disclaimer() {
  return (
    <div className="alert alert-warn mt-16" role="note">
      <strong>Research prototype:</strong> Values are model estimates on a synthetic target — they illustrate the pipeline, not real market prices. Treat outputs as directional signals for discussion, not ground truth.
    </div>
  )
}

/** Caveat about data source */
export function DataCaveat({ source }) {
  return (
    <div className="alert alert-info mt-8" role="note" style={{ fontSize: '0.8rem' }}>
      <strong>Data:</strong> {source || 'Sample/synthetic data generated from real column schemas. Real data required for live deployment.'}
    </div>
  )
}

/** Error box */
export function ErrorBox({ message, onReset, resetLabel = '↺ Reset filters' }) {
  let text = message
  if (Array.isArray(message)) {
    text = message.map(m => (typeof m === 'string' ? m : m?.msg || JSON.stringify(m))).join('; ')
  } else if (message && typeof message === 'object') {
    text = message.detail || message.msg || JSON.stringify(message)
  }
  return (
    <div
      className="alert alert-danger animate-fade flex items-center justify-between wrap gap-12"
      role="alert"
      style={{ marginBottom: 16 }}
    >
      <span>⚠️ {text || 'Value not found or invalid input. Please check your filters and try again.'}</span>
      {onReset && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onReset}>
          {resetLabel}
        </button>
      )}
    </div>
  )
}

/** Progress bar */
export function Bar({ value, max = 1, color = 'var(--c-primary)' }) {
  const pct = Math.min(100, (value / max) * 100)
  return (
    <div className="progress">
      <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

/** Star rating display */
export function Stars({ value, max = 5 }) {
  return (
    <span aria-label={`${value} out of ${max} stars`}>
      {Array.from({ length: max }, (_, i) => (
        <span key={i} style={{ color: i < value ? 'var(--c-yellow)' : 'var(--c-subtle)' }}>★</span>
      ))}
    </span>
  )
}

/** Section header with optional subtitle */
export function SectionHead({ title, subtitle, children }) {
  return (
    <div className="section-head">
      <h2>{title}</h2>
      {subtitle && <p className="text-muted mt-8">{subtitle}</p>}
      {children}
    </div>
  )
}

/** Stat pill for hero stats row */
export function StatPill({ value, label, color }) {
  return (
    <div className="stat-pill">
      <div className="stat-pill-value" style={color ? { color } : undefined}>{value}</div>
      <div className="stat-pill-label">{label}</div>
    </div>
  )
}
