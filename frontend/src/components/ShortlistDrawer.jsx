import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useShortlist } from '../shortlist'
import { fmtValue } from '../utils'
import { PosChip } from './UI'
import { IconScale, IconClipboard } from './Icons'

const POS_LABELS = {
  G: 'Goalkeepers',
  D: 'Defenders',
  M: 'Midfielders',
  F: 'Forwards',
}
const POS_ORDER = ['F', 'M', 'D', 'G']
const normPos = (p) => {
  const raw = String(p?.position || '').toUpperCase()
  return raw === 'GK' ? 'G' : raw
}

/** Reusable star/bookmark button for adding/removing any player from My Shortlist */
export function ShortlistBtn({ player, compact = false }) {
  const { has, toggle } = useShortlist()
  const pid = Number(player?.id ?? player?.player_id)
  if (!Number.isFinite(pid)) return null
  const saved = has(pid)

  function onClick(e) {
    e.preventDefault()
    e.stopPropagation()
    const added = toggle(player)
    const nm = player.name ?? player.player_name ?? 'Player'
    toast.success(added ? `Added ${nm} to Shortlist` : `Removed ${nm} from Shortlist`, { duration: 1800 })
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`btn btn-sm ${saved ? 'btn-primary' : 'btn-secondary'}`}
      style={{
        padding: compact ? '7px 9px' : '6px 12px',
        fontSize: compact ? '0.78rem' : '0.82rem',
        gap: 5,
      }}
      title={saved ? 'Remove from My Shortlist' : 'Save to My Shortlist'}
      aria-pressed={saved}
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill={saved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
      {!compact && <span>{saved ? 'Shortlisted' : 'Shortlist'}</span>}
    </button>
  )
}

