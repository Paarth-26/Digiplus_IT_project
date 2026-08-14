import { Link } from 'react-router-dom'
import { ONGOING_STATUSES, useIncidents } from '../context/IncidentsContext'
import IncidentList from '../components/IncidentList'
import { PageHeader } from '../components/states'

export default function Ongoing() {
  const { incidents, loading, error, refresh } = useIncidents()

  // "Ongoing" spans two statuses, which the list endpoint can't express in one
  // call -- so the split happens here, over the board already in memory.
  const ongoing = incidents.filter((i) => ONGOING_STATUSES.includes(i.status))

  return (
    <>
      <PageHeader title="Ongoing" subtitle="Open and in-progress incidents still needing work.">
        <button type="button" className="btn-secondary" onClick={refresh}>
          🔄 Refresh
        </button>
        <Link to="/incidents/new" className="btn-primary">
          ➕ New incident
        </Link>
      </PageHeader>

      <IncidentList
        incidents={ongoing}
        loading={loading}
        error={error}
        emptyState={{
          emoji: '🎉',
          title: 'Nothing ongoing',
          hint: 'Every incident on the board has been resolved.',
          action: { to: '/incidents/completed', label: 'View completed' },
        }}
      />
    </>
  )
}
