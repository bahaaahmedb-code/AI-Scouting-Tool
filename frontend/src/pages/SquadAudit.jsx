import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getMeta, getClubAudit } from '../api'
import { fmtValue } from '../utils'
import { PageLoading, ErrorBox, PosChip, Disclaimer, RangeSlider } from '../components/UI'
import { ShortlistBtn } from '../components/ShortlistDrawer'
import { IconStadium, IconTarget, IconAlert, IconShield, IconScale } from '../components/Icons'

function PitchPlayerCard({ player }) {
  const isAging = player.age >= 31
  const isLowRole = (player.role_index ?? 70) < 65
  const borderCol = isAging
    ? 'rgba(251, 191, 36, 0.55)'
    : isLowRole
      ? 'rgba(244, 63, 94, 0.45)'
      : 'rgba(200, 245, 66, 0.28)'

  return (
    <Link
      to={`/players/${player.id}`}
      style={{
        background: 'rgba(9, 20, 14, 0.90)',
        backdropFilter: 'blur(6px)',
        border: `1px solid ${borderCol}`,
        borderRadius: 10,
        padding: '10px 12px',
        minWidth: 132,
        maxWidth: 168,
        flex: '0 1 154px',
        textAlign: 'center',
        boxShadow: '0 8px 20px rgba(0,0,0,0.45)',
        transition: 'transform 0.18s ease, border-color 0.18s ease',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
      }}
      onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-3px)' }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)' }}
    >
      <div className="flex items-center justify-between" style={{ width: '100%', gap: 6 }}>
        <PosChip pos={player.position} />
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: '0.72rem', fontWeight: 700,
          color: isAging ? '#fcd34d' : 'var(--c-muted)',
        }}>
          {player.age}y
        </span>
      </div>
      <div style={{
        fontWeight: 700, fontSize: '0.84rem', color: 'var(--c-text)',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%',
      }}>
        {player.name}
      </div>
      <div className="flex items-center justify-between" style={{ width: '100%', fontSize: '0.73rem', fontFamily: 'var(--font-mono)' }}>
        <span style={{ color: 'var(--c-primary)', fontWeight: 700 }}>
          {player.role_index?.toFixed(0)}<span style={{ color: 'var(--c-subtle)', fontWeight: 400 }}>/100</span>
        </span>
        <span style={{ color: 'var(--c-accent)', fontWeight: 700 }}>
          {fmtValue(player.estimated_value_eur)}
        </span>
      </div>
    </Link>
  )
}

