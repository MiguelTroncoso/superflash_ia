import { Radio } from 'lucide-react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useChannelsData } from '../../hooks/useChannelsData'
import { usePageTitle } from '../../hooks/usePageTitle'
import { formatCompactNumber, formatDateTime, formatNullableThroughput } from '../../utils/formatters'

export function ChannelsPage(): React.JSX.Element {
  usePageTitle('Channels')
  const data = useChannelsData()

  if (data.isLoading) {
    return <DashboardState state="loading" message="Loading channels and their latest read-only samples." />
  }
  if (data.isError) {
    return <DashboardState state="error" message="The channel inventory could not be loaded." onRetry={() => void data.refetch()} />
  }

  const activeRows = data.rows.filter(({ channel }) => channel.enabled)
  const viewerCount = activeRows.reduce((total, { metric }) => total + (metric?.viewers ?? 0), 0)
  const sampledRows = data.rows.filter(({ metric }) => metric !== null)
  const avgBitrate = sampledRows.length
    ? sampledRows.reduce((total, { metric }) => total + (metric?.bitrate_mbps ?? 0), 0) / sampledRows.length
    : null

  return (
    <>
      <PageHeader
        eyebrow="Streaming inventory"
        title="Channels"
        description="Registered channel relationships and their latest collected samples. Xtream integration is not enabled."
      />
      <DashboardFreshness
        isFetching={data.isFetching}
        isStale={data.isStale}
        lastUpdatedAt={data.lastUpdatedAt}
        onRefresh={() => void data.refetch()}
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Enabled channels" value={String(activeRows.length)} detail={`${data.rows.length} registered`} />
        <SummaryCard label="Current viewers" value={formatCompactNumber(viewerCount)} detail={sampledRows.length ? 'From latest samples' : 'No samples available'} />
        <SummaryCard label="Average bitrate" value={avgBitrate === null ? '—' : `${avgBitrate.toFixed(1)} Mbps`} detail={avgBitrate === null ? 'No samples available' : 'From latest samples'} />
      </div>
      <Surface className="mt-5 overflow-hidden">
        {data.rows.length === 0 ? (
          <DashboardState state="empty" message="No channels are registered in the monitor inventory." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px] text-left text-sm">
              <thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted">
                <tr><th className="px-5 py-4">Channel</th><th className="px-5 py-4">Category</th><th className="px-5 py-4">Viewers</th><th className="px-5 py-4">Bitrate</th><th className="px-5 py-4">Collected</th><th className="px-5 py-4 text-right">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-line/70">
                {data.rows.map(({ channel, metric, state }) => (
                  <tr key={channel.id} className="transition hover:bg-panel-raised/40">
                    <td className="px-5 py-4"><div className="flex items-center gap-3"><span className="rounded-lg bg-violet-400/10 p-2 text-violet-300"><Radio size={16} /></span><span><span className="block font-semibold text-copy">{channel.name}</span><span className="mt-1 block text-[11px] text-muted">{channel.external_id}</span></span></div></td>
                    <td className="px-5 py-4 text-muted">{channel.category ?? '—'}</td>
                    <td className="px-5 py-4 text-copy">{metric ? formatCompactNumber(metric.viewers) : '—'}</td>
                    <td className="px-5 py-4 text-muted">{formatNullableThroughput(metric?.bitrate_mbps ?? null)}</td>
                    <td className="px-5 py-4 text-muted">{formatDateTime(metric?.collected_at ?? null)}</td>
                    <td className="px-5 py-4 text-right"><StatusBadge state={state} label={metric?.status ?? (channel.enabled ? 'no data' : 'disabled')} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Surface>
    </>
  )
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail: string }): React.JSX.Element {
  return <Surface className="p-5"><p className="text-sm text-muted">{label}</p><p className="mt-3 text-3xl font-semibold text-copy">{value}</p><p className="mt-1 text-xs text-muted">{detail}</p></Surface>
}
