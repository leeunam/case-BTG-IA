import { useQuery } from '@tanstack/react-query'
import { Zap } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { fmtVolume } from '../../lib/formatters'
import { OFFER_TYPE_LABELS, DISTRIBUTION_RITE_LABELS } from '../../lib/constants'
import { Card, Badge, LoadingState, EmptyState } from '../shared'

export default function TopNewOffersCard() {
  const { data, isLoading } = useQuery({
    queryKey: qk.topNewOffers(),
    queryFn:  api.getTopNewOffers,
    refetchInterval: 5 * 60_000,
  })

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-4 h-4 text-amber-500" />
        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Novas ofertas hoje
        </span>
      </div>

      {isLoading && <LoadingState />}

      {!isLoading && (!data || data.length === 0) && (
        <EmptyState message="Nenhuma oferta nova hoje." />
      )}

      {data && data.length > 0 && (
        <ul className="flex flex-col gap-3">
          {data.map(offer => (
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
