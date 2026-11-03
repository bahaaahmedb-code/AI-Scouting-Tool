import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getPlayer, getShap } from '../api'
import { fmtValue, fmtNum } from '../utils'
import { PageLoading, ErrorBox, PosChip, Disclaimer, DataCaveat } from '../components/UI'
import WaterfallChart from '../components/WaterfallChart'

/** Normalize API player object to consistent field names */
function norm(p) {
  if (!p) return p
  return {
    ...p,
    player_id: p.id ?? p.player_id,
    player_name: p.name ?? p.player_name,
    minutes_played: p.minutes ?? p.minutes_played,
    estimated_value: p.estimated_value_eur ?? p.estimated_value,
    market_value_eur: p.listed_value_eur ?? p.market_value_eur,
    nationality: p.nation ?? p.nationality,
  }
}

/** Normalize SHAP response: {rows, prediction_eur, base_value_eur} → {features, predicted, base_value} */
function normShap(s) {
  if (!s) return s
  return {
    base_value: s.base_value_eur ?? s.base_value ?? 0,
    predicted: s.prediction_eur ?? s.predicted ?? 0,
    features: (s.rows ?? s.features ?? []).map(r => ({
      name: r.label ?? r.name ?? r.feature,
      value: r.value,
      shap: r.contribution ?? r.shap,
      tooltip: r.tooltip ?? '',
      group: r.group,
    })),
  }
}

