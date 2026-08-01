import { StatusBadge } from '../common/StatusBadge'
import { Surface } from '../common/Surface'
import type { DashboardServerRow } from '../../utils/dashboardMetrics'
import { formatNullablePercent, formatNullableThroughput } from '../../utils/formatters'

interface ActivityTableProps {
  rows: DashboardServerRow[]
}

export function ActivityTable({ rows }: ActivityTableProps): React.JSX.Element {
  return (
    <Surface className="overflow-hidden">
      <div className="flex items-start justify-between gap-4 p-5">
        <div>
          <p className="text-sm font-semibold text-copy">Server health</p>
          <p className="mt-1 text-xs text-muted">Latest server metrics from the read-only API</p>
        </div>
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
            </tr>
          </thead>
          <tbody className="divide-y divide-line/70">
            {rows.map((server) => (
              <tr key={server.id} className="transition hover:bg-panel-raised/40">
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <span
                      className={
                        server.state === 'healthy'
                          ? 'h-2 w-2 rounded-full bg-success shadow-[0_0_8px_rgba(52,211,153,0.7)]'
                          : 'h-2 w-2 rounded-full bg-warning shadow-[0_0_8px_rgba(251,191,36,0.7)]'
                      }
                    />
                    <div>
                      <p className="font-semibold text-copy">{server.name}</p>
                      <p className="mt-1 text-[11px] text-muted">
                        {server.hostname ?? 'Hostname unavailable'}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4 text-muted">{server.role}</td>
                <td className="px-5 py-4 font-medium text-copy">
                  {formatNullablePercent(server.cpuPercent)}
                </td>
                <td className="px-5 py-4 font-medium text-copy">
                  {formatNullablePercent(server.memoryPercent)}
                </td>
                <td className="px-5 py-4 text-muted">
                  {formatNullableThroughput(server.outputMbps)}
                </td>
                <td className="px-5 py-4 text-right">
                  <StatusBadge state={server.state} label={server.stateLabel} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Surface>
  )
}
