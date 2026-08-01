import { Link } from 'react-router-dom'
import { ChevronDown, ChevronUp, Search, Server } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { usePageTitle } from '../../hooks/usePageTitle'
import { useServersData, type ServerTableRow } from '../../hooks/useServersData'
import { formatNullablePercent, formatNullableThroughput, formatUptime } from '../../utils/formatters'

type SortKey = 'status' | 'name' | 'cpu' | 'memory' | 'disk' | 'network' | 'uptime' | 'group' | 'provider' | 'country'

const PAGE_SIZE = 10

export function ServersPage(): React.JSX.Element {
  usePageTitle('Servers')
  const data = useServersData()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [provider, setProvider] = useState('all')
  const [group, setGroup] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [ascending, setAscending] = useState(true)
  const [page, setPage] = useState(1)

  const providers = useMemo(
    () => unique(data.rows.map(({ server }) => server.provider)),
    [data.rows],
  )
  const groups = useMemo(() => unique(data.rows.map(({ server }) => server.group)), [data.rows])
  const filteredRows = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return [...data.rows]
      .filter(({ server }) => status === 'all' || server.status === status)
      .filter(({ server }) => provider === 'all' || server.provider === provider)
      .filter(({ server }) => group === 'all' || server.group === group)
      .filter(({ server }) => {
        if (!normalizedSearch) return true
        return [server.name, server.hostname, server.external_id, server.country]
          .filter(Boolean)
          .some((value) => value!.toLowerCase().includes(normalizedSearch))
      })
      .sort((left, right) => compareRows(left, right, sortKey) * (ascending ? 1 : -1))
  }, [ascending, data.rows, group, provider, search, sortKey, status])
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE))
  const visibleRows = filteredRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  useEffect(() => {
    setPage(1)
  }, [group, provider, search, status])

  if (data.isLoading) {
    return <DashboardState state="loading" message="Loading server inventory and latest metrics." />
  }
  if (data.isError) {
    return <DashboardState state="error" message="The server inventory could not be loaded." onRetry={() => void data.refetch()} />
  }

  return (
    <>
      <PageHeader
        eyebrow="Infrastructure"
        title="Servers"
        description="Managed inventory with current health and latest read-only metrics."
      />
      <DashboardFreshness
        isFetching={data.isFetching}
        isStale={data.isStale}
        lastUpdatedAt={data.lastUpdatedAt}
        onRefresh={() => void data.refetch()}
      />
      <Surface className="mt-5 overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-5 lg:flex-row lg:items-center">
          <label className="relative min-w-0 flex-1">
            <Search size={15} className="pointer-events-none absolute left-3 top-3 text-muted" />
            <input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
              placeholder="Search name, hostname or external id"
              className="w-full rounded-xl border border-line bg-panel-raised py-2.5 pl-9 pr-3 text-xs text-copy outline-none placeholder:text-muted focus:border-brand"
            />
          </label>
          <FilterSelect value={status} onChange={setStatus} options={['all', 'online', 'degraded', 'offline', 'maintenance', 'unknown']} label="Status" />
          <FilterSelect value={provider} onChange={setProvider} options={['all', ...providers]} label="Provider" />
          <FilterSelect value={group} onChange={setGroup} options={['all', ...groups]} label="Group" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1160px] text-left text-xs">
            <thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted">
              <tr>
                <SortableHeader label="Status" sortKey="status" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="Name" sortKey="name" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="CPU" sortKey="cpu" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="RAM" sortKey="memory" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="Disk" sortKey="disk" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="Network" sortKey="network" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="Uptime" sortKey="uptime" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="Group" sortKey="group" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="Provider" sortKey="provider" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
                <SortableHeader label="Country" sortKey="country" sortKeyValue={sortKey} ascending={ascending} onSort={sort} />
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {visibleRows.map(({ server, metric, state }) => (
                <tr key={server.id} className="transition hover:bg-panel-raised/40">
                  <td className="px-4 py-4"><StatusBadge state={state} label={server.status} /></td>
                  <td className="px-4 py-4">
                    <Link to={`/server/${server.id}`} className="flex items-center gap-3 hover:text-brand">
                      <span className="rounded-lg bg-brand/10 p-2 text-brand"><Server size={15} /></span>
                      <span><span className="block font-semibold text-copy">{server.name}</span><span className="mt-1 block text-[11px] text-muted">{server.hostname ?? server.external_id}</span></span>
                    </Link>
                  </td>
                  <td className="px-4 py-4 text-copy">{formatNullablePercent(metric?.cpu_percent ?? null)}</td>
                  <td className="px-4 py-4 text-copy">{formatNullablePercent(metric?.memory_percent ?? null)}</td>
                  <td className="px-4 py-4 text-copy">{formatNullablePercent(metric?.disk_percent ?? null)}</td>
                  <td className="px-4 py-4 text-muted">{formatNullableThroughput(metric?.output_mbps ?? null)}</td>
                  <td className="px-4 py-4 text-muted">{formatUptime(metric?.uptime_seconds ?? null)}</td>
                  <td className="px-4 py-4 text-muted">{server.group ?? '—'}</td>
                  <td className="px-4 py-4 text-muted">{server.provider ?? '—'}</td>
                  <td className="px-4 py-4 text-muted">{server.country ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {visibleRows.length === 0 && <p className="p-8 text-center text-xs text-muted">No servers match the current filters.</p>}
        </div>
        <div className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-muted">
          <span>{filteredRows.length} servers · page {page} of {pageCount}</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">Previous</button>
            <button disabled={page >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">Next</button>
          </div>
        </div>
      </Surface>
    </>
  )

  function sort(nextKey: SortKey): void {
    if (sortKey === nextKey) setAscending((value) => !value)
    else {
      setSortKey(nextKey)
      setAscending(true)
    }
    setPage(1)
  }
}

function unique(values: Array<string | null>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort()
}

function compareRows(left: ServerTableRow, right: ServerTableRow, key: SortKey): number {
  const values: Record<SortKey, [string | number, string | number]> = {
    status: [left.server.status, right.server.status],
    name: [left.server.name, right.server.name],
    cpu: [left.metric?.cpu_percent ?? -1, right.metric?.cpu_percent ?? -1],
    memory: [left.metric?.memory_percent ?? -1, right.metric?.memory_percent ?? -1],
    disk: [left.metric?.disk_percent ?? -1, right.metric?.disk_percent ?? -1],
    network: [left.metric?.output_mbps ?? -1, right.metric?.output_mbps ?? -1],
    uptime: [left.metric?.uptime_seconds ?? -1, right.metric?.uptime_seconds ?? -1],
    group: [left.server.group ?? '', right.server.group ?? ''],
    provider: [left.server.provider ?? '', right.server.provider ?? ''],
    country: [left.server.country ?? '', right.server.country ?? ''],
  }
  const [leftValue, rightValue] = values[key]
  return typeof leftValue === 'number' && typeof rightValue === 'number'
    ? leftValue - rightValue
    : String(leftValue).localeCompare(String(rightValue))
}

function FilterSelect({ value, onChange, options, label }: { value: string; onChange: (value: string) => void; options: string[]; label: string }): React.JSX.Element {
  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(event) => { onChange(event.target.value) }} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none focus:border-brand">
        {options.map((option) => <option key={option} value={option}>{option === 'all' ? `All ${label}` : option}</option>)}
      </select>
    </label>
  )
}

function SortableHeader({ label, sortKey, sortKeyValue, ascending, onSort }: { label: string; sortKey: SortKey; sortKeyValue: SortKey; ascending: boolean; onSort: (key: SortKey) => void }): React.JSX.Element {
  const active = sortKey === sortKeyValue
  return (
    <th className="px-4 py-3 font-semibold">
      <button type="button" onClick={() => onSort(sortKey)} className="inline-flex items-center gap-1 hover:text-copy">
        {label}{active && (ascending ? <ChevronUp size={12} /> : <ChevronDown size={12} />)}
      </button>
    </th>
  )
}
