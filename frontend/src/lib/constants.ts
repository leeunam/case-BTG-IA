import type { Period } from '../types'

export const DEFAULT_PERIOD: Period = '1m'

export const PERIOD_OPTIONS: { label: string; value: Period }[] = [
  { label: '7 dias',  value: '7d'  },
  { label: '15 dias', value: '15d' },
  { label: '1 mês',   value: '1m'  },
]

export const OFFER_STATUS_OPTIONS = [
  { label: 'Todas',        value: 'all'       },
  { label: 'Em andamento', value: 'ongoing'   },
  { label: 'Novas hoje',   value: 'new'       },
  { label: 'Encerradas',   value: 'closed'    },
  { label: 'Canceladas',   value: 'cancelled' },
]

export const ALERT_TYPE_LABELS: Record<string, string> = {
  new_offer:          'Nova oferta',
  status_change:      'Mudança de status',
  volume_change:      'Alteração de volume',
  collection_failed:  'Falha de coleta',
  source_stale:       'Fonte desatualizada',
  data_inconsistency: 'Inconsistência de dados',
  concentration:      'Concentração',
  data_gap:           'Dado indisponível',
}

export const OFFER_TYPE_LABELS: Record<string, string> = {
  ipo:       'IPO',
  follow_on: 'Follow-on',
}

export const DISTRIBUTION_RITE_LABELS: Record<string, string> = {
  rito_ordinario:   'Rito Ordinário',
  rito_automatico:  'Rito Automático',
  esforcos_restritos: 'Esforços Restritos',
}

export const PDF_POLL_INTERVAL_MS = 2500
export const STALE_SOURCE_HOURS   = 26
