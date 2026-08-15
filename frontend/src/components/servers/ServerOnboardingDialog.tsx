import { LoaderCircle, RefreshCw, ServerCog, ShieldCheck, X } from 'lucide-react'
import { useState } from 'react'
import { useServerOnboarding } from '../../hooks/useServerOnboarding'
import type { OnboardingStartRequest } from '../../types/api'

interface Props {
  onClose: () => void
}

const steps = [
  ['connecting', 'Connect'], ['authenticating', 'Authenticate'], ['discovering', 'Discover'],
  ['installing_exporter', 'Node Exporter'], ['configuring_firewall', 'Firewall'],
  ['verifying_exporter', 'Verify exporter'], ['registering_inventory', 'Inventory'],
  ['configuring_monitoring', 'Prometheus'], ['validating', 'Final diagnosis'],
]

export function ServerOnboardingDialog({ onClose }: Props): React.JSX.Element {
  const [form, setForm] = useState<OnboardingStartRequest>({
    name: '', ip: '', ssh_port: 22, ssh_username: 'root', auth_method: 'private_key', host_key_fingerprint: '',
  })
  const [onboardingId, setOnboardingId] = useState<number | null>(null)
  const [privateKey, setPrivateKey] = useState('')
  const [password, setPassword] = useState('')
  const [discovery, setDiscovery] = useState<ReturnType<typeof useServerOnboarding>['discover']['data']>()
  const [confirmHostKey, setConfirmHostKey] = useState(false)
  const onboarding = useServerOnboarding(onboardingId)
  const active = onboarding.onboarding
  const busy = onboarding.start.isPending || onboarding.discover.isPending || onboarding.retry.isPending || onboarding.rollback.isPending

  function update<K extends keyof OnboardingStartRequest>(key: K, value: OnboardingStartRequest[K]): void {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function credentials(): { auth_method: OnboardingStartRequest['auth_method']; password?: string; private_key?: string } {
    return {
      auth_method: form.auth_method,
      password: form.auth_method === 'password' ? password : undefined,
      private_key: form.auth_method === 'private_key' ? privateKey : undefined,
    }
  }

  async function discoverServer(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    const response = await onboarding.discover.mutateAsync({
      host: form.ip,
      port: form.ssh_port,
      username: form.ssh_username,
      ...credentials(),
      host_key_fingerprint: discovery?.host_key_fingerprint ?? undefined,
      confirm_host_key: confirmHostKey,
    })
    setDiscovery(response)
    setForm((current) => ({
      ...current,
      network_interface: current.network_interface ?? response.detected_interface ?? undefined,
    }))
    setConfirmHostKey(response.host_key_status !== 'new' && response.host_key_status !== 'changed')
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!discovery?.host_key_fingerprint || discovery.blocking_errors.length > 0) return
    const response = await onboarding.start.mutateAsync({
      ...form,
      host_key_fingerprint: discovery.host_key_fingerprint,
      ...credentials(),
    })
    setOnboardingId(response.id)
  }

  async function retry(): Promise<void> {
    if (!onboardingId) return
    await onboarding.retry.mutateAsync({ id: onboardingId, payload: credentials() })
  }

  const error = onboarding.discover.error?.message ?? onboarding.start.error?.message ?? onboarding.retry.error?.message ?? active?.last_error_message_sanitized
  const diagnosis = onboarding.diagnose.data
  const reviewReady = discovery !== undefined
  const hostKeyConfirmed = discovery?.host_key_status !== 'new' && discovery?.host_key_status !== 'changed'
  const requiresHostKeyConfirmation = discovery?.blocking_errors.includes('HOST_KEY_CONFIRMATION_REQUIRED') ?? false
  const primaryActionReady = reviewReady
    ? requiresHostKeyConfirmation
      ? confirmHostKey
      : Boolean(form.name && hostKeyConfirmed && discovery?.blocking_errors.length === 0)
    : Boolean(form.ip)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
      <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-line bg-panel p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand">Secure onboarding</p><h2 className="mt-2 text-xl font-semibold text-copy">Detect and prepare a server</h2><p className="mt-2 text-sm text-muted">Credentials stay in memory for the request only. Discovery is read-only until you confirm the review.</p></div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-muted hover:bg-panel-raised hover:text-copy" aria-label="Close"><X size={18} /></button>
        </div>
        {!active ? (
          <form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={(event) => { void (reviewReady && !requiresHostKeyConfirmation ? submit(event) : discoverServer(event)) }}>
            <Field label="Name" value={form.name} required={reviewReady} onChange={(value) => update('name', value)} />
            <Field label="IP or hostname" value={form.ip} required onChange={(value) => update('ip', value)} />
            <Field label="SSH user" value={form.ssh_username} required onChange={(value) => update('ssh_username', value)} />
            <Field label="SSH port" type="number" value={String(form.ssh_port)} required onChange={(value) => update('ssh_port', Number(value))} />
            <label className="grid gap-2 text-xs text-muted sm:col-span-2">Authentication<select value={form.auth_method} onChange={(event) => update('auth_method', event.target.value as OnboardingStartRequest['auth_method'])} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-copy"><option value="private_key">Private key</option><option value="password">Temporary password</option></select></label>
            {form.auth_method === 'private_key' ? <label className="grid gap-2 text-xs text-muted sm:col-span-2">Private key<textarea required value={privateKey} onChange={(event) => setPrivateKey(event.target.value)} rows={5} className="rounded-xl border border-line bg-panel-raised p-3 font-mono text-xs text-copy outline-none focus:border-brand" autoComplete="off" /></label> : <Field label="Temporary password" type="password" value={password} required onChange={setPassword} autoComplete="new-password" />}
            {reviewReady && <ReviewPanel discovery={discovery} confirmHostKey={confirmHostKey} setConfirmHostKey={setConfirmHostKey} />}
            {reviewReady && <div className="grid gap-4 sm:col-span-2 sm:grid-cols-2"><Field label="Name" value={form.name} required onChange={(value) => update('name', value)} /><Field label="Provider" value={form.provider ?? ''} onChange={(value) => update('provider', value || undefined)} /><Field label="Datacenter" value={form.datacenter ?? ''} onChange={(value) => update('datacenter', value || undefined)} /><Field label="Country" value={form.country ?? ''} onChange={(value) => update('country', value.toUpperCase() || undefined)} /><Field label="Network interface override" value={form.network_interface ?? ''} onChange={(value) => update('network_interface', value || undefined)} /></div>}
            {error && <p className="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger sm:col-span-2">{error}</p>}
            {!reviewReady && <div className="flex items-center gap-2 rounded-xl border border-brand/20 bg-brand/5 p-3 text-xs text-muted sm:col-span-2"><ShieldCheck size={16} className="shrink-0 text-brand" />First detect is read-only. A new SSH fingerprint must be explicitly confirmed before onboarding.</div>}
            <button disabled={busy || !primaryActionReady} type="submit" className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 text-xs font-semibold text-slate-950 disabled:opacity-50 sm:col-span-2">{busy && <LoaderCircle size={14} className="animate-spin" />}{!reviewReady ? 'Detect server' : requiresHostKeyConfirmation ? 'Confirm fingerprint and detect again' : 'Confirm and prepare server'}</button>
            {reviewReady && <button type="button" disabled={busy} onClick={() => { setDiscovery(undefined); setConfirmHostKey(false) }} className="rounded-xl border border-line px-4 py-2.5 text-xs text-muted sm:col-span-2">Start a new discovery</button>}
          </form>
        ) : (
          <div className="mt-6">
            <div className="flex items-center justify-between text-xs"><span className="font-semibold text-copy">{active.status}</span><span className="text-muted">{active.progress_percent}%</span></div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-panel-raised"><div className="h-full bg-brand transition-all" style={{ width: `${active.progress_percent}%` }} /></div>
            <div className="mt-6 grid gap-2 sm:grid-cols-3">{steps.map(([key, label]) => <div key={key} className={`rounded-xl border p-3 text-xs ${active.current_step === key ? 'border-brand bg-brand/10 text-copy' : active.last_successful_step === key ? 'border-success/30 text-success' : 'border-line text-muted'}`}><span className="block font-semibold">{label}</span><span className="mt-1 block">{active.last_successful_step === key ? 'Complete' : active.current_step === key ? 'In progress' : 'Pending'}</span></div>)}</div>
            {error && <p className="mt-5 rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</p>}
            {(active.status === 'pending' || active.status === 'failed' || active.status === 'rollback_required' || active.status === 'cancelled') && <div className="mt-5 flex flex-wrap gap-2"><button type="button" onClick={() => { void retry() }} className="inline-flex items-center gap-2 rounded-xl border border-line px-4 py-2.5 text-xs font-semibold text-copy"><RefreshCw size={14} />{active.status === 'pending' ? 'Resume' : 'Retry'}</button><button type="button" onClick={() => { void onboarding.rollback.mutateAsync({ id: active.id, payload: credentials() }) }} className="rounded-xl border border-warning/30 px-4 py-2.5 text-xs font-semibold text-warning">Rollback managed changes</button></div>}
            {!['completed', 'failed', 'rollback_required', 'cancelled'].includes(active.status) && <button type="button" onClick={() => { void onboarding.cancel.mutateAsync() }} className="mt-5 rounded-xl border border-line px-4 py-2.5 text-xs text-muted">Cancel</button>}
            {active.status === 'completed' && <p className="mt-5 flex items-center gap-2 text-sm text-success"><ServerCog size={16} />Server connected and ready for read-only monitoring.</p>}
            {onboarding.health && <p className="mt-3 rounded-xl border border-line bg-panel-raised p-3 text-xs text-muted">Health: {onboarding.health.overall_status} · SSH {onboarding.health.ssh} · Exporter {onboarding.health.node_exporter} · Prometheus {onboarding.health.prometheus} · Metrics {onboarding.health.metrics_available ? 'available' : 'not available'} · Last scrape {onboarding.health.last_scrape ?? '—'}</p>}
            <div className="mt-5"><button type="button" disabled={onboarding.diagnose.isPending} onClick={() => { void onboarding.diagnose.mutateAsync({ id: active.id, payload: credentials() }) }} className="inline-flex items-center gap-2 rounded-xl border border-line px-4 py-2.5 text-xs font-semibold text-copy"><ShieldCheck size={14} />Diagnose</button>{diagnosis && <div className="mt-3 rounded-xl border border-line bg-panel-raised p-4 text-xs"><p className="font-semibold text-copy">Diagnosis: {diagnosis.status}</p><p className="mt-2 text-muted">Node Exporter {diagnosis.node_exporter} · Prometheus {diagnosis.prometheus} · Firewall {diagnosis.firewall} · Network {diagnosis.network} · Latency {diagnosis.latency_ms ?? '—'} ms</p>{diagnosis.errors.length > 0 && <ul className="mt-2 list-disc pl-4 text-warning">{diagnosis.errors.map((item) => <li key={item}>{item}</li>)}</ul>}</div>}</div>
          </div>
        )}
      </div>
    </div>
  )
}

