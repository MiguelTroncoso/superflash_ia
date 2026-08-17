import { LoaderCircle, ServerCog, ShieldCheck, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useActiveOnboardings, useServerOnboarding } from '../../hooks/useServerOnboarding'
import type { OnboardingDiscoveryResponse, OnboardingStartRequest, OnboardingTestSSHResponse } from '../../types/api'
import { OnboardingDiagnosticSummary } from './OnboardingDiagnosticSummary'
import { OnboardingStepProgress } from './OnboardingStepProgress'

interface Props { onClose: () => void }
type Phase = 'detect' | 'fingerprint' | 'test' | 'prepare'
type RequestKind = 'discover' | 'test_ssh' | 'start'

const REQUEST_TIMEOUT_MS = 30_000
const JOB_VISUAL_TIMEOUT_SECONDS = 30

const steps = [
  { key: 'connecting', label: 'Connect' }, { key: 'authenticating', label: 'Authenticate' },
  { key: 'discovering', label: 'Discover' }, { key: 'test_ssh', label: 'Test SSH' },
  { key: 'installing_exporter', label: 'Node Exporter' }, { key: 'configuring_firewall', label: 'Firewall' },
  { key: 'verifying_exporter', label: 'Verify exporter' }, { key: 'registering_inventory', label: 'Inventory' },
  { key: 'configuring_monitoring', label: 'Prometheus' }, { key: 'validating', label: 'Final diagnosis' },
]

const capacityOptions = [
  ['100', '100 Mbps'], ['1000', '1 Gbps'], ['2500', '2.5 Gbps'], ['10000', '10 Gbps'],
  ['25000', '25 Gbps'], ['40000', '40 Gbps'], ['100000', '100 Gbps'], ['custom', 'Custom'],
] as const

