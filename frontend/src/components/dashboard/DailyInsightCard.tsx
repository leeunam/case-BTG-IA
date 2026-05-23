import { useQuery } from '@tanstack/react-query'
import { Sparkles, Clock, AlertCircle } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { fmtDateTime } from '../../lib/formatters'
import { Card, LoadingState } from '../shared'

export default function DailyInsightCard() {
  const { data, isLoading, isError } = useQuery({
    queryKey: qk.dailyInsight(),
    queryFn:  api.getDailyInsight,
    staleTime: 5 * 60_000,
  })

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-brand-600 dark:text-brand-400" />
        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Panorama do dia
        </span>
        <span className="ml-auto text-xs text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
          Sem recomendação de investimento
        </span>
      </div>

      {isLoading && <LoadingState label="Carregando panorama..." />}

      {isError && (
        <div className="flex items-center gap-2 text-red-500 text-sm py-2">
          <AlertCircle className="w-4 h-4" />
          <span>Não foi possível carregar o panorama.</span>
        </div>
      )}

      {data && data.status === 'not_generated' && (
        <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-sm py-2">
          <AlertCircle className="w-4 h-4" />
          <span>Insight do dia não gerado.</span>
        </div>
      )}

      {data && data.status === 'failed' && (
        <div className="flex items-center gap-2 text-red-500 text-sm py-2">
          <AlertCircle className="w-4 h-4" />
          <span>Falha na geração do insight.</span>
        </div>
      )}

      {data && (data.status === 'generated' || data.status === 'stale') && data.text && (
        <>
          {data.status === 'stale' && (
            <div className="text-xs text-amber-600 dark:text-amber-400 mb-2">
              ⚠️ Insight desatualizado
            </div>
          )}
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">
            {data.text}
          </p>
          {data.generated_at && (
            <div className="flex items-center gap-1 mt-3 text-xs text-gray-400">
              <Clock className="w-3 h-3" />
              <span>Gerado em {fmtDateTime(data.generated_at)}</span>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
