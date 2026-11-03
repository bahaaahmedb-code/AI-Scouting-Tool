import { Link } from 'react-router-dom'

export default function About() {
  return (
    <main className="page animate-fade">
      <div className="container" style={{ maxWidth: 860 }}>
        {/* Header */}
        <div className="section-head">
          <h1>ℹ️ About This Tool</h1>
          <p className="text-muted">
            A BSc thesis artefact exploring AI-driven football player valuation in the English Premier League.
          </p>
        </div>

        {/* Caveats box */}
        <div className="alert alert-warn mb-32">
          <strong>⚠️ Research prototype with synthetic data.</strong> The market-value target used for training was
          synthetically constructed from performance features plus noise. All estimated values are illustrative — they
          demonstrate that the pipeline works, not how accurate it is on real Transfermarkt prices. No commercial or
          recruitment decisions should be based on these outputs.
        </div>

        {/* What it does */}
        <div className="card mb-24">
          <h2 className="mb-16">🎯 What does this tool do?</h2>
          <p style={{ lineHeight: 1.8, color: 'var(--c-muted)' }}>
            Moneyball EPL is a prototype scouting-and-valuation tool for non-technical football analysts. It:
          </p>
          <ul style={{ marginTop: 16, paddingLeft: 24, color: 'var(--c-muted)', lineHeight: 2 }}>
            <li>Estimates the market value of EPL outfield players using an <strong style={{ color: 'var(--c-text)' }}>XGBoost regression model</strong></li>
            <li>Explains every estimate using <strong style={{ color: 'var(--c-text)' }}>SHAP (SHapley Additive exPlanations)</strong> waterfall charts</li>
            <li>Finds <strong style={{ color: 'var(--c-text)' }}>cheaper, stylistically similar</strong> players using cosine similarity on standardised feature vectors</li>
            <li>Ranks players by any statistic with optional position, age, and minutes filters</li>
            <li>Answers plain-English questions via a <strong style={{ color: 'var(--c-text)' }}>rule-based NLU chatbot</strong> backed by pre-computed facts</li>
          </ul>
        </div>

        {/* Data & Model */}
        <div className="card mb-24">
          <h2 className="mb-16">📊 Data & Model</h2>
          <div className="grid-2" style={{ gap: 20 }}>
            <div>
              <div className="label mb-8">Data sources</div>
              <ul style={{ paddingLeft: 20, color: 'var(--c-muted)', lineHeight: 1.9, fontSize: '0.9rem' }}>
                <li><strong style={{ color: 'var(--c-text)' }}>FBref</strong> — Season stats (goals, xG, passes, tackles…)</li>
                <li><strong style={{ color: 'var(--c-text)' }}>Transfermarkt</strong> — Market values (real deployment)</li>
                <li><strong style={{ color: 'var(--c-text)' }}>Kaggle EPL dataset</strong> — Supplementary player info</li>
              </ul>
            </div>
            <div>
              <div className="label mb-8">Model pipeline</div>
              <ul style={{ paddingLeft: 20, color: 'var(--c-muted)', lineHeight: 1.9, fontSize: '0.9rem' }}>
                <li>3-step fuzzy name-matching to merge sources</li>
                <li>~40 engineered features (per-90, ratios, flags)</li>
                <li>XGBoost with 5-fold cross-validation (configurable)</li>
                <li>SHAP TreeExplainer for local + global explanations</li>
                <li>Cosine-similarity matrix on z-scored feature vectors</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Limitations */}
        <div className="card mb-24">
          <h2 className="mb-16">⚠️ Known limitations</h2>
          <div className="grid-2" style={{ gap: 16 }}>
            {LIMITATIONS.map((l, i) => (
              <div key={i} style={{ background: 'var(--c-surface)', borderRadius: 8, padding: 16, borderLeft: '3px solid var(--c-yellow)' }}>
                <div style={{ fontWeight: 600, marginBottom: 6, fontSize: '0.9rem' }}>{l.title}</div>
                <p style={{ color: 'var(--c-muted)', fontSize: '0.85rem', lineHeight: 1.6 }}>{l.text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* For evaluators */}
        <div className="card mb-24" style={{ borderColor: 'rgba(139,92,246,0.4)', boxShadow: '0 0 20px rgba(139,92,246,0.08)' }}>
          <h2 className="mb-12">🎓 For evaluators</h2>
          <p style={{ color: 'var(--c-muted)', marginBottom: 16, fontSize: '0.9rem' }}>
            This tool was built as a BSc thesis prototype. If you are a study participant or evaluator, you can record
            ratings and task timings using the access-code-protected Evaluation Console.
          </p>
          <Link to="/eval" className="btn btn-secondary" id="about-eval-link">
            🔬 Open Evaluation Console
          </Link>
        </div>

        {/* Navigation shortcuts */}
        <div className="grid-3" style={{ gap: 16 }}>
          {[
            { to: '/players',  icon: '🔍', label: 'Browse Players' },
            { to: '/scout',    icon: '🎯', label: 'Scout Tool' },
            { to: '/compare',  icon: '⚖️', label: 'Compare Players' },
            { to: '/rankings', icon: '🏆', label: 'Rankings' },
            { to: '/explain',  icon: '🧠', label: 'SHAP Explanations' },
            { to: '/chat',     icon: '💬', label: 'AI Chat' },
          ].map(l => (
            <Link key={l.to} to={l.to} className="card card--gradient card--glow" style={{ display: 'block', textAlign: 'center', padding: '20px 16px' }}>
              <div style={{ fontSize: '1.8rem', marginBottom: 8 }}>{l.icon}</div>
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{l.label}</div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  )
}

const LIMITATIONS = [
  {
    title: 'Synthetic target variable',
    text: 'The training target is computed from features + Gaussian noise. It proves the pipeline works but does not reflect true Transfermarkt valuations.',
  },
  {
    title: 'Single season snapshot',
    text: 'Data covers one EPL season only. Longitudinal trends, injury history, and contract length are not included.',
  },
  {
    title: 'EPL outfield players only',
    text: 'Goalkeepers are excluded. The model is not calibrated for lower-league or international players.',
  },
  {
    title: 'Cosine similarity ≠ football suitability',
    text: 'Similar feature vectors don\'t guarantee positional or tactical fit. A scout\'s contextual judgment is still essential.',
  },
  {
    title: 'Rule-based NLU',
    text: 'The chatbot uses regex pattern matching, not a large language model. Complex multi-hop questions may not be understood.',
  },
  {
    title: 'Sample data for demo',
    text: 'The live demo runs on synthetically generated data matching the real column schemas. Real data requires the actual CSV/Excel files.',
  },
]
