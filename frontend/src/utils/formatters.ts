export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`
}

export function formatNullablePercent(value: number | null): string {
  return value === null ? '—' : formatPercent(value)
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

export function formatNullableThroughput(value: number | null): string {
  return value === null ? '—' : formatThroughput(value)
}

export function formatDateTime(value: string | null): string {
  if (value === null) return 'No data available'
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
