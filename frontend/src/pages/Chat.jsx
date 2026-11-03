import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  ResponsiveContainer, ScatterChart, Scatter, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'
import { postChat, getShap, getRadar, getDependence, getGeminiStatus, postGeminiKey } from '../api'
import WaterfallChart from '../components/WaterfallChart'
import RadarChart from '../components/RadarChart'
import { Disclaimer, Spinner } from '../components/UI'
import { fmtNum } from '../utils'

const SUGGESTIONS = [
  'What is the best attacker to buy in the range of 35 million to 55 million?',
  'Who are the most undervalued midfielders?',
  'What are Bukayo Saka\'s strengths and weaknesses?',
  'Which club has the highest squad value?',
  'Find me cheap alternatives to the highest-valued forward',
  'Show radar for Joao Pedro and Viktor Gyokeres',
  'How does the model work?',
  'What are the limitations of the model?',
]

const INTENT_LABELS = {
  valuation: '💰 Valuation',
  explanation: '🧠 Explanation',
  scouting: '🎯 Scouting',
  comparison: '⚖️ Comparison',
  ranking: '🏆 Ranking',
  whatif: '🔮 What-If',
  glossary: '📖 Glossary',
  howto: '🧭 Guide',
  data_quality: '📋 Dataset',
  out_of_scope: 'ℹ️ Scope Note',
  clarify: '❓ Clarification',
}

const POS_COLOR = { D: '#3b82f6', M: '#10b981', F: '#ef4444' }
const POS_NAME = { D: 'Defenders', M: 'Midfielders', F: 'Attackers' }
const CHART_TIP = {
  background: 'var(--c-card2)',
  border: '1px solid var(--c-border2)',
  borderRadius: 8,
  color: 'var(--c-text)',
  fontSize: '0.82rem',
}
const CHART_AXIS = { fill: 'var(--c-muted)', fontSize: 11 }

function renderInline(str) {
  if (!str) return null
  const tokens = String(str).split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g)
  return tokens.map((tok, i) => {
    if (tok.startsWith('**') && tok.endsWith('**') && tok.length > 4) {
      return <strong key={i} style={{ color: '#fff', fontWeight: 700 }}>{tok.slice(2, -2)}</strong>
    }
    if (tok.startsWith('*') && tok.endsWith('*') && tok.length > 2) {
      return <em key={i} style={{ color: 'var(--c-muted)' }}>{tok.slice(1, -1)}</em>
    }
    if (tok.startsWith('`') && tok.endsWith('`') && tok.length > 2) {
      return <code key={i}>{tok.slice(1, -1)}</code>
    }
    return tok
  })
}

function MarkdownText({ text }) {
  if (!text) return null
  const lines = String(text).split('\n')
  const blocks = []
  let listType = null
  let listItems = []

  const flushList = () => {
    if (!listItems.length) return
    const items = listItems
    const type = listType
    listItems = []
    listType = null
    if (type === 'ol') {
      blocks.push(<ol key={`l-${blocks.length}`}>{items.map((it, idx) => <li key={idx}>{renderInline(it)}</li>)}</ol>)
    } else {
      blocks.push(<ul key={`l-${blocks.length}`}>{items.map((it, idx) => <li key={idx}>{renderInline(it)}</li>)}</ul>)
    }
  }

  lines.forEach((raw) => {
    const trimmed = raw.trim()
    if (!trimmed) {
      flushList()
      return
    }
    if (/^---+$/.test(trimmed)) {
      flushList()
      blocks.push(<div key={`hr-${blocks.length}`} className="divider" style={{ margin: '12px 0' }} />)
      return
    }
    const ulMatch = trimmed.match(/^[-•]\s+(.+)$/)
    if (ulMatch) {
      if (listType && listType !== 'ul') flushList()
      listType = 'ul'
      listItems.push(ulMatch[1])
      return
    }
    const olMatch = trimmed.match(/^\d+\.\s+(.+)$/)
    if (olMatch) {
      if (listType && listType !== 'ol') flushList()
      listType = 'ol'
      listItems.push(olMatch[1])
      return
    }
    flushList()
    blocks.push(<p key={`p-${blocks.length}`}>{renderInline(trimmed)}</p>)
  })
  flushList()

  return <div className="chat-md">{blocks}</div>
}

