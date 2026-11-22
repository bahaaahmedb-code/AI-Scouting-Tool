import { useEffect, useState } from 'react'
import playerPhotos from '../data/playerPhotos.json'
import { IconBall } from './Icons'

/**
 * Displays a player's official Premier League headshot (with multi-CDN fallback
 * and graceful fallback to the football icon if unavailable).
 */
export default function PlayerAvatar({ name, size = 74, radius = 16 }) {
  const code = name ? playerPhotos[name] : null
  const [stage, setStage] = useState(0)

  useEffect(() => {
    setStage(0)
  }, [name, code])

  const urls = code
    ? [
        `https://resources.premierleague.com/premierleague/photos/players/250x250/p${code}.png`,
        `https://resources.premierleague.com/premierleague25/photos/players/110x140/${code}.png`,
      ]
    : []

  const src = urls[stage] || null

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        background: 'linear-gradient(145deg, rgba(200, 245, 66, 0.16), rgba(12, 28, 19, 0.92))',
        border: '1px solid rgba(200, 245, 66, 0.38)',
        color: 'var(--c-primary)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        flexShrink: 0,
        boxShadow: '0 6px 18px rgba(0, 0, 0, 0.35)',
      }}
    >
      {src ? (
        <img
          src={src}
          alt={name || 'Player'}
          loading="lazy"
          onError={() => setStage(s => s + 1)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            objectPosition: 'top center',
            display: 'block',
          }}
        />
      ) : (
        <IconBall size={Math.round(size * 0.52)} />
      )}
    </div>
  )
}
