import { Activity, ArrowUpRight, CircleCheck, Clock3 } from 'lucide-react'
import { Surface } from '../common/Surface'
import { StatusBadge } from '../common/StatusBadge'

export function StatusOverview(): React.JSX.Element {
  return (
    <Surface className="h-full p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-copy">General status</p>
          <p className="mt-1 text-xs text-muted">Read-only platform snapshot</p>
        </div>
        <StatusBadge state="healthy" compact />
      </div>

      <div className="mt-7 flex items-center gap-5">
        <div
          className="relative flex h-28 w-28 shrink-0 items-center justify-center rounded-full"
          style={{ background: 'conic-gradient(#34d399 0deg 338deg, #253044 338deg 360deg)' }}
        >
          <div className="flex h-20 w-20 flex-col items-center justify-center rounded-full bg-panel">
            <span className="text-2xl font-semibold text-copy">94</span>
            <span className="text-[10px] uppercase tracking-wider text-muted">score</span>
          </div>
        </div>
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs text-muted">
            <CircleCheck size={14} className="text-success" /> All core services online
          </div>
          <div className="flex items-center gap-2 text-xs text-muted">
            <Clock3 size={14} className="text-brand" /> Last collection 2 min ago
          </div>
          <div className="flex items-center gap-2 text-xs text-muted">
            <Activity size={14} className="text-violet-300" /> Scheduler cycle 04:58
          </div>
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between border-t border-line pt-4 text-xs">
        <span className="text-muted">View system details</span>
        <ArrowUpRight size={15} className="text-brand" />
      </div>
    </Surface>
  )
}
