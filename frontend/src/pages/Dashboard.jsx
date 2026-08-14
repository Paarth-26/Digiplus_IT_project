import { Link } from 'react-router-dom'
import { useIncidents } from '../context/IncidentsContext'
import StatCard from '../components/StatCard'
import PriorityDistribution from '../components/PriorityDistribution'
import IncidentCard from '../components/IncidentCard'
import { CardSkeleton, EmptyState, ErrorState, PageHeader } from '../components/states'

export default function Dashboard() {
  const { incidents, counts, loading, error, refresh } = useIncidents()

  // Newest first, by id -- created_at ties are common when a batch is seeded.
  const recent = incidents.slice().sort((a, b) => b.id - a.id).slice(0, 5)

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Board health at a glance.">
        <button type="button" className="btn-secondary" onClick={refresh}>
          🔄 Refresh
        </button>
        <Link to="/incidents/new" className="btn-primary">
          ➕ New incident
        </Link>
      </PageHeader>

      {error ? (
        <ErrorState error={error} />
      ) : loading ? (
        <CardSkeleton count={4} />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Total" value={counts.all} icon="🗂️" to="/incidents" delay={0} />
            <StatCard
              label="Ongoing"
              value={counts.ongoing}
              icon="🔄"
              to="/incidents/ongoing"
              tone="accent"
              delay={60}
            />
            <StatCard
              label="Completed"
              value={counts.completed}
              icon="✅"
              to="/incidents/completed"
              delay={120}
            />
            <StatCard label="Awaiting AI" value={counts.awaitingAi} icon="⏳" delay={180} />
          </div>

          {incidents.length === 0 ? (
            <EmptyState
              title="No incidents yet"
              hint="Log the first one and AI triage will summarise it, set a priority, and match knowledge base articles automatically."
              action={{ to: '/incidents/new', label: '➕ Log the first incident' }}
            />
          ) : (
            <>
              <PriorityDistribution incidents={incidents} />

              <section>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-bold text-ink">Recent activity</h2>
                  <Link
                    to="/incidents"
                    className="text-sm font-semibold text-accent hover:text-accent-hover"
                  >
                    View all →
                  </Link>
                </div>
                <div className="space-y-3">
                  {recent.map((incident, index) => (
                    <IncidentCard key={incident.id} incident={incident} delay={index * 40} />
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      )}
    </>
  )
}
