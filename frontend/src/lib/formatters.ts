export function fmtVolume(value: number | null | undefined): string {
  if (value == null) return 'N/D'
  if (value >= 1e9) return `R$ ${(value / 1e9).toFixed(1)} B`
  if (value >= 1e6) return `R$ ${(value / 1e6).toFixed(0)} M`
  if (value >= 1e3) return `R$ ${(value / 1e3).toFixed(0)} K`
  return `R$ ${value.toFixed(0)}`
}

export function fmtPct(value: number | null | undefined, decimals = 2): string {
  if (value == null) return 'N/D'
  return `${value.toFixed(decimals)}%`
}

export function fmtNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null) return 'N/D'
  return value.toFixed(decimals)
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('pt-BR')
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function fmtRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'há menos de 1h'
  if (h < 24) return `há ${h}h`
  const d = Math.floor(h / 24)
  return `há ${d} dia${d > 1 ? 's' : ''}`
}
