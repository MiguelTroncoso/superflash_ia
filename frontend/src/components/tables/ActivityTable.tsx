import { ArrowUpRight, MoreHorizontal } from 'lucide-react'
import { StatusBadge } from '../common/StatusBadge'
import { Surface } from '../common/Surface'
import { serverSummaries } from '../../utils/mockData'
import { formatPercent } from '../../utils/formatters'

export function ActivityTable(): React.JSX.Element {
  return (
    <Surface className="overflow-hidden">
      <div className="flex items-start justify-between gap-4 p-5">
        <div>
          <p className="text-sm font-semibold text-copy">Server health</p>
          <p className="mt-1 text-xs text-muted">
            Top infrastructure signals, simulated for preview
          </p>
        </div>
        <button className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:text-cyan-200">
          All servers <ArrowUpRight size={14} />
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-xs">
          <thead className="border-y border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted">
            <tr>
              <th className="px-5 py-3 font-semibold">Server</th>
              <th className="px-5 py-3 font-semibold">Role</th>
              <th className="px-5 py-3 font-semibold">CPU</th>
              <th className="px-5 py-3 font-semibold">Memory</th>
              <th className="px-5 py-3 font-semibold">Network</th>
              <th className="px-5 py-3 text-right font-semibold">State</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line/70">
            {serverSummaries.map((server) => (
              <tr key={server.name} className="group transition hover:bg-panel-raised/40">
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <span className="h-2 w-2 rounded-full bg-success shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
                    <div>
                      <p className="font-semibold text-copy">{server.name}</p>
                      <p className="mt-1 text-[11px] text-muted">{server.host}</p>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4 text-muted">{server.role}</td>
                <td className="px-5 py-4 font-medium text-copy">{formatPercent(server.cpu)}</td>
                <td className="px-5 py-4 font-medium text-copy">{formatPercent(server.memory)}</td>
                <td className="px-5 py-4 text-muted">{server.network}</td>
                <td className="px-5 py-4 text-right">
                  <StatusBadge state={server.state} compact />
                </td>
                <td className="px-5 py-4 text-right">
                  <button
                    aria-label={`More actions for ${server.name}`}
                    className="rounded-lg p-1.5 text-muted opacity-0 hover:bg-panel-raised hover:text-copy group-hover:opacity-100"
                  >
                    <MoreHorizontal size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Surface>
  )
}
