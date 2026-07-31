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
import { PageHeader } from '../../components/common/PageHeader'
import { MetricCard } from '../../components/common/MetricCard'
import { Surface } from '../../components/common/Surface'
import { ActivityFeed } from '../../components/dashboard/ActivityFeed'
import { StatusOverview } from '../../components/dashboard/StatusOverview'
import { SystemLoadChart } from '../../components/charts/SystemLoadChart'
import { TrafficChart } from '../../components/charts/TrafficChart'
import { ActivityTable } from '../../components/tables/ActivityTable'
import { usePageTitle } from '../../hooks/usePageTitle'

const metrics = [
  {
    label: 'CPU usage',
    value: '62.4%',
    detail: 'Across 5 servers',
    trend: '4.8%',
    trendPositive: false,
    tone: 'cyan' as const,
    icon: CircleGauge,
  },
  {
    label: 'Memory',
    value: '68.1%',
    detail: '21.6 GB / 32 GB',
    trend: '2.1%',
    trendPositive: false,
    tone: 'violet' as const,
    icon: MemoryStick,
  },
  {
    label: 'Disk usage',
    value: '54.8%',
    detail: '1.42 TB allocated',
    trend: '0.6%',
    trendPositive: false,
    tone: 'amber' as const,
    icon: HardDrive,
  },
  {
    label: 'Network IN',
    value: '24.8 Mbps',
    detail: 'Peak 31.4 Mbps',
    trend: '8.3%',
    trendPositive: true,
    tone: 'emerald' as const,
    icon: Network,
  },
  {
    label: 'Network OUT',
    value: '146.2 Mbps',
    detail: 'Peak 168.0 Mbps',
    trend: '6.7%',
    trendPositive: true,
    tone: 'cyan' as const,
    icon: Network,
  },
  {
    label: 'Servers',
    value: '5',
    detail: '4 healthy · 1 warning',
    tone: 'slate' as const,
    icon: Server,
  },
  {
    label: 'Channels',
    value: '24',
    detail: 'All mock sources',
    tone: 'violet' as const,
    icon: Boxes,
  },
  { label: 'Alerts', value: '2', detail: 'Needs attention', tone: 'rose' as const, icon: BellRing },
  {
    label: 'General status',
    value: 'Healthy',
    detail: '94% operational score',
    tone: 'emerald' as const,
    icon: Users,
  },
]

export function DashboardPage(): React.JSX.Element {
  usePageTitle('Dashboard')

  return (
    <>
      <PageHeader
        eyebrow="Operations center"
        title="Good afternoon, Monitor team"
        description="A simulated read-only view of the SuperFlash infrastructure. Real API integration will be added in a later phase."
        action={
          <button className="rounded-xl border border-line bg-panel px-4 py-2.5 text-xs font-semibold text-copy transition hover:border-slate-600 hover:bg-panel-raised">
            Last 24 hours <span className="ml-2 text-muted">⌄</span>
          </button>
        }
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
              <p className="mt-1 text-xs text-muted">Average utilization over the last 24 hours</p>
            </div>
            <span className="rounded-lg border border-line bg-panel-raised px-2.5 py-1.5 text-[10px] font-medium text-muted">
              Mock data
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
              <p className="mt-1 text-xs text-muted">Inbound and outbound throughput</p>
            </div>
            <span className="rounded-lg border border-line bg-panel-raised px-2.5 py-1.5 text-[10px] font-medium text-muted">
              Mbps
            </span>
          </div>
          <div className="mt-4">
            <TrafficChart />
          </div>
        </Surface>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <StatusOverview />
        <ActivityFeed />
      </div>

      <div className="mt-5">
        <ActivityTable />
      </div>
    </>
  )
}
