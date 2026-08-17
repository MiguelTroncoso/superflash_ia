import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, LoaderCircle, ShieldAlert, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { apiService } from '../../services/apiService'
import type { ServerDeletionResponse, ServerResponse } from '../../types/api'

interface Props {
  server: ServerResponse
  onClose: () => void
  onDeleted: (result: ServerDeletionResponse) => void
}

export function ServerDeletionDialog({ server, onClose, onDeleted }: Props): React.JSX.Element {
  const queryClient = useQueryClient()
  const [armed, setArmed] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const impact = useQuery({
    queryKey: ['server-deletion-impact', server.id],
    queryFn: () => apiService.getServerDeletionImpact(server.id),
    staleTime: 10_000,
    retry: false,
  })
  const deletion = useMutation({
    mutationFn: () => apiService.deleteServer(server.id, { confirmation, hostname: server.hostname }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['servers'] })
      await queryClient.invalidateQueries({ queryKey: ['server', server.id] })
      onDeleted(result)
    },
  })
  const canConfirm = Boolean(impact.data && armed && confirmation === server.name && !deletion.isPending)

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4" role="alertdialog" aria-modal="true" aria-labelledby="server-delete-title">
      <div className="w-full max-w-lg rounded-2xl border border-danger/30 bg-panel p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3"><span className="rounded-xl bg-danger/10 p-2 text-danger"><ShieldAlert size={19} /></span><div><h2 id="server-delete-title" className="text-lg font-semibold text-copy">Archive or delete server</h2><p className="mt-1 text-xs text-muted">This protected API action requires two explicit confirmations.</p></div></div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-muted hover:bg-panel-raised hover:text-copy" aria-label="Close"><X size={17} /></button>
        </div>
        <div className="mt-5 rounded-xl border border-line bg-panel-raised p-4 text-sm"><p className="font-semibold text-copy">{server.name}</p><p className="mt-1 font-mono text-xs text-muted">{server.hostname ?? 'Host not configured'}</p></div>
        {impact.isPending && <p className="mt-4 flex items-center gap-2 text-xs text-muted"><LoaderCircle size={14} className="animate-spin" />Checking related metrics, alerts, jobs and history…</p>}
        {impact.isError && <p className="mt-4 rounded-xl border border-danger/30 bg-danger/10 p-3 text-xs text-danger">The server impact could not be checked. Nothing was changed.</p>}
        {impact.data && <div className="mt-4 rounded-xl border border-line p-4 text-xs text-muted"><p>{impact.data.can_hard_delete ? 'No productive relations were found. A complete test-inventory deletion is allowed.' : 'Historical or operational relations exist. The server will be archived and history will be preserved.'}</p><p className="mt-2">Metrics {impact.data.relations.metrics} · Alerts {impact.data.relations.alerts} · Snapshots {impact.data.relations.inventory_snapshots} · Channels {impact.data.relations.assigned_channels} · Onboarding jobs {impact.data.relations.onboarding_jobs}</p></div>}
        <label className="mt-5 flex items-start gap-2 text-xs text-muted"><input type="checkbox" checked={armed} onChange={(event) => setArmed(event.target.checked)} disabled={!impact.data || deletion.isPending} /><span>I understand that <strong className="text-copy">{server.name}</strong> and host <strong className="text-copy">{server.hostname ?? 'not configured'}</strong> are the target.</span></label>
        {armed && <label className="mt-4 grid gap-2 text-xs text-muted">Type the server name to confirm<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder={server.name} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-copy outline-none focus:border-danger" autoComplete="off" /></label>}
        {deletion.error && <p className="mt-4 rounded-xl border border-danger/30 bg-danger/10 p-3 text-xs text-danger">{deletion.error.message}</p>}
        <div className="mt-6 flex flex-wrap justify-end gap-2"><button type="button" onClick={onClose} disabled={deletion.isPending} className="rounded-xl border border-line px-4 py-2.5 text-xs text-muted disabled:opacity-50">Cancel</button><button type="button" onClick={() => { void deletion.mutateAsync() }} disabled={!canConfirm} className="inline-flex items-center gap-2 rounded-xl bg-danger px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-40">{deletion.isPending && <LoaderCircle size={14} className="animate-spin" />}{impact.data?.can_hard_delete ? <Trash2 size={14} /> : <Archive size={14} />}{impact.data?.can_hard_delete ? 'Delete server' : 'Archive server'}</button></div>
      </div>
    </div>
  )
}
