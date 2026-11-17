import { fmtValue } from '../utils'
import { IconTarget, IconClipboard, IconAlert, IconTrendDown } from './Icons'

export default function AgingProjectionPanel({ projection }) {
  if (!projection) {
    return (
      <div className="card">
        <p className="text-muted">No multi-season aging or contract projection available for this player.</p>
      </div>
    )
  }

  const {
    name,
    position_name,
    subrole,
    current_age,
    peak_age_window,
    confidence,
    trajectory_label,
    trajectory_badge,
    current_role_index,
    current_value_eur,
    headline_metrics = [],
    timeline = [],
    future = [],
    contract = {},
  } = projection

  const badgeClass =
    trajectory_badge === 'green' ? 'badge-green' :
    trajectory_badge === 'blue' ? 'badge-blue' :
    trajectory_badge === 'red' ? 'badge-red' : 'badge-amber'

  // SVG Trajectory Chart dimensions (generous left/right/top/bottom padding so labels never clip or collide)
  const W = 860
  const H = 270
  const padL = 92
  const padR = 84
  const padT = 44
  const padB = 54
  const innerW = W - padL - padR
  const innerH = H - padT - padB

  const nPts = timeline.length
  const xAt = (idx) => padL + (nPts > 1 ? (idx / (nPts - 1)) * innerW : innerW / 2)

  const roleVals = timeline.map(t => Number(t.role_index || 50))
  const minRole = Math.max(10, Math.floor((Math.min(...roleVals) - 10) / 5) * 5)
  const maxRole = Math.min(100, Math.ceil((Math.max(...roleVals) + 8) / 5) * 5)
  const yRole = (v) => padT + innerH - ((v - minRole) / Math.max(1, maxRole - minRole)) * innerH

  const curIdx = timeline.findIndex(t => t.type === 'current')
  const pastPts = timeline.slice(0, curIdx + 1)
  const futPts = curIdx >= 0 ? timeline.slice(curIdx) : []

  const polyPoints = (arr, offset = 0) =>
    arr.map((t, k) => `${xAt(offset + k).toFixed(1)},${yRole(t.role_index).toFixed(1)}`).join(' ')

  return (
    <div className="animate-fade">
      {/* ── Top Contract & Trajectory Advisory Banner ──────────────────────── */}
      <div className="card mb-16" style={{
        background: 'linear-gradient(135deg, rgba(16, 33, 24, 0.96), rgba(9, 19, 14, 0.98))',
        border: '1px solid rgba(200, 245, 66, 0.25)',
      }}>
        <div className="flex justify-between items-start wrap gap-16 mb-20">
          <div>
            <div className="flex items-center gap-10 wrap mb-8">
              <span className="badge badge-blue">Multi-Season Aging &amp; Contract Advisor</span>
              <span className={`badge ${badgeClass}`}>{trajectory_label}</span>
              {subrole && <span className="badge flex items-center gap-6" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--c-text)' }}><IconTarget size={13} /> {subrole}</span>}
            </div>
            <h3 style={{ fontSize: '1.35rem', marginBottom: 4 }}>
              Contract Recommendation for {name} (Age {current_age})
            </h3>
            <div className="text-muted" style={{ fontSize: '0.83rem' }}>
              Typical {position_name} Peak Window: <strong>Ages {peak_age_window}</strong> · Model Confidence: <strong>{confidence}</strong>
            </div>
          </div>

          <div style={{
            background: 'rgba(200, 245, 66, 0.09)',
            border: '1px solid rgba(200, 245, 66, 0.35)',
            borderRadius: 12,
            padding: '12px 18px',
            textAlign: 'right',
            minWidth: 210,
          }}>
            <div className="label" style={{ color: 'var(--c-primary)', marginBottom: 2 }}>Recommended Deal Length</div>
            <div style={{ fontSize: '1.65rem', fontWeight: 800, color: 'var(--c-primary)', fontFamily: 'var(--font-mono)' }}>
              {contract.recommended_years || '—'}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--c-text)', fontWeight: 600 }}>
              {contract.verdict}
            </div>
          </div>
        </div>

        {/* Rationale & Structure Callout */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.03)',
          borderLeft: '3px solid var(--c-primary)',
          borderRadius: '0 8px 8px 0',
          padding: '12px 16px',
          marginBottom: 20,
        }}>
          <div style={{ fontSize: '0.92rem', color: 'var(--c-text)', lineHeight: 1.55, marginBottom: 6 }}>
            <strong>Scouting &amp; Recruitment Verdict:</strong> {contract.rationale}
          </div>
          <div className="flex gap-16 wrap" style={{ fontSize: '0.8rem', color: 'var(--c-muted)' }}>
            <span className="flex items-center gap-6"><IconClipboard size={14} /> <strong>Suggested Structure:</strong> {contract.contract_structure}</span>
            <span className="flex items-center gap-6"><IconAlert size={14} /> <strong>Contract Risk:</strong> {contract.risk_level}</span>
            <span className="flex items-center gap-6"><IconTrendDown size={14} /> <strong>3-Year Resale Retention:</strong> {contract.val_retention_3y_pct > 0 ? `+${contract.val_retention_3y_pct}%` : `${contract.val_retention_3y_pct}%`}</span>
          </div>
        </div>

        {/* 3-Year Forward Snapshot Cards */}
        <div className="grid-4" style={{ gap: 12 }}>
          <div style={{ background: 'var(--c-surface)', borderRadius: 10, padding: '12px 14px', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="label mb-4">Current (2025-26 · Age {current_age})</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--c-text)', fontFamily: 'var(--font-mono)' }}>
              {fmtValue(current_value_eur)}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--c-muted)', marginTop: 4 }}>
              Role Index: <strong style={{ color: 'var(--c-text)' }}>{current_role_index?.toFixed(1)} / 100</strong>
            </div>
          </div>

          {future.map((f, idx) => {
            const isUp = (f.perf_change_pts || 0) >= 0
            const valUp = (f.value_change_pct || 0) >= 0
            return (
              <div key={f.season} style={{
                background: 'var(--c-surface)',
                borderRadius: 10,
                padding: '12px 14px',
                border: idx === 1 ? '1px solid rgba(200, 245, 66, 0.35)' : '1px solid rgba(255,255,255,0.06)',
              }}>
                <div className="label mb-4">Year +{idx + 1} ({f.season} · Age {f.age})</div>
                <div className="flex items-center gap-8">
                  <span style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--c-text)', fontFamily: 'var(--font-mono)' }}>
                    {fmtValue(f.estimated_value_eur)}
                  </span>
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: valUp ? 'var(--c-green)' : 'var(--c-red)',
                  }}>
                    ({valUp ? '+' : ''}{f.value_change_pct?.toFixed(0)}%)
                  </span>
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--c-muted)', marginTop: 4 }}>
                  Role Index: <strong style={{ color: 'var(--c-text)' }}>{f.role_index?.toFixed(1)}</strong>{' '}
                  <span style={{ color: isUp ? 'var(--c-green)' : '#f59e0b', fontWeight: 600 }}>
                    ({isUp ? '+' : ''}{f.perf_change_pts?.toFixed(1)} pts)
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Visual Trajectory Chart (Historical + 3-Year Forecast) ────────── */}
      <div className="card mb-24" style={{ padding: '26px 28px' }}>
        <div className="flex justify-between items-start wrap gap-16" style={{ marginBottom: 22 }}>
          <div style={{ flex: '1 1 420px' }}>
            <h3 style={{ marginBottom: 6 }}>Multi-Season Performance &amp; Valuation Trajectory (2022–2029)</h3>
            <p className="text-muted" style={{ fontSize: '0.84rem', margin: 0, lineHeight: 1.5 }}>
              Solid line = verified historical Opta/FBref seasons · Dashed line = projected trajectory based on last 3 seasons + Premier League {position_name.toLowerCase()} aging curve
            </p>
          </div>
          <div className="flex gap-12 wrap" style={{ fontSize: '0.8rem', marginTop: 4 }}>
            <span className="flex items-center gap-8" style={{
              padding: '6px 12px', borderRadius: 999,
              background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.28)',
              color: 'var(--c-text)', fontWeight: 600,
            }}>
              <span style={{ width: 16, height: 3, borderRadius: 2, background: '#38bdf8', display: 'inline-block' }} />
              <span>Historical / Current</span>
            </span>
            <span className="flex items-center gap-8" style={{
              padding: '6px 12px', borderRadius: 999,
              background: 'rgba(200, 245, 66, 0.08)', border: '1px solid rgba(200, 245, 66, 0.28)',
              color: 'var(--c-text)', fontWeight: 600,
            }}>
              <span style={{ width: 16, height: 0, borderBottom: '3px dashed #c8f542', display: 'inline-block' }} />
              <span>Projected (Age +1 to +3)</span>
            </span>
          </div>
        </div>

        <div style={{ width: '100%', overflowX: 'auto', paddingTop: 4 }}>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', minWidth: 640, height: 'auto', display: 'block' }}>
            {/* Horizontal grid lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
              const val = minRole + t * (maxRole - minRole)
              const y = yRole(val)
              return (
                <g key={i}>
                  <line x1={42} y1={y} x2={W - 24} y2={y} stroke="rgba(255,255,255,0.07)" strokeDasharray="3,3" />
                  <text x={32} y={y + 4} textAnchor="end" fill="#8fa696" fontSize="10.5" fontFamily="monospace">
                    {Math.round(val)}
                  </text>
                </g>
              )
            })}

            {/* Current season vertical divider */}
            {curIdx >= 0 && (
              <line
                x1={xAt(curIdx)}
                y1={padT - 14}
                x2={xAt(curIdx)}
                y2={H - padB}
                stroke="rgba(200, 245, 66, 0.35)"
                strokeWidth="1.5"
                strokeDasharray="4,4"
              />
            )}

            {/* Historical solid polyline */}
            {pastPts.length > 1 && (
              <polyline
                fill="none"
                stroke="#38bdf8"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={polyPoints(pastPts, 0)}
              />
            )}

            {/* Future dashed polyline */}
            {futPts.length > 1 && (
              <polyline
                fill="none"
                stroke="#c8f542"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray="6,5"
                points={polyPoints(futPts, curIdx)}
              />
            )}

            {/* Points & Pill Labels (rendered after polylines so lines never cut through text) */}
            {timeline.map((pt, idx) => {
              const cx = xAt(idx)
              const cy = yRole(pt.role_index)
              const isProj = pt.type === 'projected'
              const isCur = pt.type === 'current'
              const dotColor = isCur ? '#ffffff' : isProj ? '#c8f542' : '#38bdf8'
              const labelText = `${pt.role_index?.toFixed(1)} (${fmtValue(pt.estimated_value_eur)})`
              const pillW = Math.max(96, labelText.length * 6.4 + 14)
              const labelY = cy - 18
              return (
                <g key={pt.season}>
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isCur ? 6.5 : 5}
                    fill={dotColor}
                    stroke="#07100c"
                    strokeWidth="2"
                  />
                  {/* Opaque dark pill behind label so line/grid never overlaps text */}
                  <rect
                    x={cx - pillW / 2}
                    y={labelY - 12}
                    width={pillW}
                    height={18}
                    rx="5"
                    fill="#0b1711"
                    fillOpacity="0.92"
                    stroke={isProj ? 'rgba(200, 245, 66, 0.32)' : 'rgba(56, 189, 248, 0.32)'}
                    strokeWidth="1"
                  />
                  {/* Role Index + Value above point */}
                  <text
                    x={cx}
                    y={labelY}
                    textAnchor="middle"
                    fill={isProj ? '#c8f542' : '#eef5f0'}
                    fontSize="10.5"
                    fontWeight="700"
                    fontFamily="monospace"
                  >
                    {labelText}
                  </text>
                  {/* Season & Age on X axis */}
                  <text
                    x={cx}
                    y={H - padB + 20}
                    textAnchor="middle"
                    fill={isCur ? '#c8f542' : '#eef5f0'}
                    fontSize="11"
                    fontWeight={isCur ? '800' : '600'}
                  >
                    {pt.season}
                  </text>
                  <text
                    x={cx}
                    y={H - padB + 36}
                    textAnchor="middle"
                    fill="#8fa696"
                    fontSize="10"
                  >
                    Age {pt.age} {isProj ? '(Proj)' : isCur ? '(Now)' : ''}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>
      </div>

      {/* ── Season-by-Season Detailed Stat & Valuation Table ──────────────── */}
      <div className="card" style={{ padding: '26px 28px' }}>
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 6 }}>Season-by-Season Per-90 Breakdown (Past 3 Seasons → Next 3 Seasons)</h3>
          <p className="text-muted" style={{ fontSize: '0.84rem', margin: 0 }}>
            Complete historical progression and 3-year projected role index, market valuation, and key per-90 indicators.
          </p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Season</th>
                <th>Status</th>
                <th>Club</th>
                <th>Age</th>
                <th>Minutes</th>
                <th>Role Index</th>
                <th>Est. Fair Value</th>
                {headline_metrics.map(m => (
                  <th key={m.key}>{m.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {timeline.map(row => {
                const isProj = row.type === 'projected'
                const isCur = row.type === 'current'
                return (
                  <tr
                    key={row.season}
                    style={{
                      background: isCur
                        ? 'rgba(200, 245, 66, 0.08)'
                        : isProj
                        ? 'rgba(255, 255, 255, 0.02)'
                        : 'transparent',
                    }}
                  >
                    <td style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{row.season}</td>
                    <td>
                      {isCur ? (
                        <span className="badge badge-blue">Current</span>
                      ) : isProj ? (
                        <span className="badge badge-amber">Projected</span>
                      ) : (
                        <span className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--c-muted)' }}>Historical</span>
                      )}
                    </td>
                    <td>{row.club}</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{row.age}</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{row.minutes?.toLocaleString()}</td>
                    <td>
                      <strong style={{ color: isProj ? 'var(--c-primary)' : 'var(--c-text)', fontFamily: 'var(--font-mono)' }}>
                        {row.role_index?.toFixed(1)}
                      </strong>
                      <span className="text-muted" style={{ fontSize: '0.75rem' }}> / 100</span>
                    </td>
                    <td style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--c-text)' }}>
                      {fmtValue(row.estimated_value_eur)}
                    </td>
                    {headline_metrics.map(m => (
                      <td key={m.key} style={{ fontFamily: 'var(--font-mono)' }}>
                        {row.stats?.[m.key] != null
                          ? ['pass_accuracy', 'save_pct', 'clean_sheet_pct'].includes(m.key)
                            ? `${row.stats[m.key].toFixed(1)}%`
                            : row.stats[m.key].toFixed(2)
                          : '—'}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

