import { Link } from 'react-router-dom'

export function EmptyState({ emoji = '📭', title, hint, action }) {
  return (
    <div className="rounded-panel border border-dashed border-line bg-card px-6 py-16 text-center">
      <div className="text-4xl">{emoji}</div>
      <p className="mt-3 font-semibold text-ink">{title}</p>
      {hint && <p className="mx-auto mt-1 max-w-md text-sm text-muted">{hint}</p>}
      {action && (
        <Link to={action.to} className="btn-primary mt-5">
          {action.label}
        </Link>
      )}
    </div>
  )
}

export function ErrorState({ error }) {
  return (
    <div className="rounded-panel border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
      <p className="font-semibold">⚠️ {error}</p>
      <p className="mt-2 text-red-600">
        Start the backend with{' '}
        <code className="rounded bg-red-100 px-1.5 py-0.5 font-mono text-xs">
          uvicorn app.main:app --reload
        </code>
      </p>
    </div>
  )
}

export function CardSkeleton({ count = 3 }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }, (_, n) => (
        <div key={n} className="h-28 animate-pulse rounded-card border border-line bg-card" />
      ))}
    </div>
  )
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-3">{children}</div>}
    </header>
  )
}
