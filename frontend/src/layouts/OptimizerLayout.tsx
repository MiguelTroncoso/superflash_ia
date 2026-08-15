import { BrainCircuit, Calculator, CircleDollarSign, Gauge, Lightbulb } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'
import { PageHeader } from '../components/common/PageHeader'
import { cn } from '../utils/formatters'

const optimizerLinks = [
  { label: 'Capacity', path: '/optimizer/capacity', icon: Gauge },
  { label: 'Costs', path: '/optimizer/costs', icon: CircleDollarSign },
  { label: 'Simulator', path: '/optimizer/simulator', icon: Calculator },
  { label: 'Recommendations', path: '/optimizer/recommendations', icon: Lightbulb },
]

export function OptimizerLayout(): React.JSX.Element {
  return (
    <>
      <PageHeader
        eyebrow="Infrastructure intelligence"
        title="Optimizer"
        description="Deterministic, explainable planning tools. Every scenario is local and read-only."
        action={<BrainCircuit className="text-brand" size={30} />}
      />
      <nav className="mb-6 flex flex-wrap gap-2" aria-label="Optimizer sections">
        {optimizerLinks.map(({ label, path, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              cn(
                'inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition',
                isActive
                  ? 'border-brand/40 bg-brand/10 text-brand'
                  : 'border-line bg-panel text-muted hover:text-copy',
              )
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  )
}
