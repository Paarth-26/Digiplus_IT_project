import { EmptyState } from '../components/states'

export default function NotFound() {
  return (
    <EmptyState
      emoji="🧭"
      title="Page not found"
      hint="That route doesn't exist."
      action={{ to: '/', label: 'Back to dashboard' }}
    />
  )
}
