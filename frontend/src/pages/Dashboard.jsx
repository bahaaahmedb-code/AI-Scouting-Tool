import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell, ReferenceLine,
  ScatterChart, Scatter, CartesianGrid, Legend,
} from 'recharts'
import {
  getMeta, getPlayers, getGlobalImportance, getDependence, getShap, getRadar,
} from '../api'
import { fmtNum, fmtValue } from '../utils'
import RadarChart from '../components/RadarChart'
import WaterfallChart from '../components/WaterfallChart'
import { PageLoading, ErrorBox, Disclaimer, DataCaveat } from '../components/UI'

const POS = [
  { value: '', label: 'All' },
  { value: 'D', label: 'Defenders' },
  { value: 'M', label: 'Midfielders' },
  { value: 'F', label: 'Attackers' },
]
const POS_COLOR = { D: '#60a5fa', M: '#5eead4', F: '#fb923c' }
const RADAR_COLORS = ['#c8f542', '#5eead4']

function fmtPercentile(n) {
  if (n == null) return '—'
  return `${Math.round(n)}%`
}

function fmtRawStat(axis, v) {
  if (v == null) return '—'
  if (axis.toLowerCase().includes('accuracy')) return `${fmtNum(v, 1)}%`
  if (axis.includes('/90')) return `${fmtNum(v, 2)} /90`
  return fmtNum(v, 2)
}
const POS_NAME = { D: 'Defenders', M: 'Midfielders', F: 'Attackers' }
const TIP = {
  background: 'var(--c-card2)', border: '1px solid var(--c-border2)', borderRadius: 8, fontSize: '0.82rem',
}
const AXIS = { fill: 'var(--c-muted)', fontSize: 11 }