export default function SquadAudit() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [clubs, setClubs] = useState([])
  const [club, setClub] = useState(searchParams.get('club') || 'Liverpool')
  const [maxPct, setMaxPct] = useState(90)
  const [audit, setAudit] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getMeta()
      .then(m => {
        const list = m.clubs || []
        setClubs(list)
        if (list.length && !list.includes(club)) setClub(list[0])
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!club) return
    setLoading(true)
    setError(null)
    getClubAudit(club, maxPct)
      .then(d => { setAudit(d); setLoading(false) })
      .catch(e => { setError(e.response?.data?.detail || e.message); setLoading(false) })
  }, [club, maxPct])

  function changeClub(nextClub) {
    setClub(nextClub)
    setSearchParams({ club: nextClub })
  }

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <h1 className="flex items-center gap-12">
            <IconStadium size={28} style={{ color: 'var(--c-primary)' }} /> Club Squad Audit &amp; Best XI
          </h1>
          <p className="text-muted">
            Automated Sporting Director audit for any Premier League club: visual Best XI formation, aging &amp; performance vulnerability detection, and recommended transfer replacements.
          </p>
        </div>

        {/* ── Controls ────────────────────────────────────────── */}
        <div className="card mb-24" style={{ padding: '20px 24px' }}>
          <div className="flex gap-32 wrap items-center">
            <div style={{ flex: '1 1 240px', maxWidth: 320 }}>
              <label className="label mb-8" htmlFor="audit-club-select" style={{ display: 'block' }}>Select Premier League Club</label>
              <select
                id="audit-club-select"
                className="input select"
                value={club}
                onChange={e => changeClub(e.target.value)}
              >
                {clubs.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div style={{ flex: '1 1 300px', maxWidth: 440 }}>
              <label className="label mb-8" htmlFor="audit-max-pct" style={{ display: 'block' }}>
                Replacement Budget Cap: <strong style={{ color: 'var(--c-primary)' }}>{maxPct}%</strong> of Starter Value
              </label>
              <RangeSlider
                id="audit-max-pct"
                min={50}
                max={150}
                step={5}
                value={maxPct}
                onChange={setMaxPct}
                tickStep={10}
                formatTick={v => `${v}%`}
                ariaLabel={`Replacement budget cap ${maxPct}% of starter value`}
              />
            </div>
            {audit && (
              <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                <div className="label mb-4">Auto Formation</div>
                <span className="badge badge-blue" style={{ fontSize: '0.88rem', padding: '5px 14px', fontFamily: 'var(--font-mono)' }}>
                  {audit.formation}
                </span>
              </div>
            )}
          </div>
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoading />}

        {!loading && !error && audit && (
          <div className="animate-slide">
            {/* ── Club KPIs ───────────────────────────────────── */}
            <div className="grid-4 mb-24" style={{ gap: 14 }}>
              <div className="card" style={{ padding: '16px 18px' }}>
                <div className="label mb-4">Best XI Value (11 Starters)</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--c-accent)', fontFamily: 'var(--font-mono)' }}>
                  {fmtValue(audit.best_xi_est_eur)}
                </div>
                <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: 4 }}>
                  Listed: {fmtValue(audit.best_xi_mkt_eur)} ({audit.best_xi_gap_pct >= 0 ? '+' : ''}{audit.best_xi_gap_pct}%)
                </div>
              </div>
              <div className="card" style={{ padding: '16px 18px' }}>
                <div className="label mb-4">Qualified Squad ({audit.n_players} Players)</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--c-text)', fontFamily: 'var(--font-mono)' }}>
                  {fmtValue(audit.total_est_eur)}
                </div>
                <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: 4 }}>
                  Team Strength: <strong style={{ color: 'var(--c-primary)' }}>{audit.team_strength}</strong>
                </div>
              </div>
              <div className="card" style={{ padding: '16px 18px' }}>
                <div className="label mb-4">Best XI Average Age</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: audit.best_xi_avg_age >= 28 ? '#fcd34d' : 'var(--c-green)', fontFamily: 'var(--font-mono)' }}>
                  {audit.best_xi_avg_age} yrs
                </div>
                <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: 4 }}>
                  Full squad avg: {audit.avg_age} yrs
                </div>
              </div>
              <div className="card" style={{ padding: '16px 18px' }}>
                <div className="label mb-4">Best XI Avg Role Index</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--c-primary)', fontFamily: 'var(--font-mono)' }}>
                  {audit.best_xi_avg_role_index} / 100
                </div>
                <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: 4 }}>
                  Weighted positional quality
                </div>
              </div>
            </div>

            {/* ── Floodlit Football Pitch (Best XI) ────────────── */}
            <div className="card mb-24" style={{ padding: '24px 26px' }}>
              <div className="flex justify-between items-center wrap gap-12 mb-16">
                <div>
                  <h3 style={{ marginBottom: 4 }}>{audit.club} — Best XI Tactical Pitch ({audit.formation})</h3>
                  <p className="text-muted" style={{ fontSize: '0.84rem', margin: 0 }}>
                    Top 11 qualified starters ranked by Role Performance Index &amp; playing time. Gold border = age 31+ succession watch; click any player to open profile.
                  </p>
                </div>
              </div>

              <div
                style={{
                  position: 'relative',
                  borderRadius: 16,
                  overflow: 'hidden',
                  border: '1px solid rgba(200, 245, 66, 0.22)',
                  background:
                    'repeating-linear-gradient(0deg, rgba(20, 52, 34, 0.65) 0px, rgba(20, 52, 34, 0.65) 68px, rgba(14, 38, 25, 0.72) 68px, rgba(14, 38, 25, 0.72) 136px)',
                  padding: '28px 18px',
                }}
              >
                {/* Pitch chalk markings SVG */}
                <svg
                  viewBox="0 0 800 540"
                  preserveAspectRatio="none"
                  style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', opacity: 0.24 }}
                  aria-hidden="true"
                >
                  <g fill="none" stroke="#eef4e8" strokeWidth="2">
                    <rect x="18" y="14" width="764" height="512" rx="4" />
                    <line x1="18" y1="270" x2="782" y2="270" />
                    <circle cx="400" cy="270" r="64" />
                    <circle cx="400" cy="270" r="4" fill="#eef4e8" />
                    <rect x="240" y="14" width="320" height="82" />
                    <rect x="240" y="444" width="320" height="82" />
                  </g>
                </svg>

                {/* 4 Tactical Lines: ATT -> MID -> DEF -> GK */}
                <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', gap: 26 }}>
                  {[
                    { key: 'att', label: 'ATTACK', players: audit.pitch?.att || [] },
                    { key: 'mid', label: 'MIDFIELD', players: audit.pitch?.mid || [] },
                    { key: 'def', label: 'DEFENSE', players: audit.pitch?.def || [] },
                    { key: 'gk',  label: 'GOALKEEPER', players: audit.pitch?.gk || [] },
                  ].map(line => (
                    <div key={line.key} style={{ display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap' }}>
                      {line.players.map(p => (
                        <PitchPlayerCard key={p.id} player={p} />
                      ))}
                    </div>
                  ))}
                </div>
              </div>

              {/* Bench / Rotation Players */}
              {audit.bench?.length > 0 && (
                <div className="mt-20">
                  <div className="label mb-10">Qualified Rotation &amp; Bench ({audit.bench.length} players ≥ 900 mins)</div>
                  <div className="flex gap-10 wrap">
                    {audit.bench.map(p => (
                      <Link
                        key={p.id}
                        to={`/players/${p.id}`}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 8,
                          padding: '8px 12px', borderRadius: 8,
                          background: 'var(--c-surface)', border: '1px solid var(--c-border)',
                          fontSize: '0.82rem',
                        }}
                      >
                        <PosChip pos={p.position} />
                        <span style={{ fontWeight: 600, color: 'var(--c-text)' }}>{p.name}</span>
                        <span className="text-muted">({p.age}y · {p.role_index}/100)</span>
                        <span style={{ color: 'var(--c-accent)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                          {fmtValue(p.estimated_value_eur)}
                        </span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* ── Automated Recruitment Priorities & Recommended Signings ── */}
            <div className="section-head" style={{ marginBottom: 20 }}>
              <h2 className="flex items-center gap-10" style={{ fontSize: '1.5rem' }}>
                <IconTarget size={22} style={{ color: 'var(--c-primary)' }} /> Automated Transfer Priorities for {audit.club}
              </h2>
              <p className="text-muted" style={{ fontSize: '0.9rem' }}>
                Flagged succession risks and performance upgrade targets across the Best XI, paired with the top 3 younger statistical replacements across the Premier League.
              </p>
            </div>

            <div className="flex-col gap-20">
              {(audit.vulnerabilities || []).map((v, idx) => {
                const st = v.starter
                const prioCls = v.priority === 'High' ? 'badge-red' : v.priority === 'Medium' ? 'badge-amber' : 'badge-blue'
                return (
                  <div key={st.id} className="card" style={{ padding: '22px 24px' }}>
                    <div className="flex justify-between items-start wrap gap-12 mb-16">
                      <div>
                        <div className="flex items-center gap-10 wrap mb-6">
                          <span className={`badge ${prioCls}`}>
                            <IconAlert size={12} /> {v.priority} Priority #{idx + 1}
                          </span>
                          <PosChip pos={st.position} />
                          <Link to={`/players/${st.id}`} style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--c-text)' }}>
                            {st.name}
                          </Link>
                          <span className="text-muted" style={{ fontSize: '0.85rem' }}>
                            Age {st.age} · {st.subrole} · Role Index {st.role_index}/100
                          </span>
                        </div>
                        <div className="flex gap-8 wrap">
                          {v.reasons.map((r, ri) => (
                            <span key={ri} style={{ fontSize: '0.82rem', color: 'var(--c-muted)' }}>
                              • {r}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div className="label">Current Starter Est.</div>
                        <div style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--c-accent)', fontFamily: 'var(--font-mono)' }}>
                          {fmtValue(st.estimated_value_eur)}
                        </div>
                        <div className="text-subtle" style={{ fontSize: '0.75rem' }}>
                          Contract Rec: {st.recommended_years}
                        </div>
                      </div>
                    </div>

                    {v.replacements?.length > 0 ? (
                      <div className="grid-3" style={{ gap: 14 }}>
                        {v.replacements.map(rec => (
                          <div
                            key={rec.id}
                            style={{
                              background: 'var(--c-surface)',
                              border: '1px solid var(--c-border)',
                              borderRadius: 10,
                              padding: '14px 16px',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                              gap: 10,
                            }}
                          >
                            <div>
                              <div className="flex items-center justify-between gap-8 mb-6">
                                <Link to={`/players/${rec.id}`} style={{ fontWeight: 700, color: 'var(--c-primary)', fontSize: '0.95rem' }}>
                                  {rec.name}
                                </Link>
                                <span className="badge badge-green" style={{ fontSize: '0.7rem' }}>
                                  {(rec.similarity * 100).toFixed(0)}% fit
                                </span>
                              </div>
                              <div className="text-muted" style={{ fontSize: '0.8rem', marginBottom: 8 }}>
                                {rec.club} · Age <strong>{rec.age}</strong> · Role Index <strong>{rec.role_index}/100</strong>
                              </div>
                              <div className="flex items-center justify-between" style={{ fontSize: '0.82rem', marginBottom: 6 }}>
                                <span className="text-muted">Model Est:</span>
                                <strong style={{ color: 'var(--c-accent)', fontFamily: 'var(--font-mono)' }}>{fmtValue(rec.estimated_value_eur)}</strong>
                              </div>
                              <div className="flex items-center justify-between" style={{ fontSize: '0.8rem', marginBottom: 8 }}>
                                <span className="text-muted">Ideal Contract:</span>
                                <strong style={{ color: 'var(--c-text)' }}>{rec.recommended_years}</strong>
                              </div>
                              {rec.shared_labels?.length > 0 && (
                                <div className="flex gap-4 wrap">
                                  {rec.shared_labels.map((s, si) => (
                                    <span key={si} className="badge badge-gray" style={{ fontSize: '0.68rem' }}>{s}</span>
                                  ))}
                                </div>
                              )}
                            </div>

                            <div className="flex gap-8 pt-8" style={{ borderTop: '1px solid var(--c-border)', paddingTop: 10 }}>
                              <ShortlistBtn player={rec} />
                              <Link to={`/compare?ids=${st.id},${rec.id}`} className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto', fontSize: '0.78rem' }}>
                                <IconScale size={13} /> Compare
                              </Link>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-muted" style={{ fontSize: '0.85rem' }}>
                        No external replacements found within the current budget cap. Try increasing the budget slider above.
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <Disclaimer />
      </div>
    </main>
  )
}
