/**
 * Format an API timestamp in the viewer's local timezone.
 *
 * The backend stores UTC (`models.utcnow`), but SQLite has no native timestamp
 * type and drops the tzinfo, so values come back as naive strings like
 * "2026-08-14T08:45:36.805106". `new Date()` reads a bare datetime as *local*
 * time, which would silently shift every timestamp by the viewer's UTC offset --
 * so a missing designator is treated as the UTC it actually is.
 */
export function formatTimestamp(value) {
  if (!value) return null

  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  const date = new Date(hasTimezone ? value : `${value}Z`)

  if (Number.isNaN(date.getTime())) return value // unparseable: show it raw
  return date.toLocaleString()
}
