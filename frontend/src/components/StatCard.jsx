import { Link } from 'react-router-dom'

/**
 * Stat tile: label + value, optionally linking to the filtered view behind it.
 *
 * A handful of headline numbers is a KPI row, not a chart -- there is nothing to
 * compare visually that the numbers don't already say.
 */
export default function StatCard({ label, value, icon, to, tone = 'default', delay = 0 }) {
  const body = (
    <>
      <div className="flex items-center gap-2">
        {icon && (
          <span aria-hidden="true" className="text-sm">
            {icon}
          </span>
        )}
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</span>
      </div>
      {/* Proportional figures: tabular-nums makes a standalone display number look
          loose. Alignment only matters in columns, and these aren't one. */}
      <div
        className={`mt-2 text-3xl font-bold leading-none ${
          tone === 'accent' ? 'text-accent' : 'text-ink'
        }`}
      >
        {value}
      </div>
    </>
  )

  const className = `card p-5 animate-slide-up ${
    to ? 'block transition-shadow duration-150 hover:shadow-card-hover' : ''
  }`

  if (to) {
    return (
      <Link to={to} className={className} style={{ animationDelay: `${delay}ms` }}>
        {body}
      </Link>
    )
  }

  return (
    <div className={className} style={{ animationDelay: `${delay}ms` }}>
      {body}
    </div>
  )
}
