import { IconAlert } from './Icons'

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

/** Position chip: GK / D / M / F */
export function PosChip({ pos }) {
  const code = pos === 'GK' ? 'G' : pos
  const label = (pos === 'G' || pos === 'GK') ? 'GK' : pos
  return <span className={`pos-chip pos-${code}`}>{label}</span>
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
  return null
}

/** Caveat about data source */
export function DataCaveat() {
  return null
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
      <span className="flex items-center gap-8">
        <IconAlert size={17} />
        <span>{text || 'Value not found or invalid input. Please check your filters and try again.'}</span>
      </span>
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

/** Range slider with vertical | tick marks at 10, 20, 30, ... intervals */
export function RangeSlider({
  id,
  min,
  max,
  step = 1,
  value,
  onChange,
  tickStep = 10,
  labelStep,
  formatTick,
  ariaLabel,
  style,
  className = '',
}) {
  const numVal = Number(value)
  const span = Math.max(max - min, 1e-9)
  const fillPct = Math.max(0, Math.min(100, ((numVal - min) / span) * 100))

  const ticks = []
  if (tickStep > 0) {
    const first = Math.ceil(min / tickStep) * tickStep
    for (let t = first; t <= max + 1e-9; t = Math.round((t + tickStep) * 1e6) / 1e6) {
      if (t >= min - 1e-9 && t <= max + 1e-9) ticks.push(t)
    }
  }

  const resolvedLabelStep = labelStep ?? (
    ticks.length <= 11 ? tickStep : ticks.length <= 22 ? tickStep * 2 : tickStep * 5
  )

  return (
    <div className={`range-slider-wrap ${className}`.trim()} style={style}>
      <input
        id={id}
        type="range"
        className="range-slider-input"
        min={min}
        max={max}
        step={step}
        value={numVal}
        aria-label={ariaLabel}
        onChange={e => onChange(Number(e.target.value))}
        style={{
          background: `linear-gradient(to right, var(--c-primary) 0%, var(--c-primary) ${fillPct}%, rgba(255,255,255,0.16) ${fillPct}%, rgba(255,255,255,0.16) 100%)`,
        }}
      />
      {ticks.length > 0 && (
        <div className="range-slider-ticks" aria-hidden="true">
          {ticks.map(t => {
            const pct = ((t - min) / span) * 100
            const showLabel = Math.abs(t % resolvedLabelStep) < 1e-6
            const isActive = Math.abs(numVal - t) < 1e-6
            return (
              <span
                key={t}
                className={`range-slider-tick${showLabel ? ' is-major' : ''}${isActive ? ' is-active' : ''}`}
                style={{ left: `${pct}%` }}
                onClick={() => onChange(t)}
                title={formatTick ? formatTick(t) : String(t)}
              >
                <span className="range-slider-tick-bar" />
                {showLabel && (
                  <span className="range-slider-tick-label">
                    {formatTick ? formatTick(t) : t}
                  </span>
                )}
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}
