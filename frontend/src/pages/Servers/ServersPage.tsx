import { Plus, Server } from 'lucide-react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { usePageTitle } from '../../hooks/usePageTitle'
import { serverSummaries } from '../../utils/mockData'
import { formatPercent } from '../../utils/formatters'

export function ServersPage(): React.JSX.Element {
  usePageTitle('Servers')

  return (
    <>
      <PageHeader
        eyebrow="Infrastructure"
        title="Servers"
        description="Placeholder inventory for monitored infrastructure. Server discovery will be connected to the API later."
        action={
          <button className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-xs font-semibold text-slate-950 shadow-lg shadow-brand/10 transition hover:bg-cyan-300">
            <Plus size={15} /> Add server
          </button>
        }
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <Surface className="p-5">
          <p className="text-sm text-muted">Total servers</p>
          <p className="mt-3 text-3xl font-semibold text-copy">5</p>
          <p className="mt-1 text-xs text-success">All inventory sources healthy</p>
        </Surface>
        <Surface className="p-5">
          <p className="text-sm text-muted">Avg. utilization</p>
          <p className="mt-3 text-3xl font-semibold text-copy">62.4%</p>
          <p className="mt-1 text-xs text-muted">Across current mock sample</p>
        </Surface>
        <Surface className="p-5">
          <p className="text-sm text-muted">Last collection</p>
          <p className="mt-3 text-3xl font-semibold text-copy">2m</p>
          <p className="mt-1 text-xs text-muted">Scheduler heartbeat received</p>
        </Surface>
      </div>
      <Surface className="mt-5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted">
              <tr>
                <th className="px-5 py-4">Server</th>
                <th className="px-5 py-4">Role</th>
                <th className="px-5 py-4">CPU</th>
                <th className="px-5 py-4">Memory</th>
                <th className="px-5 py-4">Network</th>
                <th className="px-5 py-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {serverSummaries.map((server) => (
                <tr key={server.name} className="transition hover:bg-panel-raised/40">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <span className="rounded-lg bg-brand/10 p-2 text-brand">
                        <Server size={16} />
                      </span>
                      <div>
                        <p className="font-semibold text-copy">{server.name}</p>
                        <p className="mt-1 text-xs text-muted">{server.host}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-muted">{server.role}</td>
                  <td className="px-5 py-4 text-copy">{formatPercent(server.cpu)}</td>
                  <td className="px-5 py-4 text-copy">{formatPercent(server.memory)}</td>
                  <td className="px-5 py-4 text-muted">{server.network}</td>
                  <td className="px-5 py-4 text-right">
                    <StatusBadge state={server.state} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Surface>
    </>
  )
}
