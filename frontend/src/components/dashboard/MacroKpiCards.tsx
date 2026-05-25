import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { Card, LoadingState } from '../shared'

export default function MacroKpiCards() {
  const { data, isLoading } = useQuery({
    queryKey: qk.macroKpis(),
    queryFn:  api.getMacroKpis,
    staleTime: 5 * 60_000,
  })

  const KPI_ORDER = ['SELIC_META', 'CDI', 'IPCA_PROJ', 'IFIX']

  if (isLoading) return <LoadingState />

  const kpis = KPI_ORDER
    .map(code => data?.find(k => k.code === code))
    .filter(Boolean) as NonNullable<typeof data>

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {kpis.map(kpi => (
        <Card key={kpi.code} className="p-5 flex flex-col items-center justify-center text-center min-h-[100px]">
          <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">{kpi.label}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-2">
            {kpi.display_value}
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-600 mt-1.5 truncate max-w-full" title={kpi.source}>
            {kpi.source}
          </p>
          {kpi.metric_date && (
            <p className="text-xs text-gray-400 dark:text-gray-600 mt-0.5">
              {new Date(kpi.metric_date).toLocaleDateString('pt-BR')}
            </p>
          )}
        </Card>
      ))}
    </div>
  )
}
