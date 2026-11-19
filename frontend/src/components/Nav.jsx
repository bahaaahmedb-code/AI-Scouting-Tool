import { NavLink } from 'react-router-dom'
import { useState } from 'react'
import { useShortlist } from '../shortlist'
import ShortlistDrawer from './ShortlistDrawer'

const links = [
  { to: '/', label: 'Home', end: true },
  { to: '/players', label: 'Players' },
  { to: '/squad', label: 'Squad Audit' },
  { to: '/rankings', label: 'Rankings' },
  { to: '/scout', label: 'Scout' },
  { to: '/compare', label: 'Compare' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/chat', label: 'Chat' },
  { to: '/about', label: 'About' },
]

export default function Nav() {
  const [open, setOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { count } = useShortlist()

  return (
    <>
      <nav className="nav" role="navigation" aria-label="Main navigation">
        <div className="nav-inner">
          <NavLink to="/" className="nav-logo">
            <div className="nav-logo-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 3v18M3 12h18" />
                <circle cx="12" cy="12" r="3.2" />
              </svg>
            </div>
            <span>Moneyball <em style={{ color: 'var(--c-primary)', fontStyle: 'italic', fontWeight: 500 }}>EPL</em></span>
          </NavLink>

          <div className="nav-links" role="menubar">
            {links.map(l => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
                role="menuitem"
              >
                {l.label}
              </NavLink>
            ))}
          </div>

          <div className="flex items-center gap-8">
            <button
              type="button"
              id="nav-shortlist-btn"
              className={`btn btn-sm ${count > 0 ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setDrawerOpen(true)}
              style={{ padding: '6px 12px', fontSize: '0.8rem', gap: 6 }}
              aria-label={`Open My Scouting Shortlist (${count} players)`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill={count > 0 ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2.1" aria-hidden="true">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
              <span>Shortlist</span>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: '0.72rem', fontWeight: 800,
                padding: '1px 6px', borderRadius: 999,
                background: count > 0 ? 'rgba(7, 16, 12, 0.22)' : 'rgba(255, 255, 255, 0.08)',
              }}>
                {count}
              </span>
            </button>

            <button
              className="nav-mobile-btn btn-ghost"
              aria-label="Toggle menu"
              aria-expanded={open}
              onClick={() => setOpen(v => !v)}
            >
              {open ? '✕' : '☰'}
            </button>
          </div>
        </div>

        {/* Mobile drawer */}
        {open && (
          <div
            style={{
              position: 'fixed', top: 64, left: 0, right: 0, bottom: 0,
              background: 'rgba(7,16,12,0.98)', zIndex: 99,
              display: 'flex', flexDirection: 'column', gap: 4, padding: '16px 24px',
            }}
          >
            {links.map(l => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                onClick={() => setOpen(false)}
                className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
                style={{ fontSize: '1.1rem', padding: '12px 16px' }}
              >
                {l.label}
              </NavLink>
            ))}
          </div>
        )}
      </nav>
      <ShortlistDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </>
  )
}
