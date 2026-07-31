import { Radio } from 'lucide-react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { usePageTitle } from '../../hooks/usePageTitle'
import { channelSummaries } from '../../utils/mockData'

export function ChannelsPage(): React.JSX.Element {
  usePageTitle('Channels')

  return (
    <>
      <PageHeader
        eyebrow="Streaming signals"
        title="Channels"
        description="Placeholder channel inventory for the future read-only streaming source adapter."
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <Surface className="p-5">
          <p className="text-sm text-muted">Active channels</p>
          <p className="mt-3 text-3xl font-semibold text-copy">24</p>
          <p className="mt-1 text-xs text-success">100% simulated availability</p>
        </Surface>
        <Surface className="p-5">
          <p className="text-sm text-muted">Total viewers</p>
          <p className="mt-3 text-3xl font-semibold text-copy">48.2K</p>
          <p className="mt-1 text-xs text-muted">Across all categories</p>
        </Surface>
        <Surface className="p-5">
          <p className="text-sm text-muted">Avg. bitrate</p>
          <p className="mt-3 text-3xl font-semibold text-copy">4.9 Mbps</p>
          <p className="mt-1 text-xs text-muted">Current mock snapshot</p>
        </Surface>
      </div>
      <Surface className="mt-5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted">
              <tr>
                <th className="px-5 py-4">Channel</th>
                <th className="px-5 py-4">Category</th>
                <th className="px-5 py-4">Viewers</th>
                <th className="px-5 py-4">Bitrate</th>
                <th className="px-5 py-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {channelSummaries.map((channel) => (
                <tr key={channel.name} className="transition hover:bg-panel-raised/40">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <span className="rounded-lg bg-violet-400/10 p-2 text-violet-300">
                        <Radio size={16} />
                      </span>
                      <span className="font-semibold text-copy">{channel.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-muted">{channel.category}</td>
                  <td className="px-5 py-4 font-medium text-copy">{channel.viewers}</td>
                  <td className="px-5 py-4 text-muted">{channel.bitrate}</td>
                  <td className="px-5 py-4 text-right">
                    <StatusBadge state={channel.state} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Surface>
    </>
  )
}
