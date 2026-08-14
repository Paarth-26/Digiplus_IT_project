import { useIncidents } from '../context/IncidentsContext'
import IncidentList from '../components/IncidentList'
import { PageHeader } from '../components/states'

export default function Completed() {
  const { incidents, loading, error, refresh } = useIncidents()

  const completed = incidents.filter((i) => i.status === 'resolved')

  return (
    <>
      <PageHeader title="Completed" subtitle="Resolved incidents and the notes they closed with.">
        <button type="button" className="btn-secondary" onClick={refresh}>
          🔄 Refresh
        </button>
      </PageHeader>

      <IncidentList
        incidents={completed}
        loading={loading}
        error={error}
        emptyState={{
          emoji: '📭',
          title: 'Nothing completed yet',
          hint: 'Resolved incidents will appear here once you close one out.',
          action: { to: '/incidents/ongoing', label: 'View ongoing' },
        }}
      />
    </>
  )
}
