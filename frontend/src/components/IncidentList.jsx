import { useEffect, useMemo, useRef, useState } from 'react'
import IncidentCard from './IncidentCard'
import { CardSkeleton, EmptyState, ErrorState } from './states'

const SORTS = {
  newest: { label: 'Newest first', compare: (a, b) => b.id - a.id },
  oldest: { label: 'Oldest first', compare: (a, b) => a.id - b.id },
  priority: {
    label: 'Highest priority',
    // Untriaged incidents sort last rather than first -- a missing priority is
    // unknown severity, not zero severity.
    compare: (a, b) => {
      const rank = { critical: 0, high: 1, medium: 2, low: 3 }
      const av = rank[a.priority] ?? 4
      const bv = rank[b.priority] ?? 4
      return av - bv || b.id - a.id
    },
  },
}

const PRIORITY_FILTERS = ['critical', 'high', 'medium', 'low']

export default function IncidentList({ incidents, loading, error, emptyState }) {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('newest')
  const [priorities, setPriorities] = useState([])
  const searchRef = useRef(null)

  // "/" focuses search, the way most list-heavy tools behave. Ignored while the
  // caret is already in a field, so typing a slash into the box still works.
  useEffect(() => {
    const onKeyDown = (event) => {
      const tag = document.activeElement?.tagName
      if (event.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()

    return incidents
      .filter((i) => priorities.length === 0 || priorities.includes(i.priority))
      .filter((i) => {
        if (!needle) return true
        return [i.title, i.description, i.ai_summary, i.category, `#${i.id}`]
          .filter(Boolean)
          .some((field) => String(field).toLowerCase().includes(needle))
      })
      .slice()
      .sort(SORTS[sort].compare)
  }, [incidents, query, sort, priorities])

  function togglePriority(value) {
    setPriorities((current) =>
      current.includes(value) ? current.filter((p) => p !== value) : [...current, value],
    )
  }

  if (error) return <ErrorState error={error} />
  if (loading) return <CardSkeleton />

  const filtering = Boolean(query.trim()) || priorities.length > 0

  return (
    <div className="space-y-5">
      {/* controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <span
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-faint"
            aria-hidden="true"
          >
            🔍
          </span>
          <input
            ref={searchRef}
            type="search"
            className="field pl-9"
            placeholder="Search incidents…  (press / to focus)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search incidents"
          />
        </div>

        <select
          className="field w-auto"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          aria-label="Sort incidents"
        >
          {Object.entries(SORTS).map(([key, { label }]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* priority filter chips */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="section-label mr-1">Priority</span>
        {PRIORITY_FILTERS.map((value) => {
          const active = priorities.includes(value)
          return (
            <button
              key={value}
              type="button"
              onClick={() => togglePriority(value)}
              aria-pressed={active}
              className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize transition-colors ${
                active
                  ? 'border-accent bg-accent text-white'
                  : 'border-line bg-card text-muted hover:border-accent-line hover:text-ink'
              }`}
            >
              {value}
            </button>
          )
        })}
        {filtering && (
          <button
            type="button"
            onClick={() => {
              setQuery('')
              setPriorities([])
            }}
            className="ml-1 text-xs font-semibold text-accent hover:text-accent-hover"
          >
            Clear filters
          </button>
        )}
      </div>

      <p className="section-label" aria-live="polite">
        Showing {visible.length} of {incidents.length}
      </p>

      {visible.length === 0 ? (
        filtering ? (
          <EmptyState
            emoji="🔍"
            title="No matches"
            hint="Nothing matches your search or filters. Try clearing them."
          />
        ) : (
          <EmptyState {...emptyState} />
        )
      ) : (
        <div className="space-y-3">
          {visible.map((incident, index) => (
            <IncidentCard
              key={incident.id}
              incident={incident}
              // Stagger only the first handful; past that the last card would
              // wait noticeably before appearing.
              delay={Math.min(index, 8) * 40}
            />
          ))}
        </div>
      )}
    </div>
  )
}
