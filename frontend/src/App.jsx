import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AllIncidents from './pages/AllIncidents'
import Ongoing from './pages/Ongoing'
import Completed from './pages/Completed'
import CreateIncident from './pages/CreateIncident'
import IncidentDetail from './pages/IncidentDetail'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        {/* "new" is declared before ":id" so it is matched as a literal segment
            rather than as an incident id. */}
        <Route path="incidents" element={<AllIncidents />} />
        <Route path="incidents/new" element={<CreateIncident />} />
        <Route path="incidents/ongoing" element={<Ongoing />} />
        <Route path="incidents/completed" element={<Completed />} />
        <Route path="incidents/:id" element={<IncidentDetail />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