function buildCsvString(table) {
  if (table.csv) return table.csv
  const cols = (table.columns || []).map(c => (typeof c === 'string' ? { key: c, label: c } : c))
  const esc = v => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const header = cols.map(c => esc(c.label)).join(',')
  const body = (table.rows || []).map(row => {
    if (Array.isArray(row)) return row.map(esc).join(',')
    return cols.map(c => esc(row[c.key])).join(',')
  })
  return [header, ...body].join('\n')
}

function ChatTable({ table }) {
  if (!table || !table.columns?.length || !table.rows?.length) return null
  const cols = table.columns.map((c, idx) => (
    typeof c === 'string' ? { key: String(idx), label: c } : c
  ))

  function handleCopyCsv() {
    const csv = buildCsvString(table)
    navigator.clipboard.writeText(csv)
      .then(() => toast.success('Table copied to clipboard as CSV'))
      .catch(() => toast.error('Could not copy CSV'))
  }

  function handleDownloadCsv() {
    const csv = buildCsvString(table)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = table.csv_name || 'moneyball_table.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success(`Downloaded ${table.csv_name || 'moneyball_table.csv'}`)
  }

  return (
    <div className="mt-12">
      <div className="table-wrap" style={{ maxHeight: 320, overflowY: 'auto', background: 'var(--c-surface)' }}>
        <table>
          <thead>
            <tr>
              {cols.map((c, i) => (
                <th key={c.key || i} style={{ padding: '9px 12px', fontSize: '0.73rem' }}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, ri) => {
              const isArr = Array.isArray(row)
              const pid = !isArr ? row?._id : null
              return (
                <tr key={ri}>
                  {cols.map((c, ci) => {
                    const cell = isArr ? row[ci] : row?.[c.key]
                    const isPlayerCol = pid != null && (c.key === 'name' || c.key === 'player')
                    return (
                      <td key={c.key || ci} style={{ padding: '9px 12px', fontSize: '0.83rem' }}>
                        {isPlayerCol ? (
                          <Link
                            to={`/players/${pid}`}
                            style={{ color: 'var(--c-primary)', fontWeight: 600 }}
                          >
                            {cell ?? '—'}
                          </Link>
                        ) : (
                          cell ?? '—'
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="flex gap-8 mt-8" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={handleCopyCsv} style={{ fontSize: '0.76rem', padding: '4px 10px' }}>
          📋 Copy CSV
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={handleDownloadCsv} style={{ fontSize: '0.76rem', padding: '4px 10px' }}>
          ⬇ Download CSV
        </button>
      </div>
    </div>
  )
}

function ChatChart({ chart }) {
  const [open, setOpen] = useState(true)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open || !chart) return
    let active = true
    setLoading(true)
    const load = async () => {
      try {
        if (chart.type === 'waterfall' && chart.ids?.length) {
          const d = await getShap(chart.ids[0])
          if (active) setData(d)
        } else if (chart.type === 'radar' && chart.ids?.length) {
          const r = await getRadar(chart.ids)
          if (active) {
            setData({
              axes: r.axes,
              players: r.players.map(p => ({ name: p.name, values: p.percentiles })),
            })
          }
        } else if (chart.type === 'dependence' && chart.feature) {
          const d = await getDependence(chart.feature)
          if (active) setData(d)
        }
      } catch {
        if (active) setData(null)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [open, chart])

  if (!chart) return null

  const chartTitle =
    chart.type === 'waterfall' ? 'SHAP Waterfall Breakdown'
    : chart.type === 'radar' ? 'Position Percentile Radar'
    : `SHAP Dependence${data?.label ? `: ${data.label}` : ''}`

  return (
    <div className="mt-12" style={{ border: '1px solid var(--c-border)', borderRadius: 'var(--r-md)', background: 'var(--c-surface)', overflow: 'hidden' }}>
      <div
        className="flex items-center justify-between"
        style={{ padding: '8px 12px', borderBottom: open ? '1px solid var(--c-border)' : 'none' }}
      >
        <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--c-muted)' }}>
          📊 {chartTitle}
        </span>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          style={{ fontSize: '0.75rem', padding: '2px 8px' }}
          onClick={() => setOpen(v => !v)}
        >
          {open ? 'Hide chart' : 'Show chart'}
        </button>
      </div>

      {open && (
        <div style={{ padding: 14 }}>
          {loading && (
            <div className="flex items-center gap-8" style={{ padding: 16 }}>
              <Spinner size={16} />
              <span className="text-muted" style={{ fontSize: '0.82rem' }}>Loading visual…</span>
            </div>
          )}
          {!loading && data && chart.type === 'waterfall' && (
            <WaterfallChart data={data} />
          )}
          {!loading && data && chart.type === 'radar' && (
            <RadarChart data={data} />
          )}
          {!loading && data && chart.type === 'dependence' && (
            data.categorical ? (
              <div style={{ height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.categories} layout="vertical" margin={{ left: 8, right: 20, top: 6, bottom: 6 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border)" />
                    <XAxis type="number" tick={CHART_AXIS} tickFormatter={v => `${v >= 0 ? '+' : ''}${fmtNum(v, 0)}%`} />
                    <YAxis type="category" dataKey="category" width={110} tick={{ fill: 'var(--c-text)', fontSize: 11 }} />
                    <ReferenceLine x={0} stroke="gray" strokeDasharray="4 4" />
                    <Tooltip contentStyle={CHART_TIP} formatter={v => [`${v >= 0 ? '+' : ''}${fmtNum(v, 1)}%`, 'Avg effect on value']} />
                    <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
                      {(data.categories ?? []).map((c, i) => (
                        <Cell key={i} fill={c.pct >= 0 ? '#10b981' : '#ef4444'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border)" />
                    <XAxis
                      dataKey="x"
                      type="number"
                      height={44}
                      tick={CHART_AXIS}
                      domain={['auto', 'auto']}
                      label={{ value: data.label, position: 'insideBottom', offset: 8, fill: 'var(--c-muted)', fontSize: 11 }}
                    />
                    <YAxis dataKey="shap" type="number" tick={CHART_AXIS} tickFormatter={v => v.toFixed(2)} />
                    <ReferenceLine y={0} stroke="gray" strokeDasharray="4 4" />
                    <Tooltip
                      contentStyle={CHART_TIP}
                      content={({ payload }) => {
                        const p = payload?.[0]?.payload
                        if (!p) return null
                        return (
                          <div style={{ ...CHART_TIP, padding: 10 }}>
                            <strong>{p.name}</strong>
                            <div className="text-muted">{POS_NAME[p.position]}</div>
                            <div>{data.label}: {fmtNum(p.x, 2)}</div>
                            <div>Effect: {p.pct >= 0 ? '+' : ''}{fmtNum(p.pct, 1)}% on value</div>
                          </div>
                        )
                      }}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={24}
                      iconSize={8}
                      wrapperStyle={{ bottom: 0, fontSize: '0.74rem', paddingTop: 6 }}
                    />
                    {['D', 'M', 'F'].map(k => (
                      <Scatter
                        key={k}
                        name={POS_NAME[k]}
                        fill={POS_COLOR[k]}
                        fillOpacity={0.7}
                        data={(data.points ?? []).filter(p => p.position === k)}
                      />
                    ))}
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            )
          )}
        </div>
      )}
    </div>
  )
}

function ChatMessage({ msg, onSend, disabled }) {
  const isUser = msg.role === 'user'
  const [showDetails, setShowDetails] = useState(false)
  const hasRich = Boolean(!isUser && (msg.table || msg.chart || msg.details))

  if (isUser) {
    return (
      <div className="chat-bubble user">
        <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{msg.text}</div>
      </div>
    )
  }

  return (
    <div className={`chat-bubble bot${hasRich ? ' has-rich' : ''}`}>
      {/* Intent badge & context note */}
      {(msg.intent || msg.context_note) && (
        <div className="flex items-center gap-8 wrap mb-8">
          {msg.intent && (
            <span className="badge badge-blue" style={{ fontSize: '0.7rem', padding: '2px 8px' }}>
              {INTENT_LABELS[msg.intent] || msg.intent}
            </span>
          )}
          {msg.context_note && (
            <span style={{ fontSize: '0.76rem', color: 'var(--c-accent)' }}>
              ↳ {msg.context_note}
            </span>
          )}
        </div>
      )}

      {/* Markdown body */}
      <MarkdownText text={msg.text} />

      {/* Structured table */}
      {msg.table && <ChatTable table={msg.table} />}

      {/* Interactive chart */}
      {msg.chart && <ChatChart chart={msg.chart} />}

      {/* Expandable SHAP details */}
      {msg.details && (
        <div className="mt-12">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ fontSize: '0.78rem', padding: '4px 10px' }}
            onClick={() => setShowDetails(v => !v)}
          >
            {showDetails ? '▾ Hide full SHAP breakdown' : '▸ Show full SHAP breakdown'}
          </button>
          {showDetails && (
            <div
              className="mt-8"
              style={{
                padding: '12px 14px',
                background: 'var(--c-surface)',
                border: '1px solid var(--c-border)',
                borderRadius: 'var(--r-md)',
              }}
            >
              <MarkdownText text={msg.details} />
            </div>
          )}
        </div>
      )}

      {/* Legacy bullets fallback */}
      {msg.bullets && msg.bullets.length > 0 && (
        <ul style={{ marginTop: 10, paddingLeft: 20, fontSize: '0.88rem' }}>
          {msg.bullets.map((b, i) => <li key={i} style={{ marginBottom: 4 }}>{b}</li>)}
        </ul>
      )}

      {/* Action links */}
      {msg.actions && msg.actions.length > 0 && (
        <div className="flex gap-8 wrap mt-12">
          {msg.actions.map((a, i) => (
            <Link key={i} to={a.href} className="btn btn-secondary btn-sm" style={{ fontSize: '0.78rem' }}>
              {a.label} →
            </Link>
          ))}
        </div>
      )}

      {/* Follow-up suggestion chips */}
      {msg.suggestions && msg.suggestions.length > 0 && (
        <div className="flex gap-8 wrap mt-12" style={{ paddingTop: 10, borderTop: '1px solid var(--c-border)' }}>
          <span className="text-subtle" style={{ fontSize: '0.74rem', alignSelf: 'center' }}>Follow up:</span>
          {msg.suggestions.map((s, i) => (
            <button
              key={i}
              type="button"
              className="btn btn-ghost btn-sm"
              style={{
                fontSize: '0.76rem',
                padding: '4px 10px',
                border: '1px solid var(--c-border2)',
                background: 'rgba(59,130,246,0.06)',
              }}
              disabled={disabled}
              onClick={() => onSend(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Not understood hint */}
      {msg.understood === false && (!msg.suggestions || msg.suggestions.length === 0) && (
        <div className="alert alert-warn mt-12" style={{ fontSize: '0.82rem' }}>
          💡 Try rephrasing or ask about a specific player, valuation, scouting shortlist, or glossary term.
        </div>
      )}

      {(msg.rephrased || msg.rewritten_query) && (
        <div className="flex gap-12 wrap" style={{ fontSize: '0.73rem', color: 'var(--c-subtle)', marginTop: 8 }}>
          {msg.rephrased && (
            <span>✨ Enhanced by Gemini{msg.llm_model ? ` (${msg.llm_model})` : ''} · 100% fact-checked</span>
          )}
          {msg.rewritten_query && (
            <span>🔎 Interpreted as: <em>“{msg.rewritten_query}”</em></span>
          )}
        </div>
      )}
    </div>
  )
}

const WELCOME_MSG = {
  role: 'bot',
  text: '👋 Hello! I\'m the **Moneyball EPL** assistant. Ask me anything across all tabs — **budget transfer targets** (e.g. *35m to 55m*), **player valuations & SHAP waterfalls**, **strengths & weaknesses**, **scouting shortlists**, **radar comparisons**, **club & position summaries**, **what-if scenarios**, or **model accuracy & caveats**.',
  understood: true,
  suggestions: [
    'What is the best attacker to buy in the range of 35 million to 55 million?',
    'What are Bukayo Saka\'s strengths and weaknesses?',
  ],
}

export default function Chat() {
  const [messages, setMessages] = useState([WELCOME_MSG])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [context, setContext] = useState(null)
  const [gemini, setGemini] = useState({ configured: false, enabled: true, masked_key: null, model: 'gemini-3.8-flash' })
  const [showKeyBox, setShowKeyBox] = useState(false)
  const [keyInput, setKeyInput] = useState('')
  const [savingKey, setSavingKey] = useState(false)
  const messagesListRef = useRef(null)

  useEffect(() => {
    getGeminiStatus().then(setGemini).catch(() => {})
  }, [])

  useEffect(() => {
    const container = messagesListRef.current
    if (!container || messages.length <= 1) return
    if (loading) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
      return
    }
    const items = container.querySelectorAll('.chat-bubble')
    const lastBubble = items[items.length - 1]
    if (lastBubble) {
      const targetTop = Math.max(0, lastBubble.offsetTop - 16)
      container.scrollTo({ top: targetTop, behavior: 'smooth' })
    }
  }, [messages, loading])

  async function handleSaveKey(e) {
    e?.preventDefault()
    if (!keyInput.trim() || savingKey) return
    setSavingKey(true)
    try {
      const st = await postGeminiKey({ api_key: keyInput.trim(), enabled: true })
      setGemini(st)
      setKeyInput('')
      setShowKeyBox(false)
      toast.success(`Gemini connected (${st.model})!`)
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Could not verify Gemini API key.'
      toast.error(detail)
    } finally {
      setSavingKey(false)
    }
  }

  async function handleToggleGemini() {
    try {
      const st = await postGeminiKey({ enabled: !gemini.enabled })
      setGemini(st)
      toast.success(st.enabled ? 'Gemini enhancement enabled' : 'Gemini paused (using deterministic mode)')
    } catch {
      toast.error('Could not update Gemini toggle')
    }
  }

  async function handleClearKey() {
    setSavingKey(true)
    try {
      const st = await postGeminiKey({ api_key: '' })
      setGemini(st)
      setShowKeyBox(false)
      toast.success('Removed Gemini API key')
    } catch {
      toast.error('Could not clear Gemini API key')
    } finally {
      setSavingKey(false)
    }
  }

  async function send(text) {
    const msg = (text ?? input).trim()
    if (!msg || loading) return
    setInput('')
    setMessages(v => [...v, { role: 'user', text: msg }])
    setLoading(true)
    try {
      const reply = await postChat({ message: msg, session_id: sessionId })
      if (reply.session_id) setSessionId(reply.session_id)
      if (reply.context) setContext(reply.context)
      setMessages(v => [...v, { role: 'bot', ...reply }])
    } catch (err) {
      const detail = err?.response?.data?.detail
      const isTimeout = err?.code === 'ECONNABORTED' || String(err?.message || '').toLowerCase().includes('timeout')
      setMessages(v => [...v, {
        role: 'bot',
        text: detail
          ? `⚠️ ${detail}`
          : isTimeout
            ? '⚠️ The request timed out while waiting for Gemini. Please try sending your question again.'
            : '⚠️ Could not reach the server. Make sure the backend API is running on port 8000.',
        understood: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setSessionId(null)
    setContext(null)
    setMessages([WELCOME_MSG])
    toast.success('Started a fresh chat session')
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <main className="page animate-fade">
      <div className="container" style={{ maxWidth: 920 }}>
        <div className="section-head">
          <h1>💬 AI Chat Assistant</h1>
          <p className="text-muted">
            Ask plain-English questions about players, valuations, scouting shortlists, what-if changes, and SHAP explanations.
          </p>
        </div>

        {/* ── Quick prompt chips ───────────────────────────────── */}
        <div className="flex gap-8 wrap mb-20">
          {SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              id={`chat-suggest-${i}`}
              className="btn btn-secondary btn-sm"
              onClick={() => send(s)}
              disabled={loading}
            >
              {s}
            </button>
          ))}
        </div>

        {/* ── Chat window ──────────────────────────────────────── */}
        <div
          className="card"
          style={{ padding: 0, display: 'flex', flexDirection: 'column', height: '68vh', minHeight: 480 }}
          role="log"
          aria-label="Chat conversation"
          aria-live="polite"
        >
          {/* Active session context & reset bar */}
          <div className="chat-header-bar">
            <div className="flex items-center gap-8 wrap" style={{ fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--c-green)', fontSize: '0.65rem' }}>●</span>
              <span className="text-muted">Grounded in 2025-26 EPL model outputs</span>
              {context?.target && (
                <Link
                  to={`/players/${context.target.id}`}
                  className="badge badge-blue"
                  style={{ fontSize: '0.73rem', textDecoration: 'none' }}
                  title="Active player in conversation memory"
                >
                  Target: {context.target.name}
                </Link>
              )}
              {context?.shortlist?.length > 0 && (
                <span className="badge badge-green" style={{ fontSize: '0.73rem' }}>
                  Shortlist: {context.shortlist.length} players
                </span>
              )}
            </div>
            <div className="flex items-center gap-8">
              <button
                id="chat-gemini-btn"
                type="button"
                className={gemini.configured && gemini.enabled ? 'badge badge-green' : 'badge badge-blue'}
                onClick={() => setShowKeyBox(v => !v)}
                style={{ cursor: 'pointer', border: 'none', fontSize: '0.74rem', padding: '4px 10px' }}
                title="Configure or toggle your free Google AI Studio Gemini API key"
              >
                {gemini.configured
                  ? (gemini.enabled ? `✨ Gemini Active (${gemini.masked_key})` : '⏸ Gemini Paused')
                  : '🔑 Connect Free Gemini API'}
              </button>
              <button
                id="chat-reset-btn"
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={handleReset}
                disabled={loading || messages.length <= 1}
                style={{ fontSize: '0.78rem', padding: '4px 10px' }}
              >
                ↺ New chat
              </button>
            </div>
          </div>

          {/* Collapsible Free Gemini API Key Setup Panel */}
          {showKeyBox && (
            <div style={{
              padding: '12px 16px',
              background: 'rgba(59, 130, 246, 0.08)',
              borderBottom: '1px solid var(--c-border)',
              fontSize: '0.82rem',
            }}>
              <div className="flex items-center justify-between wrap gap-8 mb-8">
                <div>
                  <strong style={{ color: '#fff' }}>✨ Google Gemini Free-Tier Integration</strong>{' '}
                  <span className="text-muted">
                    — Powered by <code>{gemini.model}</code> with strict 100% numeric fact-checking.
                  </span>
                </div>
                <a
                  href="https://aistudio.google.com/apikey"
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: 'var(--c-accent)', fontWeight: 600 }}
                >
                  Get a free API key in Google AI Studio (no credit card) ↗
                </a>
              </div>
              <form onSubmit={handleSaveKey} className="flex gap-8 wrap items-center">
                <input
                  type="password"
                  className="input"
                  style={{ flex: '1 1 280px', padding: '7px 12px', fontSize: '0.83rem' }}
                  placeholder={gemini.configured ? `Current key: ${gemini.masked_key} — paste a new key to replace` : 'Paste your free GEMINI_API_KEY (starts with AQ. or AIza...)'}
                  value={keyInput}
                  onChange={e => setKeyInput(e.target.value)}
                  disabled={savingKey}
                />
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={!keyInput.trim() || savingKey}
                >
                  {savingKey ? 'Verifying…' : 'Verify & Save'}
                </button>
                {gemini.configured && (
                  <>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={handleToggleGemini}
                      disabled={savingKey}
                    >
                      {gemini.enabled ? 'Pause Gemini' : 'Resume Gemini'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={handleClearKey}
                      disabled={savingKey}
                    >
                      Remove Key
                    </button>
                  </>
                )}
              </form>
            </div>
          )}

          {/* Messages */}
          <div ref={messagesListRef} className="chat-messages" style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
            {messages.map((m, i) => (
              <ChatMessage key={i} msg={m} onSend={send} disabled={loading} />
            ))}
            {loading && (
              <div className="chat-bubble bot" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Spinner size={18} />
                <span style={{ color: 'var(--c-muted)', fontSize: '0.85rem' }}>Computing grounded answer…</span>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="chat-input-row">
            <input
              id="chat-input"
              type="text"
              placeholder={
                context?.target
                  ? `Ask a follow-up about ${context.target.name}, or ask anything else…`
                  : 'Ask about a player, valuation, scouting alternatives, rankings, or what-if…'
              }
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              disabled={loading}
              aria-label="Chat message input"
            />
            <button
              id="chat-send-btn"
              className="btn btn-primary"
              onClick={() => send()}
              disabled={!input.trim() || loading}
              aria-label="Send message"
            >
              {loading ? '…' : '↑ Send'}
            </button>
          </div>
        </div>

        {/* ── Tips ─────────────────────────────────────────────── */}
        <div className="card mt-24" style={{ padding: 20 }}>
          <h3 className="mb-12" style={{ fontSize: '0.95rem' }}>💡 What you can ask</h3>
          <div className="grid-2" style={{ gap: 12 }}>
            {CHAT_TIPS.map((t, i) => (
              <div key={i} style={{ fontSize: '0.85rem', color: 'var(--c-muted)', lineHeight: 1.6 }}>
                <span style={{ color: 'var(--c-primary)', marginRight: 6 }}>›</span>
                {t}
              </div>
            ))}
          </div>
        </div>

        <Disclaimer />
      </div>
    </main>
  )
}

const CHAT_TIPS = [
  '"Value Bukayo Saka" or "Saka stats" — valuation, confidence band & radar profile',
  '"Explain Bukayo Saka" — full TreeSHAP waterfall breakdown of value drivers',
  '"Scout Bukayo Saka" then "Now under 23" — multi-turn scouting & filtering',
  '"Compare Saka and Palmer" or "Why is Saka valued higher than Palmer?" — head-to-head',
  '"Who are the most undervalued midfielders?" or "Arsenal squad" — league & club tables',
  '"What if Saka scored 20 goals?" or "What if Haaland was 30?" — counterfactual what-ifs',
  '"Explain what xG means" or "What is SHAP?" — football & ML glossary definitions',
  '"How does the model work?" — dataset, feature pipeline & 5-fold CV accuracy table',
]
