import {
  BellRing,
  Boxes,
  CircleGauge,
  HardDrive,
  MemoryStick,
  Network,
  Server,
  Users,
} from 'lucide-react'
import { MetricCard } from '../common/MetricCard'
import { Surface } from '../common/Surface'
import { ActivityFeed } from './ActivityFeed'
import { StatusOverview } from './StatusOverview'
import { SystemLoadChart } from '../charts/SystemLoadChart'
import { TrafficChart } from '../charts/TrafficChart'
import { ActivityTable } from '../tables/ActivityTable'
import { DashboardFreshness } from './DashboardFreshness'
import type { CollectionStatusResponse, HealthResponse } from '../../types/api'
import type { DashboardServerRow, DashboardSummary } from '../../utils/dashboardMetrics'
import { formatNullablePercent, formatNullableThroughput } from '../../utils/formatters'

interface DashboardContentProps {
  summary: DashboardSummary
  rows: DashboardServerRow[]
  health: HealthResponse
  collectionStatus: CollectionStatusResponse
  isFetching: boolean
  isStale: boolean
  lastUpdatedAt: number
  onRefresh: () => void
}

export function DashboardContent({
  summary,
  rows,
  health,
  collectionStatus,
  isFetching,
  isStale,
  lastUpdatedAt,
  onRefresh,
}: DashboardContentProps): React.JSX.Element {
  const healthyServers = rows.filter((row) => row.state === 'healthy').length
  const warningServers = rows.length - healthyServers
  const metrics = [
    {
      label: 'CPU average',
      value: formatNullablePercent(summary.avgCpuPercent),
      detail: `${summary.serverCount} enabled servers`,
      tone: 'cyan' as const,
      icon: CircleGauge,
    },
    {
      label: 'Memory average',
      value: formatNullablePercent(summary.avgMemoryPercent),
      detail: 'Latest overview aggregate',
      tone: 'violet' as const,
      icon: MemoryStick,
    },
    {
      label: 'Disk average',
      value: formatNullablePercent(summary.avgDiskPercent),
      detail: summary.avgDiskPercent === null ? 'No disk samples returned' : 'Latest server samples',
      tone: 'amber' as const,
      icon: HardDrive,
    },
    {
      label: 'Network IN',
      value: formatNullableThroughput(summary.totalInputMbps),
      detail: 'Latest overview aggregate',
      tone: 'emerald' as const,
      icon: Network,
    },
    {
      label: 'Network OUT',
      value: formatNullableThroughput(summary.totalOutputMbps),
      detail: 'Latest overview aggregate',
      tone: 'cyan' as const,
      icon: Network,
    },
    {
      label: 'Servers',
      value: String(summary.serverCount),
      detail: `${healthyServers} healthy · ${warningServers} attention`,
      tone: 'slate' as const,
      icon: Server,
    },
    {
      label: 'Channels',
      value: String(summary.channelCount),
      detail: 'API inventory',
      tone: 'violet' as const,
      icon: Boxes,
    },
    {
      label: 'Alerts',
      value: String(summary.alertCount),
      detail: summary.alertCount > 0 ? 'Needs attention' : 'No active alerts',
      tone: 'rose' as const,
      icon: BellRing,
    },
    {
      label: 'General status',
      value: summary.generalLabel,
      detail: summary.collectionLabel,
      tone: summary.generalState === 'healthy' ? ('emerald' as const) : ('amber' as const),
      icon: Users,
    },
  ]

  return (
    <>
      <DashboardFreshness
        isFetching={isFetching}
        isStale={isStale}
        lastUpdatedAt={lastUpdatedAt}
        onRefresh={onRefresh}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <Surface className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-copy">System load</p>
              <p className="mt-1 text-xs text-muted">Historical endpoint not available yet</p>
            </div>
            <span className="rounded-lg border border-line bg-panel-raised px-2.5 py-1.5 text-[10px] font-medium text-muted">
              Simulated data
            </span>
          </div>
          <div className="mt-4">
            <SystemLoadChart />
          </div>
        </Surface>
        <Surface className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-copy">Network traffic</p>
              <p className="mt-1 text-xs text-muted">Historical endpoint not available yet</p>
            </div>
            <span className="rounded-lg border border-line bg-panel-raised px-2.5 py-1.5 text-[10px] font-medium text-muted">
              Simulated data
            </span>
          </div>
          <div className="mt-4">
            <TrafficChart />
          </div>
        </Surface>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <StatusOverview
          health={health}
          collectionStatus={collectionStatus}
          summary={summary}
        />
        <ActivityFeed />
      </div>

      <div className="mt-5">
        <ActivityTable rows={rows} />
      </div>
    </>
  )
}
