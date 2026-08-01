import { Radio, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useChannelsData } from '../../hooks/useChannelsData'
import { usePageTitle } from '../../hooks/usePageTitle'
import { formatCompactNumber, formatDateTime, formatNullableThroughput } from '../../utils/formatters'

type SortKey = 'name' | 'category' | 'server' | 'viewers' | 'bitrate' | 'output' | 'status' | 'last_updated_at'

const PAGE_SIZE = 50

export function ChannelsPage(): React.JSX.Element {
  usePageTitle('Channels')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [enabled, setEnabled] = useState('all')
  const [sortBy, setSortBy] = useState<SortKey>('name')
  const [ascending, setAscending] = useState(true)
  const [page, setPage] = useState(1)
  const data = useChannelsData({
    page,
    page_size: PAGE_SIZE,
    search: search.trim() || undefined,
    category: category.trim() || undefined,
    enabled: enabled === 'all' ? undefined : enabled === 'true',
    sort_by: sortBy,
    sort_order: ascending ? 'asc' : 'desc',
  })

  useEffect(() => {
    setPage(1)
  }, [category, enabled, search])

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
  const pageCount = Math.max(1, data.totalPages)

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
        <SummaryCard label="Registered channels" value={String(data.total)} detail="Backend total" />
        <SummaryCard label="Current viewers" value={formatCompactNumber(viewerCount)} detail={sampledRows.length ? 'Current page samples' : 'No samples available'} />
        <SummaryCard label="Average bitrate" value={avgBitrate === null ? '—' : `${avgBitrate.toFixed(1)} Mbps`} detail={avgBitrate === null ? 'No samples available' : 'Current page samples'} />
      </div>
      <Surface className="mt-5 overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-5 lg:flex-row lg:items-center">
          <label className="relative min-w-0 flex-1">
            <Search size={15} className="pointer-events-none absolute left-3 top-3 text-muted" />
            <input
              value={search}
              onChange={(event) => { setSearch(event.target.value); setPage(1) }}
              placeholder="Search channel, category or server"
              className="w-full rounded-xl border border-line bg-panel-raised py-2.5 pl-9 pr-3 text-xs text-copy outline-none placeholder:text-muted focus:border-brand"
            />
          </label>
          <input
            value={category}
            onChange={(event) => { setCategory(event.target.value); setPage(1) }}
            placeholder="Category"
            className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none placeholder:text-muted focus:border-brand"
          />
          <FilterSelect value={enabled} onChange={(value) => { setEnabled(value); setPage(1) }} options={['all', 'true', 'false']} label="Enabled" />
          <FilterSelect value={sortBy} onChange={(value) => { setSortBy(value as SortKey); setAscending(true); setPage(1) }} options={['name', 'category', 'server', 'viewers', 'bitrate', 'output', 'status']} label="Sort" />
          <button type="button" onClick={() => { setAscending((value) => !value); setPage(1) }} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy">
            {ascending ? 'Ascending' : 'Descending'}
          </button>
        </div>
        {data.rows.length === 0 ? (
          <DashboardState state="empty" message="No channels match the current filters." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted">
                <tr><th className="px-5 py-4">Channel</th><th className="px-5 py-4">Category</th><th className="px-5 py-4">Server</th><th className="px-5 py-4">Viewers</th><th className="px-5 py-4">Bitrate</th><th className="px-5 py-4">Output</th><th className="px-5 py-4">Collected</th><th className="px-5 py-4 text-right">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-line/70">
                {data.rows.map(({ channel, metric, state }) => (
                  <tr key={channel.id} className="transition hover:bg-panel-raised/40">
                    <td className="px-5 py-4"><div className="flex items-center gap-3"><span className="rounded-lg bg-violet-400/10 p-2 text-violet-300"><Radio size={16} /></span><span><span className="block font-semibold text-copy">{channel.name}</span><span className="mt-1 block text-[11px] text-muted">{channel.external_id}</span></span></div></td>
                    <td className="px-5 py-4 text-muted">{channel.category ?? '—'}</td>
                    <td className="px-5 py-4 text-muted">{channel.current_server_name ?? 'Unassigned'}</td>
                    <td className="px-5 py-4 text-copy">{metric ? formatCompactNumber(metric.viewers) : '—'}</td>
                    <td className="px-5 py-4 text-muted">{formatNullableThroughput(metric?.bitrate_mbps ?? null)}</td>
                    <td className="px-5 py-4 text-muted">{formatNullableThroughput(metric?.estimated_output_mbps ?? null)}</td>
                    <td className="px-5 py-4 text-muted">{formatDateTime(metric?.collected_at ?? null)}</td>
                    <td className="px-5 py-4 text-right"><StatusBadge state={state} label={metric?.status ?? (channel.enabled ? 'no data' : 'disabled')} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-muted">
          <span>{data.total} channels · page {data.page} of {pageCount}</span>
          <div className="flex gap-2">
            <button disabled={data.page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">Previous</button>
            <button disabled={data.page >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">Next</button>
          </div>
        </div>
      </Surface>
    </>
  )
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail: string }): React.JSX.Element {
  return <Surface className="p-5"><p className="text-sm text-muted">{label}</p><p className="mt-3 text-3xl font-semibold text-copy">{value}</p><p className="mt-1 text-xs text-muted">{detail}</p></Surface>
}

function FilterSelect({ value, onChange, options, label }: { value: string; onChange: (value: string) => void; options: string[]; label: string }): React.JSX.Element {
  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none focus:border-brand">
        {options.map((option) => <option key={option} value={option}>{option === 'all' ? `All ${label}` : option}</option>)}
      </select>
    </label>
  )
}
