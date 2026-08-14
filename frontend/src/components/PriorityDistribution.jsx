/**
 * Priority distribution — a horizontal bar chart of incident counts per tier.
 *
 * Priority is an ordered severity scale, so colour is a single-hue ordinal ramp
 * (light = low, dark = critical) rather than four unrelated hues: the ramp says
 * "more severe" on its own, where categorical colour would only say "different".
 * The steps are validated against the white card surface (see index.css).
 *
 * One series, so no legend box -- the heading names what is plotted, and every bar
 * is directly labelled with its tier and count.
 */

const TIERS = [
  { key: 'critical', label: 'Critical', color: 'var(--color-sev-critical)' },
  { key: 'high', label: 'High', color: 'var(--color-sev-high)' },
  { key: 'medium', label: 'Medium', color: 'var(--color-sev-medium)' },
  { key: 'low', label: 'Low', color: 'var(--color-sev-low)' },
]

export default function PriorityDistribution({ incidents }) {
  const counts = TIERS.map((tier) => ({
    ...tier,
    count: incidents.filter((i) => i.priority === tier.key).length,
  }))

  const untriaged = incidents.filter((i) => !i.priority).length
  // Bars are scaled against the largest tier, not the total, so a small board
  // still produces readable bar lengths.
  const max = Math.max(1, ...counts.map((c) => c.count))

  return (
    <section className="card p-6">
      <h2 className="font-bold text-ink">Priority distribution</h2>
      <p className="mt-1 text-sm text-muted">
        {incidents.length} incident{incidents.length === 1 ? '' : 's'} across four severity tiers
      </p>

      <div className="mt-5 space-y-3">
        {counts.map((tier, index) => (
          <div key={tier.key} className="flex items-center gap-3">
            <span className="w-16 shrink-0 text-xs font-semibold text-muted">{tier.label}</span>

            {/* The track is the surface, not a filled band: the bar is the only
                thing carrying ink, so an empty tier reads as genuinely empty. */}
            <div className="h-5 flex-1">
              <div
                className="h-full animate-grow-bar rounded-r-[4px]"
                style={{
                  width: `${Math.max((tier.count / max) * 100, tier.count > 0 ? 2 : 0)}%`,
                  backgroundColor: tier.color,
                  animationDelay: `${index * 60}ms`,
                }}
              />
            </div>

            {/* Value at the tip, in a text token -- never the mark's own colour. */}
            <span className="w-8 shrink-0 text-right text-sm font-bold tabular-nums text-ink">
              {tier.count}
            </span>
          </div>
        ))}
      </div>

      {untriaged > 0 && (
        <p className="mt-4 border-t border-line-soft pt-3 text-xs text-muted">
          ⏳ {untriaged} awaiting AI triage — no priority assigned yet
        </p>
      )}
    </section>
  )
}
