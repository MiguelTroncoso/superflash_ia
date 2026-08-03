import { CalendarClock, Radio, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useChannelsData } from '../../hooks/useChannelsData'
import { usePageTitle } from '../../hooks/usePageTitle'
import type { ApiChannelType, ChannelListItem } from '../../types/api'
import { formatCompactNumber, formatDateTime, formatNullableThroughput } from '../../utils/formatters'

type SortKey = 'name' | 'category' | 'server' | 'viewers' | 'bitrate' | 'output' | 'status' | 'last_updated_at'
type ChannelTypeFilter = 'all' | ApiChannelType

const PAGE_SIZE = 50
const CHANNEL_TYPES: ChannelTypeFilter[] = ['all', 'event', 'temporary', 'permanent', 'scheduled', 'archived']

export function ChannelsPage(): React.JSX.Element {
  usePageTitle('Channels')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [serverId, setServerId] = useState('')
  const [channelType, setChannelType] = useState<ChannelTypeFilter>('all')
  const [active, setActive] = useState('all')
  const [eventStartFrom, setEventStartFrom] = useState('')
  const [eventStartTo, setEventStartTo] = useState('')
  const [enabled, setEnabled] = useState('all')
  const [sortBy, setSortBy] = useState<SortKey>('name')
  const [ascending, setAscending] = useState(true)
  const [page, setPage] = useState(1)
  const parsedServerId = /^\d+$/.test(serverId) ? Number(serverId) : undefined
  const data = useChannelsData({
    page,
    page_size: PAGE_SIZE,
    search: search.trim() || undefined,
    category: category.trim() || undefined,
    category_id: categoryId.trim() || undefined,
    source_id: sourceId.trim() || undefined,
    server_id: parsedServerId,
    channel_type: channelType === 'all' ? undefined : channelType,
    active: active === 'all' ? undefined : active === 'true',
    event_start_from: eventStartFrom ? `${eventStartFrom}T00:00:00Z` : undefined,
    event_start_to: eventStartTo ? `${eventStartTo}T23:59:59Z` : undefined,
    enabled: enabled === 'all' ? undefined : enabled === 'true',
    sort_by: sortBy,
    sort_order: ascending ? 'asc' : 'desc',
  })

  useEffect(() => {
    setPage(1)
  }, [active, category, categoryId, enabled, eventStartFrom, eventStartTo, search, serverId, sourceId, channelType])

  if (data.isLoading) {
    return <DashboardState state="loading" message="Loading dynamic channels and their latest read-only samples." />
  }
  if (data.isError) {
    return <DashboardState state="error" message="The channel inventory could not be loaded." onRetry={() => void data.refetch()} />
  }

  const activeRows = data.rows.filter(({ channel }) => channel.active)
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
        description="Dynamic channel inventory with event lifecycle, source identity and latest collected samples."
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
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-5">
          <label className="relative min-w-[220px] flex-1">
            <Search size={15} className="pointer-events-none absolute left-3 top-3 text-muted" />
            <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Search channel, category or server" className="w-full rounded-xl border border-line bg-panel-raised py-2.5 pl-9 pr-3 text-xs text-copy outline-none placeholder:text-muted focus:border-brand" />
          </label>
          <FilterInput value={category} onChange={setCategory} placeholder="Category" />
          <FilterInput value={categoryId} onChange={setCategoryId} placeholder="Category ID" />
          <FilterInput value={sourceId} onChange={setSourceId} placeholder="Xtream source" />
          <FilterInput value={serverId} onChange={(value) => setServerId(value.replace(/\D/g, ''))} placeholder="Server ID" inputMode="numeric" />
          <FilterSelect value={channelType} onChange={(value) => setChannelType(value as ChannelTypeFilter)} options={CHANNEL_TYPES} label="Type" />
          <FilterSelect value={active} onChange={setActive} options={['all', 'true', 'false']} label="Activity" />
          <FilterSelect value={enabled} onChange={setEnabled} options={['all', 'true', 'false']} label="Enabled" />
          <label className="flex items-center gap-2 text-xs text-muted">
            <span className="sr-only">Event from</span>
            <input type="date" value={eventStartFrom} onChange={(event) => setEventStartFrom(event.target.value)} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none" />
          </label>
          <label className="flex items-center gap-2 text-xs text-muted">
            <span className="sr-only">Event to</span>
            <input type="date" value={eventStartTo} onChange={(event) => setEventStartTo(event.target.value)} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none" />
          </label>
          <FilterSelect value={sortBy} onChange={(value) => { setSortBy(value as SortKey); setAscending(true); setPage(1) }} options={['name', 'category', 'server', 'viewers', 'bitrate', 'output', 'status']} label="Sort" />
          <button type="button" onClick={() => { setAscending((value) => !value); setPage(1) }} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy">
            {ascending ? 'Ascending' : 'Descending'}
          </button>
        </div>
        {data.rows.length === 0 ? (
          <DashboardState state="empty" message="No channels match the current filters." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1280px] text-left text-sm">
              <thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted">
                <tr><th className="px-5 py-4">Channel</th><th className="px-5 py-4">Lifecycle</th><th className="px-5 py-4">Category</th><th className="px-5 py-4">Source</th><th className="px-5 py-4">Server</th><th className="px-5 py-4">Viewers</th><th className="px-5 py-4">Bitrate</th><th className="px-5 py-4">Output</th><th className="px-5 py-4">Collected</th><th className="px-5 py-4 text-right">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-line/70">
                {data.rows.map(({ channel, metric, state }) => (
                  <tr key={channel.id} className="transition hover:bg-panel-raised/40">
                    <td className="px-5 py-4"><div className="flex items-center gap-3"><span className="rounded-lg bg-violet-400/10 p-2 text-violet-300"><Radio size={16} /></span><span><span className="block font-semibold text-copy">{channel.name}</span><span className="mt-1 block text-[11px] text-muted">{channel.source_id} · {channel.external_id}</span>{channel.event_name ? <span className="mt-1 flex items-center gap-1 text-[11px] text-cyan-300"><CalendarClock size={11} />{channel.event_name}{channel.event_start_at ? ` · ${formatDateTime(channel.event_start_at)}` : ''}</span> : null}{channel.technical_stream_name ? <span className="mt-1 block text-[11px] text-muted">Stream: {channel.technical_stream_name}</span> : null}</span></div></td>
                    <td className="px-5 py-4"><LifecycleBadge channel={channel} /></td>
                    <td className="px-5 py-4 text-muted">{channel.category_name ?? channel.category ?? '—'}</td>
                    <td className="px-5 py-4 text-muted">{channel.source_id}</td>
                    <td className="px-5 py-4 text-muted">{channel.current_server_name ?? 'Unassigned'}</td>
                    <td className="px-5 py-4 text-copy">{metric ? formatCompactNumber(metric.viewers) : '—'}</td>
                    <td className="px-5 py-4 text-muted">{formatNullableThroughput(metric?.bitrate_mbps ?? null)}</td>
                    <td className="px-5 py-4 text-muted">{formatNullableThroughput(metric?.estimated_output_mbps ?? null)}</td>
                    <td className="px-5 py-4 text-muted">{formatDateTime(metric?.collected_at ?? null)}</td>
                    <td className="px-5 py-4 text-right"><StatusBadge state={state} label={channel.archived_at ? 'archived' : !channel.active ? 'inactive' : (metric?.status ?? 'no data')} /></td>
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

function FilterInput({ value, onChange, placeholder, inputMode }: { value: string; onChange: (value: string) => void; placeholder: string; inputMode?: 'numeric' }): React.JSX.Element {
  return <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} inputMode={inputMode} className="w-32 rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none placeholder:text-muted focus:border-brand" />
}

function FilterSelect({ value, onChange, options, label }: { value: string; onChange: (value: string) => void; options: readonly string[]; label: string }): React.JSX.Element {
  return <label className="flex items-center gap-2 text-xs text-muted"><span className="sr-only">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none focus:border-brand">{options.map((option) => <option key={option} value={option}>{option === 'all' ? `All ${label}` : option}</option>)}</select></label>
}

function LifecycleBadge({ channel }: { channel: ChannelListItem }): React.JSX.Element {
  const label = channel.archived_at
    ? 'Archived'
    : !channel.active
      ? 'Inactive'
      : channel.channel_type === 'event'
        ? 'Event'
        : channel.channel_type === 'temporary'
          ? 'Temporary'
          : channel.channel_type === 'scheduled'
            ? 'Scheduled'
            : 'Permanent'
  return <span className="rounded-full border border-line bg-panel-raised px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted">{label}</span>
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail: string }): React.JSX.Element {
  return <Surface className="p-5"><p className="text-sm text-muted">{label}</p><p className="mt-3 text-3xl font-semibold text-copy">{value}</p><p className="mt-1 text-xs text-muted">{detail}</p></Surface>
}
