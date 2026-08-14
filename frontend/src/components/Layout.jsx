import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { API_BASE } from '../api/client'
import { useIncidents } from '../context/IncidentsContext'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '📊', end: true },
  { to: '/incidents', label: 'All incidents', icon: '🗂️', countKey: 'all', end: true },
  { to: '/incidents/ongoing', label: 'Ongoing', icon: '🔄', countKey: 'ongoing' },
  { to: '/incidents/completed', label: 'Completed', icon: '✅', countKey: 'completed' },
  { to: '/incidents/new', label: 'New incident', icon: '➕' },
]

function NavItems({ counts, onNavigate }) {
  return (
    <nav className="space-y-1">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-semibold transition-colors ${
              isActive
                ? 'bg-accent-soft text-accent-ink'
                : 'text-muted hover:bg-canvas hover:text-ink'
            }`
          }
        >
          <span aria-hidden="true" className="text-base leading-none">
            {item.icon}
          </span>
          <span className="flex-1">{item.label}</span>
          {item.countKey !== undefined && (
            <span className="rounded-full bg-canvas px-2 py-0.5 text-xs font-bold text-muted">
              {counts[item.countKey]}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

export default function Layout() {
  const { counts, health, toast } = useIncidents()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  // A route change should land the reader at the top of the new page; the browser
  // otherwise keeps the previous scroll offset on a client-side navigation.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-canvas">
      {/* mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-card/90 px-4 py-3 backdrop-blur lg:hidden">
        <button
          type="button"
          className="btn-ghost px-2"
          onClick={() => setMenuOpen((v) => !v)}
          aria-expanded={menuOpen}
          aria-label="Toggle navigation"
        >
          <span className="text-lg">{menuOpen ? '✕' : '☰'}</span>
        </button>
        <span className="font-bold text-ink">🎯 Triage Assistant</span>
      </header>

      {menuOpen && (
        <div className="border-b border-line bg-card px-4 py-3 lg:hidden animate-fade-in">
          <NavItems counts={counts} onNavigate={() => setMenuOpen(false)} />
        </div>
      )}

      <div className="mx-auto flex max-w-7xl">
        {/* desktop sidebar */}
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-card px-4 py-6 lg:flex">
          <div className="px-3">
            <p className="text-lg font-bold leading-tight tracking-tight text-ink">
              🎯 Triage Assistant
            </p>
            <p className="mt-1 text-xs text-muted">AI-assisted support triage</p>
          </div>

          <div className="mt-8 flex-1">
            <NavItems counts={counts} />
          </div>

          <div className="border-t border-line-soft px-3 pt-4 text-xs text-muted">
            {health ? (
              <>
                <p className="flex items-center gap-1.5">
                  <span aria-hidden="true">{health.status_emoji}</span>
                  Backend {health.status}
                </p>
                <p className="mt-1">
                  {health.groq_api_key_loaded ? '🔑 Groq key loaded' : '⚠️ GROQ_API_KEY missing'}
                </p>
              </>
            ) : (
              <p>🔌 Backend unreachable</p>
            )}
            <p className="mt-1 truncate text-faint" title={API_BASE}>
              {API_BASE}
            </p>
          </div>
        </aside>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 sm:py-10">
          <Outlet />
        </main>
      </div>

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-50 max-w-[90vw] -translate-x-1/2 rounded-control
                     bg-ink px-4 py-2.5 text-sm font-medium text-white shadow-modal animate-rise-in"
        >
          {toast}
        </div>
      )}
    </div>
  )
}
