import { Boxes, Palette, SlidersHorizontal, Sparkles } from 'lucide-react'
import { PageHeader } from '../../components/common/PageHeader'
import { Surface } from '../../components/common/Surface'
import { usePageTitle } from '../../hooks/usePageTitle'

const settingGroups = [
  {
    title: 'Workspace',
    description: 'UI preferences and navigation behavior.',
    icon: SlidersHorizontal,
    items: ['Default time range', 'Sidebar density', 'Refresh preferences'],
  },
  {
    title: 'Appearance',
    description: 'Visual system for the monitoring workspace.',
    icon: Palette,
    items: ['Dark theme', 'Accent color', 'Chart contrast'],
  },
  {
    title: 'Data sources',
    description: 'Future adapter configuration boundary.',
    icon: Boxes,
    items: ['Mock source', 'Prometheus adapter', 'Streaming adapter'],
  },
]

export function SettingsPage(): React.JSX.Element {
  usePageTitle('Settings')

  return (
    <>
      <PageHeader
        eyebrow="Workspace configuration"
        title="Settings"
        description="Visual placeholders for future frontend preferences. No settings are persisted or sent to the backend in this phase."
      />
      <div className="grid gap-5 lg:grid-cols-3">
        {settingGroups.map(({ title, description, icon: Icon, items }) => (
          <Surface key={title} className="p-5">
            <span className="inline-flex rounded-xl bg-brand/10 p-2.5 text-brand">
              <Icon size={19} />
            </span>
            <h2 className="mt-5 text-sm font-semibold text-copy">{title}</h2>
            <p className="mt-2 text-xs leading-5 text-muted">{description}</p>
            <div className="mt-5 space-y-2">
              {items.map((item) => (
                <div
                  key={item}
                  className="flex items-center justify-between rounded-lg border border-line bg-panel-raised/40 px-3 py-2.5 text-xs text-muted"
                >
                  <span>{item}</span>
                  <span className="rounded-full bg-slate-500/10 px-2 py-0.5 text-[10px] text-slate-400">
                    Soon
                  </span>
                </div>
              ))}
            </div>
          </Surface>
        ))}
      </div>
      <Surface className="mt-5 flex flex-col gap-4 border-brand/20 bg-brand/[0.04] p-5 sm:flex-row sm:items-center">
        <span className="rounded-xl bg-brand/10 p-3 text-brand">
          <Sparkles size={21} />
        </span>
        <div>
          <p className="text-sm font-semibold text-copy">Frontend foundation ready</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            API services, TanStack Query and state boundaries are prepared without making network
            requests.
          </p>
        </div>
      </Surface>
    </>
  )
}
