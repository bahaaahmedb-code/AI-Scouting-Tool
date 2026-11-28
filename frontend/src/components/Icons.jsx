/** Clean, Floodlit-Pitch-styled SVG vector icons to replace all emojis across the application */

const baseProps = (size = 18, style = {}) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.85,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  style: { display: 'inline-block', verticalAlign: '-0.18em', flexShrink: 0, ...style },
  'aria-hidden': 'true',
})

export function IconSearch({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <circle cx="11" cy="11" r="7" />
      <line x1="20" y1="20" x2="16.2" y2="16.2" />
    </svg>
  )
}

export function IconBrain({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M9.5 4a3.5 3.5 0 0 0-3.3 4.7A3.5 3.5 0 0 0 5 15a3.5 3.5 0 0 0 4.5 3.3V4Z" />
      <path d="M14.5 4a3.5 3.5 0 0 1 3.3 4.7A3.5 3.5 0 0 1 19 15a3.5 3.5 0 0 1-4.5 3.3V4Z" />
    </svg>
  )
}

export function IconTarget({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </svg>
  )
}

export function IconScale({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M12 3v18" />
      <path d="M5 7h14" />
      <path d="M5 7 2 14h6L5 7Z" />
      <path d="M19 7l-3 7h6l-3-7Z" />
      <path d="M8 21h8" />
    </svg>
  )
}

export function IconTrophy({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M6 4h12v4a6 6 0 0 1-12 0V4Z" />
      <path d="M6 6H3v2a3 3 0 0 0 3 3" />
      <path d="M18 6h3v2a3 3 0 0 1-3 3" />
      <path d="M12 14v4" />
      <path d="M8 21h8" />
    </svg>
  )
}

export function IconChat({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z" />
      <line x1="8" y1="11" x2="16" y2="11" />
      <line x1="8" y1="15" x2="13" y2="15" />
    </svg>
  )
}

export function IconChart({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
      <line x1="3" y1="20" x2="21" y2="20" />
    </svg>
  )
}

export function IconTrendUp({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  )
}

export function IconTrendDown({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <polyline points="22 17 13.5 8.5 8.5 13.5 2 7" />
      <polyline points="16 17 22 17 22 11" />
    </svg>
  )
}

export function IconShield({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
    </svg>
  )
}

export function IconBolt({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  )
}

export function IconAlert({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}

export function IconInfo({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  )
}

export function IconBall({ size = 24, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <circle cx="12" cy="12" r="9.5" />
      <polygon points="12 7.5 16 10.3 14.5 15 9.5 15 8 10.3" />
      <line x1="12" y1="2.5" x2="12" y2="7.5" />
      <line x1="16" y1="10.3" x2="21" y2="9" />
      <line x1="14.5" y1="15" x2="17.8" y2="19.5" />
      <line x1="9.5" y1="15" x2="6.2" y2="19.5" />
      <line x1="8" y1="10.3" x2="3" y2="9" />
    </svg>
  )
}

export function IconStadium({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <ellipse cx="12" cy="7" rx="9" ry="4" />
      <path d="M3 7v8c0 2.2 4 4 9 4s9-1.8 9-4V7" />
      <path d="M9 19v-4h6v4" />
    </svg>
  )
}

export function IconCalendar({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <rect x="3" y="4" width="18" height="17" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  )
}

export function IconGlobe({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <circle cx="12" cy="12" r="9" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18Z" />
    </svg>
  )
}

export function IconClock({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <circle cx="12" cy="12" r="9" />
      <polyline points="12 7 12 12 15.5 14" />
    </svg>
  )
}

export function IconClipboard({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" />
    </svg>
  )
}

export function IconContract({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="13" y2="17" />
    </svg>
  )
}

export function IconSparkle({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="m12 3 1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3Z" />
    </svg>
  )
}

export function IconKey({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <circle cx="7.5" cy="15.5" r="4.5" />
      <path d="m21 3-9.6 9.6" />
      <path d="m15.5 8.5 3 3" />
    </svg>
  )
}

export function IconRadar({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <polygon points="12 2 21 8.5 17.5 19.5 6.5 19.5 3 8.5" />
      <polygon points="12 6.5 17 10 15 16 9 16 7 10" />
      <line x1="12" y1="2" x2="12" y2="19.5" />
    </svg>
  )
}

export function IconFlask({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M9 3h6" />
      <path d="M10 3v6.5L4.5 18.2A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.8L14 9.5V3" />
      <line x1="7" y1="15" x2="17" y2="15" />
    </svg>
  )
}

export function IconBook({ size = 18, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
    </svg>
  )
}

export function IconStar({ size = 16, filled = false, style }) {
  return (
    <svg {...baseProps(size, style)} fill={filled ? 'currentColor' : 'none'}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  )
}

export function IconDownload({ size = 16, style }) {
  return (
    <svg {...baseProps(size, style)}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

export function IconMedal({ rank = 1, size = 28 }) {
  const colors = {
    1: { fill: '#facc15', stroke: '#fde047', text: '#07100c' },
    2: { fill: '#cbd5e1', stroke: '#e2e8f0', text: '#07100c' },
    3: { fill: '#d97706', stroke: '#f59e0b', text: '#07100c' },
  }[rank] || { fill: '#334155', stroke: '#475569', text: '#fff' }

  return (
    <svg width={size} height={size} viewBox="0 0 32 32" style={{ display: 'inline-block', verticalAlign: 'middle' }} aria-label={`Rank ${rank}`}>
      <path d="M10 3h5l2 7h-5L10 3Z" fill={colors.stroke} opacity="0.65" />
      <path d="M22 3h-5l-2 7h5l2-7Z" fill={colors.fill} opacity="0.85" />
      <circle cx="16" cy="19" r="9.5" fill={colors.fill} stroke={colors.stroke} strokeWidth="1.5" />
      <text x="16" y="22.5" textAnchor="middle" fill={colors.text} fontSize="11" fontWeight="800" fontFamily="var(--font-mono)">
        {rank}
      </text>
    </svg>
  )
}

