import { CheckCircle2, CircleAlert, CircleX } from 'lucide-react'
import type { HealthState } from '../../types/monitoring'
import { cn } from '../../utils/formatters'

const stateCopy: Record<HealthState, string> = {
  healthy: 'Healthy',
  warning: 'Warning',
  critical: 'Critical',
}

const stateStyles: Record<HealthState, string> = {
  healthy: 'border-success/20 bg-success/10 text-success',
  warning: 'border-warning/20 bg-warning/10 text-warning',
  critical: 'border-danger/20 bg-danger/10 text-danger',
}

const StateIcon: Record<HealthState, typeof CheckCircle2> = {
  healthy: CheckCircle2,
  warning: CircleAlert,
  critical: CircleX,
}

interface StatusBadgeProps {
  state: HealthState
  compact?: boolean
  label?: string
}

export function StatusBadge({ state, compact = false, label }: StatusBadgeProps): React.JSX.Element {
  const Icon = StateIcon[state]

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium',
        stateStyles[state],
      )}
    >
      <Icon size={compact ? 12 : 14} strokeWidth={2.2} />
      {!compact && (label ?? stateCopy[state])}
    </span>
  )
}
