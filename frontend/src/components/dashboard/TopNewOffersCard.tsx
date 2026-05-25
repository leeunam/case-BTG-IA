import { useQuery } from '@tanstack/react-query'
import { Zap } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { fmtVolume } from '../../lib/formatters'
import { OFFER_TYPE_LABELS, DISTRIBUTION_RITE_LABELS } from '../../lib/constants'
import { Card, Badge, LoadingState, EmptyState } from '../shared'

function fmtRefDate(isoDate: string, isToday: boolean): string {
  if (isToday) return 'hoje'
  const d = new Date(isoDate + 'T12:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
}

export default function TopNewOffersCard() {
  const { data, isLoading } = useQuery({
    queryKey: qk.topNewOffers(),
    queryFn:  api.getTopNewOffers,
    refetchInterval: 5 * 60_000,
  })

  const items = Array.isArray(data) ? [] : (data?.items ?? [])
  const refDate = Array.isArray(data) ? null : data?.ref_date ?? null
  const isToday = Array.isArray(data) ? false : (data?.is_today ?? true)

  const title = refDate
    ? `Novas ofertas — ${fmtRefDate(refDate, isToday)}`
    : 'Novas ofertas hoje'

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-4 h-4 text-amber-500" />
        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          {title}
        </span>
      </div>

      {isLoading && <LoadingState />}

      {!isLoading && items.length === 0 && (
        <EmptyState message="Nenhuma oferta registrada." />
      )}

      {items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {items.map(offer => (
            <li key={offer.id} className="flex flex-col gap-1 pb-3 border-b border-gray-100 dark:border-gray-800 last:border-0 last:pb-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[180px]">
                  {offer.name}
                </span>
                {offer.ticker && (
                  <span className="text-xs text-gray-500 font-mono">[{offer.ticker}]</span>
                )}
                <Badge variant={offer.offer_type === 'ipo' ? 'purple' : 'blue'}>
                  {OFFER_TYPE_LABELS[offer.offer_type] ?? offer.offer_type}
                </Badge>
                {offer.distribution_rite && (
                  <Badge variant="gray">
                    {DISTRIBUTION_RITE_LABELS[offer.distribution_rite] ?? offer.distribution_rite}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                <span>Vol.: {fmtVolume(offer.total_volume)}</span>
                {offer.coordinator && <span>· {offer.coordinator}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
