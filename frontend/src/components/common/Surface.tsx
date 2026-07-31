import type { PropsWithChildren } from 'react'
import { cn } from '../../utils/formatters'

interface SurfaceProps extends PropsWithChildren {
  className?: string
}

export function Surface({ children, className }: SurfaceProps): React.JSX.Element {
  return (
    <section
      className={cn(
        'rounded-2xl border border-line bg-panel shadow-[0_14px_40px_rgba(0,0,0,0.16)]',
        className,
      )}
    >
      {children}
    </section>
  )
}
