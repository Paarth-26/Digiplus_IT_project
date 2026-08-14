import Pill from './Pill'

// Fallbacks only: the API returns `status_emoji` on every incident, and that value
// is preferred so the glyph mapping stays owned by app/constants.py.
const FALLBACK_EMOJI = {
  open: '🔵',
  in_progress: '🟡',
  resolved: '🟢',
}

const LABELS = {
  open: 'Open',
  in_progress: 'In progress',
  resolved: 'Resolved',
}

export default function StatusBadge({ status, emoji }) {
  if (!status) return <Pill tone="muted" emoji="⏳">status pending</Pill>

  return (
    <Pill tone={status} emoji={emoji || FALLBACK_EMOJI[status] || '⚪'}>
      {LABELS[status] || status.replace(/_/g, ' ')}
    </Pill>
  )
}
