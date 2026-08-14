import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useIncidents } from '../context/IncidentsContext'
import { formatTimestamp } from '../utils/datetime'
import Pill from '../components/Pill'
import StatusBadge from '../components/StatusBadge'
import PriorityBadge from '../components/PriorityBadge'
import { ErrorState } from '../components/states'

function Section({ label, children }) {
  return (
    <section>
      <h3 className="section-label mb-2">{label}</h3>
      {children}
    </section>
  )
}

function KBLink({ link }) {
  const [open, setOpen] = useState(false)
  const article = link.kb_article || {}
  const score =
    typeof link.relevance_score === 'number' ? `${Math.round(link.relevance_score * 100)}%` : 'n/a'

  return (
    <div className="rounded-card border border-line border-l-[3px] border-l-accent bg-accent-soft/25 p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold text-ink">📄 {article.title || 'Unknown article'}</p>
        <span className="shrink-0 rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-bold tabular-nums text-accent-ink">
          {score}
        </span>
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-muted">
        {link.rationale || 'No rationale recorded.'}
      </p>

      {(article.tag_list || []).length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {article.tag_list.map((tag) => (
            <Pill key={tag} tone="muted">
              {tag}
            </Pill>
          ))}
        </div>
      )}

      <button
        type="button"
        className="mt-3 text-sm font-semibold text-accent hover:text-accent-hover"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? 'Hide article ▲' : 'Read article ▼'}
      </button>
      {open && (
        <p className="mt-2 whitespace-pre-wrap border-t border-line pt-3 text-sm leading-relaxed text-ink animate-fade-in">
          {article.content || 'This article has no content.'}
        </p>
      )}
    </div>
  )
}

