import { CalendarClock, CircleDollarSign, Receipt, TrendingDown } from 'lucide-react'
import { MetricCard } from '../../components/common/MetricCard'
import { PageHeader } from '../../components/common/PageHeader'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useCostsData } from '../../hooks/useCostsData'
import { usePageTitle } from '../../hooks/usePageTitle'
import { formatDateTime } from '../../utils/formatters'
import type { PaymentStatus } from '../../types/api'

export function CostsPage(): React.JSX.Element {
  usePageTitle('Optimizer · Costs')
  const data = useCostsData()
  if (data.isLoading) return <DashboardState state="loading" message="Loading local cost profiles." />
  if (data.isError || !data.costs) return <DashboardState state="error" message="Cost data could not be loaded. No estimates are shown." onRetry={() => void data.refetch()} />
  const costs = data.costs
  if (costs.profiled_server_count === 0) return <DashboardState state="empty" message="No local cost profiles are configured yet." />

  return (
    <>
      <PageHeader eyebrow="Optimizer" title="Costs" description="Local monthly profiles and upcoming payment dates. No payment provider is contacted." />
      <DashboardFreshness isFetching={data.isFetching} isStale={data.isStale} lastUpdatedAt={data.lastUpdatedAt} onRefresh={() => void data.refetch()} />
      {costs.missing_profile_count > 0 && <div className="mb-5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-xs text-warning">{costs.missing_profile_count} enabled server(s) have no cost profile. Totals cover profiled servers only.</div>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Monthly total" value={money(costs.monthly_total, costs.profiles[0]?.currency)} detail="Profiled servers" icon={CircleDollarSign} tone="cyan" />
        <MetricCard label="Annual projection" value={money(costs.annual_projected, costs.profiles[0]?.currency)} detail="Monthly × 12" icon={TrendingDown} tone="emerald" />
        <MetricCard label="Average / server" value={costs.average_per_server === null ? '—' : money(costs.average_per_server, costs.profiles[0]?.currency)} detail="Comparable currency only" icon={Receipt} tone="violet" />
        <MetricCard label="Upcoming payments" value={String(costs.upcoming.length)} detail="Next 30 days" icon={CalendarClock} tone="amber" />
      </div>
      <Surface className="mt-5 overflow-hidden"><div className="border-b border-line px-5 py-4"><h2 className="text-sm font-semibold text-copy">Payment calendar</h2><p className="mt-1 text-xs text-muted">Due soon and overdue statuses are calculated without mutating stored profiles.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[680px] text-left text-xs"><thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted"><tr><th className="px-5 py-3">Server</th><th className="px-5 py-3">Amount</th><th className="px-5 py-3">Due</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Auto renew</th></tr></thead><tbody className="divide-y divide-line/70">{costs.upcoming.map((payment) => <tr key={`${payment.server_id}-${payment.next_payment_date}`}><td className="px-5 py-3 font-medium text-copy">{payment.server_name}</td><td className="px-5 py-3 text-copy">{money(payment.amount, payment.currency)}</td><td className="px-5 py-3 text-muted">{payment.next_payment_date} ({payment.days_until_due}d)</td><td className="px-5 py-3"><PaymentBadge status={payment.payment_status} /></td><td className="px-5 py-3 text-muted">{payment.auto_renew ? 'Enabled' : 'Manual'}</td></tr>)}</tbody></table></div>{costs.upcoming.length === 0 && <p className="px-5 py-6 text-sm text-muted">No payments due in the next 30 days.</p>}</Surface>
      <Surface className="mt-5 overflow-hidden"><div className="border-b border-line px-5 py-4"><h2 className="text-sm font-semibold text-copy">Cost profiles</h2></div><div className="overflow-x-auto"><table className="w-full min-w-[680px] text-left text-xs"><thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted"><tr><th className="px-5 py-3">Server</th><th className="px-5 py-3">Provider</th><th className="px-5 py-3">Monthly</th><th className="px-5 py-3">Next payment</th></tr></thead><tbody className="divide-y divide-line/70">{costs.profiles.map((profile) => <tr key={profile.id}><td className="px-5 py-3 font-medium text-copy">{profile.server_name}</td><td className="px-5 py-3 text-muted">{profile.provider ?? '—'}</td><td className="px-5 py-3 text-copy">{money(profile.monthly_cost, profile.currency)}</td><td className="px-5 py-3 text-muted">{profile.next_payment_date ?? 'Not scheduled'} · {formatDateTime(profile.updated_at)}</td></tr>)}</tbody></table></div></Surface>
    </>
  )
}

function money(value: number, currency = 'USD'): string { return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value) }

function PaymentBadge({ status }: { status: PaymentStatus }): React.JSX.Element { const style: Record<PaymentStatus, string> = { paid: 'text-success bg-success/10', pending: 'text-muted bg-panel-raised', due_soon: 'text-warning bg-warning/10', overdue: 'text-danger bg-danger/10', cancelled: 'text-muted bg-panel-raised' }; return <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase ${style[status]}`}>{status.replace('_', ' ')}</span> }
