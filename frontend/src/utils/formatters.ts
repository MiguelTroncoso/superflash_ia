export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`
}

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

export function formatThroughput(value: number): string {
  return `${value.toFixed(1)} Mbps`
}

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