export function ServerOnboardingDialog({ onClose }: Props): React.JSX.Element {
  const [phase, setPhase] = useState<Phase>('detect')
  const [form, setForm] = useState<OnboardingStartRequest>({
    name: '', ip: '', ssh_port: 22, ssh_username: 'root', auth_method: 'password',
    host_key_fingerprint: '', server_profile: 'replaceable',
  })
  const [capacityChoice, setCapacityChoice] = useState('1000')
  const [customCapacity, setCustomCapacity] = useState('')
  const [onboardingId, setOnboardingId] = useState<number | null>(null)
  const [privateKey, setPrivateKey] = useState('')
  const [password, setPassword] = useState('')
  const [discovery, setDiscovery] = useState<OnboardingDiscoveryResponse>()
  const [testResult, setTestResult] = useState<OnboardingTestSSHResponse>()
  const [confirmHostKey, setConfirmHostKey] = useState(false)
  const [requestStartedAt, setRequestStartedAt] = useState<number | null>(null)
  const [requestTimedOut, setRequestTimedOut] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)
  const [, setClock] = useState(() => Date.now())
  const requestGeneration = useRef(0)
  const requestRef = useRef<{ kind: RequestKind; generation: number; controller: AbortController } | undefined>(undefined)
  const requestTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const onboarding = useServerOnboarding(onboardingId)
  const activeJobs = useActiveOnboardings()
  const active = onboarding.onboarding
  const busy = requestStartedAt !== null && !requestTimedOut
  const runningStep = requestRef.current?.kind === 'test_ssh'
    ? 'test_ssh'
    : requestRef.current?.kind === 'start'
      ? 'registering_inventory'
      : 'discovering'
  const progressStep = busy
    ? runningStep
    : discovery
      ? phase === 'fingerprint' ? 'discovering' : phase === 'test' ? 'test_ssh' : 'registering_inventory'
      : null
  const progress = busy
    ? requestRef.current?.kind === 'test_ssh' ? 30 : requestRef.current?.kind === 'start' ? 40 : 5
    : discovery
      ? phase === 'fingerprint' ? 20 : phase === 'test' ? 30 : 40
      : 0

  useEffect(() => {
    if (requestStartedAt === null && onboardingId === null) return undefined
    const timer = setInterval(() => setClock(Date.now()), 1_000)
    return () => clearInterval(timer)
  }, [onboardingId, requestStartedAt])

  useEffect(() => () => {
    requestRef.current?.controller.abort()
    if (requestTimer.current) clearTimeout(requestTimer.current)
  }, [])

  function beginRequest(kind: RequestKind): { generation: number; controller: AbortController } {
    requestRef.current?.controller.abort()
    if (requestTimer.current) clearTimeout(requestTimer.current)
    const generation = requestGeneration.current + 1
    requestGeneration.current = generation
    const controller = new AbortController()
    requestRef.current = { kind, generation, controller }
    setRequestStartedAt(Date.now())
    setRequestTimedOut(false)
    setRequestError(null)
    requestTimer.current = setTimeout(() => {
      if (requestRef.current?.generation !== generation) return
      controller.abort()
      setRequestTimedOut(true)
      setRequestError('La solicitud de onboarding superó los 30 segundos. Puedes reintentar o iniciar una nueva discovery.')
    }, REQUEST_TIMEOUT_MS)
    return { generation, controller }
  }

  function finishRequest(generation: number): void {
    if (requestRef.current?.generation !== generation) return
    if (requestTimer.current) clearTimeout(requestTimer.current)
    requestRef.current = undefined
    setRequestStartedAt(null)
  }

  function resetDiscovery(): void {
    requestGeneration.current += 1
    requestRef.current?.controller.abort()
    if (requestTimer.current) clearTimeout(requestTimer.current)
    requestRef.current = undefined
    setRequestStartedAt(null)
    setRequestTimedOut(false)
    setRequestError(null)
    setOnboardingId(null)
    setDiscovery(undefined)
    setTestResult(undefined)
    setConfirmHostKey(false)
    setPrivateKey('')
    setPassword('')
    setForm((current) => ({ ...current, network_interface: undefined, host_key_fingerprint: '' }))
    setPhase('detect')
  }

  function isCurrentRequest(generation: number): boolean {
    return requestRef.current?.generation === generation
  }

  function update<K extends keyof OnboardingStartRequest>(key: K, value: OnboardingStartRequest[K]): void {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function resumeExisting(job: (typeof activeJobs.jobs)[number]): void {
    setOnboardingId(job.id)
    setPhase('prepare')
    setRequestStartedAt(null)
    setRequestTimedOut(false)
    setRequestError(null)
    setDiscovery(undefined)
    setTestResult(undefined)
    setConfirmHostKey(false)
    setForm((current) => ({
      ...current,
      name: job.server_name,
      ip: job.server_hostname ?? '',
      ssh_port: job.ssh_port,
      ssh_username: job.ssh_username,
      auth_method: job.auth_method,
    }))
  }

  function credentials(): { auth_method: OnboardingStartRequest['auth_method']; password?: string; private_key?: string } {
    return { auth_method: form.auth_method, password: form.auth_method === 'password' ? password : undefined, private_key: form.auth_method === 'private_key' ? privateKey : undefined }
  }

  async function detectServer(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    const request = beginRequest('discover')
    try {
      const response = await onboarding.discover.mutateAsync({ payload: { host: form.ip, port: form.ssh_port, username: form.ssh_username, ...credentials(), confirm_host_key: false }, signal: request.controller.signal })
      if (!isCurrentRequest(request.generation)) return
      setDiscovery(response)
      update('network_interface', response.detected_interface ?? undefined)
      setConfirmHostKey(response.host_key_status === 'already_trusted' || response.host_key_status === 'confirmed')
      setPhase(response.host_key_status === 'new' || response.host_key_status === 'changed' ? 'fingerprint' : 'test')
    } catch (error) {
      if (isCurrentRequest(request.generation) && !request.controller.signal.aborted) setRequestError(errorMessage(error))
    } finally {
      finishRequest(request.generation)
    }
  }

  async function confirmFingerprint(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!confirmHostKey || !discovery?.host_key_fingerprint) return
    const request = beginRequest('discover')
    try {
      const response = await onboarding.discover.mutateAsync({ payload: { host: form.ip, port: form.ssh_port, username: form.ssh_username, ...credentials(), host_key_fingerprint: discovery.host_key_fingerprint, confirm_host_key: true }, signal: request.controller.signal })
      if (!isCurrentRequest(request.generation)) return
      setDiscovery(response)
      if (response.host_key_status !== 'changed') setPhase('test')
    } catch (error) {
      if (isCurrentRequest(request.generation) && !request.controller.signal.aborted) setRequestError(errorMessage(error))
    } finally {
      finishRequest(request.generation)
    }
  }

  async function testSSH(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!discovery?.host_key_fingerprint) return
    const request = beginRequest('test_ssh')
    try {
      const response = await onboarding.testSSH.mutateAsync({ payload: { host: form.ip, port: form.ssh_port, username: form.ssh_username, ...credentials(), host_key_fingerprint: discovery.host_key_fingerprint, confirm_host_key: true }, signal: request.controller.signal })
      if (!isCurrentRequest(request.generation)) return
      setTestResult(response)
      if (response.host_key_status !== 'changed' && response.authentication_ok) setPhase('prepare')
    } catch (error) {
      if (isCurrentRequest(request.generation) && !request.controller.signal.aborted) setRequestError(errorMessage(error))
    } finally {
      finishRequest(request.generation)
    }
  }

  async function prepareServer(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!discovery?.host_key_fingerprint || !testResult?.authentication_ok || !form.name) return
    const request = beginRequest('start')
    try {
      const response = await onboarding.start.mutateAsync({ payload: { ...form, host_key_fingerprint: discovery.host_key_fingerprint, physical_capacity_mbps: selectedCapacity(capacityChoice, customCapacity), ...credentials() }, signal: request.controller.signal })
      if (!isCurrentRequest(request.generation)) return
      setOnboardingId(response.id)
      setPassword('')
      setPrivateKey('')
    } catch (error) {
      if (isCurrentRequest(request.generation) && !request.controller.signal.aborted) setRequestError(errorMessage(error))
    } finally {
      finishRequest(request.generation)
    }
  }

  async function submit(event: React.FormEvent): Promise<void> {
    if (phase === 'detect') return detectServer(event)
    if (phase === 'fingerprint') return confirmFingerprint(event)
    if (phase === 'test') return testSSH(event)
    return prepareServer(event)
  }

  async function retry(): Promise<void> {
    if (onboardingId) await onboarding.retry.mutateAsync({ id: onboardingId, payload: credentials() })
  }

  const error = requestError ?? discovery?.error_message ?? testResult?.error_message ?? active?.last_error_message_sanitized ?? onboarding.error?.message ?? mutationError(onboarding.discover.error) ?? mutationError(onboarding.testSSH.error) ?? mutationError(onboarding.start.error) ?? mutationError(onboarding.retry.error)
  const hasCredentials = form.auth_method === 'password' ? password.length > 0 : privateKey.length > 0
  const canSubmit = phase === 'detect' ? Boolean(form.ip && form.ssh_username && hasCredentials) : phase === 'fingerprint' ? confirmHostKey : phase === 'test' ? Boolean(discovery?.host_key_fingerprint) : Boolean(form.name && testResult?.authentication_ok && testResult.privilege_ok && testResult.temp_write_ok)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
      <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-line bg-panel p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand">Secure onboarding</p><h2 className="mt-2 text-xl font-semibold text-copy">Detect and prepare a server</h2><p className="mt-2 text-sm text-muted">Detect → confirm fingerprint → test SSH → prepare. Credentials stay in memory and are never returned or persisted.</p></div><button type="button" onClick={onClose} className="rounded-lg p-2 text-muted hover:bg-panel-raised hover:text-copy" aria-label="Close"><X size={18} /></button></div>
        {!active ? <><div className="mt-6"><OnboardingStepProgress steps={steps} activeStep={progressStep} progress={progress} /></div><form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={(event) => { void submit(event) }}>
          <Field label="Server name" value={form.name} required onChange={(value) => update('name', value)} />
          <Field label="IP or hostname" value={form.ip} required onChange={(value) => update('ip', value)} />
          <Field label="SSH user" value={form.ssh_username} required onChange={(value) => update('ssh_username', value)} />
          <Field label="SSH port" type="number" value={String(form.ssh_port)} required onChange={(value) => update('ssh_port', Number(value))} />
          <CredentialSelector form={form} update={update} privateKey={privateKey} setPrivateKey={setPrivateKey} password={password} setPassword={setPassword} />
          {discovery && <ReviewPanel discovery={discovery} confirmHostKey={confirmHostKey} setConfirmHostKey={setConfirmHostKey} />}
          {testResult && <TestResultPanel result={testResult} />}
          {phase === 'prepare' && <PrepareFields form={form} update={update} capacityChoice={capacityChoice} setCapacityChoice={setCapacityChoice} customCapacity={customCapacity} setCustomCapacity={setCustomCapacity} />}
          {error && <ErrorPanel message={error} probableCause={discovery?.probable_cause ?? testResult?.probable_cause} />}
          {!discovery && <InfoPanel text="Detect is read-only. No installer, firewall rule or remote file is changed during this step." />}
          {activeJobs.jobs.length > 0 && !discovery && <ResumeJobs jobs={activeJobs.jobs} onResume={resumeExisting} />}
          <button disabled={busy || !canSubmit} type="submit" className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 text-xs font-semibold text-slate-950 disabled:opacity-50 sm:col-span-2">{busy && <LoaderCircle size={14} className="animate-spin" />}{phase === 'detect' ? 'Detect server' : phase === 'fingerprint' ? 'Confirm fingerprint and continue' : phase === 'test' ? 'Test SSH connection' : 'Prepare server'}</button>
          {requestStartedAt && <p className="text-xs text-muted sm:col-span-2">{requestTimedOut ? 'Request timed out' : `Running for ${formatElapsed(Date.now() - requestStartedAt)}`}</p>}
          {(discovery || requestTimedOut) && <button type="button" disabled={busy} onClick={resetDiscovery} className="rounded-xl border border-line px-4 py-2.5 text-xs text-muted sm:col-span-2">Start a new discovery</button>}
        </form></> : <ActiveOnboarding active={active} onboarding={onboarding} error={error ?? undefined} hasCredentials={hasCredentials} retry={retry} credentials={credentials} form={form} update={update} privateKey={privateKey} setPrivateKey={setPrivateKey} password={password} setPassword={setPassword} />}
      </div>
    </div>
  )
}

