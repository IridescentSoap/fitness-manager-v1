export function businessToday(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

export function addDays(iso: string, days: number): string {
  const [year, month, day] = iso.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export function monthBounds(iso: string): { from: string; to: string } {
  const [year, month] = iso.split('-').map(Number)
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const prefix = `${year.toString().padStart(4, '0')}-${month.toString().padStart(2, '0')}`
  return { from: `${prefix}-01`, to: `${prefix}-${last.toString().padStart(2, '0')}` }
}

export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(2)}%`
}

export function weekdayOf(iso: string): number {
  const [year, month, day] = iso.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  const dayIndex = date.getUTCDay()
  return dayIndex === 0 ? 7 : dayIndex
}
