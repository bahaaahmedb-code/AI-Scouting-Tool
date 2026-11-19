import { useEffect, useState, useCallback } from 'react'

const STORAGE_KEY = 'moneyball_epl_shortlist_v1'
const EVENT_NAME = 'moneyball-shortlist-changed'

function readShortlist() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeShortlist(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
  } catch {
    // ignore quota errors
  }
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: list }))
}

export function normalizePlayerForShortlist(p) {
  const id = Number(p.id ?? p.player_id)
  return {
    id,
    name: p.name ?? p.player_name ?? `Player #${id}`,
    club: p.club ?? p.team_name ?? '',
    position: p.position ?? 'M',
    age: p.age ?? null,
    estimated_value_eur: p.estimated_value_eur ?? p.estimated_value ?? p.value_eur ?? 0,
    listed_value_eur: p.listed_value_eur ?? p.market_value_eur ?? 0,
  }
}

export function useShortlist() {
  const [items, setItems] = useState(readShortlist)

  useEffect(() => {
    const onSync = (e) => setItems(Array.isArray(e.detail) ? e.detail : readShortlist())
    const onStorage = (e) => { if (e.key === STORAGE_KEY) setItems(readShortlist()) }
    window.addEventListener(EVENT_NAME, onSync)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener(EVENT_NAME, onSync)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  const has = useCallback((id) => items.some(x => x.id === Number(id)), [items])

  const toggle = useCallback((player) => {
    const norm = normalizePlayerForShortlist(player)
    const cur = readShortlist()
    const exists = cur.some(x => x.id === norm.id)
    const next = exists ? cur.filter(x => x.id !== norm.id) : [...cur, norm]
    writeShortlist(next)
    return !exists
  }, [])

  const remove = useCallback((id) => {
    const next = readShortlist().filter(x => x.id !== Number(id))
    writeShortlist(next)
  }, [])

  const clear = useCallback(() => {
    writeShortlist([])
  }, [])

  return { items, has, toggle, remove, clear, count: items.length }
}
