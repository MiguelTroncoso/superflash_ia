import { CheckCircle2, Circle, LoaderCircle } from 'lucide-react'

export interface OnboardingProgressStep {
  key: string
  label: string
}

interface Props {
  steps: OnboardingProgressStep[]
  activeStep: string | null
  completedStep?: string | null
  progress: number
}

export function OnboardingStepProgress({ steps, activeStep, completedStep, progress }: Props): React.JSX.Element {
  const completedIndex = steps.findIndex((step) => step.key === completedStep)
  const hasStarted = Boolean(activeStep) || progress > 0 || Boolean(completedStep)

  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-copy">Onboarding progress</span>
        <span className="text-muted">{progress}%{hasStarted ? ' · estimated time ~2 min' : ''}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-panel-raised">
        <div className="h-full bg-brand transition-all" style={{ width: `${progress}%` }} />
      </div>
      <div className="mt-6 grid gap-2 sm:grid-cols-3">
        {steps.map((step, index) => {
          const isActive = activeStep === step.key
          const isComplete = hasStarted && (index <= completedIndex || step.key === 'completed')
          return (
            <div key={step.key} className={`rounded-xl border p-3 text-xs ${isActive ? 'border-brand bg-brand/10 text-copy' : isComplete ? 'border-success/30 text-success' : 'border-line text-muted'}`}>
              <span className="flex items-center gap-2 font-semibold">
                {isActive ? <LoaderCircle size={14} className="animate-spin" /> : isComplete ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                {step.label}
              </span>
              <span className="mt-1 block">{isComplete ? 'Complete' : isActive ? 'In progress' : hasStarted ? 'Pending' : 'Not started'}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
