import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { MetricTone } from '../../types/monitoring'
import { cn } from '../../utils/formatters'
import { Surface } from './Surface'

const toneStyles: Record<MetricTone, { icon: string; glow: string }> = {
  cyan: { icon: 'bg-cyan-400/10 text-cyan-300', glow: 'shadow-cyan-500/5' },
  violet: { icon: 'bg-violet-400/10 text-violet-300', glow: 'shadow-violet-500/5' },
  amber: { icon: 'bg-amber-400/10 text-amber-300', glow: 'shadow-amber-500/5' },
  emerald: { icon: 'bg-emerald-400/10 text-emerald-300', glow: 'shadow-emerald-500/5' },
  rose: { icon: 'bg-rose-400/10 text-rose-300', glow: 'shadow-rose-500/5' },
  slate: { icon: 'bg-slate-400/10 text-slate-300', glow: 'shadow-slate-500/5' },
}

interface MetricCardProps {
  label: string
  value: string
  detail: string
  tone: MetricTone
  icon: LucideIcon
  trend?: string
  trendPositive?: boolean
}

export function MetricCard({
  label,
  value,
  detail,
  tone,
  icon: Icon,
  trend,
  trendPositive,
}: MetricCardProps): React.JSX.Element {
  const TrendIcon = trend ? (trendPositive ? ArrowUpRight : ArrowDownRight) : Minus
  const style = toneStyles[tone]

  return (
    <Surface
      className={cn(
        'group p-5 transition duration-200 hover:-translate-y-0.5 hover:border-slate-600',
        style.glow,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-muted">{label}</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-copy">{value}</p>
        </div>
        <div className={cn('rounded-xl p-2.5', style.icon)}>
          <Icon size={20} strokeWidth={1.8} />
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between gap-2 text-xs">
        <span className="text-muted">{detail}</span>
        {trend && (
          <span
            className={cn(
              'inline-flex items-center gap-0.5 font-medium',
              trendPositive ? 'text-success' : 'text-warning',
            )}
          >
            <TrendIcon size={13} />
            {trend}
          </span>
        )}
      </div>
    </Surface>
  )
}
