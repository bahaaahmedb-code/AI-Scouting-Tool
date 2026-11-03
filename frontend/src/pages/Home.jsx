import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMeta } from '../api'
import { fmtValue } from '../utils'
import { StatPill, Disclaimer } from '../components/UI'

export default function Home() {
  const [meta, setMeta] = useState(null)

  useEffect(() => {
    getMeta().then(setMeta).catch(() => {})
  }, [])

  return (
    <main className="page animate-fade">
      {/* ── Hero ─────────────────────────────────────────────── */}
      <section
        style={{
          background: 'var(--g-hero)',
          borderBottom: '1px solid var(--c-border)',
          padding: '80px 0 60px',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Glow orbs */}
        <div style={{
          position: 'absolute', top: -60, left: '30%',
          width: 500, height: 500, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', bottom: -80, right: '20%',
          width: 400, height: 400, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(6,182,212,0.1) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <div className="container" style={{ position: 'relative', zIndex: 1 }}>
          <div className="flex gap-12 items-center mb-16" style={{ flexWrap: 'wrap' }}>
            <span className="badge badge-blue">BSc Thesis Prototype</span>
            <span className="badge badge-yellow">⚠️ Synthetic data – research only</span>
          </div>

          <h1 style={{ marginBottom: 20, maxWidth: 700 }}>
            AI-Powered{' '}
            <span style={{ background: 'var(--g-cta)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              Player Valuation
            </span>{' '}
            for the Premier League
          </h1>

          <p style={{ color: 'var(--c-muted)', fontSize: '1.15rem', maxWidth: 600, marginBottom: 36, lineHeight: 1.7 }}>
            Estimate market values with machine learning, explain every number with SHAP, scout cheaper alternatives, and ask plain-English questions — all without writing a line of code.
          </p>

          <div className="flex gap-12 wrap">
            <Link to="/players" className="btn btn-primary btn-lg" id="hero-cta-players">
              🔍 Browse Players
            </Link>
            <Link to="/chat" className="btn btn-secondary btn-lg" id="hero-cta-chat">
              💬 Ask a Question
            </Link>
            <Link to="/scout" className="btn btn-secondary btn-lg" id="hero-cta-scout">
              🎯 Scout Alternatives
            </Link>
          </div>

          {/* Stats row */}
          {meta && (
            <div className="flex gap-16 wrap mt-32">
              <StatPill value={meta.counts?.with_age ?? meta.n_players ?? '—'} label="Players" color="var(--c-primary)" />
              <StatPill value={meta.clubs?.length ?? meta.n_clubs ?? '—'} label="Clubs" color="var(--c-accent)" />
              <StatPill value={meta.num_features?.length ?? meta.n_features ?? '—'} label="Features" color="var(--c-green)" />
              <StatPill
                value={meta.error?.cv_mae_eur ? fmtValue(meta.error.cv_mae_eur) : (meta.cv_mae_eur ? fmtValue(meta.cv_mae_eur) : '—')}
                label="CV MAE"
                color="var(--c-yellow)"
              />
              <StatPill
                value={meta.chosen_model ?? meta.model_type ?? '—'}
                label="Model"
                color="var(--c-purple)"
              />
            </div>
          )}
        </div>
      </section>

      {/* ── Feature tiles ─────────────────────────────────────── */}
      <section className="container" style={{ paddingTop: 64 }}>
        <div className="section-head">
          <h2>Everything a scout needs, nothing they don't</h2>
          <p>Six integrated tools designed for football analysts with no technical background.</p>
        </div>

        <div className="grid-3" style={{ gap: 20 }}>
          {FEATURES.map(f => (
            <Link key={f.to} to={f.to} className="card card--gradient card--glow" style={{ display: 'block', transition: 'all 0.25s' }}
              id={`feature-tile-${f.id}`}>
              <div style={{ fontSize: '2rem', marginBottom: 12 }}>{f.icon}</div>
              <h3 style={{ marginBottom: 8 }}>{f.title}</h3>
              <p className="text-muted" style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>{f.desc}</p>
              <div style={{ marginTop: 16, color: 'var(--c-primary)', fontSize: '0.85rem', fontWeight: 600 }}>
                Open →
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ── How it works ──────────────────────────────────────── */}
      <section className="container" style={{ paddingTop: 64 }}>
        <div className="section-head">
          <h2>How it works</h2>
          <p>Three steps from raw stats to actionable insight.</p>
        </div>
        <div className="grid-3">
          {STEPS.map((s, i) => (
            <div key={i} className="card" style={{ borderTop: `3px solid ${s.color}` }}>
              <div style={{
                width: 40, height: 40, borderRadius: '50%',
                background: s.color + '22', color: s.color,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 800, fontSize: '1.1rem', marginBottom: 16,
              }}>{i + 1}</div>
              <h3 style={{ marginBottom: 8 }}>{s.title}</h3>
              <p className="text-muted" style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Disclaimer ─────────────────────────────────────────── */}
      <section className="container" style={{ paddingTop: 40, paddingBottom: 40 }}>
        <Disclaimer />
      </section>
    </main>
  )
}

const FEATURES = [
  { id: 'players',  to: '/players',  icon: '🔍', title: 'Player Profiles',   desc: 'Search 400+ EPL outfield players. See stats, estimated value, position, age, and club at a glance.' },
  { id: 'explain',  to: '/explain',  icon: '🧠', title: 'SHAP Explanations', desc: 'Understand why the model assigned a value. Waterfall charts break down each feature\'s contribution in plain language.' },
  { id: 'scout',    to: '/scout',    icon: '🎯', title: 'Scouting Tool',     desc: 'Pick a target player and find similar, cheaper alternatives. Filter by position, age, and budget.' },
  { id: 'compare',  to: '/compare',  icon: '⚖️', title: 'Side-by-Side',      desc: 'Compare up to 4 players across stats, estimated values, and a radar chart of key attributes.' },
  { id: 'rankings', to: '/rankings', icon: '🏆', title: 'Rankings',          desc: 'League tables by estimated value, goals, assists, xG, minutes, and more. Filter by club or position.' },
  { id: 'chat',     to: '/chat',     icon: '💬', title: 'AI Chat',           desc: 'Ask plain-English questions: "Who are the most undervalued midfielders?" — get structured answers instantly.' },
]

const STEPS = [
  { title: 'Data ingestion & cleaning', color: 'var(--c-primary)',
    desc: 'FBref season stats and Transfermarkt values are loaded, cleaned, and merged by name-matching.' },
  { title: 'Feature engineering & modelling', color: 'var(--c-accent)',
    desc: 'An XGBoost regressor is trained via 5-fold cross-validation and SHAP values are computed for every player.' },
  { title: 'Scouting & explanations', color: 'var(--c-green)',
    desc: 'A cosine-similarity matrix finds comparable players; the chat engine answers questions from pre-computed facts.' },
]
