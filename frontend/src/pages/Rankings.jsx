import { useEffect, useState } from 'react'
import { getRankings } from '../api'
import { fmtValue, fmtNum } from '../utils'
import { PageLoading, ErrorBox, PosChip, Disclaimer, DataCaveat } from '../components/UI'
import { Link } from 'react-router-dom'

const RANK_OPTIONS = [
  { value: 'estimated_value', label: '💰 Estimated Value' },
  { value: 'goals',           label: '⚽ Goals' },
  { value: 'assists',         label: '🎯 Assists' },
  { value: 'xg_filled',       label: '📊 Expected Goals (xG)' },
  { value: 'xa_filled',       label: '📊 Expected Assists (xA)' },
  { value: 'minutes',         label: '⏱️ Minutes Played' },
  { value: 'pass_accuracy',   label: '🎯 Pass Completion %' },
  { value: 'tackles_won_p90', label: '🛡️ Tackles Won /90' },
  { value: 'dribbles_p90',    label: '⚡ Dribbles /90' },
]

const POSITIONS = [
  { value: '',  label: 'All positions' },
  { value: 'D', label: 'Defenders' },
  { value: 'M', label: 'Midfielders' },
  { value: 'F', label: 'Attackers' },
]

const MEDAL = ['🥇', '🥈', '🥉']