function ResumeJobs({ jobs, onResume }: { jobs: ReturnType<typeof useActiveOnboardings>['jobs']; onResume: (job: (typeof jobs)[number]) => void }): React.JSX.Element {
  return <div className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-xs sm:col-span-2"><p className="font-semibold text-copy">Resume existing onboarding</p><p className="mt-1 text-muted">A confirmed backend onboarding is still active. Resume it instead of creating a duplicate discovery.</p><div className="mt-3 grid gap-2">{jobs.map((job) => <button key={job.id} type="button" onClick={() => onResume(job)} className="flex items-center justify-between rounded-lg border border-line bg-panel px-3 py-2 text-left hover:border-brand"><span><strong className="block text-copy">{job.server_name}</strong><span className="text-muted">{job.server_hostname ?? 'Host unavailable'} · {job.status}</span></span><span className="font-semibold text-brand">Resume</span></button>)}</div></div>
}

function ActiveOnboarding({ active, onboarding, error, hasCredentials, retry, credentials, form, update, privateKey, setPrivateKey, password, setPassword }: { active: NonNullable<ReturnType<typeof useServerOnboarding>['onboarding']>; onboarding: ReturnType<typeof useServerOnboarding>; error?: string; hasCredentials: boolean; retry: () => Promise<void>; credentials: () => { auth_method: OnboardingStartRequest['auth_method']; password?: string; private_key?: string }; form: OnboardingStartRequest; update: <K extends keyof OnboardingStartRequest>(key: K, value: OnboardingStartRequest[K]) => void; privateKey: string; setPrivateKey: (value: string) => void; password: string; setPassword: (value: string) => void }): React.JSX.Element {
  const diagnosis = onboarding.diagnose.data
  const terminal = ['completed', 'failed', 'rollback_required', 'cancelled'].includes(active.status)
  const canRetry = active.status === 'pending' || ['failed', 'rollback_required', 'cancelled'].includes(active.status)
  const startedAt = Date.parse(active.started_at ?? active.created_at)
  const elapsedSeconds = Number.isFinite(startedAt) ? Math.max(0, Math.floor((Date.now() - startedAt) / 1_000)) : 0
  const timedOut = !terminal && elapsedSeconds >= JOB_VISUAL_TIMEOUT_SECONDS

  return <div className="mt-6">
    <OnboardingStepProgress steps={steps} activeStep={active.current_step} completedStep={active.last_successful_step} progress={active.progress_percent} />
    <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-panel-raised px-4 py-3 text-xs text-muted">
      <span>Current step: <strong className="text-copy">{formatStep(active.current_step)}</strong></span>
      <span>Status: <strong className="text-copy">{active.status}</strong> · elapsed {formatElapsed(elapsedSeconds * 1_000)}</span>
    </div>
    {timedOut && <div className="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">This job has exceeded the 30-second visual timeout. Refresh the status, cancel the job, or retry it after it reaches a terminal state.</div>}
    {error && <div className="mt-5"><ErrorPanel message={error} /></div>}
    <div className="mt-5"><CredentialSelector form={form} update={update} privateKey={privateKey} setPrivateKey={setPrivateKey} password={password} setPassword={setPassword} /></div>
    <div className="mt-5 flex flex-wrap gap-2">
      {canRetry && <button type="button" disabled={!hasCredentials || onboarding.retry.isPending} onClick={() => { void retry().catch(() => undefined) }} className="rounded-xl border border-line px-4 py-2.5 text-xs font-semibold text-copy disabled:opacity-50">Retry Job</button>}
      {!terminal && <button type="button" disabled={onboarding.cancel.isPending} onClick={() => { void onboarding.cancel.mutateAsync().catch(() => undefined) }} className="rounded-xl border border-line px-4 py-2.5 text-xs text-muted disabled:opacity-50">Cancel Job</button>}
      <button type="button" disabled={onboarding.isFetching} onClick={() => { void onboarding.refetch().catch(() => undefined) }} className="rounded-xl border border-line px-4 py-2.5 text-xs text-muted disabled:opacity-50">Force Refresh Status</button>
      <button type="button" disabled={onboarding.diagnose.isPending || !hasCredentials} onClick={() => { void onboarding.diagnose.mutateAsync({ id: active.id, payload: credentials() }).catch(() => undefined) }} className="inline-flex items-center gap-2 rounded-xl border border-line px-4 py-2.5 text-xs font-semibold text-copy disabled:opacity-50"><ShieldCheck size={14} />Diagnose</button>
    </div>
    {onboarding.isFetching && <p className="mt-3 text-xs text-muted">Refreshing onboarding status…</p>}
    {active.status === 'completed' && <p className="mt-5 flex items-center gap-2 text-sm text-success"><ServerCog size={16} />Server connected and ready for read-only monitoring.</p>}
    {onboarding.health && <OnboardingDiagnosticSummary checks={[{ label: 'SSH', value: onboarding.health.ssh }, { label: 'Node Exporter', value: onboarding.health.node_exporter }, { label: 'Prometheus', value: onboarding.health.prometheus_target_status ?? onboarding.health.prometheus }, { label: 'Firewall', value: onboarding.health.firewall }, { label: 'Metrics', value: onboarding.health.metrics_available ? 'available' : 'not_available' }, { label: 'Freshness', value: onboarding.health.freshness }]} />}
    {diagnosis && <OnboardingDiagnosticSummary checks={[{ label: 'Node Exporter', value: diagnosis.node_exporter }, { label: 'Prometheus', value: diagnosis.prometheus_target_status ?? diagnosis.prometheus }, { label: 'Firewall', value: diagnosis.firewall }, { label: 'Network', value: diagnosis.network }, { label: 'Latency', value: `${diagnosis.latency_ms ?? '—'} ms` }, { label: 'Last sample', value: diagnosis.last_sample ?? 'missing' }]} errors={diagnosis.errors} />}
  </div>
}

