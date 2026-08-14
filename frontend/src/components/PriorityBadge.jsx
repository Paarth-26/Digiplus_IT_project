import Pill from './Pill'

// Fallbacks only — see the note in StatusBadge.
const FALLBACK_EMOJI = {
  critical: '🔴',
  high: '🟠',
  medium: '🟡',
  low: '🟢',
}

export default function PriorityBadge({ priority, emoji }) {
  // Priority is null until AI triage lands, which is a real state worth showing
  // rather than an empty gap in the badge row.
  if (!priority) {
    return (
      <Pill tone="muted" emoji="⏳">
        priority pending
      </Pill>
    )
  }

  return (
    <Pill tone={priority} emoji={emoji || FALLBACK_EMOJI[priority] || '⚪'}>
      {priority.charAt(0).toUpperCase() + priority.slice(1)}
    </Pill>
  )
}
