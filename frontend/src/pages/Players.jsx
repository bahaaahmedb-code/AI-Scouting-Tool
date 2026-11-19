import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { getPlayers, getMeta } from '../api'
import { fmtValue, debounce, posClass } from '../utils'
import { PageLoading, ErrorBox, PosChip, Disclaimer } from '../components/UI'
import { ShortlistBtn } from '../components/ShortlistDrawer'

const POSITIONS = ['', 'G', 'D', 'M', 'F']
const POS_LABELS = { '': 'All positions', G: 'Goalkeepers', D: 'Defenders', M: 'Midfielders', F: 'Attackers' }

export default function Players() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [q, setQ] = useState('')
  const [pos, setPos] = useState('')
  const [club, setClub] = useState('')
  const [limit, setLimit] = useState(50)
  const [sortBy, setSortBy] = useState('estimated_value')
  const [sortAsc, setSortAsc] = useState(false)

  const load = useCallback(
    debounce((query, position, clubFilter, lim) => {
      setLoading(true)
      setError(null)
      getPlayers({ q: query, position: position || undefined, club: clubFilter || undefined, limit: lim })
        .then(d => { setRows(d.value ?? d.players ?? d); setLoading(false) })
        .catch(e => { setError(e.message); setLoading(false) })
    }, 350),
    []
  )

  useEffect(() => { load(q, pos, club, limit) }, [q, pos, club, limit, load])

  // Normalise row fields to consistent names
  const norm = r => ({
    ...r,
    player_id: r.id ?? r.player_id,
    player_name: r.name ?? r.player_name,
    minutes_played: r.minutes ?? r.minutes_played,
    estimated_value: r.estimated_value_eur ?? r.estimated_value,
    market_value_eur: r.listed_value_eur ?? r.market_value_eur,
  })

  const sorted = [...rows].map(norm).sort((a, b) => {
    const col = sortBy === 'estimated_value' ? 'estimated_value'
              : sortBy === 'market_value_eur' ? 'market_value_eur'
              : sortBy === 'minutes_played' ? 'minutes_played' : sortBy
    const va = a[col] ?? -Infinity
    const vb = b[col] ?? -Infinity
    return sortAsc ? va - vb : vb - va
  })

  const [clubs, setClubs] = useState([])
  useEffect(() => { getMeta().then(m => setClubs(m.clubs || [])).catch(() => {}) }, [])

  // Club recruitment summary (whole squad, independent of the table's position / search / limit filters)
  const [squad, setSquad] = useState(null)
  useEffect(() => {
    if (!club) { setSquad(null); return }
    let active = true
    getPlayers({ club, limit: 100 })
      .then(d => {
        if (!active) return
        const list = (Array.isArray(d) ? d : (d.value ?? d.players ?? [])).map(norm)
        if (!list.length) { setSquad(null); return }
        const est = list.reduce((s, p) => s + (p.estimated_value ?? 0), 0)
        const mkt = list.reduce((s, p) => s + (p.market_value_eur ?? 0), 0)
        const avgAge = list.reduce((s, p) => s + (p.age ?? 0), 0) / list.length
        const top = [...list].sort((a, b) => (b.estimated_value ?? 0) - (a.estimated_value ?? 0))[0]
        const bargains = list
          .filter(p => p.market_value_eur > 0 && p.estimated_value > 0)
          .map(p => ({ ...p, ratio: p.estimated_value / p.market_value_eur }))
          .sort((a, b) => b.ratio - a.ratio)
        setSquad({ n: list.length, est, mkt, gap: mkt > 0 ? (est / mkt - 1) * 100 : null, avgAge, top, bargain: bargains[0] })
      })
      .catch(() => { if (active) setSquad(null) })
    return () => { active = false }
  }, [club])

  function handleSort(col) {
    if (sortBy === col) setSortAsc(v => !v)
    else { setSortBy(col); setSortAsc(false) }
  }

  function SortHead({ col, label }) {
    const active = sortBy === col
    return (
      <th className="th-sort" onClick={() => handleSort(col)} aria-sort={active ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
        {label} {active ? (sortAsc ? '↑' : '↓') : ''}
      </th>
    )
  }

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <h1>Player Database</h1>
          <p className="text-muted">Search, filter, and sort all EPL players and goalkeepers in the dataset.</p>
        </div>

        {/* ── Filters ─────────────────────────────────────────── */}
        <div className="card mb-24" style={{ padding: 20 }}>
          <div className="flex gap-12 wrap">
            {/* Search */}
            <div className="search-wrap" style={{ flex: '1 1 220px', minWidth: 180 }}>
              <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
              </svg>
              <input
                id="player-search"
                type="search"
                className="input"
                placeholder="Search by name…"
                value={q}
                onChange={e => setQ(e.target.value)}
                aria-label="Search players by name"
              />
            </div>

            {/* Position */}
            <select
              id="player-pos-filter"
              className="input select"
              style={{ flex: '0 0 160px' }}
              value={pos}
              onChange={e => setPos(e.target.value)}
              aria-label="Filter by position"
            >
              {POSITIONS.map(p => (
                <option key={p} value={p}>{POS_LABELS[p]}</option>
              ))}
            </select>

            {/* Club */}
            <select
              id="player-club-filter"
              className="input select"
              style={{ flex: '0 0 200px' }}
              value={club}
              onChange={e => setClub(e.target.value)}
              aria-label="Filter by club"
            >
              <option value="">All clubs</option>
              {clubs.map(c => <option key={c} value={c}>{c}</option>)}
            </select>

            {/* Limit */}
            <select
              id="player-limit"
              className="input select"
              style={{ flex: '0 0 120px' }}
              value={limit}
              onChange={e => setLimit(Number(e.target.value))}
              aria-label="Number of results"
            >
              {[20, 50, 100, 200].map(n => <option key={n} value={n}>Top {n}</option>)}
            </select>
          </div>
        </div>

        {/* ── Club recruitment summary ────────────────────────── */}
        {squad && (
          <div className="card card--gradient mb-24 animate-fade" style={{ padding: '22px 24px' }} id="club-summary">
            <div className="flex items-center justify-between wrap gap-12" style={{ marginBottom: 18 }}>
              <div>
                <div className="label" style={{ marginBottom: 4 }}>Club recruitment summary</div>
                <h3 style={{ margin: 0 }}>{club}</h3>
              </div>
              <div className="flex items-center gap-12 wrap">
                <span className="text-muted" style={{ fontSize: '0.82rem' }}>{squad.n} qualified players (≥ 900 min)</span>
                <Link to={`/squad?club=${encodeURIComponent(club)}`} className="btn btn-primary btn-sm">
                  Open Squad Audit &amp; Best XI →
                </Link>
              </div>
            </div>
            <div className="grid-4" style={{ gap: 14 }}>
              <div style={{ background: 'var(--c-surface)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--c-border)' }}>
                <div className="label mb-4">Squad value (model)</div>
                <div style={{ fontWeight: 800, fontSize: '1.25rem', color: 'var(--c-accent)', fontFamily: 'var(--font-mono)' }}>{fmtValue(squad.est)}</div>
                <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: 6 }}>
                  Transfermarkt: <strong style={{ color: 'var(--c-text)' }}>{fmtValue(squad.mkt)}</strong>
                  {squad.gap != null && (
                    <span style={{ marginLeft: 6, fontWeight: 700, color: squad.gap >= 0 ? 'var(--c-green)' : 'var(--c-red)' }}>
                      ({squad.gap >= 0 ? '+' : ''}{squad.gap.toFixed(0)}%)
                    </span>
                  )}
                </div>
              </div>
              <div style={{ background: 'var(--c-surface)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--c-border)' }}>
                <div className="label mb-4">Average squad age</div>
                <div style={{ fontWeight: 800, fontSize: '1.25rem', fontFamily: 'var(--font-mono)' }}>{squad.avgAge.toFixed(1)}</div>
                <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: 6 }}>years across {squad.n} players</div>
              </div>
              <div style={{ background: 'var(--c-surface)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--c-border)' }}>
                <div className="label mb-4">Highest-valued player</div>
                <Link to={`/players/${squad.top.player_id}`} style={{ fontWeight: 700, color: 'var(--c-primary)' }}>{squad.top.player_name}</Link>
                <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: 6 }}>
                  {fmtValue(squad.top.estimated_value)} · age {squad.top.age}
                </div>
              </div>
              <div style={{ background: 'var(--c-surface)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--c-border)' }}>
                <div className="label mb-4">Top undervalued bargain</div>
                {squad.bargain && squad.bargain.ratio > 1 ? (
                  <>
                    <Link to={`/players/${squad.bargain.player_id}`} style={{ fontWeight: 700, color: 'var(--c-primary)' }}>{squad.bargain.player_name}</Link>
                    <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: 6 }}>
                      Est. {fmtValue(squad.bargain.estimated_value)} vs listed {fmtValue(squad.bargain.market_value_eur)}
                      <span style={{ marginLeft: 6, fontWeight: 700, color: 'var(--c-green)' }}>(+{((squad.bargain.ratio - 1) * 100).toFixed(0)}%)</span>
                    </div>
                  </>
                ) : (
                  <div className="text-muted" style={{ fontSize: '0.85rem' }}>No player is valued above his listed price.</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Table ───────────────────────────────────────────── */}
        {error && <ErrorBox message={error} onReset={() => { setQ(''); setPos(''); setClub('') }} />}
        {loading && <PageLoading />}

        {!loading && !error && sorted.length === 0 && (
          <ErrorBox
            message={
              q.trim()
                ? `Value not found: No player matching "${q.trim()}" was found in the 2025-26 EPL outfield sample (minimum 900 minutes). Check the spelling or clear filters.`
                : 'No players found matching the selected position and club filters.'
            }
            onReset={() => { setQ(''); setPos(''); setClub('') }}
            resetLabel="↺ Reset search"
          />
        )}

        {!loading && !error && sorted.length > 0 && (
          <>
            <div className="table-wrap" style={{ marginBottom: 16 }}>
              <table className="table-compact" role="grid" aria-label="Player table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Pos</th>
                    <th>Club</th>
                    <SortHead col="age" label="Age" />
                    <SortHead col="minutes_played" label="Mins" />
                    <SortHead col="goals" label="Goals" />
                    <SortHead col="assists" label="Ast" />
                    <SortHead col="estimated_value" label="Est. Value" />
                    <SortHead col="market_value_eur" label="Mkt Value" />
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((p, i) => (
                    <tr key={p.player_id}>
                      <td>
                        <div className="flex items-center gap-10">
                          <span
                            className="text-subtle"
                            style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', minWidth: 22, textAlign: 'right' }}
                          >
                            {i + 1}
                          </span>
                          <Link
                            to={`/players/${p.player_id}`}
                            style={{ color: 'var(--c-primary)', fontWeight: 600 }}
                            id={`player-row-${p.player_id}`}
                          >
                            {p.player_name}
                          </Link>
                        </div>
                      </td>
                      <td><PosChip pos={p.position} /></td>
                      <td className="text-muted" style={{ fontSize: '0.85rem' }}>{p.club}</td>
                      <td>{p.age ?? '—'}</td>
                      <td>{p.minutes_played?.toLocaleString() ?? '—'}</td>
                      <td>{p.goals ?? '—'}</td>
                      <td>{p.assists ?? '—'}</td>
                      <td>
                        <span style={{ fontWeight: 700, color: 'var(--c-accent)' }}>
                          {fmtValue(p.estimated_value)}
                        </span>
                      </td>
                      <td className="text-muted">
                        {p.market_value_eur ? fmtValue(p.market_value_eur) : '—'}
                      </td>
                      <td>
                        <div className="flex gap-8 items-center">
                          <ShortlistBtn player={p} compact />
                          <Link
                            to={`/players/${p.player_id}`}
                            className="btn btn-secondary btn-sm"
                            id={`player-profile-btn-${p.player_id}`}
                          >
                            Profile
                          </Link>
                          <Link
                            to={`/scout?target=${p.player_id}`}
                            className="btn btn-ghost btn-sm"
                            id={`player-scout-btn-${p.player_id}`}
                          >
                            Scout
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-subtle" style={{ fontSize: '0.82rem' }}>
              Showing {sorted.length} players · Click column headers to sort
            </p>
          </>
        )}

        <Disclaimer />
      </div>
    </main>
  )
}
