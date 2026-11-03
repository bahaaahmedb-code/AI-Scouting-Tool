import {
  RadarChart as ReRadar,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6']

/**
 * Multi-player radar chart.
 * Props: { data } where data = { axes: string[], players: [{name, values: number[]}] }
 */
export default function RadarChart({ data }) {
  if (!data || !data.axes) return null

  const { axes, players } = data

  // Recharts expects [{axis, p0, p1, ...}]
  const chartData = axes.map((axis, i) => {
    const row = { axis }
    players.forEach((p, pi) => {
      const vals = p.values ?? p.percentiles ?? []
      row[`p${pi}`] = vals[i] ?? 0
    })
    return row
  })

  return (
    <div className="radar-wrap" style={{ width: '100%', height: 380 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ReRadar data={chartData} cx="50%" cy="50%" outerRadius="63%">
          <PolarGrid stroke="var(--c-border2)" />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fill: 'var(--c-muted)', fontSize: 11, fontFamily: 'Inter' }}
          />
          {players.map((p, i) => (
            <Radar
              key={i}
              name={p.name}
              dataKey={`p${i}`}
              stroke={COLORS[i]}
              fill={COLORS[i]}
              fillOpacity={0.15}
              strokeWidth={2}
            />
          ))}
          <Legend
            formatter={(v) => <span style={{ color: 'var(--c-text)', fontSize: '0.85rem' }}>{v}</span>}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--c-card2)',
              border: '1px solid var(--c-border2)',
              borderRadius: 8,
              color: 'var(--c-text)',
              fontSize: '0.85rem',
            }}
            formatter={(val, name) => [val != null ? `${Math.round(val)}%` : '—', name]}
          />
        </ReRadar>
      </ResponsiveContainer>
    </div>
  )
}
