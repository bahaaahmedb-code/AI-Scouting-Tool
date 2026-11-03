import { useState, useEffect } from 'react'
import { evalLogin, postRatings, postTask, postSus, getEvalSummary, getPlayers, postScout } from '../api'
import { fmtValue } from '../utils'
import { ErrorBox, PageLoading, PosChip, Disclaimer } from '../components/UI'

const SUS_QUESTIONS = [
  'I think that I would like to use this system frequently.',
  'I found the system unnecessarily complex.',
  'I thought the system was easy to use.',
  'I think that I would need the support of a technical person to be able to use this system.',
  'I found the various functions in this system were well integrated.',
  'I thought there was too much inconsistency in this system.',
  'I would imagine that most people would learn to use this system very quickly.',
  'I found the system very cumbersome to use.',
  'I felt very confident using the system.',
  'I needed to learn a lot of things before I could get going with this system.',
]

export default function Eval() {
  const [code, setCode] = useState('')
  const [authed, setAuthed] = useState(false)
  const [authError, setAuthError] = useState(null)

  const [tab, setTab] = useState('ratings')

  // Ratings state
  const [targetSearch, setTargetSearch] = useState('')
  const [targetId, setTargetId] = useState('')
  const [targetName, setTargetName] = useState('')
  const [candidates, setCandidates] = useState([])
  const [evaluator, setEvaluator] = useState('')
  const [ratings, setRatings] = useState({})
  const [comparableText, setComparableText] = useState('')
  const [ratingComment, setRatingComment] = useState('')
  const [ratingSaved, setRatingSaved] = useState(false)

  // Task state
  const [taskParticipant, setTaskParticipant] = useState('')
  const [taskName, setTaskName] = useState('')
  const [taskSuccess, setTaskSuccess] = useState(true)
  const [taskSeconds, setTaskSeconds] = useState('')
  const [taskNotes, setTaskNotes] = useState('')
  const [taskSaved, setTaskSaved] = useState(false)
  const [timer, setTimer] = useState(null)
  const [timerRunning, setTimerRunning] = useState(false)
  const [timerSeconds, setTimerSeconds] = useState(0)

  // SUS state
  const [susParticipant, setSusParticipant] = useState('')
  const [susAnswers, setSusAnswers] = useState(Array(10).fill(null))
  const [susSaved, setSusSaved] = useState(null)

  // Summary state
  const [summary, setSummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function login() {
    try {
      await evalLogin(code)
      setAuthed(true)
      setAuthError(null)
    } catch {
      setAuthError('Invalid access code')
    }
  }

  // Timer logic
  useEffect(() => {
    if (timerRunning) {
      const id = setInterval(() => setTimerSeconds(v => v + 1), 1000)
      return () => clearInterval(id)
    }
  }, [timerRunning])

  function startTimer() {
    setTimerSeconds(0)
    setTimerRunning(true)
  }

  function stopTimer() {
    setTimerRunning(false)
    setTaskSeconds(String(timerSeconds))
  }

  // Search target for scouting ratings
  async function searchTarget(q) {
    if (!q || q.length < 2) return
    const data = await getPlayers({ q, limit: 5 })
    const players = data.players ?? data
    return players
  }

  async function loadCandidates() {
    if (!targetId) return
    setLoading(true)
    try {
      const data = await postScout({ target: Number(targetId), position_mode: 'same', max_pct: 100, n: 10 })
      setCandidates(data.candidates ?? [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function saveRatings() {
    const items = Object.entries(ratings).map(([pid, rating]) => {
      const c = candidates.find(x => x.player_id === Number(pid))
      return {
        candidate_id: Number(pid),
        rank: candidates.indexOf(c) + 1,
        similarity: c?.similarity ?? 0,
        rating: Number(rating),
      }
    })
    if (!items.length) { setError('Rate at least one candidate'); return }
    try {
      await postRatings({
        evaluator, target_id: Number(targetId),
        items, comparable_players: comparableText, comment: ratingComment,
      }, code)
      setRatingSaved(true)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  async function saveTask() {
    try {
      await postTask({
        participant: taskParticipant, task: taskName,
        success: taskSuccess, seconds: Number(taskSeconds), notes: taskNotes,
      }, code)
      setTaskSaved(true)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  async function saveSus() {
    if (susAnswers.some(v => v === null)) { setError('Answer all 10 SUS questions'); return }
    try {
      const res = await postSus({ participant: susParticipant, answers: susAnswers }, code)
      setSusSaved(res.score)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  async function loadSummary() {
    setSummaryLoading(true)
    try {
      const data = await getEvalSummary(code)
      setSummary(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setSummaryLoading(false)
    }
  }

  if (!authed) {
    return (
      <main className="page animate-fade">
        <div className="container" style={{ maxWidth: 480, paddingTop: 80 }}>
          <div className="card" style={{ textAlign: 'center', padding: 40 }}>
            <div style={{ fontSize: '3rem', marginBottom: 16 }}>🔬</div>
            <h2 className="mb-8">Evaluation Console</h2>
            <p className="text-muted mb-24">Enter the access code provided by the study administrator.</p>
            {authError && <ErrorBox message={authError} />}
            <input
              id="eval-code-input"
              type="password"
              className="input mb-16"
              placeholder="Access code"
              value={code}
              onChange={e => setCode(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && login()}
              aria-label="Evaluation access code"
            />
            <button id="eval-login-btn" className="btn btn-primary" style={{ width: '100%' }} onClick={login}>
              Unlock Console
            </button>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <div className="flex items-center gap-12">
            <h1>🔬 Evaluation Console</h1>
            <span className="badge badge-green">Authenticated</span>
          </div>
          <p className="text-muted">Record scout ratings, task timings, SUS scores, and view the summary dashboard.</p>
        </div>

        {error && <ErrorBox message={error} />}

        {/* Tabs */}
        <div className="tabs">
          {[
            { id: 'ratings',  label: '⭐ Scout Ratings' },
            { id: 'tasks',    label: '⏱️ Task Timings' },
            { id: 'sus',      label: '📋 SUS Survey' },
            { id: 'summary',  label: '📊 Summary' },
          ].map(t => (
            <button
              key={t.id}
              id={`eval-tab-${t.id}`}
              className={`tab${tab === t.id ? ' active' : ''}`}
              onClick={() => { setTab(t.id); setError(null); if (t.id === 'summary') loadSummary() }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── RATINGS tab ──────────────────────────────────────── */}
        {tab === 'ratings' && (
          <div className="animate-fade">
            <div className="card mb-20" style={{ padding: 24 }}>
              <h3 className="mb-16">Scout Ratings</h3>
              <p className="text-muted mb-20" style={{ fontSize: '0.88rem' }}>
                Select a target player, load scouting candidates, then rate each on how well they substitute the target (1=poor, 5=excellent).
              </p>

              <div className="grid-2" style={{ gap: 20, marginBottom: 20 }}>
                <div>
                  <label className="label mb-8" htmlFor="eval-evaluator">Evaluator ID</label>
                  <input
                    id="eval-evaluator"
                    type="text"
                    className="input"
                    placeholder="e.g. Scout_01"
                    value={evaluator}
                    onChange={e => setEvaluator(e.target.value)}
                  />
                </div>
                <div>
                  <label className="label mb-8" htmlFor="eval-target-search">Target player</label>
                  <EvalPlayerSearch
                    onSelect={(p) => { setTargetId(String(p.player_id)); setTargetName(p.player_name); setCandidates([]) }}
                    placeholder="Search target…"
                    id="eval-target-search"
                  />
                  {targetName && <span className="badge badge-blue mt-8">{targetName}</span>}
                </div>
              </div>

              <button
                id="eval-load-candidates"
                className="btn btn-secondary"
                onClick={loadCandidates}
                disabled={!targetId || loading}
              >
                {loading ? '⏳ Loading…' : '🎯 Load Scout Candidates'}
              </button>
            </div>

            {candidates.length > 0 && (
              <div className="card">
                <h3 className="mb-16">Rate Candidates for "{targetName}"</h3>
                <div className="table-wrap mb-20">
                  <table aria-label="Rating candidates">
                    <thead>
                      <tr>
                        <th>Rank</th>
                        <th>Player</th>
                        <th>Pos</th>
                        <th>Club</th>
                        <th>Similarity</th>
                        <th>Est. Value</th>
                        <th>Rating (1–5)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.map((c, i) => (
                        <tr key={c.player_id}>
                          <td>{i + 1}</td>
                          <td style={{ fontWeight: 600 }}>{c.player_name}</td>
                          <td><PosChip pos={c.position} /></td>
                          <td className="text-muted">{c.club}</td>
                          <td>{(c.similarity * 100).toFixed(0)}%</td>
                          <td>{fmtValue(c.estimated_value)}</td>
                          <td>
                            <div className="flex gap-4">
                              {[1, 2, 3, 4, 5].map(r => (
                                <button
                                  key={r}
                                  id={`eval-rating-${c.player_id}-${r}`}
                                  onClick={() => setRatings(v => ({ ...v, [c.player_id]: r }))}
                                  style={{
                                    width: 32, height: 32, borderRadius: '50%', fontWeight: 700,
                                    fontSize: '0.85rem',
                                    background: ratings[c.player_id] === r ? 'var(--c-primary)' : 'var(--c-card2)',
                                    color: ratings[c.player_id] === r ? '#fff' : 'var(--c-muted)',
                                    border: `1px solid ${ratings[c.player_id] === r ? 'var(--c-primary)' : 'var(--c-border2)'}`,
                                    transition: 'all 0.15s',
                                  }}
                                  aria-label={`Rate ${c.player_name} ${r} stars`}
                                  aria-pressed={ratings[c.player_id] === r}
                                >{r}</button>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
                  <div>
                    <label className="label mb-8" htmlFor="eval-comparable">Who would you pick? (names)</label>
                    <input
                      id="eval-comparable"
                      type="text"
                      className="input"
                      placeholder="e.g. Player A, Player B"
                      value={comparableText}
                      onChange={e => setComparableText(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="label mb-8" htmlFor="eval-rating-comment">Comment (optional)</label>
                    <input
                      id="eval-rating-comment"
                      type="text"
                      className="input"
                      placeholder="Any notes…"
                      value={ratingComment}
                      onChange={e => setRatingComment(e.target.value)}
                    />
                  </div>
                </div>

                {ratingSaved
                  ? <div className="alert alert-success">✅ Ratings saved successfully!</div>
                  : (
                    <button id="eval-save-ratings" className="btn btn-primary" onClick={saveRatings}>
                      💾 Save Ratings
                    </button>
                  )}
              </div>
            )}
          </div>
        )}

        {/* ── TASKS tab ─────────────────────────────────────────── */}
        {tab === 'tasks' && (
          <div className="animate-fade">
            <div className="card" style={{ padding: 28, maxWidth: 600 }}>
              <h3 className="mb-20">Task Timing Logger</h3>

              <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
                <div>
                  <label className="label mb-8" htmlFor="eval-task-participant">Participant ID</label>
                  <input id="eval-task-participant" type="text" className="input" placeholder="e.g. P01" value={taskParticipant} onChange={e => setTaskParticipant(e.target.value)} />
                </div>
                <div>
                  <label className="label mb-8" htmlFor="eval-task-name">Task description</label>
                  <input id="eval-task-name" type="text" className="input" placeholder="e.g. Find cheapest midfielder similar to Salah" value={taskName} onChange={e => setTaskName(e.target.value)} />
                </div>
              </div>

              {/* Timer */}
              <div className="card" style={{ padding: 20, marginBottom: 20, textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', fontFamily: 'var(--font-head)', fontWeight: 800, color: 'var(--c-primary)', marginBottom: 16 }}>
                  {String(Math.floor(timerSeconds / 60)).padStart(2, '0')}:{String(timerSeconds % 60).padStart(2, '0')}
                </div>
                <div className="flex gap-12 justify-center">
                  <button id="eval-timer-start" className="btn btn-primary" onClick={startTimer} disabled={timerRunning}>▶ Start</button>
                  <button id="eval-timer-stop" className="btn btn-secondary" onClick={stopTimer} disabled={!timerRunning}>⏹ Stop</button>
                </div>
              </div>

              <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
                <div>
                  <label className="label mb-8">Success?</label>
                  <div className="flex gap-8">
                    <button
                      id="eval-task-success-yes"
                      className={`btn btn-sm ${taskSuccess ? 'btn-green' : 'btn-secondary'}`}
                      onClick={() => setTaskSuccess(true)}
                      aria-pressed={taskSuccess}
                    >✓ Yes</button>
                    <button
                      id="eval-task-success-no"
                      className={`btn btn-sm ${!taskSuccess ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setTaskSuccess(false)}
                      aria-pressed={!taskSuccess}
                      style={!taskSuccess ? { background: 'var(--c-red)' } : {}}
                    >✗ No</button>
                  </div>
                </div>
                <div>
                  <label className="label mb-8" htmlFor="eval-task-seconds">Time (seconds)</label>
                  <input id="eval-task-seconds" type="number" className="input" value={taskSeconds} onChange={e => setTaskSeconds(e.target.value)} />
                </div>
              </div>

              <div className="mb-16">
                <label className="label mb-8" htmlFor="eval-task-notes">Notes</label>
                <textarea id="eval-task-notes" className="input" rows={3} value={taskNotes} onChange={e => setTaskNotes(e.target.value)} style={{ resize: 'vertical' }} />
              </div>

              {taskSaved
                ? <div className="alert alert-success">✅ Task logged!</div>
                : <button id="eval-save-task" className="btn btn-primary" onClick={saveTask}>💾 Log Task</button>}
            </div>
          </div>
        )}

        {/* ── SUS tab ───────────────────────────────────────────── */}
        {tab === 'sus' && (
          <div className="animate-fade">
            <div className="card" style={{ padding: 28, maxWidth: 720 }}>
              <h3 className="mb-8">System Usability Scale (SUS)</h3>
              <p className="text-muted mb-24" style={{ fontSize: '0.88rem' }}>
                Rate each statement from 1 (Strongly Disagree) to 5 (Strongly Agree).
              </p>

              <div className="mb-20">
                <label className="label mb-8" htmlFor="eval-sus-participant">Participant ID</label>
                <input id="eval-sus-participant" type="text" className="input" style={{ maxWidth: 240 }} value={susParticipant} onChange={e => setSusParticipant(e.target.value)} placeholder="e.g. P01" />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {SUS_QUESTIONS.map((q, i) => (
                  <div key={i} style={{ background: 'var(--c-surface)', padding: '14px 16px', borderRadius: 8 }}>
                    <div style={{ marginBottom: 10, fontSize: '0.9rem', lineHeight: 1.5 }}>
                      <span style={{ color: 'var(--c-muted)', marginRight: 8 }}>{i + 1}.</span>
                      {q}
                    </div>
                    <div className="flex gap-8">
                      {[1, 2, 3, 4, 5].map(v => (
                        <button
                          key={v}
                          id={`eval-sus-q${i}-${v}`}
                          onClick={() => setSusAnswers(a => { const n = [...a]; n[i] = v; return n })}
                          style={{
                            flex: 1, padding: '8px 0', borderRadius: 6, fontWeight: 700,
                            fontSize: '0.85rem',
                            background: susAnswers[i] === v ? 'var(--c-primary)' : 'var(--c-card2)',
                            color: susAnswers[i] === v ? '#fff' : 'var(--c-muted)',
                            border: `1px solid ${susAnswers[i] === v ? 'var(--c-primary)' : 'var(--c-border2)'}`,
                            transition: 'all 0.15s',
                          }}
                          aria-label={`Question ${i + 1}: ${v}`}
                          aria-pressed={susAnswers[i] === v}
                        >{v}</button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-24">
                {susSaved != null
                  ? <div className="alert alert-success">✅ SUS score saved: <strong>{susSaved.toFixed(1)}</strong> / 100</div>
                  : <button id="eval-save-sus" className="btn btn-primary" onClick={saveSus}>💾 Submit SUS</button>}
              </div>
            </div>
          </div>
        )}

        {/* ── SUMMARY tab ───────────────────────────────────────── */}
        {tab === 'summary' && (
          <div className="animate-fade">
            {summaryLoading && <PageLoading />}
            {summary && (
              <div className="grid-2" style={{ gap: 24 }}>
                {Object.entries(summary).map(([table, stats]) => (
                  <div key={table} className="card">
                    <h3 className="mb-16" style={{ textTransform: 'capitalize' }}>{table.replace('_', ' ')}</h3>
                    <div className="table-wrap">
                      <table>
                        <tbody>
                          {Object.entries(stats).map(([k, v]) => (
                            <tr key={k}>
                              <td className="text-muted" style={{ fontSize: '0.85rem' }}>{k}</td>
                              <td style={{ fontWeight: 600 }}>{typeof v === 'number' ? v.toFixed(2) : String(v)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <Disclaimer />
      </div>
    </main>
  )
}

/** Inline player search for eval forms */
function EvalPlayerSearch({ onSelect, placeholder, id }) {
  const [q, setQ] = useState('')
  const [opts, setOpts] = useState([])

  useEffect(() => {
    if (!q || q.length < 2) { setOpts([]); return }
    getPlayers({ q, limit: 5 }).then(d => setOpts(d.players ?? d)).catch(() => {})
  }, [q])

  return (
    <div style={{ position: 'relative' }}>
      <input
        id={id}
        type="text"
        className="input"
        placeholder={placeholder}
        value={q}
        onChange={e => setQ(e.target.value)}
      />
      {opts.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20,
          background: 'var(--c-card2)', border: '1px solid var(--c-border2)',
          borderRadius: 8, marginTop: 4, boxShadow: 'var(--shadow-pop)',
        }}>
          {opts.map(p => (
            <button
              key={p.player_id}
              onClick={() => { onSelect(p); setQ(p.player_name); setOpts([]) }}
              style={{
                width: '100%', padding: '10px 14px', textAlign: 'left',
                display: 'flex', gap: 8, alignItems: 'center',
                color: 'var(--c-text)', fontSize: '0.88rem',
                borderBottom: '1px solid var(--c-border)',
              }}
              className="btn-ghost"
            >
              <PosChip pos={p.position} />
              <span style={{ fontWeight: 600 }}>{p.player_name}</span>
              <span className="text-muted" style={{ fontSize: '0.8rem', marginLeft: 'auto' }}>{p.club}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
