import { useNavigate } from 'react-router-dom'
import Pill from './Pill'
import StatusBadge from './StatusBadge'
import PriorityBadge from './PriorityBadge'
import { formatTimestamp } from '../utils/datetime'

/** One incident row. The whole card navigates to the detail route. */
export default function IncidentCard({ incident, delay = 0 }) {
  const navigate = useNavigate()
  const { id, title, status, priority, category, ai_summary } = incident

  const open = () => navigate(`/incidents/${id}`)

  return (
    <article
      onClick={open}
      onKeyDown={(event) => {
        // A div-with-onClick is invisible to the keyboard, so Enter/Space are
        // wired up explicitly to match the button semantics declared by role.
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          open()
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`Incident ${id}: ${title}`}
      style={{ animationDelay: `${delay}ms` }}
      className="group card animate-slide-up cursor-pointer p-5 transition-shadow duration-150
                 hover:shadow-card-hover"
    >
      <div className="flex items-start justify-between gap-4">
        <h3 className="text-base font-semibold leading-snug text-ink">
          <span className="mr-1.5 font-bold text-muted">#{id}</span>
          {title}
        </h3>
        <span
          className="shrink-0 text-sm font-semibold text-accent opacity-0 transition-opacity
                     group-hover:opacity-100"
          aria-hidden="true"
        >
          View →
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <StatusBadge status={status} emoji={incident.status_emoji} />
        <PriorityBadge priority={priority} emoji={incident.priority_emoji} />
        {category ? (
          <Pill tone="accent" emoji={incident.category_emoji || '🏷️'}>
            {category}
          </Pill>
        ) : (
          <Pill tone="muted" emoji="⏳">
            category pending
          </Pill>
        )}
      </div>

      {ai_summary ? (
        <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-muted">🤖 {ai_summary}</p>
      ) : (
        <p className="mt-3 text-sm italic text-amber-700">🤖 AI analysis pending ⏳</p>
      )}

      <p className="mt-3 text-xs text-faint">Logged {formatTimestamp(incident.created_at)}</p>
    </article>
  )
}
