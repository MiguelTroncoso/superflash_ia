import { BellRing, Filter, ShieldAlert, TriangleAlert } from 'lucide-react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { usePageTitle } from '../../hooks/usePageTitle'
import { alertSummary } from '../../utils/mockData'

const alerts = [
  {
    title: 'Network utilization approaching threshold',
    target: 'sf-edge-03',
    description: 'Output traffic is at 82% of the simulated capacity.',
    time: '18 min ago',
    state: 'warning' as const,
  },
  {
    title: 'Memory pressure observation',
    target: 'sf-edge-03',
    description: 'Memory utilization crossed the informational threshold.',
    time: '42 min ago',
    state: 'warning' as const,
  },
]

export function AlertsPage(): React.JSX.Element {
  usePageTitle('Alerts')

  return (
    <>
      <PageHeader
        eyebrow="Signal center"
        title="Alerts"
        description="Read-only alert placeholders. Notification delivery and persistence will be introduced with API integration."
        action={
          <button className="inline-flex items-center gap-2 rounded-xl border border-line bg-panel px-4 py-2.5 text-xs font-semibold text-copy hover:border-slate-600 hover:bg-panel-raised">
            <Filter size={15} /> Filter
          </button>
        }
      />
      <div className="grid gap-4 md:grid-cols-3">
        {alertSummary.map((item) => (
          <Surface key={item.label} className="flex items-center justify-between p-5">
            <div>
              <p className="text-sm text-muted">{item.label}</p>
              <p className="mt-3 text-3xl font-semibold text-copy">{item.count}</p>
            </div>
            <span
              className={
                item.state === 'critical'
                  ? 'rounded-xl bg-danger/10 p-3 text-danger'
                  : item.state === 'warning'
                    ? 'rounded-xl bg-warning/10 p-3 text-warning'
                    : 'rounded-xl bg-success/10 p-3 text-success'
              }
            >
              {item.state === 'critical' ? (
                <ShieldAlert size={22} />
              ) : item.state === 'warning' ? (
                <TriangleAlert size={22} />
              ) : (
                <BellRing size={22} />
              )}
            </span>
          </Surface>
        ))}
      </div>
      <div className="mt-5 space-y-3">
        {alerts.map((alert) => (
          <Surface
            key={alert.title}
            className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center"
          >
            <span className="rounded-xl bg-warning/10 p-3 text-warning">
              <TriangleAlert size={21} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold text-copy">{alert.title}</h2>
                <StatusBadge state={alert.state} compact />
              </div>
              <p className="mt-1 text-xs text-muted">{alert.description}</p>
              <p className="mt-2 text-[11px] text-muted">
                {alert.target} · {alert.time}
              </p>
            </div>
            <button className="text-left text-xs font-semibold text-brand hover:text-cyan-200 sm:text-right">
              View signal
            </button>
          </Surface>
        ))}
      </div>
    </>
  )
}