function ReviewPanel({ discovery, confirmHostKey, setConfirmHostKey }: { discovery: OnboardingDiscoveryResponse; confirmHostKey: boolean; setConfirmHostKey: (value: boolean) => void }): React.JSX.Element {
  const keyStatus = discovery.host_key_status === 'already_trusted' ? 'Already Trusted' : discovery.host_key_status === 'changed' ? 'Host Key Changed' : discovery.host_key_status === 'new' ? 'New fingerprint' : discovery.host_key_status
  return <div className="grid gap-3 rounded-xl border border-line bg-panel-raised p-4 text-xs sm:col-span-2"><p className="font-semibold text-copy">Detected inventory</p><p className="text-muted">Reachable {discovery.reachable ? 'yes' : 'no'} · Authentication {discovery.authentication_ok ? 'ok' : 'failed'} · Privilege {discovery.privilege_ok ? 'ok' : 'needs review'} · Interface {discovery.detected_interface ?? '—'} · Exporter {discovery.exporter_status}</p><p className="text-muted">Host key: <span className={discovery.host_key_status === 'changed' ? 'text-danger' : 'text-copy'}>{keyStatus}</span></p><p className="break-all font-mono text-muted">{discovery.host_key_fingerprint ?? 'not available'}</p>{discovery.discovered_inventory && <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-[11px] text-muted">{JSON.stringify(discovery.discovered_inventory, null, 2)}</pre>}{discovery.warnings.length > 0 && <p className="text-warning">Warnings: {discovery.warnings.join(', ')}</p>}{discovery.blocking_errors.length > 0 && <p className="text-danger">Blocking checks: {discovery.blocking_errors.join(', ')}</p>}{discovery.host_key_status === 'new' && <label className="flex items-start gap-2 text-warning"><input type="checkbox" checked={confirmHostKey} onChange={(event) => setConfirmHostKey(event.target.checked)} />I reviewed this new SSH fingerprint and want to confirm it for this server.</label>}{discovery.host_key_status === 'changed' && <p className="text-danger">The fingerprint changed. Onboarding is blocked until the operator verifies the server identity.</p>}</div>
}

function TestResultPanel({ result }: { result: OnboardingTestSSHResponse }): React.JSX.Element {
  return <div className="grid gap-2 rounded-xl border border-brand/20 bg-brand/5 p-4 text-xs sm:col-span-2"><p className="font-semibold text-copy">SSH preflight (read-only)</p><p className="text-muted">SSH {result.reachable && result.authentication_ok ? 'OK' : 'Failed'} · Privilege {result.privilege_ok ? 'OK' : 'Failed'} · Temporary directory {result.temp_write_ok ? 'OK' : 'Unavailable'} · Host key {result.host_key_status}</p><p className="text-muted">{result.hostname ?? '—'} · {result.os ?? '—'} {result.os_version ?? ''} · {result.architecture ?? '—'}</p><p className="text-muted">Interfaces: {result.interfaces.map((item) => String(item.name ?? 'unknown')).join(', ') || 'none detected'}</p></div>
}

function PrepareFields({ form, update, capacityChoice, setCapacityChoice, customCapacity, setCustomCapacity }: { form: OnboardingStartRequest; update: <K extends keyof OnboardingStartRequest>(key: K, value: OnboardingStartRequest[K]) => void; capacityChoice: string; setCapacityChoice: (value: string) => void; customCapacity: string; setCustomCapacity: (value: string) => void }): React.JSX.Element {
  return <div className="grid gap-4 rounded-xl border border-line bg-panel-raised p-4 sm:col-span-2 sm:grid-cols-2"><p className="text-xs font-semibold text-copy sm:col-span-2">Inventory, network and financial details</p><Field label="Provider" value={form.provider ?? ''} onChange={(value) => update('provider', value || undefined)} /><Field label="Datacenter" value={form.datacenter ?? ''} onChange={(value) => update('datacenter', value || undefined)} /><Field label="Country" value={form.country ?? ''} onChange={(value) => update('country', value.toUpperCase() || undefined)} /><Field label="Network interface (detected, editable)" value={form.network_interface ?? ''} onChange={(value) => update('network_interface', value || undefined)} /><label className="grid gap-2 text-xs text-muted">Network capacity<select value={capacityChoice} onChange={(event) => { setCapacityChoice(event.target.value); if (event.target.value !== 'custom') update('physical_capacity_mbps', Number(event.target.value)) }} className="rounded-xl border border-line bg-panel px-3 py-2.5 text-copy">{capacityOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>{capacityChoice === 'custom' && <Field label="Custom capacity (Mbps)" type="number" value={customCapacity} onChange={(value) => { setCustomCapacity(value); update('physical_capacity_mbps', value ? Number(value) : undefined) }} />}{(['operational_target_mbps', 'recommended_max_mbps', 'minimum_reserve_mbps'] as const).map((key) => <Field key={key} label={key.replaceAll('_', ' ')} type="number" value={form[key] == null ? '' : String(form[key])} onChange={(value) => update(key, value ? Number(value) : undefined)} />)}<Field label="Monthly cost" type="number" value={form.monthly_cost == null ? '' : String(form.monthly_cost)} onChange={(value) => update('monthly_cost', value ? Number(value) : undefined)} /><Field label="Currency" value={form.currency ?? ''} onChange={(value) => update('currency', value.toUpperCase() || undefined)} /><Field label="Next payment date" type="date" value={form.next_payment_date ?? ''} onChange={(value) => update('next_payment_date', value || undefined)} /><label className="grid gap-2 text-xs text-muted">Server profile<select value={form.server_profile ?? 'replaceable'} onChange={(event) => update('server_profile', event.target.value as OnboardingStartRequest['server_profile'])} className="rounded-xl border border-line bg-panel px-3 py-2.5 text-copy"><option value="critical">Critical</option><option value="replaceable">Replaceable</option><option value="shared">Shared</option></select></label><Field label="Prometheus URL" value={form.prometheus_url ?? ''} onChange={(value) => update('prometheus_url', value || undefined)} /><label className="grid gap-2 text-xs text-muted sm:col-span-2">Notes<textarea value={form.notes ?? ''} onChange={(event) => update('notes', event.target.value || undefined)} rows={3} className="rounded-xl border border-line bg-panel px-3 py-2.5 text-copy" /></label></div>
}

function CredentialSelector({ form, update, privateKey, setPrivateKey, password, setPassword }: { form: OnboardingStartRequest; update: <K extends keyof OnboardingStartRequest>(key: K, value: OnboardingStartRequest[K]) => void; privateKey: string; setPrivateKey: (value: string) => void; password: string; setPassword: (value: string) => void }): React.JSX.Element {
  return <div className="grid gap-3 sm:col-span-2"><label className="grid gap-2 text-xs text-muted">Authentication<select value={form.auth_method} onChange={(event) => update('auth_method', event.target.value as OnboardingStartRequest['auth_method'])} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-copy"><option value="password">Temporary password</option><option value="private_key">Private key</option></select></label>{form.auth_method === 'password' ? <Field label="Temporary password" type="password" value={password} required onChange={setPassword} autoComplete="new-password" /> : <label className="grid gap-2 text-xs text-muted">Private key<textarea required value={privateKey} onChange={(event) => setPrivateKey(event.target.value)} rows={5} className="rounded-xl border border-line bg-panel-raised p-3 font-mono text-xs text-copy" autoComplete="off" /></label>}</div>
}

function ErrorPanel({ message, probableCause }: { message: string; probableCause?: string | null }): React.JSX.Element {
  return <div className="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger sm:col-span-2"><p>{message}</p>{probableCause && <p className="mt-1 text-xs text-warning">Probable cause: {probableCause}</p>}</div>
}

function InfoPanel({ text }: { text: string }): React.JSX.Element {
  return <div className="flex items-center gap-2 rounded-xl border border-brand/20 bg-brand/5 p-3 text-xs text-muted sm:col-span-2"><ShieldCheck size={16} className="shrink-0 text-brand" />{text}</div>
}

function Field({ label, value, onChange, type = 'text', required = false, autoComplete }: { label: string; value: string; onChange: (value: string) => void; type?: string; required?: boolean; autoComplete?: string }): React.JSX.Element {
  return <label className="grid gap-2 text-xs text-muted">{label}<input type={type} required={required} value={value} onChange={(event) => onChange(event.target.value)} autoComplete={autoComplete} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-copy outline-none focus:border-brand" /></label>
}

function selectedCapacity(choice: string, custom: string): number | undefined {
  return choice === 'custom' ? (custom ? Number(custom) : undefined) : Number(choice)
}

function formatElapsed(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1_000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}m ${String(seconds).padStart(2, '0')}s`
}

function formatStep(step: string): string {
  return step.replaceAll('_', ' ')
}

function errorMessage(error: unknown): string {
  return error instanceof Error && error.message ? error.message : 'La solicitud de onboarding no pudo completarse.'
}

function mutationError(error: Error | null): string | undefined {
  if (!error || error.name === 'AbortError' || error.name === 'CanceledError') return undefined
  return error.message || 'La solicitud de onboarding no pudo completarse.'
}