export default function PlayerProfile() {
  const { pid } = useParams()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [shap, setShap] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('stats')

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.all([getPlayer(Number(pid)), getShap(Number(pid))])
      .then(([rawP, rawS]) => {
        setProfile(norm(rawP))
        setShap(normShap(rawS))
        setLoading(false)
      })
      .catch(e => { setError(e.response?.data?.detail || e.message); setLoading(false) })
  }, [pid])

  if (loading) return <PageLoading />
  if (error) return (
    <main className="page"><div className="container"><ErrorBox message={error} />
      <button className="btn btn-secondary mt-16" onClick={() => navigate(-1)}>← Back</button>
    </div></main>
  )
  if (!profile) return null

  const p = profile
  const estVal = p.estimated_value_eur ?? p.estimated_value
  const mktVal = p.listed_value_eur ?? p.market_value_eur
  const ratio = mktVal ? estVal / mktVal : null

  // Group features for stats tab — API returns p.stats (not p.features)
  const featuresByGroup = {}
  const statList = p.stats ?? p.features ?? []
  statList.forEach(f => {
    const g = f.group || 'Other'
    if (!featuresByGroup[g]) featuresByGroup[g] = []
    featuresByGroup[g].push(f)
  })

  // Derive strengths/weaknesses from percentile data in stats
  const derivedStrengths = statList
    .filter(f => f.pct_in_position != null && f.pct_in_position >= 75)
    .sort((a, b) => b.pct_in_position - a.pct_in_position)
    .slice(0, 6)
    .map(f => f.label ?? f.key)
  const derivedWeaknesses = statList
    .filter(f => f.pct_in_position != null && f.pct_in_position <= 25)
    .sort((a, b) => a.pct_in_position - b.pct_in_position)
    .slice(0, 4)
    .map(f => f.label ?? f.key)
  const strengths = p.strengths?.length ? p.strengths : derivedStrengths
  const weaknesses = p.weaknesses?.length ? p.weaknesses : derivedWeaknesses
  const playerName = p.name ?? p.player_name

  return (
    <main className="page animate-fade">
      <div className="container">
        {/* ── Breadcrumb ──────────────────────────────────────── */}
        <div className="flex items-center gap-8 mb-24" style={{ fontSize: '0.85rem', color: 'var(--c-muted)' }}>
          <Link to="/players" style={{ color: 'var(--c-primary)' }}>Players</Link>
          <span>›</span>
          <span>{p.name ?? p.player_name}</span>
        </div>

        {/* ── Hero card ───────────────────────────────────────── */}
        <div className="card card--gradient card-glow-blue mb-24" style={{ padding: 32 }}>
          <div className="flex gap-24 wrap">
            <div style={{
              width: 80, height: 80, borderRadius: 16,
              background: 'linear-gradient(135deg, var(--c-primary), var(--c-accent))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '2rem', flexShrink: 0,
            }}>⚽</div>

            <div style={{ flex: 1 }}>
              <div className="flex items-center gap-12 wrap mb-8">
                <h1 style={{ fontSize: '2rem', marginBottom: 0 }}>{p.name ?? p.player_name}</h1>
                <PosChip pos={p.position} />
              </div>
              <div className="flex gap-16 wrap" style={{ color: 'var(--c-muted)', fontSize: '0.9rem' }}>
                <span>🏟️ {p.club}</span>
                <span>🎂 Age {p.age}</span>
                {(p.nation ?? p.nationality) && <span>🌍 {p.nation ?? p.nationality}</span>}
                <span>⏱️ {(p.minutes ?? p.minutes_played)?.toLocaleString() ?? '—'} mins</span>
                {p.position_name && <span>📋 {p.position_name}</span>}
              </div>
            </div>

            <div style={{ textAlign: 'right', minWidth: 180 }}>
              <div className="label mb-4">Model Estimate</div>
              <div className="val-big" id="player-estimated-value">
                {fmtValue(p.estimated_value_eur ?? p.estimated_value)}
              </div>
              {(p.listed_value_eur ?? p.market_value_eur) && (
                <div className="text-muted mt-4" style={{ fontSize: '0.85rem' }}>
                  Mkt: {fmtValue(p.listed_value_eur ?? p.market_value_eur)}
                  {ratio && (
                    <span style={{ marginLeft: 8, color: ratio < 1 ? 'var(--c-green)' : 'var(--c-red)', fontWeight: 600 }}>
                      ({ratio < 1 ? '-' : '+'}{Math.abs((1 - ratio) * 100).toFixed(0)}%)
                    </span>
                  )}
                </div>
              )}
              <div className="flex gap-8 mt-12" style={{ justifyContent: 'flex-end' }}>
                <Link to={`/scout?target=${pid}`} className="btn btn-secondary btn-sm" id="profile-scout-btn">🎯 Scout</Link>
                <Link to={`/compare?ids=${pid}`} className="btn btn-ghost btn-sm" id="profile-compare-btn">⚖️ Compare</Link>
              </div>
            </div>
          </div>
        </div>

        {/* ── Tabs ─────────────────────────────────────────────── */}
        <div className="tabs" role="tablist">
          {[
            { id: 'stats',     label: '📊 Statistics' },
            { id: 'explain',   label: '🧠 SHAP Explanation' },
            { id: 'strengths', label: '💪 Strengths' },
          ].map(t => (
            <button key={t.id} role="tab" aria-selected={tab === t.id}
              className={`tab${tab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)} id={`profile-tab-${t.id}`}>
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Tab: Statistics ──────────────────────────────────── */}
        {tab === 'stats' && (
          <div className="animate-fade">
            {Object.entries(featuresByGroup).map(([group, feats]) => (
              <div key={group} className="card mb-16">
                <h3 className="mb-16">{group}</h3>
                <div className="grid-4" style={{ gap: 12 }}>
                  {feats.map(f => (
                    <div key={f.key} style={{ background: 'var(--c-surface)', borderRadius: 8, padding: '10px 14px' }}>
                      <div className="label mb-4">{f.label}</div>
                      <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--c-text)' }}>
                        {fmtNum(f.value)}
                      </div>
                      {f.pct_in_position != null && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--c-muted)', marginTop: 4 }}>
                          {f.pct_in_position.toFixed(0)}th percentile in position
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {!Object.keys(featuresByGroup).length && (
              <p className="text-muted">No detailed stats available for this player.</p>
            )}
          </div>
        )}

        {/* ── Tab: SHAP ─────────────────────────────────────────── */}
        {tab === 'explain' && (
          <div className="animate-fade">
            <div className="card mb-16">
              <div className="flex items-center gap-12 mb-24" style={{ flexWrap: 'wrap' }}>
                <h3>SHAP Waterfall</h3>
                <span className="badge badge-blue">XGBoost</span>
                <span className="text-muted" style={{ fontSize: '0.85rem' }}>
                  How much does each stat push the estimated value up or down?
                </span>
              </div>
              <WaterfallChart data={shap} />
            </div>
            <div className="alert alert-info">
              <strong>Reading this chart:</strong> Green bars increase the estimate above the average player; red bars decrease it. The <em>base value</em> is the average model prediction across all players.
            </div>
          </div>
        )}

        {/* ── Tab: Strengths ────────────────────────────────────── */}
        {tab === 'strengths' && (
          <div className="animate-fade">
            <div className="card mb-16">
              <h3 className="mb-20">Key Strengths &amp; Weaknesses</h3>
              {strengths.length > 0 ? (
                <div className="mb-20">
                  <div className="label text-green mb-12">💪 Strengths (≥75th percentile)</div>
                  <div className="flex gap-8 wrap">
                    {strengths.map((s, i) => <span key={i} className="badge badge-green">{s}</span>)}
                  </div>
                </div>
              ) : null}
              {weaknesses.length > 0 ? (
                <div>
                  <div className="label text-red mb-12">⚠️ Areas to improve (≤25th percentile)</div>
                  <div className="flex gap-8 wrap">
                    {weaknesses.map((s, i) => <span key={i} className="badge badge-red">{s}</span>)}
                  </div>
                </div>
              ) : null}
              {!strengths.length && !weaknesses.length && (
                <p className="text-muted">No percentile data available for this player.</p>
              )}
            </div>

            {/* Top drivers */}
            {p.top_drivers?.length > 0 && (
              <div className="card mb-16">
                <h3 className="mb-16">Top value drivers</h3>
                {p.top_drivers.map((d, i) => (
                  <div key={i} className="flex items-center gap-12 mb-12">
                    <span style={{ color: 'var(--c-primary)', fontWeight: 700, width: 20 }}>{i + 1}</span>
                    <span style={{ flex: 1 }}>{d.label}</span>
                    <span style={{ color: 'var(--c-accent)', fontWeight: 600 }}>{d.pct?.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            )}

            <div className="card">
              <h3 className="mb-12">Find similar players</h3>
              <p className="text-muted mb-16" style={{ fontSize: '0.9rem' }}>
                Use the scouting tool to find players with similar playing styles at a lower estimated cost.
              </p>
              <Link to={`/scout?target=${pid}`} className="btn btn-primary" id="strengths-scout-btn">
                🎯 Scout alternatives for {playerName}
              </Link>
            </div>
          </div>
        )}

        <DataCaveat />
        <Disclaimer />
      </div>
    </main>
  )
}
