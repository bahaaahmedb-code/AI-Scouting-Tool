import { NavLink } from 'react-router-dom'
import { useState } from 'react'

const links = [
  { to: '/',         label: '🏠 Home',     end: true },
  { to: '/players',  label: '🔍 Players' },
  { to: '/rankings', label: '🏆 Rankings' },
  { to: '/scout',    label: '🎯 Scout' },
  { to: '/compare',  label: '⚖️ Compare' },
  { to: '/dashboard', label: '📊 Dashboard' },
  { to: '/chat',     label: '💬 Chat' },
  { to: '/about',    label: 'ℹ️ About' },
]

export default function Nav() {
  const [open, setOpen] = useState(false)

  return (
    <nav className="nav" role="navigation" aria-label="Main navigation">
      <div className="nav-inner">
        <NavLink to="/" className="nav-logo">
          <div className="nav-logo-icon" aria-hidden="true">⚽</div>
          <span>Moneyball <span style={{ color: 'var(--c-primary)' }}>EPL</span></span>
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

        <button
          className="nav-mobile-btn btn-ghost"
          aria-label="Toggle menu"
          aria-expanded={open}
          onClick={() => setOpen(v => !v)}
        >
          {open ? '✕' : '☰'}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div
          style={{
            position: 'fixed', top: 64, left: 0, right: 0, bottom: 0,
            background: 'rgba(10,12,18,0.97)', zIndex: 99,
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
  )
}
