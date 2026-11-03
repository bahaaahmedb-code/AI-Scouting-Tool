import { useEffect, useState, useRef } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { getPlayers, getCompare, getRadar } from '../api'
import { fmtValue, fmtNum, debounce } from '../utils'
import { PageLoading, ErrorBox, PosChip, Disclaimer, DataCaveat } from '../components/UI'
import RadarChart from '../components/RadarChart'

export default function Compare() {
  const [searchParams] = useSearchParams()
  const [selected, setSelected] = useState(() => {
    const ids = searchParams.get('ids')
    return ids ? ids.split(',').slice(0, 4).map(Number).filter(Boolean) : []
  })
  const [search, setSearch] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [searched, setSearched] = useState(false)
  const [allPlayers, setAllPlayers] = useState([])
  const [compare, setCompare] = useState(null)
  const [radar, setRadar] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('table')

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
  }

  async function runCompare() {
    if (selected.length < 2) return
    setLoading(true)
    setError(null)
    try {
      // compare API includes radar data, no need for separate radar call
      const cmp = await getCompare(selected)
      setCompare(cmp)
      setRadar(cmp.radar ?? null)
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

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6']

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <h1>⚖️ Compare Players</h1>
          <p className="text-muted">
            Select 2–4 players for a side-by-side stats comparison and radar chart.
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
                  padding: '8px 14px', borderRadius: 100,
                  background: COLORS[i] + '22',
                  border: `1px solid ${COLORS[i]}55`,
                  fontSize: '0.88rem', fontWeight: 600,
                  color: COLORS[i],
                }}
              >
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
                  ⚠️ Value not found: No available player matching "{search.trim()}" exists in the sample.
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
              {loading ? '⏳ Comparing…' : '⚖️ Compare'}
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => { setSelected([]); setCompare(null); setRadar(null) }}
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
                { id: 'table', label: '📊 Stats Table' },
                { id: 'radar', label: '🕸️ Radar Chart' },
              ].map(t => (
                <button
                  key={t.id}
                  className={`tab${activeTab === t.id ? ' active' : ''}`}
                  onClick={() => setActiveTab(t.id)}
                  id={`compare-tab-${t.id}`}
                >
                  {t.label}
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
                          <th key={i} style={{ color: COLORS[i], minWidth: 130 }}>
                            <Link to={`/players/${p.id ?? p.player_id}`} style={{ color: COLORS[i] }}>
                              {p.name ?? p.player_name}
                            </Link>
                            <br />
                            <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--c-muted)' }}>
                              {p.club}
                            </span>
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
          </div>
        )}

        <DataCaveat />
        <Disclaimer />
      </div>
    </main>
  )
}
