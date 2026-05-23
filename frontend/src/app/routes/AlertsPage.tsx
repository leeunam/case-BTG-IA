import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, BellOff, CheckCheck } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { DEFAULT_PERIOD, ALERT_TYPE_LABELS, OFFER_TYPE_LABELS } from '../../lib/constants'
import { fmtDateTime } from '../../lib/formatters'
import { Card, PeriodFilter, Badge, LoadingState, ErrorState, EmptyState } from '../../components/shared'
import type { Period } from '../../types'
import { clsx } from 'clsx'

const ALERT_PERIOD_OPTIONS = [
  { label: '1 dia',  value: '1d'  },
  { label: '7 dias', value: '7d'  },
  { label: '14 dias',value: '15d' },
  { label: '1 mês',  value: '1m'  },
]

function alertVariant(type: string) {
  if (['new_offer'].includes(type)) return 'green'
  if (['status_change', 'volume_change'].includes(type)) return 'blue'
  if (['collection_failed', 'source_stale'].includes(type)) return 'red'
  return 'gray'
}

export default function AlertsPage() {
  const [period, setPeriod] = useState<Period>(DEFAULT_PERIOD)
  const [page, setPage] = useState(1)
  const qc = useQueryClient()

  const { data: summary } = useQuery({
    queryKey: qk.alertSummary(period),
    queryFn:  () => api.getAlertSummary(period),
  })
  const { data, isLoading, isError } = useQuery({
    queryKey: qk.alerts(period, page),
    queryFn:  () => api.getAlerts(period, page),
    placeholderData: prev => prev,
  })

  const markSeen = useMutation({
    mutationFn: ({ id, seen }: { id: number; seen: boolean }) => api.markAlertSeen(id, seen),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.alerts(period, page) })
      qc.invalidateQueries({ queryKey: qk.alertSummary(period) })
    },
  })
  const markAll = useMutation({
    mutationFn: () => api.markAllSeen(period),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] })
      qc.invalidateQueries({ queryKey: ['alert-summary'] })
    },
  })

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Alertas</h1>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{summary.total}</p>
            <p className="text-xs text-gray-500 mt-1">Total de alertas</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-emerald-600">{summary.seen}</p>
            <p className="text-xs text-gray-500 mt-1">✅ Vistos</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-red-500">{summary.unseen}</p>
            <p className="text-xs text-gray-500 mt-1">Não vistos</p>
          </Card>
        </div>
      )}

      {/* Filters + actions */}
      <div className="flex flex-wrap items-center gap-3">
        <PeriodFilter value={period} onChange={p => { setPeriod(p); setPage(1) }} />
        <button
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending || summary?.unseen === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors ml-auto"
        >
          <CheckCheck className="w-4 h-4" />
          Marcar todos como vistos
        </button>
      </div>

      {/* Alerts table */}
      {isLoading && <LoadingState />}
      {isError && <ErrorState message="Erro ao carregar alertas." />}
      {!isLoading && !isError && data?.items.length === 0 && (
        <EmptyState message="Nenhum alerta no período selecionado." />
      )}
      {!isLoading && !isError && data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <table className="w-full text-sm min-w-[700px]">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-800 text-left">
                <th className="px-4 py-3 text-xs font-semibold text-gray-400 w-10">Visto</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-400">Tipo</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-400">Ativo</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-400">Fundo</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-400">Ticker</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-400">Data/hora</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-400">Detalhe</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map(alert => (
                <tr
                  key={alert.id}
                  className={clsx(
                    'border-b border-gray-50 dark:border-gray-800/50 last:border-0 transition-colors',
                    alert.seen
                      ? 'hover:bg-gray-50 dark:hover:bg-gray-800/30'
                      : 'bg-amber-50/40 dark:bg-amber-900/5 hover:bg-amber-50/60 dark:hover:bg-amber-900/10',
                  )}
                >
                  <td className="px-4 py-3">
                    <button
                      onClick={() => markSeen.mutate({ id: alert.id, seen: !alert.seen })}
                      className="rounded p-0.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                      title={alert.seen ? 'Marcar como não visto' : 'Marcar como visto'}
                    >
                      {alert.seen
                        ? <Bell className="w-4 h-4 text-gray-300" />
                        : <BellOff className="w-4 h-4 text-amber-500" />}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={alertVariant(alert.type)}>
                      {ALERT_TYPE_LABELS[alert.type] ?? alert.type}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400 text-xs">
                    {alert.offer_type ? OFFER_TYPE_LABELS[alert.offer_type] : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-800 dark:text-gray-200 max-w-[160px] truncate block">
                      {alert.offer_name ?? '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs font-mono text-gray-500">{alert.ticker ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {fmtDateTime(alert.created_at)}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 max-w-[200px]">
                    {alert.detail}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