/** Slide-over Transfer Shortlist & Budget Planner Drawer */
export default function ShortlistDrawer({ open, onClose }) {
  const { items, remove, clear } = useShortlist()
  const navigate = useNavigate()
  const [selectedPos, setSelectedPos] = useState('')

  if (!open) return null

  const totalEst = items.reduce((s, p) => s + (p.estimated_value_eur || 0), 0)
  const totalMkt = items.reduce((s, p) => s + (p.listed_value_eur || 0), 0)
  const avgAge = items.length ? items.reduce((s, p) => s + (p.age || 0), 0) / items.length : 0
  const valueGap = totalEst - totalMkt

  // Group shortlisted players by position for same-position-only comparisons
  const groupsByPos = POS_ORDER.map(pos => ({
    pos,
    label: POS_LABELS[pos],
    players: items.filter(p => normPos(p) === pos),
  })).filter(g => g.players.length > 0)

  const comparableGroups = groupsByPos.filter(g => g.players.length >= 2)
  const activeGroup = comparableGroups.find(g => g.pos === selectedPos) ?? comparableGroups[0] ?? null

  function handleExportCsv() {
    if (!items.length) return
    const header = 'Player,Club,Position,Age,Model Estimate (EUR),Listed Value (EUR),Value Gap (EUR)'
    const rows = items.map(p => {
      const est = Math.round(p.estimated_value_eur || 0)
      const mkt = Math.round(p.listed_value_eur || 0)
      return `"${p.name}","${p.club}",${p.position === 'G' ? 'GK' : p.position},${p.age ?? ''},${est},${mkt},${est - mkt}`
    })
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'moneyball_transfer_shortlist.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success('Exported transfer shortlist CSV')
  }

  function handleComparePosition(group = activeGroup) {
    if (!group || group.players.length < 2) return
    const ids = group.players.slice(0, 4).map(p => p.id).join(',')
    onClose()
    navigate(`/compare?ids=${ids}`)
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(3, 8, 5, 0.72)', backdropFilter: 'blur(4px)',
        display: 'flex', justifyContent: 'flex-end',
      }}
      onClick={onClose}
    >
      <aside
        style={{
          width: '100%', maxWidth: 430, height: '100%',
          background: 'var(--c-surface)', borderLeft: '1px solid var(--c-border2)',
          display: 'flex', flexDirection: 'column', boxShadow: 'var(--shadow-pop)',
        }}
        onClick={e => e.stopPropagation()}
        aria-label="My Scouting Shortlist"
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid var(--c-border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <div className="label" style={{ color: 'var(--c-primary)', marginBottom: 2 }}>Transfer Window Cart</div>
            <h3 style={{ margin: 0 }}>My Scouting Shortlist ({items.length})</h3>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close shortlist" style={{ fontSize: '1.1rem' }}>
            ✕
          </button>
        </div>

        {/* Budget Summary */}
        {items.length > 0 && (
          <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--c-border)', background: 'var(--c-card)' }}>
            <div className="grid-2" style={{ gap: 12 }}>
              <div style={{ background: 'var(--c-surface)', borderRadius: 8, padding: '10px 12px', border: '1px solid var(--c-border)' }}>
                <div className="label mb-4">Total Model Value</div>
                <div style={{ fontWeight: 800, fontSize: '1.15rem', color: 'var(--c-accent)', fontFamily: 'var(--font-mono)' }}>
                  {fmtValue(totalEst)}
                </div>
              </div>
              <div style={{ background: 'var(--c-surface)', borderRadius: 8, padding: '10px 12px', border: '1px solid var(--c-border)' }}>
                <div className="label mb-4">Listed Budget Req.</div>
                <div style={{ fontWeight: 800, fontSize: '1.15rem', color: 'var(--c-text)', fontFamily: 'var(--font-mono)' }}>
                  {fmtValue(totalMkt)}
                </div>
              </div>
            </div>
            <div className="flex justify-between items-center mt-12" style={{ fontSize: '0.8rem', color: 'var(--c-muted)' }}>
              <span>Avg Target Age: <strong style={{ color: 'var(--c-text)' }}>{avgAge.toFixed(1)} yrs</strong></span>
              <span>
                Value Edge:{' '}
                <strong style={{ color: valueGap >= 0 ? 'var(--c-green)' : 'var(--c-red)' }}>
                  {valueGap >= 0 ? '+' : '−'}{fmtValue(Math.abs(valueGap))}
                </strong>
              </span>
            </div>
          </div>
        )}

        {/* List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px' }}>
          {items.length === 0 ? (
            <div className="empty-state" style={{ padding: '60px 16px' }}>
              <div style={{ marginBottom: 12, color: 'var(--c-muted)' }}>
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              </div>
              <h4 style={{ marginBottom: 8 }}>Your shortlist is empty</h4>
              <p className="text-muted" style={{ fontSize: '0.86rem' }}>
                Click the star button on any player across Players, Scout, Rankings, Squad Audit, or Player Profile to build your transfer window target list.
              </p>
            </div>
          ) : (
            <div className="flex-col gap-12">
              {items.map(p => (
                <div
                  key={p.id}
                  style={{
                    background: 'var(--c-card)', border: '1px solid var(--c-border)',
                    borderRadius: 10, padding: '12px 14px',
                    display: 'flex', alignItems: 'center', gap: 12,
                  }}
                >
                  <PosChip pos={p.position} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Link
                      to={`/players/${p.id}`}
                      onClick={onClose}
                      style={{ fontWeight: 700, color: 'var(--c-primary)', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                    >
                      {p.name}
                    </Link>
                    <div className="text-muted" style={{ fontSize: '0.78rem' }}>
                      {p.club} · Age {p.age}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 700, color: 'var(--c-accent)', fontSize: '0.88rem', fontFamily: 'var(--font-mono)' }}>
                      {fmtValue(p.estimated_value_eur)}
                    </div>
                    <div className="text-subtle" style={{ fontSize: '0.72rem' }}>
                      Mkt {fmtValue(p.listed_value_eur)}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => remove(p.id)}
                    aria-label={`Remove ${p.name}`}
                    style={{ padding: '4px 6px', fontSize: '0.85rem' }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer actions */}
        {items.length > 0 && (
          <div style={{ padding: '16px 24px', borderTop: '1px solid var(--c-border)', background: 'var(--c-card)' }}>
            {comparableGroups.length > 1 && (
              <div className="mb-12">
                <div className="label mb-6" style={{ fontSize: '0.68rem' }}>
                  Compare Position Group (Same Position Only)
                </div>
                <div className="flex gap-6 wrap">
                  {comparableGroups.map(g => {
                    const active = activeGroup?.pos === g.pos
                    return (
                      <button
                        key={g.pos}
                        type="button"
                        onClick={() => setSelectedPos(g.pos)}
                        className={`btn btn-sm ${active ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '4px 10px', fontSize: '0.76rem' }}
                        aria-pressed={active}
                      >
                        {g.label} ({g.players.length})
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {comparableGroups.length === 0 && (
              <p className="text-subtle mb-8" style={{ fontSize: '0.76rem', textAlign: 'center' }}>
                Add at least 2 players in the same position to compare side by side.
              </p>
            )}

            <div className="flex gap-8 mb-8">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                style={{ flex: 1, justifyContent: 'center' }}
                disabled={!activeGroup}
                onClick={() => handleComparePosition(activeGroup)}
                title={
                  activeGroup
                    ? `Compare ${Math.min(activeGroup.players.length, 4)} ${activeGroup.label.toLowerCase()} side by side`
                    : 'Add at least 2 players in the same position to compare'
                }
              >
                <IconScale size={14} />{' '}
                {activeGroup
                  ? `Compare ${activeGroup.label} (${Math.min(activeGroup.players.length, 4)})`
                  : 'Compare (Same Pos)'}
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ flex: 1, justifyContent: 'center' }}
                onClick={handleExportCsv}
              >
                <IconClipboard size={14} /> Export CSV
              </button>
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ width: '100%', justifyContent: 'center', fontSize: '0.78rem' }}
              onClick={() => { clear(); toast.success('Shortlist cleared') }}
            >
              Clear Shortlist
            </button>
          </div>
        )}
      </aside>
    </div>
  )
}
