import { Link } from 'react-router-dom'
import {
  IconInfo, IconTarget, IconChart, IconAlert, IconFlask,
  IconSearch, IconScale, IconTrophy, IconBrain, IconChat,
} from '../components/Icons'

export default function About() {
  return (
    <main className="page animate-fade">
      <div className="container" style={{ maxWidth: 860 }}>
        {/* Header */}
        <div className="section-head">
          <h1 className="flex items-center gap-12"><IconInfo size={28} style={{ color: 'var(--c-primary)' }} /> About This Tool</h1>
          <p className="text-muted">
            A BSc thesis artefact exploring AI-driven football player valuation, multi-season aging curves, and explainable scouting in the English Premier League.
          </p>
        </div>

        {/* What it does */}
        <div className="card mb-24">
          <h2 className="mb-16 flex items-center gap-10"><IconTarget size={22} style={{ color: 'var(--c-primary)' }} /> What does this tool do?</h2>
          <p style={{ lineHeight: 1.8, color: 'var(--c-muted)' }}>
            Moneyball EPL is a full-stack scouting, valuation, and contract-advisory system for football analysts. It:
          </p>
          <ul style={{ marginTop: 16, paddingLeft: 24, color: 'var(--c-muted)', lineHeight: 2 }}>
            <li>Estimates the market value of EPL outfield players and goalkeepers using dedicated <strong style={{ color: 'var(--c-text)' }}>XGBoost regression models</strong> (Outfield Test R² = 86.8%, Goalkeeper CV R² = 69.4%)</li>
            <li>Explains every estimate using <strong style={{ color: 'var(--c-text)' }}>SHAP (SHapley Additive exPlanations)</strong> waterfall charts</li>
            <li>Projects <strong style={{ color: 'var(--c-text)' }}>3-year aging trajectories &amp; optimal contract lengths (1–5 years)</strong> from an 8-season Big-5 archive</li>
            <li>Finds <strong style={{ color: 'var(--c-text)' }}>cheaper, stylistically similar</strong> players using cosine similarity on standardised feature vectors</li>
            <li>Answers plain-English questions via a <strong style={{ color: 'var(--c-text)' }}>grounded AI assistant</strong> backed by pre-computed facts</li>
          </ul>
        </div>

        {/* Data & Model */}
        <div className="card mb-24">
          <h2 className="mb-16 flex items-center gap-10"><IconChart size={22} style={{ color: 'var(--c-primary)' }} /> Data &amp; Model</h2>
          <div className="grid-2" style={{ gap: 20 }}>
            <div>
              <div className="label mb-8">Data sources</div>
              <ul style={{ paddingLeft: 20, color: 'var(--c-muted)', lineHeight: 1.9, fontSize: '0.9rem' }}>
                <li><strong style={{ color: 'var(--c-text)' }}>FBref / Opta (2017–2026)</strong> — Multi-season outfield &amp; keeper metrics</li>
                <li><strong style={{ color: 'var(--c-text)' }}>Transfermarkt (2025–26)</strong> — Official market values (N = 299)</li>
                <li><strong style={{ color: 'var(--c-text)' }}>Kaggle EPL 2025–26</strong> — Per-90 performance statistics</li>
              </ul>
            </div>
            <div>
              <div className="label mb-8">Model pipeline</div>
              <ul style={{ paddingLeft: 20, color: 'var(--c-muted)', lineHeight: 1.9, fontSize: '0.9rem' }}>
                <li>3-step fuzzy name-matching across all sources</li>
                <li>3-season recency weighting (55% / 30% / 15%)</li>
                <li>XGBoost, Random Forest &amp; Linear Regression with 5-fold CV</li>
                <li>SHAP TreeExplainer for local + global explanations</li>
                <li>Position-specific aging curves &amp; contract advisor</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Limitations */}
        <div className="card mb-24">
          <h2 className="mb-16 flex items-center gap-10"><IconAlert size={22} style={{ color: 'var(--c-yellow)' }} /> Known limitations</h2>
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
          <h2 className="mb-12 flex items-center gap-10"><IconFlask size={22} style={{ color: 'var(--c-purple)' }} /> For evaluators</h2>
          <p style={{ color: 'var(--c-muted)', marginBottom: 16, fontSize: '0.9rem' }}>
            This tool was built as a BSc thesis research system. If you are a study participant or evaluator, you can record
            ratings and task timings using the access-code-protected Evaluation Console.
          </p>
          <Link to="/eval" className="btn btn-secondary" id="about-eval-link">
            <IconFlask size={16} /> Open Evaluation Console
          </Link>
        </div>

        {/* Navigation shortcuts */}
        <div className="grid-3" style={{ gap: 16 }}>
          {[
            { to: '/players',  Icon: IconSearch, label: 'Browse Players' },
            { to: '/scout',    Icon: IconTarget, label: 'Scout Tool' },
            { to: '/compare',  Icon: IconScale,  label: 'Compare Players' },
            { to: '/rankings', Icon: IconTrophy, label: 'Rankings' },
            { to: '/explain',  Icon: IconBrain,  label: 'SHAP Explanations' },
            { to: '/chat',     Icon: IconChat,   label: 'AI Chat' },
          ].map(l => (
            <Link key={l.to} to={l.to} className="card card--gradient card--glow" style={{ display: 'block', textAlign: 'center', padding: '20px 16px' }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10, margin: '0 auto 10px',
                background: 'rgba(200, 245, 66, 0.10)', color: 'var(--c-primary)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <l.Icon size={20} />
              </div>
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
    title: 'Market value benchmark',
    text: 'Market values reflect community-estimated Transfermarkt valuations rather than confidential club transfer fees.',
  },
  {
    title: 'Unobserved off-pitch factors',
    text: 'Medical records, injury history, dressing-room leadership, and individual wage demands are not in the dataset.',
  },
  {
    title: 'Minimum playing-time threshold',
    text: 'Players and goalkeepers with fewer than 900 league minutes in 2025–26 are excluded to prevent noisy per-90 rates.',
  },
  {
    title: 'Cosine similarity ≠ tactical fit',
    text: 'Similar statistical profiles do not guarantee system fit. A scout\'s contextual judgement remains essential.',
  },
]
