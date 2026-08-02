import { AlertTriangle, LoaderCircle, RefreshCw } from 'lucide-react'
import { Surface } from '../common/Surface'

interface DashboardStateProps {
  state: 'loading' | 'empty' | 'error'
  message?: string
  onRetry?: () => void
}

const copy = {
  loading: {
    title: 'Loading live dashboard data',
    description: 'Reading the latest read-only metrics from SuperFlash API.',
  },
  empty: {
    title: 'No monitoring data available',
    description: 'The API responded, but there are no server samples to display yet.',
  },
  error: {
    title: 'Live dashboard unavailable',
    description: 'No live metrics are shown because the API request failed.',
  },
} as const

export function DashboardState({ state, message, onRetry }: DashboardStateProps): React.JSX.Element {
  const content = copy[state]

  return (
    <Surface className="flex min-h-[320px] flex-col items-center justify-center p-8 text-center">
      {state === 'loading' ? (
        <LoaderCircle className="animate-spin text-brand" size={28} />
      ) : (
        <AlertTriangle className="text-warning" size={28} />
      )}
      <h2 className="mt-5 text-lg font-semibold text-copy">{content.title}</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-muted">
        {message ?? content.description}
      </p>
      {state === 'error' && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 inline-flex items-center gap-2 rounded-xl border border-line bg-panel-raised px-4 py-2.5 text-xs font-semibold text-copy transition hover:border-slate-600"
        >
          <RefreshCw size={14} />
          Retry
        </button>
      )}
    </Surface>
  )
}