function ReviewPanel({ discovery, confirmHostKey, setConfirmHostKey }: { discovery: NonNullable<ReturnType<typeof useServerOnboarding>['discover']['data']>; confirmHostKey: boolean; setConfirmHostKey: (value: boolean) => void }): React.JSX.Element {
  return <div className="grid gap-3 rounded-xl border border-line bg-panel-raised p-4 text-xs sm:col-span-2"><p className="font-semibold text-copy">Detected inventory</p><p className="text-muted">Reachable {discovery.reachable ? 'yes' : 'no'} · Authentication {discovery.authentication_ok ? 'ok' : 'failed'} · Privilege {discovery.privilege_ok ? 'ok' : 'needs review'} · Interface {discovery.detected_interface ?? '—'} · Exporter {discovery.exporter_status}</p><p className="break-all text-muted">SSH fingerprint: <span className="font-mono text-copy">{discovery.host_key_fingerprint ?? 'not available'}</span></p>{discovery.discovered_inventory && <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-[11px] text-muted">{JSON.stringify(discovery.discovered_inventory, null, 2)}</pre>}{discovery.warnings.length > 0 && <p className="text-warning">Warnings: {discovery.warnings.join(', ')}</p>}{discovery.blocking_errors.length > 0 && <p className="text-danger">Blocking checks: {discovery.blocking_errors.join(', ')}</p>}{discovery.host_key_status === 'new' && <label className="flex items-start gap-2 text-warning"><input type="checkbox" checked={confirmHostKey} onChange={(event) => setConfirmHostKey(event.target.checked)} />I reviewed this new SSH fingerprint and want to confirm it for this server.</label>}</div>
}

function Field({ label, value, onChange, type = 'text', required = false, autoComplete }: { label: string; value: string; onChange: (value: string) => void; type?: string; required?: boolean; autoComplete?: string }): React.JSX.Element {
  return <label className="grid gap-2 text-xs text-muted">{label}<input type={type} required={required} value={value} onChange={(event) => onChange(event.target.value)} autoComplete={autoComplete} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-copy outline-none focus:border-brand" /></label>
}
