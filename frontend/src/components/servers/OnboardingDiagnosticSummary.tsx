import { CheckCircle2, CircleAlert, XCircle } from 'lucide-react'

interface Check {
  label: string
  value: string
}

interface Props {
  checks: Check[]
  errors?: string[]
}

export function OnboardingDiagnosticSummary({ checks, errors = [] }: Props): React.JSX.Element {
  return (
    <div className="mt-4 rounded-xl border border-line bg-panel-raised p-4 text-xs">
      <div className="grid gap-2 sm:grid-cols-3">
        {checks.map((check) => <DiagnosticCheck key={check.label} {...check} />)}
      </div>
      {errors.length > 0 && <div className="mt-4 rounded-lg border border-warning/30 bg-warning/10 p-3 text-warning"><p className="font-semibold">Errors found</p><ul className="mt-2 list-disc space-y-1 pl-4">{errors.map((error) => <li key={error}>{error}</li>)}</ul></div>}
    </div>
  )
}

function DiagnosticCheck({ label, value }: Check): React.JSX.Element {
  const failed = ['FAIL', 'CONNECTION_FAILED', 'not_available', 'missing'].includes(value)
  const pending = ['PARTIAL', 'PENDING_SCRAPE', 'unknown', 'stale'].includes(value)
  const Icon = failed ? XCircle : pending ? CircleAlert : CheckCircle2
  const color = failed ? 'text-danger' : pending ? 'text-warning' : 'text-success'
  return <div className="flex items-center justify-between rounded-lg border border-line px-3 py-2"><span className="text-muted">{label}</span><span className={`inline-flex items-center gap-1 font-semibold ${color}`}><Icon size={14} />{value}</span></div>
}
