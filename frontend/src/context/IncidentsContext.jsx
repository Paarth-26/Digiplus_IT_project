import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'

const IncidentsContext = createContext(null)

export const ONGOING_STATUSES = ['open', 'in_progress']

/**
 * One fetch of the full incident board, shared by every page.
 *
 * The list endpoint filters by a single status, but "ongoing" spans two of them --
 * and each page also needs the whole-board counts for the nav badges. Fetching once
 * and slicing in the client keeps those counts consistent and makes navigation
 * instant, at the cost of holding the board in memory (fine at this size).
 */
export function IncidentsProvider({ children }) {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [health, setHealth] = useState(null)
  const [toast, setToast] = useState(null)

  const refresh = useCallback(async () => {
    const { data, error: apiError } = await api.listIncidents({})
    setIncidents(data || [])
    setError(apiError)
    setLoading(false)
    return { data, error: apiError }
  }, [])

  useEffect(() => {
    refresh()
    api.health().then(({ data }) => setHealth(data))
  }, [refresh])

  // Toasts clear themselves; the timer is torn down if a newer toast replaces it.
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 4500)
    return () => clearTimeout(timer)
  }, [toast])

  const counts = useMemo(
    () => ({
      all: incidents.length,
      ongoing: incidents.filter((i) => ONGOING_STATUSES.includes(i.status)).length,
      completed: incidents.filter((i) => i.status === 'resolved').length,
      open: incidents.filter((i) => i.status === 'open').length,
      in_progress: incidents.filter((i) => i.status === 'in_progress').length,
      awaitingAi: incidents.filter((i) => !i.ai_summary).length,
    }),
    [incidents],
  )

  const value = useMemo(
    () => ({
      incidents,
      counts,
      loading,
      error,
      health,
      refresh,
      toast,
      notify: setToast,
    }),
    [incidents, counts, loading, error, health, refresh, toast],
  )

  return <IncidentsContext.Provider value={value}>{children}</IncidentsContext.Provider>
}

export function useIncidents() {
  const context = useContext(IncidentsContext)
  if (!context) throw new Error('useIncidents must be used inside <IncidentsProvider>')
  return context
}
