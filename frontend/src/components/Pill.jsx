/**
 * The one pill shape used by every badge in the app.
 *
 * Colour is always paired with a label (and usually a glyph), so status and
 * priority never depend on hue alone to be readable.
 */
export default function Pill({ tone = 'muted', emoji, children }) {
  const tones = {
    open: 'bg-blue-50 text-blue-700 border-blue-200',
    in_progress: 'bg-amber-50 text-amber-700 border-amber-200',
    resolved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    critical: 'bg-red-50 text-red-700 border-red-200',
    high: 'bg-orange-50 text-orange-700 border-orange-200',
    medium: 'bg-yellow-50 text-yellow-800 border-yellow-200',
    low: 'bg-green-50 text-green-700 border-green-200',
    accent: 'bg-accent-soft text-accent-ink border-accent-line',
    muted: 'bg-gray-100 text-muted border-line',
  }

  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5
                  py-0.5 text-xs font-semibold leading-5 ${tones[tone] || tones.muted}`}
    >
      {emoji && <span aria-hidden="true">{emoji}</span>}
      {children}
    </span>
  )
}
