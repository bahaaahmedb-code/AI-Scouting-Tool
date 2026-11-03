import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { getPlayers, postScout } from '../api'
import { fmtValue, debounce, posClass } from '../utils'
import { PageLoading, ErrorBox, PosChip, Disclaimer, DataCaveat } from '../components/UI'

const POS_MODES = [
  { value: 'same', label: 'Same position' },
  { value: 'any',  label: 'Any position' },
  { value: 'D',    label: 'Defenders only' },
  { value: 'M',    label: 'Midfielders only' },
  { value: 'F',    label: 'Forwards only' },
]

export default function Scout() {
  const [searchParams] = useSearchParams()
  const [targetId, setTargetId] = useState(searchParams.get('target') || '')
  const [targetSearch, setTargetSearch] = useState('')
  const [targetSuggestions, setTargetSuggestions] = useState([])
  const [targetSearched, setTargetSearched] = useState(false)
  const [targetName, setTargetName] = useState('')

  const [posMode, setPosMode] = useState('same')
  const [maxPct, setMaxPct] = useState(60)
  const [minAge, setMinAge] = useState('')
  const [maxAge, setMaxAge] = useState('')
  const [n, setN] = useState(10)

  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Pre-fill target from URL param
  useEffect(() => {
    const tid = searchParams.get('target')
    if (tid) {
      setTargetId(tid)
      // Fetch player name
      import('../api').then(({ getPlayer }) => {
        getPlayer(Number(tid)).then(p => setTargetName(p.player_name)).catch(() => {})
      })
    }
  }, [])

  // Search for target player
  useEffect(() => {
    if (!targetSearch || targetSearch.length < 2) { setTargetSuggestions([]); setTargetSearched(false); return }
    const fn = debounce((q) => {
      getPlayers({ q, limit: 8 })
        .then(d => {
          // search() returns a plain list
          const list = Array.isArray(d) ? d : (d.value ?? d.players ?? [])
          setTargetSuggestions(list.map(p => ({ ...p, player_id: p.id ?? p.player_id, player_name: p.name ?? p.player_name, estimated_value: p.estimated_value_eur ?? p.estimated_value })))
          setTargetSearched(true)
        })
        .catch(() => {})
    }, 250)
    fn(targetSearch)
  }, [targetSearch])

  function selectTarget(p) {
    setTargetId(String(p.player_id ?? p.id))
    setTargetName(p.player_name ?? p.name)
    setTargetSearch('')
    setTargetSuggestions([])
  }

  async function run() {
    if (!targetId) return
    if (minAge !== '' && (Number(minAge) < 16 || Number(minAge) > 45)) {
      setResults(null)
      setError(`Value not found: Minimum age "${minAge}" is outside the valid range (17–35 in this dataset).`)
      return
    }
    if (maxAge !== '' && (Number(maxAge) < 16 || Number(maxAge) > 45)) {
      setResults(null)
      setError(`Value not found: Maximum age "${maxAge}" is outside the valid range (17–35 in this dataset).`)
      return
    }
    if (minAge !== '' && maxAge !== '' && Number(minAge) > Number(maxAge)) {
      setResults(null)
      setError(`Invalid age range: Minimum age (${minAge}) cannot be greater than maximum age (${maxAge}).`)
      return
    }
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const data = await postScout({
        target: Number(targetId),
        position_mode: posMode,
        max_pct: Number(maxPct),
        ...(minAge ? { min_age: Number(minAge) } : {}),
        ...(maxAge ? { max_age: Number(maxAge) } : {}),
        n: Number(n),
      })
      setResults(data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <h1>🎯 Scouting Tool</h1>
          <p className="text-muted">
            Find cheaper players with similar styles to any target. Uses cosine-similarity on standardised performance features.
          </p>
        </div>

        {/* ── Filter panel ────────────────────────────────────── */}
        <div className="card mb-32" style={{ padding: 28 }}>
          <h3 className="mb-20">Scout parameters</h3>
          <div className="grid-2" style={{ gap: 20 }}>

            {/* Target player picker */}
            <div>
              <label className="label mb-8" htmlFor="scout-target-search">Target player</label>
              <div style={{ position: 'relative' }}>
                <input
                  id="scout-target-search"
                  type="text"
                  className="input"
                  placeholder={targetName || 'Type player name…'}
                  value={targetSearch}
                  onChange={e => setTargetSearch(e.target.value)}
                  aria-label="Search for target player"
                />
                {targetSuggestions.length > 0 && (
                  <div style={{
                    position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20,
                    background: 'var(--c-card2)', border: '1px solid var(--c-border2)',
                    borderRadius: 8, marginTop: 4, overflow: 'hidden',
                    boxShadow: 'var(--shadow-pop)',
                  }}>
                    {targetSuggestions.map(p => (
                      <button
                        key={p.player_id}
                        onClick={() => selectTarget(p)}
                        id={`scout-suggest-${p.player_id}`}
                        style={{
                          width: '100%', padding: '10px 14px', textAlign: 'left',
                          display: 'flex', alignItems: 'center', gap: 10,
                          color: 'var(--c-text)', fontSize: '0.9rem',
                          borderBottom: '1px solid var(--c-border)',
                          transition: 'background 0.15s',
                        }}
                        className="btn-ghost"
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.08)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <PosChip pos={p.position} />
                        <span style={{ fontWeight: 600 }}>{p.player_name}</span>
                        <span className="text-muted" style={{ fontSize: '0.8rem' }}>{p.club}</span>
                        <span className="text-accent" style={{ marginLeft: 'auto', fontSize: '0.85rem' }}>
                          {fmtValue(p.estimated_value)}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                {targetSearched && targetSearch.trim().length >= 2 && targetSuggestions.length === 0 && (
                  <div className="alert alert-danger mt-8" style={{ padding: '8px 12px', fontSize: '0.82rem' }}>
                    ⚠️ Value not found: No player matching "{targetSearch.trim()}" exists in the sample.
                  </div>
                )}
              </div>
              {targetName && (
                <div className="mt-8 flex items-center gap-8">
                  <span className="badge badge-blue">Selected: {targetName}</span>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => { setTargetId(''); setTargetName('') }}
                  >✕</button>
                </div>
              )}
            </div>

            {/* Position mode */}
            <div>
              <label className="label mb-8" htmlFor="scout-pos-mode">Position filter</label>
              <select
                id="scout-pos-mode"
                className="input select"
                value={posMode}
                onChange={e => setPosMode(e.target.value)}
                aria-label="Position filter mode"
              >
                {POS_MODES.map(m => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>

            {/* Max price % */}
            <div>
              <label className="label mb-8" htmlFor="scout-max-pct">
                Max price (% of target estimate)
              </label>
              <div className="flex items-center gap-12">
                <input
                  id="scout-max-pct"
                  type="range" min={5} max={200} step={5}
                  value={maxPct}
                  onChange={e => setMaxPct(e.target.value)}
                  style={{ flex: 1 }}
                  aria-label={`Max price ${maxPct}% of target`}
                />
                <span style={{ minWidth: 50, fontWeight: 700, color: 'var(--c-primary)' }}>{maxPct}%</span>
              </div>
              <p className="text-subtle mt-4" style={{ fontSize: '0.78rem' }}>
                Only show candidates valued at most {maxPct}% of target's estimate
              </p>
            </div>

            {/* Number of results */}
            <div>
              <label className="label mb-8" htmlFor="scout-n">Number of results</label>
              <select
                id="scout-n"
                className="input select"
                value={n}
                onChange={e => setN(e.target.value)}
                aria-label="Number of scouting results"
              >
                {[5, 10, 15, 20].map(v => <option key={v} value={v}>Top {v}</option>)}
              </select>
            </div>

            {/* Age range */}
            <div>
              <label className="label mb-8">Age range (optional)</label>
              <div className="flex gap-8">
                <input
                  id="scout-min-age"
                  type="number" min={16} max={45} placeholder="Min"
                  className="input" style={{ flex: 1 }}
                  value={minAge}
                  onChange={e => setMinAge(e.target.value)}
                  aria-label="Minimum age"
                />
                <input
                  id="scout-max-age"
                  type="number" min={16} max={45} placeholder="Max"
                  className="input" style={{ flex: 1 }}
                  value={maxAge}
                  onChange={e => setMaxAge(e.target.value)}
                  aria-label="Maximum age"
                />
              </div>
            </div>
          </div>

          <div className="mt-24">
            <button
              id="scout-run-btn"
              className="btn btn-primary btn-lg"
              onClick={run}
              disabled={!targetId || loading}
            >
              {loading ? '⏳ Searching…' : '🎯 Find Alternatives'}
            </button>
          </div>
        </div>

        {/* ── Results ──────────────────────────────────────────── */}
        {error && <ErrorBox message={error} />}
        {loading && <PageLoading />}

        {results && !loading && (
          <div className="animate-slide">
            {/* Target summary */}
            <div className="card card--gradient card-glow-blue mb-24">
              <div className="flex items-center gap-16 wrap">
                <div>
                  <div className="label mb-4">Target player</div>
                  <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>
                    {results.target?.name ?? results.target?.player_name}
                  </div>
                  <div className="text-muted" style={{ fontSize: '0.85rem' }}>
                    {results.target?.club} · Age {results.target?.age}
                  </div>
                </div>
                <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                  <div className="label mb-4">Out-of-fold estimate</div>
                  <div className="val-medium text-accent">
                    {fmtValue(results.target_value_eur ?? results.target?.oof_value_eur ?? results.target?.estimated_value_eur)}
                  </div>
                </div>
              </div>
            </div>

            {/* Relaxation suggestions */}
            {results.suggestions?.map((s, si) => (
              <div key={si} className="alert alert-warn mb-8">
                💡 {s.text}
              </div>
            ))}

            {/* Candidates table */}
            {(results.results?.length ?? 0) > 0 ? (
              <div className="table-wrap">
                <table aria-label="Scouting results">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Player</th>
                      <th>Pos</th>
                      <th>Club</th>
                      <th>Age</th>
                      <th>Similarity</th>
                      <th>Est. Value (OOF)</th>
                      <th>Savings vs target</th>
                      <th>Shared strengths</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.results.map((c, i) => {
                      const cId = c.id ?? c.player_id
                      const cName = c.name ?? c.player_name
                      const cVal = c.value_eur ?? c.estimated_value_eur ?? c.estimated_value
                      const targetVal = results.target_value_eur ?? results.target?.oof_value_eur ?? 0
                      const savings = targetVal - cVal
                      return (
                        <tr key={cId}>
                          <td>
                            <span style={{
                              width: 28, height: 28, borderRadius: '50%',
                              background: 'var(--c-card2)', display: 'inline-flex',
                              alignItems: 'center', justifyContent: 'center',
                              fontWeight: 700, fontSize: '0.82rem', color: 'var(--c-muted)',
                            }}>{c.rank ?? i + 1}</span>
                          </td>
                          <td>
                            <Link
                              to={`/players/${cId}`}
                              style={{ color: 'var(--c-primary)', fontWeight: 600 }}
                              id={`scout-result-${cId}`}
                            >
                              {cName}
                            </Link>
                          </td>
                          <td><PosChip pos={c.position} /></td>
                          <td className="text-muted" style={{ fontSize: '0.85rem' }}>{c.club}</td>
                          <td>{c.age}</td>
                          <td>
                            <div className="flex items-center gap-8">
                              <div style={{ flex: 1, width: 60 }}>
                                <div className="progress">
                                  <div className="progress-fill"
                                    style={{ width: `${(c.similarity * 100).toFixed(0)}%`, background: 'var(--c-primary)' }} />
                                </div>
                              </div>
                              <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>
                                {(c.similarity * 100).toFixed(0)}%
                              </span>
                            </div>
                          </td>
                          <td>
                            <span style={{ fontWeight: 700, color: 'var(--c-accent)' }}>
                              {fmtValue(cVal)}
                            </span>
                          </td>
                          <td>
                            <span style={{ fontWeight: 700, color: savings >= 0 ? 'var(--c-green)' : 'var(--c-red)' }}>
                              {savings >= 0 ? '−' : '+'}{fmtValue(Math.abs(savings))}
                            </span>
                          </td>
                          <td>
                            <div className="flex gap-4 wrap">
                              {(c.shared_labels ?? c.shared_strengths ?? []).slice(0, 3).map((s, si) => (
                                <span key={si} className="badge badge-green" style={{ fontSize: '0.7rem' }}>{s}</span>
                              ))}
                            </div>
                          </td>
                          <td>
                            <div className="flex gap-4">
                              <Link to={`/players/${cId}`} className="btn btn-secondary btn-sm" id={`scout-profile-btn-${cId}`}>
                                Profile
                              </Link>
                              <Link to={`/compare?ids=${targetId},${cId}`} className="btn btn-ghost btn-sm" id={`scout-compare-btn-${cId}`}>
                                Compare
                              </Link>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">🔍</div>
                <h3>No candidates found</h3>
                <p>Try relaxing the budget or position filters.</p>
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
