import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { DEFAULT_PERIOD } from '../../lib/constants'
import { fmtVolume } from '../../lib/formatters'
import { Card, SectionHeader, PeriodFilter, LoadingState } from '../../components/shared'
import DailyInsightCard from '../../components/dashboard/DailyInsightCard'
import MacroKpiCards from '../../components/dashboard/MacroKpiCards'
import TopNewOffersCard from '../../components/dashboard/TopNewOffersCard'
import PipelineHealthPanel from '../../components/dashboard/PipelineHealthPanel'
import OffersTable from '../../components/dashboard/OffersTable'
import type { Period } from '../../types'

export default function DashboardPage() {
  const [period, setPeriod] = useState<Period>(DEFAULT_PERIOD)

  const { data: volume } = useQuery({
    queryKey: qk.volume(period),
    queryFn:  () => api.getVolume(period),
  })
  const { data: ranking, isLoading: rankingLoading } = useQuery({
    queryKey: qk.ranking(period),
    queryFn:  () => api.getRanking(period),
  })
  const { data: ipoFo } = useQuery({
    queryKey: qk.ipoVsFO(period),
    queryFn:  () => api.getIpoVsFO(period),
  })

  const ipoFoData = ipoFo ? [
    { name: 'IPO', value: ipoFo.ipo_volume, count: ipoFo.ipo_count, fill: '#7c3aed' },
    { name: 'Follow-on', value: ipoFo.follow_on_volume, count: ipoFo.follow_on_count, fill: '#2563eb' },
  ] : []

  return (
    <div className="flex flex-col gap-6">
      {/* AI Insight — full width */}
      <DailyInsightCard />

      {/* Macro KPIs */}
      <MacroKpiCards />

      {/* Period selector shared by summary cards */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Período:</span>
        <PeriodFilter value={period} onChange={setPeriod} />
      </div>

      {/* Volume + IPO vs FO + Ranking */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* Volume card */}
        <Card className="p-6 flex flex-col items-center justify-center text-center min-h-[130px]">
          <p className="text-xs text-gray-500 font-medium mb-2">Vol. autorizado no período</p>
          <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {fmtVolume(volume?.total_volume ?? null)}
          </p>
          <p className="text-xs text-gray-400 mt-2">{volume?.offer_count ?? '—'} ofertas</p>
        </Card>

        {/* IPO vs FO */}
        <Card className="p-5 flex flex-col min-h-[160px]">
          <p className="text-xs text-gray-500 font-medium text-center mb-1">IPO vs Follow-on</p>
          <div className="flex-1 flex items-center justify-center">
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={ipoFoData} barCategoryGap="30%" margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis hide />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0].payload as typeof ipoFoData[0]
                    return (
                      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-2.5 text-xs shadow-lg">
                        <p className="font-semibold text-gray-700 dark:text-gray-300 mb-1.5">{d.name}</p>
                        <p className="text-gray-600 dark:text-gray-400">Vol: <span className="font-medium text-gray-800 dark:text-gray-200">{fmtVolume(d.value)}</span></p>
                        <p className="text-gray-600 dark:text-gray-400 mt-0.5">Qtd: <span className="font-medium text-gray-800 dark:text-gray-200">{d.count} oferta{d.count !== 1 ? 's' : ''}</span></p>
                      </div>
                    )
                  }}
                />
                <Bar dataKey="value" radius={[5, 5, 0, 0]} maxBarSize={90}>
                  {ipoFoData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Top 5 new offers */}
        <TopNewOffersCard />
      </div>

      {/* Ranking + Pipeline health */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Ranking */}
        <Card className="p-5">
          <SectionHeader title="Ranking por volume" subtitle="Top 10 ofertas no período" />
          {rankingLoading && <LoadingState />}
          {ranking && ranking.length === 0 && (
            <p className="text-sm text-gray-400 py-4">Nenhuma oferta no período.</p>
          )}
          {ranking && ranking.length > 0 && (
            <ol className="flex flex-col gap-2 mt-3">
              {ranking.map(item => (
                <li key={`${item.rank}-${item.name}`} className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-5 text-right font-mono">{item.rank}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate block">
                      {item.name}
                      {item.ticker && <span className="ml-1 text-xs font-mono text-gray-400">[{item.ticker}]</span>}
                    </span>
                    <span className="text-xs text-gray-400">{item.coordinator ?? '—'}</span>
                  </div>
                  <span className="text-sm font-mono text-gray-700 dark:text-gray-300 shrink-0">
                    {fmtVolume(item.total_volume)}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Card>

        {/* Pipeline health */}
        <PipelineHealthPanel />
      </div>

      {/* Offers table — the core of the product */}
      <div>
        <SectionHeader
          title="Ofertas primárias"
          subtitle="Tabela principal — use os filtros para navegar entre status e períodos"
        />
        <div className="mt-3">
          <OffersTable />
        </div>
      </div>
    </div>
  )
}