function Chips({ options, value, onChange, idPrefix }) {
  return (
    <div className="flex gap-8 wrap">
      {options.map(o => (
        <button
          key={o.value}
          id={`${idPrefix}-${o.value || 'all'}`}
          className={`btn ${value === o.value ? 'btn-primary' : 'btn-secondary'} btn-sm`}
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function Panel({ title, sub, controls, children, style }) {
  return (
    <div className="card" style={style}>
      <div className="flex gap-12 wrap" style={{ justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <h3 className="mb-4">{title}</h3>
          {sub && <p className="text-muted" style={{ fontSize: '0.85rem' }}>{sub}</p>}
        </div>
        {controls}
      </div>
      {children}
    </div>
  )
}

function Kpi({ label, value, hint }) {
  return (
    <div className="card" style={{ flex: '1 1 150px', textAlign: 'center', padding: 16 }}>
      <div className="label">{label}</div>
      <div style={{ fontWeight: 800, fontSize: '1.5rem', color: 'var(--c-accent)' }}>{value}</div>
      {hint && <div className="text-subtle" style={{ fontSize: '0.75rem' }}>{hint}</div>}
    </div>
  )
}

const MODEL_METRICS = [
  { value: 'cv_r2_mean', label: 'R² (higher is better)' },
  { value: 'cv_rmse_log', label: 'RMSE, log (lower is better)' },
  { value: 'cv_mae_log', label: 'MAE, log (lower is better)' },
  { value: 'cv_median_abs_pct', label: 'Median abs. % error' },
]

export default function Dashboard() {
  const [meta, setMeta] = useState(null)
  const [players, setPlayers] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  // model comparison
  const [modelMetric, setModelMetric] = useState('cv_r2_mean')

  // listed vs estimated
  const [scatterPos, setScatterPos] = useState('')
  const [minAge, setMinAge] = useState(16)
  const [maxAge, setMaxAge] = useState(40)

  // importance
  const [impPos, setImpPos] = useState('')
  const [impView, setImpView] = useState('features')
  const [topN, setTopN] = useState(12)
  const [importance, setImportance] = useState(null)
  const [feature, setFeature] = useState(null)
  const [dep, setDep] = useState(null)
  const [depLoading, setDepLoading] = useState(false)

  // player drill-down
  const [selected, setSelected] = useState(null)
  const [drillPos, setDrillPos] = useState('')
  const [waterfall, setWaterfall] = useState(null)
  // radar panel (independent of the waterfall)
  const [radPos, setRadPos] = useState('')
  const [radA, setRadA] = useState(null)
  const [radB, setRadB] = useState('')
  const [radar, setRadar] = useState(null)

  useEffect(() => {
    Promise.all([getMeta(), getPlayers({ limit: 500 })])
      .then(([m, p]) => {
        setMeta(m)
        setPlayers(p)
        if (p.length) { setSelected(p[0].id); setRadA(p[0].id) }
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  useEffect(() => {
    getGlobalImportance(impPos || undefined).then(d => {
      setImportance(d)
      setFeature(prev => prev ?? d.merged?.find(m => m.feature !== 'position' && m.feature !== 'nation_group')?.feature ?? null)
    }).catch(() => {})
  }, [impPos])

  useEffect(() => {
    if (!feature) return
    setDepLoading(true)
    getDependence(feature).then(d => { setDep(d); setDepLoading(false) }).catch(() => setDepLoading(false))
  }, [feature])

  useEffect(() => {
    if (selected == null) return
    getShap(selected).then(setWaterfall).catch(() => setWaterfall(null))
  }, [selected])

  useEffect(() => {
    if (radA == null) return
    const ids = radB ? [radA, Number(radB)] : [radA]
    getRadar(ids).then(r => setRadar({
      axes: r.axes,
      players: r.players.map(p => ({ name: p.name, values: p.percentiles, raw: p.raw })),
    })).catch(() => setRadar(null))
  }, [radA, radB])

  const byId = useMemo(() => Object.fromEntries(players.map(p => [p.id, p])), [players])
  const sel = byId[selected]
  const drillPlayers = useMemo(
    () => players.filter(p => !drillPos || p.position === drillPos), [players, drillPos])
  const radarPlayers = useMemo(
    () => players.filter(p => !radPos || p.position === radPos), [players, radPos])

  // clicking a dot in any chart above points both drill-down panels at that player
  function pickPlayer(id) { setSelected(id); setRadA(id) }

  function changeDrillPos(v) {
    setDrillPos(v)
    const list = players.filter(p => !v || p.position === v)
    if (list.length && !list.some(p => p.id === selected)) setSelected(list[0].id)
  }

  function changeRadPos(v) {
    setRadPos(v)
    const list = players.filter(p => !v || p.position === v)
    if (list.length && !list.some(p => p.id === radA)) setRadA(list[0].id)
    if (radB && !list.some(p => p.id === Number(radB))) setRadB('')
  }

  const scatterData = useMemo(() => players
    .filter(p => p.listed_value_eur && p.estimated_value_eur && p.age >= minAge && p.age <= maxAge)
    .filter(p => !scatterPos || p.position === scatterPos)
    .map(p => ({ ...p, listed: p.listed_value_eur / 1e6, est: p.estimated_value_eur / 1e6 })),
  [players, scatterPos, minAge, maxAge])

  const importanceRows = useMemo(() => {
    if (!importance) return []
    if (impView === 'groups') {
      return importance.groups.map(g => {
        const topInGroup = importance.merged?.find(m => m.group === g.group)
        return { label: g.group, mean_abs: g.mean_abs, pct: g.pct, topFeature: topInGroup?.feature }
      })
    }
    return importance.merged
      .filter(m => !impPos || m.feature !== 'position')
      .slice(0, topN)
  }, [importance, impView, topN, impPos])

  const modelRows = useMemo(() => (meta?.cv_results ?? [])
    .map(r => ({ ...r, v: r[modelMetric] })), [meta, modelMetric])

  if (loading) return <main className="page"><div className="container"><PageLoading /></div></main>
  if (error) return <main className="page"><div className="container"><ErrorBox message={error} /></div></main>

  const err = meta.error ?? {}
  const scatterPlayersByPos = ['D', 'M', 'F'].map(k => ({
    k, rows: scatterData.filter(p => p.position === k),
  })).filter(g => g.rows.length)

  return (
    <main className="page animate-fade">
      <div className="container">
        <div className="section-head">
          <h1>📊 Dashboard</h1>
          <p className="text-muted">
            Interactive version of the notebook visuals: model quality, listed vs estimated value, SHAP drivers,
            and per-player breakdowns. Click, filter and hover on any chart.
          </p>
        </div>

        {/* KPIs */}
        <div className="flex gap-16 wrap mb-24">
          <Kpi label="Players" value={meta.n_players} hint={`min ${meta.min_minutes} minutes`} />
          <Kpi label="Chosen model" value={meta.chosen_model} hint={`best by CV: ${meta.best_by_cv}`} />
          <Kpi label="CV R²" value={fmtNum(err.cv_r2, 2)} hint="log scale" />
          <Kpi label="CV MAE" value={fmtValue(err.cv_mae_eur)} hint="typical error" />
          <Kpi label="Median error" value={`${fmtNum(err.cv_median_abs_pct, 0)}%`} hint="abs. % of value" />
        </div>

        <div className="grid-2" style={{ gap: 24, alignItems: 'start' }}>
          {/* Model comparison */}
          <Panel
            title="Model comparison"
            sub="Cross-validated performance of each candidate model."
            controls={
              <select className="input select" style={{ width: 230 }} value={modelMetric}
                onChange={e => setModelMetric(e.target.value)} aria-label="Model metric">
                {MODEL_METRICS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            }
          >
            <div style={{ height: 300 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={modelRows} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border)" />
                  <XAxis dataKey="model" tick={AXIS} />
                  <YAxis tick={AXIS} />
                  <Tooltip contentStyle={TIP} formatter={v => [fmtNum(v, 3), 'Value']} />
                  <Bar dataKey="v" radius={[4, 4, 0, 0]}>
                    {modelRows.map(r => (
                      <Cell key={r.model} fill={r.model === meta.chosen_model ? '#f59e0b' : '#3b82f6'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-subtle" style={{ fontSize: '0.78rem' }}>Highlighted bar = model used by the app.</p>
          </Panel>

          {/* Listed vs estimated */}
          <Panel
            title="Listed vs model-estimated value"
            sub="Dots above the dashed line are valued higher by the model than listed. Click a dot to inspect that player below."
            controls={<Chips options={POS} value={scatterPos} onChange={setScatterPos} idPrefix="dash-scatter-pos" />}
          >
            <div className="flex gap-12 wrap mb-8" style={{ alignItems: 'center', fontSize: '0.82rem' }}>
              <span className="text-muted">Age {minAge}–{maxAge}</span>
              <input type="range" min={16} max={40} value={minAge} aria-label="Minimum age"
                onChange={e => setMinAge(Math.min(Number(e.target.value), maxAge))} />
              <input type="range" min={16} max={40} value={maxAge} aria-label="Maximum age"
                onChange={e => setMaxAge(Math.max(Number(e.target.value), minAge))} />
              <span className="text-subtle">{scatterData.length} players</span>
            </div>
            <div style={{ height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border)" />
                  <XAxis dataKey="listed" type="number" scale="log" domain={[0.5, 200]} allowDataOverflow
                    height={44} tick={AXIS} ticks={[0.5, 1, 2, 5, 10, 20, 50, 100, 200]}
                    label={{ value: 'Listed value (£M)', position: 'insideBottom', offset: 8, fill: 'var(--c-muted)', fontSize: 11 }} />
                  <YAxis dataKey="est" type="number" scale="log" domain={[0.5, 200]} allowDataOverflow
                    tick={AXIS} ticks={[0.5, 1, 2, 5, 10, 20, 50, 100, 200]}
                    label={{ value: 'Estimated (£M)', angle: -90, position: 'insideLeft', fill: 'var(--c-muted)', fontSize: 11 }} />
                  <ReferenceLine segment={[{ x: 0.5, y: 0.5 }, { x: 200, y: 200 }]} stroke="gray" strokeDasharray="5 5" />
                  <Tooltip
                    contentStyle={TIP}
                    content={({ payload }) => {
                      const p = payload?.[0]?.payload
                      if (!p) return null
                      return (
                        <div style={{ ...TIP, padding: 10 }}>
                          <strong>{p.name}</strong>
                          <div className="text-muted">{p.club} · {POS_NAME[p.position]} · {p.age}y</div>
                          <div>Listed £{fmtNum(p.listed)}m</div>
                          <div>Estimated £{fmtNum(p.est)}m</div>
                        </div>
                      )
                    }}
                  />
                  <Legend verticalAlign="bottom" height={24} iconSize={8}
                    wrapperStyle={{ bottom: 0, fontSize: '0.74rem', paddingTop: 6 }} />
                  {scatterPlayersByPos.map(g => (
                    <Scatter key={g.k} name={POS_NAME[g.k]} data={g.rows} fill={POS_COLOR[g.k]}
                      fillOpacity={0.7} cursor="pointer" onClick={d => pickPlayer(d.id)} />
                  ))}
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </div>

        {/* SHAP importance + dependence */}
        <Panel
          style={{ marginTop: 24 }}
          title="What drives valuations (SHAP)"
          sub="Mean absolute SHAP impact. Click a bar to see how that stat moves value across all players."
          controls={<Chips options={POS} value={impPos} onChange={setImpPos} idPrefix="dash-imp-pos" />}
        >
          <div className="flex gap-16 wrap mb-12" style={{ alignItems: 'center' }}>
            <Chips
              idPrefix="dash-imp-view" value={impView} onChange={setImpView}
              options={[{ value: 'features', label: 'By feature' }, { value: 'groups', label: 'By group' }]}
            />
            {impView === 'features' && (
              <label className="flex gap-8" style={{ alignItems: 'center', fontSize: '0.85rem' }}>
                <span className="text-muted">Top {topN}</span>
                <input type="range" min={5} max={30} value={topN} onChange={e => setTopN(Number(e.target.value))} />
              </label>
            )}
          </div>
          {!importance ? <PageLoading /> : (
            <div className="grid-2" style={{ gap: 24, alignItems: 'start' }}>
              <div style={{ height: Math.max(300, importanceRows.length * 26 + 40) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={importanceRows} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                    <XAxis type="number" tick={AXIS} tickFormatter={v => v.toFixed(2)} />
                    <YAxis type="category" dataKey="label" width={170} tick={{ fill: 'var(--c-text)', fontSize: 11 }} interval={0} />
                    <Tooltip contentStyle={TIP} cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                      formatter={(v, n, p) => [`${v.toFixed(3)} log pts (≈ ±${fmtNum(p.payload.pct, 0)}% value)`, 'Mean |SHAP|']} />
                    <Bar dataKey="mean_abs" radius={[0, 4, 4, 0]} cursor="pointer"
                      onClick={d => {
                        const next = d.feature ?? d.topFeature
                        if (next) setFeature(next)
                      }}>
                      {importanceRows.map((r, i) => {
                        const active = r.feature ? r.feature === feature : (r.topFeature && r.topFeature === feature)
                        return (
                          <Cell key={i} fill={active ? '#f59e0b' : (POS_COLOR[impPos] ?? '#3b82f6')}
                            opacity={active ? 1 : 0.8} />
                        )
                      })}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div>
                {!feature && (
                  <div className="empty-state" style={{ padding: 40 }}>
                    <div className="empty-state-icon">👆</div>
                    <p>Click a feature bar to see its dependence plot.</p>
                  </div>
                )}
                {feature && depLoading && <PageLoading />}
                {feature && !depLoading && dep && (() => {
                  const posKeys = impPos ? [impPos] : ['D', 'M', 'F']
                  const posList = (importance.merged ?? []).filter(m => !impPos || m.feature !== 'position')
                  const posRankIdx = posList.findIndex(m => m.feature === dep.feature)
                  const visibleCount = impPos ? dep.points.filter(p => p.position === impPos).length : dep.points.length
                  return (
                    <div className="animate-fade">
                      <h4 className="mb-4">
                        {dep.label}
                        {impPos && <span className="text-muted" style={{ fontWeight: 500, fontSize: '0.85rem' }}> · {POS_NAME[impPos]}</span>}
                      </h4>
                      <p className="text-muted mb-8" style={{ fontSize: '0.82rem' }}>
                        {dep.categorical
                          ? 'Average SHAP effect on estimated value by category.'
                          : `Each dot is a player (${visibleCount} shown). Above zero = this stat raises the estimate.`}
                        {posRankIdx >= 0 && ` Ranked #${posRankIdx + 1} of ${posList.length} features${impPos ? ` for ${POS_NAME[impPos].toLowerCase()}` : ''}.`}
                      </p>
                      {dep.categorical ? (
                        <div style={{ height: 300 }}>
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={dep.categories} layout="vertical" margin={{ left: 8, right: 24, top: 8, bottom: 8 }}>
                              <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border)" />
                              <XAxis type="number" tick={AXIS} tickFormatter={v => `${v >= 0 ? '+' : ''}${fmtNum(v, 0)}%`} />
                              <YAxis type="category" dataKey="category" width={110} tick={{ fill: 'var(--c-text)', fontSize: 11 }} />
                              <ReferenceLine x={0} stroke="gray" strokeDasharray="4 4" />
                              <Tooltip contentStyle={TIP} formatter={v => [`${v >= 0 ? '+' : ''}${fmtNum(v, 1)}%`, 'Avg effect on value']} />
                              <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
                                {(dep.categories ?? []).map((c, i) => (
                                  <Cell key={i} fill={c.pct >= 0 ? '#10b981' : '#ef4444'} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      ) : (
                        <div style={{ height: 325 }}>
                          <ResponsiveContainer width="100%" height="100%">
                            <ScatterChart margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
                              <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border)" />
                              <XAxis dataKey="x" type="number" height={44} tick={AXIS} domain={['auto', 'auto']}
                                label={{ value: dep.label, position: 'insideBottom', offset: 8, fill: 'var(--c-muted)', fontSize: 11 }} />
                              <YAxis dataKey="shap" type="number" tick={AXIS} tickFormatter={v => v.toFixed(2)} />
                              <ReferenceLine y={0} stroke="gray" strokeDasharray="4 4" />
                              <Tooltip contentStyle={TIP} content={({ payload }) => {
                                const p = payload?.[0]?.payload
                                if (!p) return null
                                return (
                                  <div style={{ ...TIP, padding: 10 }}>
                                    <strong>{p.name}</strong>
                                    <div className="text-muted">{POS_NAME[p.position]}</div>
                                    <div>{dep.label}: {fmtNum(p.x, 2)}</div>
                                    <div>Effect: {p.pct >= 0 ? '+' : ''}{fmtNum(p.pct, 1)}% on value</div>
                                  </div>
                                )
                              }} />
                              <Legend verticalAlign="bottom" height={24} iconSize={8}
                                wrapperStyle={{ bottom: 0, fontSize: '0.74rem', paddingTop: 6 }} />
                              {posKeys.map(k => (
                                <Scatter key={k} name={POS_NAME[k]} fill={POS_COLOR[k]} fillOpacity={0.7}
                                  data={dep.points.filter(p => p.position === k)} cursor="pointer"
                                  onClick={d => pickPlayer(d.id)} />
                              ))}
                            </ScatterChart>
                          </ResponsiveContainer>
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>
            </div>
          )}
        </Panel>

        {/* Player drill-down */}
        <Panel
          style={{ marginTop: 24 }}
          title="Value breakdown (SHAP waterfall)"
          sub="Pick a player (or click one in any chart above). The amounts add up exactly from the base to the model estimate."
          controls={
            <div className="flex gap-8 wrap" style={{ alignItems: 'center' }}>
              <Chips options={POS} value={drillPos} onChange={changeDrillPos} idPrefix="dash-drill-pos" />
              <select className="input select" style={{ width: 220 }} value={selected ?? ''}
                onChange={e => setSelected(Number(e.target.value))} aria-label="Player">
                {!drillPlayers.some(p => p.id === selected) && sel &&
                  <option value={sel.id}>{sel.name} ({sel.club})</option>}
                {drillPlayers.map(p => <option key={p.id} value={p.id}>{p.name} ({p.club})</option>)}
              </select>
            </div>
          }
        >
          {sel && (
            <p className="mb-12">
              <Link to={`/players/${sel.id}`} style={{ color: 'var(--c-primary)', fontWeight: 700 }}>{sel.name}</Link>
              <span className="text-muted"> · {sel.club} · {POS_NAME[sel.position]} · {sel.age}y · </span>
              {sel.goals ?? '—'} goals, {sel.assists ?? '—'} assists · estimated{' '}
              <strong style={{ color: 'var(--c-accent)' }}>{fmtValue(sel.estimated_value_eur)}</strong>
            </p>
          )}
          <div style={{ maxWidth: 640 }}><WaterfallChart data={waterfall} /></div>
        </Panel>

        {/* Radar: independent of the waterfall, with the numbers shown beside it */}
        <Panel
          style={{ marginTop: 24 }}
          title="Player radar (percentile within position)"
          sub="Pick up to two players to compare. 100% = best in their position. Exact percentile percentages and match stats are listed beside the chart."
          controls={
            <div className="flex gap-8 wrap" style={{ alignItems: 'center' }}>
              <Chips options={POS} value={radPos} onChange={changeRadPos} idPrefix="dash-radar-pos" />
              <select className="input select" style={{ width: 220 }} value={radA ?? ''}
                onChange={e => setRadA(Number(e.target.value))} aria-label="Radar player">
                {!radarPlayers.some(p => p.id === radA) && byId[radA] &&
                  <option value={radA}>{byId[radA].name} ({byId[radA].club})</option>}
                {radarPlayers.map(p => <option key={p.id} value={p.id}>{p.name} ({p.club})</option>)}
              </select>
              <select className="input select" style={{ width: 220 }} value={radB}
                onChange={e => setRadB(e.target.value)} aria-label="Radar compare with">
                <option value="">Compare with…</option>
                {radarPlayers.filter(p => p.id !== radA).map(p =>
                  <option key={p.id} value={p.id}>{p.name} ({p.club})</option>)}
              </select>
            </div>
          }
        >
          <div className="grid-2" style={{ gap: 24, alignItems: 'center' }}>
            <div><RadarChart data={radar} /></div>
            <div>
              {radar && (
                <div className="table-wrap">
                  <table aria-label="Radar values">
                    <thead>
                      <tr>
                        <th rowSpan={2} style={{ verticalAlign: 'bottom' }}>Metric</th>
                        {radar.players.map((p, i) => (
                          <th key={i} colSpan={2} style={{ color: RADAR_COLORS[i], borderLeft: '1px solid var(--c-border)', paddingBottom: 6 }}>
                            {p.name}
                          </th>
                        ))}
                      </tr>
                      <tr>
                        {radar.players.flatMap((_, i) => [
                          <th key={`${i}-pct`} style={{ borderLeft: '1px solid var(--c-border)', paddingTop: 4, paddingBottom: 8, fontSize: '0.7rem' }}>
                            Percentile (%)
                          </th>,
                          <th key={`${i}-raw`} style={{ paddingTop: 4, paddingBottom: 8, fontSize: '0.7rem' }}>
                            Actual Stat
                          </th>,
                        ])}
                      </tr>
                    </thead>
                    <tbody>
                      {radar.axes.map((axis, ai) => (
                        <tr key={axis}>
                          <td>{axis}</td>
                          {radar.players.flatMap((p, i) => [
                            <td key={`${i}-pct`} style={{ borderLeft: '1px solid var(--c-border)', fontWeight: 700 }}>
                              {fmtPercentile(p.values[ai])}
                            </td>,
                            <td key={`${i}-raw`} className="text-muted">
                              {fmtRawStat(axis, p.raw?.[ai])}
                            </td>,
                          ])}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="alert alert-info mt-12" style={{ fontSize: '0.81rem', padding: '10px 14px', lineHeight: 1.5 }}>
                <strong>💡 What is a Percentile?</strong> A percentile shows the <strong>percentage of Premier League peers in the same position</strong> that a player outperforms. For example, <strong>94%</strong> means the player performs better than <strong>94%</strong> of players in their position (<strong>100%</strong> = top in position, <strong>50%</strong> = position average), while <strong>Actual Stat</strong> shows their real on-pitch match output.
              </div>
            </div>
          </div>
        </Panel>

        <DataCaveat />
        <Disclaimer />
      </div>
    </main>
  )
}

