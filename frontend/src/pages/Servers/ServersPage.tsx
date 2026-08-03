import { Link } from 'react-router'
import { ChevronDown, ChevronUp, Pencil, Plus, Search, Server, Trash2, X } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { usePageTitle } from '../../hooks/usePageTitle'
import { useServersData } from '../../hooks/useServersData'
import { apiService } from '../../services/apiService'
import type { ApiServerRole, ServerListItem, ServerWriteInput } from '../../types/api'
import { formatNullablePercent, formatNullableThroughput, formatUptime } from '../../utils/formatters'

type SortKey = 'status' | 'name' | 'cpu' | 'memory' | 'disk' | 'network' | 'uptime' | 'group' | 'provider' | 'country'

interface ServerFormState {
  external_id: string
  name: string
  hostname: string
  role: ApiServerRole
  provider: string
  network_speed_mbps: string
  prometheus_url: string
  prometheus_token: string
  enabled: boolean
}

const emptyForm: ServerFormState = {
  external_id: '',
  name: '',
  hostname: '',
  role: 'other',
  provider: '',
  network_speed_mbps: '',
  prometheus_url: '',
  prometheus_token: '',
  enabled: true,
}

const PAGE_SIZE = 10

export function ServersPage(): React.JSX.Element {
  usePageTitle('Servers')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [provider, setProvider] = useState('all')
  const [group, setGroup] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [ascending, setAscending] = useState(true)
  const [page, setPage] = useState(1)
  const [form, setForm] = useState<ServerFormState>(emptyForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [diagnosing, setDiagnosing] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const data = useServersData({
    page,
    page_size: PAGE_SIZE,
    search: search.trim() || undefined,
    status: status === 'all' ? undefined : status,
    provider: provider === 'all' ? undefined : provider,
    group: group === 'all' ? undefined : group,
    sort_by: sortKey,
    sort_order: ascending ? 'asc' : 'desc',
  })

  const providers = useMemo(
    () => unique(data.rows.map(({ server }) => server.provider)),
    [data.rows],
  )
  const groups = useMemo(() => unique(data.rows.map(({ server }) => server.group)), [data.rows])
  const pageCount = Math.max(1, data.totalPages)
  const visibleRows = data.rows

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
        action={<button type="button" onClick={openCreate} className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-xs font-semibold text-canvas hover:bg-sky-300"><Plus size={15} />Add server</button>}
      />
      {formOpen && <ServerForm form={form} editing={editingId !== null} saving={saving} diagnosing={diagnosing} error={formError} onChange={updateForm} onCancel={closeForm} onDiagnose={() => void diagnoseForm()} onSubmit={submitForm} />}
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
                <th className="px-4 py-3 font-semibold">Actions</th>
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
                  <td className="px-4 py-4"><div className="flex items-center gap-2"><button type="button" title="Edit server" onClick={() => openEdit(server)} className="rounded-lg border border-line p-2 text-muted hover:text-copy"><Pencil size={14} /></button><button type="button" title="Delete server" disabled={deletingId === server.id} onClick={() => void removeServer(server.id)} className="rounded-lg border border-line p-2 text-muted hover:text-danger disabled:opacity-40"><Trash2 size={14} /></button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
          {visibleRows.length === 0 && <p className="p-8 text-center text-xs text-muted">No servers match the current filters.</p>}
        </div>
        <div className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-muted">
          <span>{data.total} servers · page {data.page} of {pageCount}</span>
          <div className="flex gap-2">
            <button disabled={data.page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">Previous</button>
            <button disabled={data.page >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">Next</button>
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

  function openCreate(): void {
    setEditingId(null)
    setForm(emptyForm)
    setFormError(null)
    setFormOpen(true)
  }

  function openEdit(server: ServerListItem): void {
    setEditingId(server.id)
    setForm({
      external_id: server.external_id,
      name: server.name,
      hostname: server.hostname ?? '',
      role: server.role,
      provider: server.provider ?? '',
      network_speed_mbps: server.network_speed_mbps?.toString() ?? '',
      prometheus_url: '',
      prometheus_token: '',
      enabled: server.enabled,
    })
    setFormError(null)
    setFormOpen(true)
  }

  function closeForm(): void {
    setFormOpen(false)
    setFormError(null)
  }

  function updateForm(field: keyof ServerFormState, value: string | boolean): void {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submitForm(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setSaving(true)
    setFormError(null)
    const payload: ServerWriteInput = {
      external_id: form.external_id.trim(),
      name: form.name.trim(),
      hostname: form.hostname.trim() || null,
      role: form.role,
      provider: form.provider.trim() || null,
      network_speed_mbps: form.network_speed_mbps ? Number(form.network_speed_mbps) : null,
      enabled: form.enabled,
    }
    if (form.prometheus_url.trim()) payload.prometheus_url = form.prometheus_url.trim()
    if (form.prometheus_token.trim()) payload.prometheus_token = form.prometheus_token.trim()
    try {
      if (editingId === null) await apiService.createServer(payload)
      else await apiService.updateServer(editingId, payload)
      await data.refetch()
      closeForm()
    } catch {
      setFormError('Server could not be saved. Check the fields and retry.')
    } finally {
      setSaving(false)
    }
  }

  async function removeServer(serverId: number): Promise<void> {
    if (!window.confirm('Delete this server and its local metric history?')) return
    setDeletingId(serverId)
    try {
      await apiService.deleteServer(serverId)
      await data.refetch()
    } catch {
      setFormError('Server could not be deleted.')
    } finally {
      setDeletingId(null)
    }
  }

  async function diagnoseForm(): Promise<void> {
    if (editingId === null) return
    setDiagnosing(true)
    setFormError(null)
    try {
      const diagnostic = await apiService.diagnoseServer(editingId)
      setFormError(`${diagnostic.prometheus.message} · ${diagnostic.node_exporter.message}${diagnostic.latency_ms === null ? '' : ` · ${diagnostic.latency_ms.toFixed(1)} ms`}`)
    } catch {
      setFormError('Connection diagnostic failed. No infrastructure details were exposed.')
    } finally {
      setDiagnosing(false)
    }
  }
}

function ServerForm({ form, editing, saving, diagnosing, error, onChange, onCancel, onDiagnose, onSubmit }: { form: ServerFormState; editing: boolean; saving: boolean; diagnosing: boolean; error: string | null; onChange: (field: keyof ServerFormState, value: string | boolean) => void; onCancel: () => void; onDiagnose: () => void; onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void> }): React.JSX.Element {
  return <Surface className="mb-5 p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-copy">{editing ? 'Edit server' : 'Connect server'}</h2><p className="mt-1 text-xs text-muted">Prometheus and Node Exporter are read-only. Tokens are never shown after saving.</p></div><button type="button" onClick={onCancel} className="rounded-lg p-2 text-muted hover:text-copy"><X size={16} /></button></div><form onSubmit={(event) => void onSubmit(event)} className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><FormInput label="Name" value={form.name} required onChange={(value) => onChange('name', value)} /><FormInput label="External ID" value={form.external_id} required disabled={editing} onChange={(value) => onChange('external_id', value)} /><FormInput label="Hostname / IP" value={form.hostname} placeholder="server.example.com" onChange={(value) => onChange('hostname', value)} /><label className="text-xs text-muted">Role<select value={form.role} onChange={(event) => onChange('role', event.target.value as ApiServerRole)} className="mt-2 w-full rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none focus:border-brand"><option value="main">main</option><option value="live">live</option><option value="vod">vod</option><option value="other">other</option></select></label><FormInput label="Provider" value={form.provider} onChange={(value) => onChange('provider', value)} /><FormInput label="Network Mbps" type="number" min="0" value={form.network_speed_mbps} onChange={(value) => onChange('network_speed_mbps', value)} /><FormInput label="Prometheus URL" value={form.prometheus_url} placeholder={editing ? 'Leave blank to keep current' : 'https://prometheus.internal'} onChange={(value) => onChange('prometheus_url', value)} /><FormInput label="Prometheus token" type="password" value={form.prometheus_token} placeholder={editing ? 'Leave blank to keep current' : 'Optional'} onChange={(value) => onChange('prometheus_token', value)} /><label className="flex items-center gap-2 text-xs text-muted sm:col-span-2"><input type="checkbox" checked={form.enabled} onChange={(event) => onChange('enabled', event.target.checked)} /> Enabled for collection</label>{error && <p className="text-xs text-danger sm:col-span-2">{error}</p>}<div className="flex justify-end gap-2 sm:col-span-2 lg:col-span-4"><button type="button" onClick={onCancel} className="rounded-xl border border-line px-4 py-2.5 text-xs font-semibold text-muted hover:text-copy">Cancel</button>{editing && <button type="button" disabled={diagnosing} onClick={onDiagnose} className="rounded-xl border border-line px-4 py-2.5 text-xs font-semibold text-muted hover:text-copy disabled:opacity-40">{diagnosing ? 'Testing…' : 'Test connection'}</button>}<button type="submit" disabled={saving || !form.name.trim() || !form.external_id.trim()} className="rounded-xl bg-brand px-4 py-2.5 text-xs font-semibold text-canvas hover:bg-sky-300 disabled:opacity-40">{saving ? 'Saving…' : editing ? 'Save changes' : 'Connect server'}</button></div></form></Surface>
}

function FormInput({ label, value, onChange, placeholder, type = 'text', min, required = false, disabled = false }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; type?: string; min?: string; required?: boolean; disabled?: boolean }): React.JSX.Element {
  return <label className="text-xs text-muted">{label}<input required={required} disabled={disabled} type={type} min={min} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-xs text-copy outline-none placeholder:text-muted focus:border-brand disabled:opacity-50" /></label>
}

function unique(values: Array<string | null>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort()
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
