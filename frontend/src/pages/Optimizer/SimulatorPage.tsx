import { Calculator, CircleCheck, CircleX, Plus } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../../components/common/PageHeader'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useCapacityData } from '../../hooks/useCapacityData'
import { usePageTitle } from '../../hooks/usePageTitle'
import { useSimulationData } from '../../hooks/useSimulationData'
import { formatNullableThroughput } from '../../utils/formatters'

export function SimulatorPage(): React.JSX.Element {
  usePageTitle('Optimizer · Simulator')
  const capacity = useCapacityData()
  const simulations = useSimulationData()
  const [name, setName] = useState('Capacity scenario')
  const [removedServerId, setRemovedServerId] = useState('')
  const [virtualName, setVirtualName] = useState('')
  const [virtualCost, setVirtualCost] = useState('30')

  if (simulations.isLoading || capacity.isLoading) return <DashboardState state="loading" message="Loading simulation inputs." />
  if (simulations.isError || capacity.isError || !capacity.capacity) return <DashboardState state="error" message="Simulation inputs could not be loaded." onRetry={() => { void simulations.refetch(); void capacity.refetch() }} />

  const runSimulation = async (): Promise<void> => {
    await simulations.run({
      name,
      removed_server_ids: removedServerId ? [Number(removedServerId)] : [],
      virtual_servers: virtualName ? [{ key: virtualName.toLowerCase().replaceAll(' ', '-'), name: virtualName, physical_capacity_mbps: 1_000, operational_limit_mbps: 700, recommended_limit_mbps: 800, minimum_reserve_mbps: 100, monthly_cost: Number(virtualCost), currency: 'USD' }] : [],
      load_units: null,
    })
  }

  const latest = simulations.latestSimulation
  return (
    <>
      <PageHeader eyebrow="Optimizer" title="Simulator" description="Compare removals and virtual replacements using the latest observed load. Results are persisted as local history only." action={<Calculator className="text-brand" size={26} />} />
      <DashboardFreshness isFetching={simulations.isFetching} isStale={simulations.isStale} lastUpdatedAt={simulations.lastUpdatedAt} onRefresh={() => void simulations.refetch()} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,420px)_1fr]">
        <Surface className="p-5"><h2 className="text-sm font-semibold text-copy">Scenario inputs</h2><p className="mt-2 text-xs leading-5 text-muted">The backend performs all capacity and cost calculations. No inventory is changed.</p><label className="mt-5 block text-xs font-medium text-muted">Scenario name<input value={name} onChange={(event) => setName(event.target.value)} className="mt-2 w-full rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-sm text-copy outline-none focus:border-brand" /></label><label className="mt-4 block text-xs font-medium text-muted">Remove server<select value={removedServerId} onChange={(event) => setRemovedServerId(event.target.value)} className="mt-2 w-full rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-sm text-copy outline-none focus:border-brand"><option value="">Keep all servers</option>{capacity.capacity.servers.map((server) => <option key={server.server_id} value={server.server_id}>{server.name}</option>)}</select></label><label className="mt-4 block text-xs font-medium text-muted">Virtual replacement name<input value={virtualName} onChange={(event) => setVirtualName(event.target.value)} placeholder="Optional" className="mt-2 w-full rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-sm text-copy outline-none focus:border-brand" /></label>{virtualName && <label className="mt-4 block text-xs font-medium text-muted">Monthly cost (USD)<input type="number" min="0" value={virtualCost} onChange={(event) => setVirtualCost(event.target.value)} className="mt-2 w-full rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-sm text-copy outline-none focus:border-brand" /></label>}<button type="button" disabled={simulations.isSubmitting || !name.trim()} onClick={() => void runSimulation()} className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 text-xs font-semibold text-canvas transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-50"><Plus size={15} />{simulations.isSubmitting ? 'Running…' : 'Run simulation'}</button>{simulations.mutationError && <p className="mt-3 text-xs text-danger">Simulation failed. Retry without exposing infrastructure details.</p>}</Surface>
        <div className="space-y-5">{latest ? <SimulationResultCard simulation={latest} /> : <Surface className="flex min-h-[260px] flex-col items-center justify-center p-8 text-center"><Calculator className="text-muted" size={28} /><h2 className="mt-4 text-sm font-semibold text-copy">No simulation run yet</h2><p className="mt-2 max-w-md text-xs leading-5 text-muted">Use the form to evaluate a local scenario. Missing metrics will be reported as insufficient data.</p></Surface>}<Surface className="overflow-hidden"><div className="border-b border-line px-5 py-4"><h2 className="text-sm font-semibold text-copy">Recent scenarios</h2></div>{simulations.simulations.length === 0 ? <p className="px-5 py-6 text-sm text-muted">No simulation history.</p> : <div className="divide-y divide-line/70">{simulations.simulations.map((simulation) => <div key={simulation.id} className="flex items-center justify-between gap-3 px-5 py-4"><div><p className="text-sm font-medium text-copy">{simulation.name}</p><p className="mt-1 text-xs text-muted">{simulation.result.risk} · {simulation.result.feasible ? 'Feasible' : 'Not feasible'}</p></div><span className="text-xs text-muted">{simulation.result.unassigned_load_mbps} Mbps unassigned</span></div>)}</div>}</Surface></div>
      </div>
    </>
  )
}

function SimulationResultCard({ simulation }: { simulation: NonNullable<ReturnType<typeof useSimulationData>['latestSimulation']> }): React.JSX.Element {
  const result = simulation.result
  return <Surface className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-brand">Latest result</p><h2 className="mt-1 text-lg font-semibold text-copy">{simulation.name}</h2></div>{result.feasible ? <CircleCheck className="text-success" /> : <CircleX className="text-danger" />}</div><p className="mt-4 text-sm text-muted">{result.explanation}</p><div className="mt-5 grid gap-3 sm:grid-cols-3"><ResultMetric label="Assigned" value={formatNullableThroughput(result.total_assigned_load_mbps)} /><ResultMetric label="Unassigned" value={formatNullableThroughput(result.unassigned_load_mbps)} /><ResultMetric label="Savings / month" value={result.monthly_savings === null ? '—' : `$${result.monthly_savings.toFixed(2)}`} /></div>{result.missing_data.length > 0 && <div className="mt-5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-xs text-warning">Insufficient data: {result.missing_data.join(', ')}</div>}<div className="mt-5 overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="border-b border-line text-[10px] uppercase tracking-wider text-muted"><tr><th className="px-2 py-3">Server</th><th className="px-2 py-3">Assigned</th><th className="px-2 py-3">Free margin</th><th className="px-2 py-3">Utilization</th></tr></thead><tbody className="divide-y divide-line/70">{result.servers.map((server) => <tr key={server.key}><td className="px-2 py-3 text-copy">{server.name}</td><td className="px-2 py-3 text-muted">{formatNullableThroughput(server.assigned_load_mbps)}</td><td className="px-2 py-3 text-muted">{formatNullableThroughput(server.free_margin_mbps)}</td><td className="px-2 py-3 text-copy">{server.utilization_percent.toFixed(1)}%</td></tr>)}</tbody></table></div></Surface>
}

function ResultMetric({ label, value }: { label: string; value: string }): React.JSX.Element { return <div className="rounded-xl bg-panel-raised p-3"><p className="text-[10px] uppercase tracking-wider text-muted">{label}</p><p className="mt-2 text-sm font-semibold text-copy">{value}</p></div> }
