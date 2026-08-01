import { ArrowDown, ArrowUp, HardDrive, Network, Server, Workflow } from 'lucide-react'
import { PageHeader } from '../../components/common/PageHeader'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useBalanceData } from '../../hooks/useBalanceData'
import { usePageTitle } from '../../hooks/usePageTitle'
import { formatDateTime, formatNullablePercent, formatNullableThroughput } from '../../utils/formatters'

export function BalancePage(): React.JSX.Element {
  usePageTitle('Balance')
  const data = useBalanceData()

  if (data.isLoading) return <DashboardState state="loading" message="Loading infrastructure balance from the API." />
  if (data.isError || !data.balance) return <DashboardState state="error" message="Infrastructure balance could not be loaded." onRetry={() => void data.refetch()} />
  const balance = data.balance

  return (
    <>
      <PageHeader eyebrow="Capacity planning" title="Balance" description="Read-only aggregates calculated from the latest collected server metrics." />
      <DashboardFreshness isFetching={data.isFetching} isStale={data.isStale} lastUpdatedAt={data.lastUpdatedAt} onRefresh={() => void data.refetch()} />
      {balance.server_count === 0 ? <DashboardState state="empty" message="No enabled servers are available for balance calculations." /> : <>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard label="Average CPU" value={formatNullablePercent(balance.average_cpu_percent)} icon={Workflow} />
          <SummaryCard label="Average RAM" value={formatNullablePercent(balance.average_memory_percent)} icon={Server} />
          <SummaryCard label="Average network" value={formatNullableThroughput(balance.average_network_mbps)} icon={Network} />
          <SummaryCard label="Average disk" value={formatNullablePercent(balance.average_disk_percent)} icon={HardDrive} />
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-3"><CapacityCard label="Capacity total" value={balance.capacity_total_mbps} icon={Server} /><CapacityCard label="Capacity used" value={balance.capacity_used_mbps} icon={ArrowUp} /><CapacityCard label="Capacity free" value={balance.capacity_free_mbps} icon={ArrowDown} /></div>
        <div className="mt-5 grid gap-5 xl:grid-cols-2">
          <Surface className="p-5"><h2 className="text-sm font-semibold text-copy">Most loaded server</h2><p className="mt-4 text-lg font-semibold text-copy">{balance.most_loaded?.name ?? 'No sampled server'}</p><p className="mt-2 text-xs text-muted">{balance.most_loaded ? `${formatNullableThroughput(balance.most_loaded.output_mbps)} · ${formatNullablePercent(balance.most_loaded.utilization_percent)}` : 'No data available'}</p></Surface>
          <Surface className="p-5"><h2 className="text-sm font-semibold text-copy">Least utilized server</h2><p className="mt-4 text-lg font-semibold text-copy">{balance.least_utilized?.name ?? 'No sampled server'}</p><p className="mt-2 text-xs text-muted">{balance.least_utilized ? `${formatNullableThroughput(balance.least_utilized.output_mbps)} · ${formatNullablePercent(balance.least_utilized.utilization_percent)}` : 'No data available'}</p></Surface>
        </div>
        <Surface className="mt-5 overflow-hidden"><div className="flex items-center justify-between border-b border-line px-5 py-4"><h2 className="text-sm font-semibold text-copy">Server capacity view</h2><span className="text-xs text-muted">{balance.sampled_server_count} sampled · {formatDateTime(balance.generated_at)}</span></div><div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-xs"><thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted"><tr><th className="px-5 py-3">Server</th><th className="px-5 py-3">Output</th><th className="px-5 py-3">Capacity</th><th className="px-5 py-3">Utilization</th></tr></thead><tbody className="divide-y divide-line/70">{balance.servers.map((server) => <tr key={server.server_id}><td className="px-5 py-3 text-copy">{server.name}</td><td className="px-5 py-3 text-muted">{formatNullableThroughput(server.output_mbps)}</td><td className="px-5 py-3 text-muted">{formatNullableThroughput(server.capacity_mbps)}</td><td className="px-5 py-3 text-copy">{formatNullablePercent(server.utilization_percent)}</td></tr>)}</tbody></table></div></Surface>
      </>}
    </>
  )
}

function SummaryCard({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Workflow }): React.JSX.Element { return <Surface className="p-5"><div className="flex items-center justify-between"><p className="text-sm text-muted">{label}</p><Icon className="text-brand" size={18} /></div><p className="mt-4 text-2xl font-semibold text-copy">{value}</p></Surface> }
function CapacityCard({ label, value, icon: Icon }: { label: string; value: number; icon: typeof Server }): React.JSX.Element { return <Surface className="p-5"><div className="flex items-center gap-2 text-sm text-muted"><Icon size={17} className="text-brand" />{label}</div><p className="mt-4 text-2xl font-semibold text-copy">{formatNullableThroughput(value)}</p></Surface> }
