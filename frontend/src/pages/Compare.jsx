import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts'
import { getPlayers, getCompare, getProjection } from '../api'
import { fmtValue, fmtNum, debounce } from '../utils'
import { PageLoading, ErrorBox, PosChip, Disclaimer, DataCaveat } from '../components/UI'
import RadarChart from '../components/RadarChart'
import PlayerAvatar from '../components/PlayerAvatar'
import { IconScale, IconChart, IconRadar, IconTrendUp } from '../components/Icons'

function parseIdsParam(ids) {
  if (!ids) return []
  return ids
    .split(',')
    .slice(0, 4)
    .map(s => s.trim())
    .filter(s => s !== '')
    .map(Number)
    .filter(Number.isFinite)
}

export default function Compare() {
  const [searchParams] = useSearchParams()
  const idsParam = searchParams.get('ids') || ''
  const [selected, setSelected] = useState(() => parseIdsParam(idsParam))
  const [search, setSearch] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [searched, setSearched] = useState(false)
  const [allPlayers, setAllPlayers] = useState([])
  const [compare, setCompare] = useState(null)
  const [radar, setRadar] = useState(null)
  const [projections, setProjections] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('table')

  // Sync URL ?ids=... changes (e.g. from Shortlist Drawer) and auto-run comparison
  useEffect(() => {
    const parsed = parseIdsParam(idsParam)
    if (!parsed.length) return
    setSelected(parsed)
    if (parsed.length >= 2) {
      setLoading(true)
      setError(null)
      Promise.all([
        getCompare(parsed),
        Promise.all(parsed.map(id => getProjection(id).catch(() => null))),
      ])
        .then(([cmp, projs]) => {
          setCompare(cmp)
          setRadar(cmp.radar ?? null)
          setProjections(projs)
        })
        .catch(e => setError(e.response?.data?.detail || e.message))
        .finally(() => setLoading(false))
    }
  }, [idsParam])

  // Fetch player name list (always, needed for chip labels)
  useEffect(() => {
    getPlayers({ limit: 500 })
      .then(d => {
        const list = Array.isArray(d) ? d : (d.value ?? d.players ?? [])
        setAllPlayers(list.map(p => ({ ...p, player_id: p.id ?? p.player_id, player_name: p.name ?? p.player_name })))
      })
      .catch(() => {})
  }, [])

  // Search suggestions
  useEffect(() => {
    if (!search || search.length < 2) { setSuggestions([]); setSearched(false); return }
    const fn = debounce((q) => {
      getPlayers({ q, limit: 8 })
        .then(d => {
          const list = Array.isArray(d) ? d : (d.value ?? d.players ?? [])
          setSuggestions(list.map(p => ({ ...p, player_id: p.id ?? p.player_id, player_name: p.name ?? p.player_name, estimated_value: p.estimated_value_eur ?? p.estimated_value })))
          setSearched(true)
        })
        .catch(() => {})
    }, 250)
    fn(search)
  }, [search])

  function addPlayer(p) {
    const pid = p.player_id ?? p.id
    if (selected.includes(pid) || selected.length >= 4) return
    setSelected(v => [...v, pid])
    setSearch('')
    setSuggestions([])
  }

  function removePlayer(pid) {
    setSelected(v => v.filter(x => x !== pid))
    setCompare(null)
    setRadar(null)
    setProjections([])
  }

  async function runCompare() {
    if (selected.length < 2) return
    setLoading(true)
    setError(null)
    try {
      const [cmp, projs] = await Promise.all([
        getCompare(selected),
        Promise.all(selected.map(id => getProjection(id).catch(() => null))),
      ])
      setCompare(cmp)
      setRadar(cmp.radar ?? null)
      setProjections(projs)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  // Get name for selected ID — check compare.players first (fast), then allPlayers
  function nameOf(pid) {
    if (compare?.players) {
      const cp = compare.players.find(x => (x.id ?? x.player_id) === pid)
      if (cp) return cp.name ?? cp.player_name ?? `#${pid}`
    }
    const p = allPlayers.find(x => (x.player_id ?? x.id) === pid)
    return p?.player_name ?? p?.name ?? `#${pid}`
  }

  const COLORS = ['#c8f542', '#5eead4', '#fbbf24', '#a78bfa']

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <h1 className="flex items-center gap-12"><IconScale size={28} style={{ color: 'var(--c-primary)' }} /> Compare Players</h1>
          <p className="text-muted">
            Select 2–4 players for a side-by-side stats comparison, percentile radar, and 3-year aging &amp; value forecast.
          </p>
        </div>

        {/* ── Player selection ──────────────────────────────────── */}
        <div className="card mb-24" style={{ padding: 24 }}>
          <div className="flex items-center gap-12 wrap mb-16">
            {selected.map((pid, i) => (
              <div
                key={pid}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '5px 14px 5px 6px', borderRadius: 100,
                  background: COLORS[i] + '22',
                  border: `1px solid ${COLORS[i]}55`,
                  fontSize: '0.88rem', fontWeight: 600,
                  color: COLORS[i],
                }}
              >
                <PlayerAvatar name={nameOf(pid)} size={24} radius={999} />
                {nameOf(pid)}
                <button
                  onClick={() => removePlayer(pid)}
                  style={{ color: COLORS[i], fontWeight: 700, fontSize: '1rem' }}
                  className="btn-ghost"
                  aria-label={`Remove ${nameOf(pid)}`}
                >×</button>
              </div>
            ))}
            {selected.length < 4 && (
              <span className="text-subtle" style={{ fontSize: '0.85rem' }}>
                {selected.length === 0 ? 'Add 2–4 players' : `Add ${4 - selected.length} more`}
              </span>
            )}
          </div>

          {/* Search */}
          {selected.length < 4 && (
            <div style={{ position: 'relative', maxWidth: 380 }}>
              <input
                id="compare-search"
                type="text"
                className="input"
                placeholder="Search to add player…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                aria-label="Search players to compare"
              />
              {suggestions.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20,
                  background: 'var(--c-card2)', border: '1px solid var(--c-border2)',
                  borderRadius: 8, marginTop: 4, boxShadow: 'var(--shadow-pop)',
                }}>
                  {suggestions.filter(s => !selected.includes(s.player_id)).map(p => (
                    <button
                      key={p.player_id}
                      onClick={() => addPlayer(p)}
                      id={`compare-suggest-${p.player_id}`}
                      style={{
                        width: '100%', padding: '10px 14px', textAlign: 'left',
                        display: 'flex', alignItems: 'center', gap: 10,
                        color: 'var(--c-text)', fontSize: '0.9rem',
                        borderBottom: '1px solid var(--c-border)',
                      }}
                      className="btn-ghost"
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.08)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <PosChip pos={p.position} />
                      <span style={{ fontWeight: 600 }}>{p.player_name}</span>
                      <span className="text-muted" style={{ fontSize: '0.8rem', marginLeft: 'auto' }}>
                        {fmtValue(p.estimated_value)}
                      </span>
                    </button>
                  ))}
                </div>
              )}
              {searched && search.trim().length >= 2 && suggestions.filter(s => !selected.includes(s.player_id)).length === 0 && (
                <div className="alert alert-danger mt-8" style={{ padding: '8px 12px', fontSize: '0.82rem' }}>
                  Value not found: No available player matching "{search.trim()}" exists in the sample.
                </div>
              )}
            </div>
          )}

          <div className="mt-16 flex gap-12">
            <button
              id="compare-run-btn"
              className="btn btn-primary"
              onClick={runCompare}
              disabled={selected.length < 2 || loading}
            >
              <IconScale size={16} /> {loading ? 'Comparing…' : 'Compare'}
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => { setSelected([]); setCompare(null); setRadar(null); setProjections([]) }}
              disabled={!selected.length}
            >
              Clear all
            </button>
          </div>
        </div>

        {error && <ErrorBox message={error} />}
        {loading && <PageLoading />}

        {compare && !loading && (
          <div className="animate-slide">
            {/* Tabs */}
            <div className="tabs">
              {[
                { id: 'table', label: 'Stats Table', Icon: IconChart },
                { id: 'radar', label: 'Radar Chart', Icon: IconRadar },
                { id: 'forecast', label: '3Y Forecast', Icon: IconTrendUp },
              ].map(t => (
                <button
                  key={t.id}
                  className={`tab${activeTab === t.id ? ' active' : ''}`}
                  onClick={() => setActiveTab(t.id)}
                  id={`compare-tab-${t.id}`}
                >
                  <span className="flex items-center gap-6"><t.Icon size={15} /> {t.label}</span>
                </button>
              ))}
            </div>

            {/* Table view */}
            {activeTab === 'table' && (() => {
              const players = compare.players ?? []
              const statLabels = compare.stat_labels ?? {}
              const statKeys = Object.keys(statLabels)
              return (
                <div className="table-wrap">
                  <table aria-label="Player comparison table">
                    <thead>
                      <tr>
                        <th style={{ minWidth: 180 }}>Stat</th>
                        {players.map((p, i) => (
                          <th key={i} style={{ color: COLORS[i], minWidth: 165 }}>
                            <div className="flex items-center gap-10">
                              <PlayerAvatar name={p.name ?? p.player_name} size={40} radius={999} />
                              <div>
                                <Link to={`/players/${p.id ?? p.player_id}`} style={{ color: COLORS[i], fontWeight: 700, display: 'block', lineHeight: 1.2 }}>
                                  {p.name ?? p.player_name}
                                </Link>
                                <span style={{ fontSize: '0.74rem', fontWeight: 400, color: 'var(--c-muted)' }}>
                                  {p.club}
                                </span>
                              </div>
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {statKeys.map(key => {
                        const vals = players.map(p => p.stats?.[key] ?? null)
                        const numVals = vals.filter(v => v != null)
                        const maxVal = numVals.length ? Math.max(...numVals) : null
                        return (
                          <tr key={key}>
                            <td style={{ color: 'var(--c-muted)', fontSize: '0.85rem' }}>{statLabels[key]}</td>
                            {vals.map((v, vi) => (
                              <td
                                key={vi}
                                style={{
                                  fontWeight: v === maxVal && numVals.filter(x => x === maxVal).length === 1 ? 700 : 400,
                                  color: v === maxVal && numVals.filter(x => x === maxVal).length === 1
                                    ? COLORS[vi] : 'var(--c-text)',
                                }}
                              >
                                {v != null ? fmtNum(v) : '—'}
                              </td>
                            ))}
                          </tr>
                        )
                      })}
                      {/* Model Estimate row */}
                      <tr style={{ borderTop: '2px solid var(--c-border2)' }}>
                        <td style={{ fontWeight: 700 }}>Model Estimate</td>
                        {players.map((p, i) => (
                          <td key={i} style={{ fontWeight: 800, color: COLORS[i], fontSize: '1.05rem' }}>
                            {fmtValue(p.estimated_value_eur ?? p.estimated_value)}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              )
            })()}

            {/* Radar view */}
            {activeTab === 'radar' && radar && (
              <div className="card">
                <h3 className="mb-16">Attribute Radar (Position Percentile %)</h3>
                <p className="text-muted mb-24" style={{ fontSize: '0.85rem' }}>
                  <strong>What is a Percentile?</strong> Each value (0%–100%) shows the percentage of Premier League peers in the same position that a player outperforms (e.g., <strong>90%</strong> = better than 90% of players in their position; <strong>50%</strong> = position average).
                </p>
                <RadarChart data={radar} />
              </div>
            )}

            {/* 3Y Aging & Value Forecast view */}
            {activeTab === 'forecast' && (() => {
              const players = compare.players ?? []
              const paired = players.map((p, i) => ({
                player: p,
                proj: projections[i] || null,
                color: COLORS[i],
                name: p.name ?? p.player_name,
              })).filter(x => x.proj)

              if (!paired.length) {
                return (
                  <div className="card">
                    <p className="text-muted">No 3-year aging projections available for the selected players.</p>
                  </div>
                )
              }

              const SEASONS = ['2025-26', '2026-27', '2027-28', '2028-29']
              const roleSeries = SEASONS.map((season, sIdx) => {
                const row = { season }
                paired.forEach(({ proj, name }) => {
                  if (sIdx === 0) {
                    row[name] = Number(proj.current_role_index?.toFixed(1) ?? 0)
                  } else {
                    const f = proj.future?.[sIdx - 1]
                    row[name] = f ? Number(f.role_index?.toFixed(1) ?? 0) : null
                  }
                })
                return row
              })

              const valueSeries = SEASONS.map((season, sIdx) => {
                const row = { season }
                paired.forEach(({ proj, name }) => {
                  const eur = sIdx === 0
                    ? proj.current_value_eur
                    : proj.future?.[sIdx - 1]?.estimated_value_eur
                  row[name] = eur != null ? Number((eur / 1e6).toFixed(1)) : null
                })
                return row
              })

              const renderForecastTooltip = (unit) => ({ active, payload, label }) => {
                if (!active || !payload?.length) return null
                return (
                  <div
                    style={{
                      background: 'var(--c-card2)',
                      border: '1px solid var(--c-border2)',
                      borderRadius: 10,
                      padding: '10px 14px',
                      boxShadow: '0 10px 26px rgba(0, 0, 0, 0.45)',
                      fontSize: '0.82rem',
                      minWidth: 185,
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#ffffff', marginBottom: 8, fontFamily: 'var(--font-mono)' }}>
                      {label}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {payload.map(entry => (
                        <div
                          key={entry.dataKey}
                          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14 }}
                        >
                          <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#e2e8f0' }}>
                            <span
                              style={{
                                width: 9,
                                height: 9,
                                borderRadius: 999,
                                background: entry.color,
                                boxShadow: `0 0 8px ${entry.color}88`,
                                flexShrink: 0,
                              }}
                            />
                            {entry.name}
                          </span>
                          <strong style={{ color: entry.color, fontFamily: 'var(--font-mono)' }}>
                            {unit === 'value'
                              ? `£${Number(entry.value).toFixed(1)}m`
                              : `${Number(entry.value).toFixed(1)} / 100`}
                          </strong>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              }

              return (
                <div className="flex-col gap-20">
                  <div className="grid-2" style={{ gap: 20 }}>
                    {/* Chart 1: Role Index Trajectory */}
                    <div className="card" style={{ padding: '22px 24px' }}>
                      <h3 className="mb-6">Projected Role Index (0–100)</h3>
                      <p className="text-muted mb-16" style={{ fontSize: '0.82rem' }}>
                        3-season performance trajectory (PyTorch TrajectoryGRU + GBR + Ridge). Spot the exact season a younger target overtakes a veteran.
                      </p>
                      <div style={{ width: '100%', height: 280 }}>
                        <ResponsiveContainer>
                          <LineChart data={roleSeries} margin={{ top: 8, right: 18, left: -12, bottom: 4 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(226,240,214,0.08)" />
                            <XAxis dataKey="season" stroke="var(--c-muted)" tick={{ fill: 'var(--c-muted)', fontSize: 12 }} />
                            <YAxis domain={['auto', 'auto']} stroke="var(--c-muted)" tick={{ fill: 'var(--c-muted)', fontSize: 12 }} />
                            <Tooltip content={renderForecastTooltip('role')} />
                            <Legend wrapperStyle={{ fontSize: '0.82rem', paddingTop: 8 }} />
                            {paired.map(({ name, color }) => (
                              <Line
                                key={name}
                                type="monotone"
                                dataKey={name}
                                stroke={color}
                                strokeWidth={2.6}
                                dot={{ r: 4, fill: color }}
                                activeDot={{ r: 6 }}
                              />
                            ))}
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 2: Projected Fair Value Trajectory */}
                    <div className="card" style={{ padding: '22px 24px' }}>
                      <h3 className="mb-6">Projected Fair Market Value (£M)</h3>
                      <p className="text-muted mb-16" style={{ fontSize: '0.82rem' }}>
                        Expected asset appreciation vs. depreciation through 2028-29 to guide transfer ROI and resale planning.
                      </p>
                      <div style={{ width: '100%', height: 280 }}>
                        <ResponsiveContainer>
                          <LineChart data={valueSeries} margin={{ top: 8, right: 18, left: -6, bottom: 4 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(226,240,214,0.08)" />
                            <XAxis dataKey="season" stroke="var(--c-muted)" tick={{ fill: 'var(--c-muted)', fontSize: 12 }} />
                            <YAxis stroke="var(--c-muted)" tick={{ fill: 'var(--c-muted)', fontSize: 12 }} tickFormatter={v => `£${v}m`} />
                            <Tooltip content={renderForecastTooltip('value')} />
                            <Legend wrapperStyle={{ fontSize: '0.82rem', paddingTop: 8 }} />
                            {paired.map(({ name, color }) => (
                              <Line
                                key={name}
                                type="monotone"
                                dataKey={name}
                                stroke={color}
                                strokeWidth={2.6}
                                dot={{ r: 4, fill: color }}
                                activeDot={{ r: 6 }}
                              />
                            ))}
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>

                  {/* Side-by-Side 3-Year Summary Table */}
                  <div className="table-wrap">
                    <table aria-label="3-year forecast comparison summary">
                      <thead>
                        <tr>
                          <th>Player</th>
                          <th>Age (Now → 2029)</th>
                          <th>Career Phase</th>
                          <th>Role Index (Now → 2029)</th>
                          <th>Fair Value (Now → 2029)</th>
                          <th>Contract Rec.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paired.map(({ player, proj, color, name }) => {
                          const y3 = proj.future?.[2]
                          const curR = proj.current_role_index ?? 0
                          const endR = y3?.role_index ?? curR
                          const dR = endR - curR
                          const curV = proj.current_value_eur ?? 0
                          const endV = y3?.estimated_value_eur ?? curV
                          const dVPct = curV > 0 ? ((endV - curV) / curV) * 100 : 0
                          const badgeCls =
                            proj.trajectory_badge === 'green' ? 'badge-green' :
                            proj.trajectory_badge === 'blue' ? 'badge-blue' :
                            proj.trajectory_badge === 'red' ? 'badge-red' : 'badge-amber'
                          return (
                            <tr key={player.id ?? player.player_id}>
                              <td>
                                <div className="flex items-center gap-10">
                                  <PlayerAvatar name={name} size={34} radius={999} />
                                  <div>
                                    <Link to={`/players/${player.id ?? player.player_id}`} style={{ color, fontWeight: 700 }}>
                                      {name}
                                    </Link>
                                    <div className="text-muted" style={{ fontSize: '0.75rem' }}>{player.club}</div>
                                  </div>
                                </div>
                              </td>
                              <td style={{ fontFamily: 'var(--font-mono)' }}>
                                {proj.current_age} → {proj.current_age + 3}
                              </td>
                              <td>
                                <span className={`badge ${badgeCls}`}>{proj.trajectory_label}</span>
                              </td>
                              <td style={{ fontFamily: 'var(--font-mono)' }}>
                                {curR.toFixed(1)} → <strong>{endR.toFixed(1)}</strong>{' '}
                                <span style={{ color: dR >= 0 ? 'var(--c-green)' : 'var(--c-red)', fontSize: '0.8rem' }}>
                                  ({dR >= 0 ? '+' : ''}{dR.toFixed(1)})
                                </span>
                              </td>
                              <td style={{ fontFamily: 'var(--font-mono)' }}>
                                {fmtValue(curV)} → <strong>{fmtValue(endV)}</strong>{' '}
                                <span style={{ color: dVPct >= 0 ? 'var(--c-green)' : 'var(--c-red)', fontSize: '0.8rem' }}>
                                  ({dVPct >= 0 ? '+' : ''}{dVPct.toFixed(0)}%)
                                </span>
                              </td>
                              <td style={{ fontWeight: 600 }}>
                                {proj.contract?.recommended_years || '—'}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            })()}
          </div>
        )}

        <DataCaveat />
        <Disclaimer />
      </div>
    </main>
  )
}
