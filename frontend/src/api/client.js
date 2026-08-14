/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Every call resolves to `{ data, error }` and never throws, so a component can
 * render an error state without a try/catch at each call site.
 */

export const API_BASE = (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000').replace(
  /\/+$/,
  '',
)

// Creating or re-analysing an incident runs three sequential Groq calls
// server-side, so writes need a far longer budget than plain reads.
const READ_TIMEOUT = 15_000
const WRITE_TIMEOUT = 120_000

/** Turn a FastAPI error body into one readable line. */
function formatDetail(payload, status) {
  const detail = payload && typeof payload === 'object' ? (payload.detail ?? payload) : payload

  // 422 bodies are a list of {loc, msg} objects; the first loc entry is just
  // "body"/"query", so it is dropped from the path.
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const path = (item.loc || []).slice(1).join('.')
        return path ? `${path}: ${item.msg}` : item.msg
      })
      .join('; ')
  }

  if (typeof detail === 'string') return detail
  return detail ? JSON.stringify(detail) : `HTTP ${status}`
}

async function request(method, path, { body, params, timeout } = {}) {
  const url = new URL(`${API_BASE}${path}`)
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value)
  })

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout ?? READ_TIMEOUT)

  try {
    const response = await fetch(url, {
      method,
      signal: controller.signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })

    let payload = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }

    if (!response.ok) {
      return { data: null, error: `${response.status} — ${formatDetail(payload, response.status)}` }
    }
    return { data: payload, error: null }
  } catch (err) {
    if (err.name === 'AbortError') {
      return { data: null, error: 'The API took too long to respond.' }
    }
    // fetch rejects with a bare TypeError for both a dead server and a blocked
    // CORS preflight, so the message names both possibilities.
    return {
      data: null,
      error: `Cannot reach the API at ${API_BASE}. Is the backend running (and CORS enabled)?`,
    }
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  listIncidents: (filters = {}) =>
    request('GET', '/incidents', {
      params: { status: filters.status, priority: filters.priority },
    }),

  getIncident: (id) => request('GET', `/incidents/${id}`),

  createIncident: (title, description) =>
    request('POST', '/incidents', {
      body: { title, description },
      timeout: WRITE_TIMEOUT,
    }),

  reanalyzeIncident: (id) =>
    request('POST', `/incidents/${id}/reanalyze`, { timeout: WRITE_TIMEOUT }),

  resolveIncident: (id, resolutionNotes) =>
    request('POST', `/incidents/${id}/resolve`, {
      body: { resolution_notes: resolutionNotes },
      timeout: WRITE_TIMEOUT,
    }),

  updateIncident: (id, changes) => request('PATCH', `/incidents/${id}`, { body: changes }),

  health: () => request('GET', '/health', { timeout: 5_000 }),
}
