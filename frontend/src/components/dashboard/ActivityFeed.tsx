import { ArrowUpRight } from 'lucide-react'
import { StatusBadge } from '../common/StatusBadge'
import { Surface } from '../common/Surface'
import { activityItems } from '../../utils/mockData'

export function ActivityFeed(): React.JSX.Element {
  return (
    <Surface className="h-full p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-copy">Recent activity</p>
          <p className="mt-1 text-xs text-muted">Signals from the monitoring workspace</p>
        </div>
        <button className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:text-cyan-200">
          View all <ArrowUpRight size={14} />
        </button>
      </div>
      <div className="mt-5 divide-y divide-line/70">
        {activityItems.map((item) => (
          <div key={item.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
            <StatusBadge state={item.state} compact />
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-copy">{item.title}</p>
              <p className="mt-1 truncate text-[11px] text-muted">{item.description}</p>
            </div>
            <time className="whitespace-nowrap text-[10px] text-muted">{item.time}</time>
          </div>
        ))}
      </div>
    </Surface>
  )
}
