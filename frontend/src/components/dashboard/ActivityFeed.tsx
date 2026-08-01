import { StatusBadge } from '../common/StatusBadge'
import { Surface } from '../common/Surface'
import type { AlertsResponse, CollectionStatusResponse } from '../../types/api'
import type { HealthState } from '../../types/monitoring'
import { formatDateTime } from '../../utils/formatters'

interface ActivityFeedProps {
  alerts: AlertsResponse['alerts']
  collectionStatus: CollectionStatusResponse
}

export function ActivityFeed({ alerts, collectionStatus }: ActivityFeedProps): React.JSX.Element {
  const items = [
    ...(collectionStatus.finished_at
      ? [
          {
            id: 'collection',
            title: 'Collection cycle completed',
            description: `${collectionStatus.inserted} samples inserted · ${collectionStatus.errors.length} errors`,
            time: formatDateTime(collectionStatus.finished_at),
            state: collectionStatus.status === 'error' ? ('critical' as const) : ('healthy' as const),
          },
        ]
      : []),
    ...alerts.slice(0, 3).map((alert) => ({
      id: String(alert.id),
      title: alert.message,
      description: `${alert.server_name} · ${alert.status}`,
      time: formatDateTime(alert.last_seen_at ?? alert.collected_at),
      state: alertState(alert.severity),
    })),
  ]

  return (
    <Surface className="h-full p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-copy">Recent activity</p>
          <p className="mt-1 text-xs text-muted">Latest collection and alert events</p>
        </div>
      </div>
      <div className="mt-5 divide-y divide-line/70">
        {items.length === 0 ? (
          <p className="py-3 text-xs text-muted">No current events</p>
        ) : (
          items.map((item) => (
          <div key={item.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
            <StatusBadge state={item.state} compact />
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-copy">{item.title}</p>
              <p className="mt-1 truncate text-[11px] text-muted">{item.description}</p>
            </div>
            <time className="whitespace-nowrap text-[10px] text-muted">{item.time}</time>
          </div>
          ))
        )}
      </div>
    </Surface>
  )
}

function alertState(severity: AlertsResponse['alerts'][number]['severity']): HealthState {
  if (severity === 'critical') return 'critical'
  if (severity === 'warning') return 'warning'
  return 'healthy'
}
