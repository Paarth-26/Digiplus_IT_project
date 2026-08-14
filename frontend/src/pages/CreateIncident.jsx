import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useIncidents } from '../context/IncidentsContext'
import { PageHeader } from '../components/states'

const EXAMPLES = [
  {
    title: 'VPN drops every 15 minutes',
    description:
      'Since this morning the office VPN disconnects roughly every 15 minutes. Reconnecting works but drops again. Affects the whole finance team on the 3rd floor.',
  },
  {
    title: 'Cannot log in after password reset',
    description:
      'A user reset their password through the self-service portal. The new password is rejected at the login screen with "invalid credentials", but the old one no longer works either.',
  },
  {
    title: 'Invoice charged twice this month',
    description:
      'A customer reports two identical charges on the same invoice number for their September subscription. They would like one refunded and an explanation of what happened.',
  },
]

export default function CreateIncident() {
  const navigate = useNavigate()
  const { refresh, notify } = useIncidents()

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    if (!title.trim() || !description.trim()) {
      setError('Title and description are both required.')
      return
    }

    setSubmitting(true)
    setError(null)
    const { data, error: apiError } = await api.createIncident(title.trim(), description.trim())
    setSubmitting(false)

    if (apiError) {
      setError(apiError)
      return
    }

    await refresh()
    notify(
      data.ai_summary
        ? `🎉 Created incident #${data.id}`
        : `⏳ Created incident #${data.id} — AI analysis did not run, triage fields are pending.`,
    )
    navigate(`/incidents/${data.id}`)
  }

  return (
    <>
      <PageHeader
        title="New incident"
        subtitle="Describe the problem. AI triage runs automatically once it's logged."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <form onSubmit={handleSubmit} className="card p-6 lg:col-span-2 sm:p-8">
          <div className="space-y-5">
            <div>
              <label htmlFor="title" className="mb-1.5 block text-sm font-semibold text-ink">
                Title
              </label>
              <input
                id="title"
                className="field"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="VPN drops every 15 minutes"
                maxLength={255}
                disabled={submitting}
                autoFocus
              />
              <p className="mt-1.5 text-xs text-muted">
                A one-line summary of the problem. {title.length}/255
              </p>
            </div>

            <div>
              <label htmlFor="description" className="mb-1.5 block text-sm font-semibold text-ink">
                Description
              </label>
              <textarea
                id="description"
                className="field min-h-56 resize-y"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What is happening, who is affected, and when it started."
                disabled={submitting}
              />
              <p className="mt-1.5 text-xs text-muted">
                More detail produces a better AI summary and knowledge base match.
              </p>
            </div>

            {error && (
              <div className="rounded-control border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                ⚠️ {error}
              </div>
            )}

            {submitting && (
              <div className="rounded-control border border-accent-line bg-accent-soft px-3 py-2.5 text-sm text-accent-ink">
                🤖 AI is analysing — summarising, setting priority, matching knowledge base
                articles, and drafting a resolution. This takes a few seconds.
              </div>
            )}

            <div className="flex flex-wrap justify-end gap-3 pt-1">
              <Link to="/incidents" className="btn-secondary" aria-disabled={submitting}>
                Cancel
              </Link>
              <button type="submit" className="btn-primary" disabled={submitting}>
                {submitting ? 'Creating…' : 'Create incident'}
              </button>
            </div>
          </div>
        </form>

        <aside className="space-y-4">
          <div className="card p-5">
            <h2 className="font-bold text-ink">What happens next</h2>
            <ol className="mt-3 space-y-2.5 text-sm text-muted">
              <li>1. The incident is saved immediately.</li>
              <li>2. AI writes a summary and assigns a category and priority.</li>
              <li>3. Relevant knowledge base articles are matched and scored.</li>
              <li>4. A suggested resolution is drafted for you to review.</li>
            </ol>
            <p className="mt-3 border-t border-line-soft pt-3 text-xs text-muted">
              If the AI step fails, the incident is still created — triage fields stay pending and
              you can re-run them from the detail page.
            </p>
          </div>

          <div className="card p-5">
            <h2 className="font-bold text-ink">Need an example?</h2>
            <p className="mt-1 text-sm text-muted">Load a sample to see triage in action.</p>
            <div className="mt-3 space-y-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example.title}
                  type="button"
                  disabled={submitting}
                  onClick={() => {
                    setTitle(example.title)
                    setDescription(example.description)
                    setError(null)
                  }}
                  className="w-full rounded-control border border-line px-3 py-2 text-left text-sm
                             font-medium text-ink transition-colors hover:border-accent-line
                             hover:bg-accent-soft disabled:opacity-50"
                >
                  {example.title}
                </button>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </>
  )
}