export default function IncidentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { refresh, notify } = useIncidents()

  const [incident, setIncident] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null) // 'reanalyze' | 'resolve' | 'status' | null
  const [actionError, setActionError] = useState(null)
  const [resolving, setResolving] = useState(false)
  const [notes, setNotes] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const { data, error: apiError } = await api.getIncident(id)
    setIncident(data)
    setError(apiError)
    setLoading(false)
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  /** Run a write, then resync both this page and the shared board. */
  async function runAction(key, call, successMessage) {
    setBusy(key)
    setActionError(null)
    const { error: apiError } = await call()
    setBusy(null)

    if (apiError) {
      setActionError(apiError)
      return false
    }
    await load()
    await refresh()
    if (successMessage) notify(successMessage)
    return true
  }

  async function handleResolve(event) {
    event.preventDefault()
    if (!notes.trim()) return
    const ok = await runAction(
      'resolve',
      () => api.resolveIncident(id, notes.trim()),
      `🎉 Incident #${id} marked resolved`,
    )
    if (ok) setResolving(false)
  }

  if (loading) {
    return <div className="h-96 animate-pulse rounded-panel border border-line bg-card" />
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <ErrorState error={error} />
      </div>
    )
  }

  const isResolved = incident.status === 'resolved'
  const kbLinks = incident.kb_links || []

  return (
    <div className="space-y-4">
      <nav className="flex items-center gap-2 text-sm text-muted">
        <Link to="/incidents" className="font-semibold text-accent hover:text-accent-hover">
          All incidents
        </Link>
        <span aria-hidden="true">/</span>
        <span>#{incident.id}</span>
      </nav>

      <div className="card p-6 sm:p-8">
        <header>
          <h1 className="text-xl font-bold leading-snug text-ink sm:text-2xl">
            <span className="mr-2 font-bold text-muted">#{incident.id}</span>
            {incident.title}
          </h1>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge status={incident.status} emoji={incident.status_emoji} />
            <PriorityBadge priority={incident.priority} emoji={incident.priority_emoji} />
            {incident.category && (
              <Pill tone="accent" emoji={incident.category_emoji || '🏷️'}>
                {incident.category}
              </Pill>
            )}
          </div>
          <p className="mt-3 text-xs text-muted">
            Logged {formatTimestamp(incident.created_at)}
            {incident.resolved_at && ` · Resolved ${formatTimestamp(incident.resolved_at)}`}
          </p>
        </header>

        <hr className="my-6 border-line" />

        <div className="space-y-6">
          <Section label="Description">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
              {incident.description}
            </p>
          </Section>

          <Section label="🤖 AI summary">
            {incident.ai_summary ? (
              <p className="rounded-card border border-accent-line bg-accent-soft px-4 py-3 text-sm leading-relaxed text-ink">
                {incident.ai_summary}
              </p>
            ) : (
              <p className="text-sm italic text-amber-700">AI analysis pending ⏳</p>
            )}
          </Section>

          <Section label={`📚 Knowledge base matches${kbLinks.length ? ` (${kbLinks.length})` : ''}`}>
            {kbLinks.length === 0 ? (
              <p className="text-sm text-muted">
                📭 No knowledge base article matched this incident.
              </p>
            ) : (
              <div className="space-y-3">
                {kbLinks.map((link) => (
                  <KBLink key={link.id} link={link} />
                ))}
              </div>
            )}
          </Section>

          <Section label={isResolved ? '✅ Resolution' : '✨ Suggested resolution'}>
            {isResolved ? (
              <p className="whitespace-pre-wrap rounded-card border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm leading-relaxed text-ink">
                {incident.resolution_notes || 'No notes recorded.'}
              </p>
            ) : incident.ai_suggested_resolution ? (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
                {incident.ai_suggested_resolution}
              </p>
            ) : (
              <p className="text-sm italic text-amber-700">AI analysis pending ⏳</p>
            )}
          </Section>
        </div>

        {actionError && (
          <div className="mt-6 rounded-control border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            ⚠️ {actionError}
          </div>
        )}

        <hr className="my-6 border-line" />

        {resolving ? (
          <form onSubmit={handleResolve}>
            <label htmlFor="resolution-notes" className="section-label mb-2 block">
              Resolution notes
            </label>
            <p className="mb-2 text-sm text-muted">
              Review and edit the drafted resolution before confirming. This cannot be undone.
            </p>
            <textarea
              id="resolution-notes"
              className="field min-h-52 resize-y"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={busy === 'resolve'}
              autoFocus
            />
            <div className="mt-4 flex flex-wrap justify-end gap-3">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setResolving(false)}
                disabled={busy === 'resolve'}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn-primary"
                disabled={!notes.trim() || busy === 'resolve'}
                title={!notes.trim() ? 'Resolution notes cannot be empty' : undefined}
              >
                {busy === 'resolve' ? 'Saving…' : '✅ Confirm resolve'}
              </button>
            </div>
          </form>
        ) : (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                // Seed the notes with the AI draft -- the operator edits it rather
                // than writing from scratch, which is the point of the draft step.
                setNotes(incident.ai_suggested_resolution || '')
                setActionError(null)
                setResolving(true)
              }}
              disabled={isResolved}
              title={isResolved ? 'Already resolved' : 'Review the draft, then confirm'}
            >
              ✅ Resolve
            </button>

            {incident.status === 'open' && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() =>
                  runAction(
                    'status',
                    () => api.updateIncident(id, { status: 'in_progress' }),
                    `🟡 Incident #${id} moved to in progress`,
                  )
                }
                disabled={busy === 'status'}
              >
                {busy === 'status' ? 'Saving…' : '▶️ Start work'}
              </button>
            )}

            {isResolved && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() =>
                  runAction(
                    'status',
                    () => api.updateIncident(id, { status: 'open' }),
                    `↩️ Incident #${id} reopened`,
                  )
                }
                disabled={busy === 'status'}
              >
                {busy === 'status' ? 'Saving…' : '↩️ Reopen'}
              </button>
            )}

            <button
              type="button"
              className="btn-secondary"
              onClick={() =>
                runAction(
                  'reanalyze',
                  () => api.reanalyzeIncident(id),
                  `🤖 Incident #${id} re-analysed`,
                )
              }
              disabled={busy === 'reanalyze'}
              title="Run AI triage, KB matching and drafting again"
            >
              {busy === 'reanalyze' ? '🤖 AI is analysing…' : '🔄 Re-analyze'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
