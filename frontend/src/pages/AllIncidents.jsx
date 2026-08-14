import { Link } from 'react-router-dom'
import { useIncidents } from '../context/IncidentsContext'
import IncidentList from '../components/IncidentList'
import { PageHeader } from '../components/states'

export default function AllIncidents() {
  const { incidents, loading, error, refresh } = useIncidents()

  return (
    <>
      <PageHeader title="All incidents" subtitle="Every incident on the board.">
        <button type="button" className="btn-secondary" onClick={refresh}>
          🔄 Refresh
        </button>
        <Link to="/incidents/new" className="btn-primary">
          ➕ New incident
        </Link>
      </PageHeader>

      <IncidentList
        incidents={incidents}
        loading={loading}
        error={error}
        emptyState={{
          title: 'No incidents yet',
          hint: 'Log the first one to get started.',
          action: { to: '/incidents/new', label: '➕ Log the first incident' },
        }}
      />
    </>
  )
}