export default function Rankings() {
  const [rows, setRows] = useState([])
  const [bounds, setBounds] = useState({ min_minutes: 900, max_minutes: 2790, min_age: 17, max_age: 35 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [by, setBy] = useState('estimated_value')
  const [pos, setPos] = useState('')
  const [minAge, setMinAge] = useState('')
  const [maxAge, setMaxAge] = useState('')
  const [minMins, setMinMins] = useState('')
  const [n, setN] = useState(25)

  function resetFilters() {
    setPos('')
    setMinAge('')
    setMaxAge('')
    setMinMins('')
    setError(null)
  }

  function validateInputs() {
    if (minMins !== '') {
      const mm = Number(minMins)
      if (!Number.isFinite(mm) || mm < 0) {
        return `Invalid input "${minMins}" for Min Minutes — please enter a positive number between 0 and ${bounds.max_minutes.toLocaleString()}.`
      }
      if (mm > bounds.max_minutes) {
        return `Value not found: "${mm.toLocaleString()}" minimum minutes exceeds the maximum minutes played in this dataset (${bounds.max_minutes.toLocaleString()} mins). Please enter a value up to ${bounds.max_minutes.toLocaleString()}.`
      }
    }
    if (minAge !== '') {
      const mia = Number(minAge)
      if (!Number.isFinite(mia) || mia < 15 || mia > bounds.max_age) {
        return `Value not found: Minimum age "${minAge}" is invalid — players in this dataset are aged ${bounds.min_age} to ${bounds.max_age}.`
      }
    }
    if (maxAge !== '') {
      const mxa = Number(maxAge)
      if (!Number.isFinite(mxa) || mxa > 45 || mxa < bounds.min_age) {
        return `Value not found: Maximum age "${maxAge}" is invalid — players in this dataset are aged ${bounds.min_age} to ${bounds.max_age}.`
      }
    }
    if (minAge !== '' && maxAge !== '' && Number(minAge) > Number(maxAge)) {
      return `Invalid age range: Minimum age (${minAge}) cannot be greater than maximum age (${maxAge}).`
    }
    return null
  }

  function load() {
    const validationErr = validateInputs()
    if (validationErr) {
      setRows([])
      setError(validationErr)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    getRankings({
      by,
      position: pos || undefined,
      min_age: minAge || undefined,
      max_age: maxAge || undefined,
      min_minutes: minMins || undefined,
      n,
    })
      .then(d => {
        if (d.bounds) setBounds(d.bounds)
        // API returns {rows:[...], by, label, ...} — normalise fields
        const raw = d.rows ?? d.rankings ?? d
        const norm = r => ({
          ...r,
          player_id: r.id ?? r.player_id,
          player_name: r.name ?? r.player_name,
          minutes_played: r.minutes ?? r.minutes_played,
          estimated_value: r.estimated_value_eur ?? r.estimated_value,
          market_value_eur: r.listed_value_eur ?? r.market_value_eur,
          [by]: r[by] ?? r.metric,
        })
        const list = Array.isArray(raw) ? raw.map(norm) : []
        setRows(list)
        if (list.length === 0) {
          const b = d.bounds || bounds
          setError(
            `No players found matching your inputs (valid dataset ranges: ${b.min_minutes.toLocaleString()}–${b.max_minutes.toLocaleString()} minutes, age ${b.min_age}–${b.max_age}). Please adjust or reset the filters.`
          )
        }
        setLoading(false)
      })
      .catch(e => {
        setRows([])
        setError(e.response?.data?.detail || e.message)
        setLoading(false)
      })
  }

  useEffect(() => { load() }, [by, pos, minAge, maxAge, minMins, n])

  const selectedOption = RANK_OPTIONS.find(o => o.value === by)

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <h1>🏆 Rankings</h1>
          <p className="text-muted">
            League tables sorted by any metric. Filter by position, age, and minutes.
          </p>
        </div>

        {/* ── Filters ─────────────────────────────────────────── */}
        <div className="card mb-24" style={{ padding: 20 }}>
          <div className="flex gap-12 wrap">
            {/* Rank by */}
            <div style={{ flex: '1 1 200px' }}>
              <label className="label mb-8" htmlFor="rank-by">Rank by</label>
              <select
                id="rank-by"
                className="input select"
                value={by}
                onChange={e => setBy(e.target.value)}
                aria-label="Sort rankings by"
              >
                {RANK_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            {/* Position */}
            <div style={{ flex: '0 0 160px' }}>
              <label className="label mb-8" htmlFor="rank-pos">Position</label>
              <select
                id="rank-pos"
                className="input select"
                value={pos}
                onChange={e => setPos(e.target.value)}
              >
                {POSITIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>

            {/* Min minutes */}
            <div style={{ flex: '0 0 155px' }}>
              <label className="label mb-8" htmlFor="rank-min-mins">Min minutes</label>
              <input
                id="rank-min-mins"
                type="number" min={0} max={bounds.max_minutes} placeholder={`900–${bounds.max_minutes}`}
                className="input"
                value={minMins}
                onChange={e => setMinMins(e.target.value)}
                aria-label="Minimum minutes played"
              />
            </div>

            {/* Age range */}
            <div style={{ flex: '0 0 200px' }}>
              <label className="label mb-8">Age range</label>
              <div className="flex gap-8">
                <input
                  id="rank-min-age"
                  type="number" min={15} max={45} placeholder="Min"
                  className="input"
                  value={minAge}
                  onChange={e => setMinAge(e.target.value)}
                />
                <input
                  id="rank-max-age"
                  type="number" min={15} max={45} placeholder="Max"
                  className="input"
                  value={maxAge}
                  onChange={e => setMaxAge(e.target.value)}
                />
              </div>
            </div>

            {/* Count */}
            <div style={{ flex: '0 0 100px' }}>
              <label className="label mb-8" htmlFor="rank-n">Show</label>
              <select id="rank-n" className="input select" value={n} onChange={e => setN(Number(e.target.value))}>
                {[10, 25, 50, 100].map(v => <option key={v} value={v}>Top {v}</option>)}
              </select>
            </div>
          </div>
        </div>

        {error && <ErrorBox message={error} onReset={resetFilters} />}
        {loading && <PageLoading />}

        {!loading && !error && rows.length > 0 && (
          <div className="animate-slide">
            {/* Podium (top 3) */}
            {rows.length >= 3 && (
              <div className="flex gap-16 mb-24 wrap" style={{ justifyContent: 'center' }}>
                {[rows[1], rows[0], rows[2]].map((p, i) => {
                  const realIdx = i === 0 ? 1 : i === 1 ? 0 : 2
                  return (
                    <div
                      key={p.player_id}
                      className="card card--gradient card--glow"
                      style={{
                        textAlign: 'center', padding: '20px 24px',
                        flex: '0 0 200px',
                        borderTop: `3px solid ${['#c0c0c0', '#ffd700', '#cd7f32'][realIdx]}`,
                      }}
                    >
                      <div style={{ fontSize: '2rem', marginBottom: 8 }}>{MEDAL[realIdx]}</div>
                      <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: 4 }}>
                        <Link to={`/players/${p.player_id}`} style={{ color: 'var(--c-text)' }}>
                          {p.player_name}
                        </Link>
                      </div>
                      <div className="text-muted" style={{ fontSize: '0.8rem', marginBottom: 12 }}>{p.club}</div>
                      <div style={{ fontWeight: 800, fontSize: '1.4rem', color: 'var(--c-accent)' }}>
                        {by === 'estimated_value' ? fmtValue(p.estimated_value) : fmtNum(p.metric ?? p[by])}
                      </div>
                      <div className="label mt-4">{selectedOption?.label}</div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Full table */}
            <div className="table-wrap">
              <table aria-label="Rankings table">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>#</th>
                    <th>Player</th>
                    <th>Pos</th>
                    <th>Club</th>
                    <th>Age</th>
                    <th>Mins</th>
                    <th>{selectedOption?.label ?? by}</th>
                    <th>Est. Value</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p, i) => (
                    <tr key={p.player_id}>
                      <td style={{ fontWeight: 700, color: i < 3 ? 'var(--c-yellow)' : 'var(--c-muted)', fontSize: '0.9rem' }}>
                        {i < 3 ? MEDAL[i] : i + 1}
                      </td>
                      <td>
                        <Link to={`/players/${p.player_id}`} style={{ color: 'var(--c-primary)', fontWeight: 600 }}
                          id={`rankings-row-${p.player_id}`}>{p.player_name}</Link>
                      </td>
                      <td><PosChip pos={p.position} /></td>
                      <td className="text-muted" style={{ fontSize: '0.85rem' }}>{p.club}</td>
                      <td>{p.age}</td>
                      <td>{(p.minutes_played ?? p.minutes)?.toLocaleString()}</td>
                      <td>
                        <span style={{ fontWeight: 700, color: 'var(--c-accent)' }}>
                          {by === 'estimated_value' ? fmtValue(p.estimated_value) : fmtNum(p[by] ?? p.metric)}
                        </span>
                      </td>
                      <td>{fmtValue(p.estimated_value)}</td>
                      <td>
                        <Link to={`/players/${p.player_id}`} className="btn btn-ghost btn-sm"
                          id={`rankings-profile-btn-${p.player_id}`}>→</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <DataCaveat />
        <Disclaimer />
      </div>
    </main>
  )
}
