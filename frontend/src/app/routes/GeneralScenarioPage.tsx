import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { DEFAULT_PERIOD } from '../../lib/constants'
import { fmtVolume, fmtPct, fmtDate } from '../../lib/formatters'
import {
  Card, SectionHeader, PeriodFilter, LoadingState, EmptyState, Badge,
} from '../../components/shared'
import type { Period } from '../../types'

const COORD_COLORS = ['#2563eb','#7c3aed','#059669','#d97706','#dc2626','#0891b2','#65a30d','#be185d']

export default function GeneralScenarioPage() {
  const [period, setPeriod] = useState<Period>(DEFAULT_PERIOD)

  const { data: kpis, isLoading: kpisLoading }    = useQuery({ queryKey: qk.macroKpis(), queryFn: api.getMacroKpis })
  const { data: ipca }    = useQuery({ queryKey: qk.ipcaMonthly(), queryFn: api.getIpcaMonthly })
  const { data: byCoord } = useQuery({ queryKey: qk.offersByCoord(period), queryFn: () => api.getOffersByCoord(period) })
  const { data: topFunds }= useQuery({ queryKey: qk.topFundsVolume(period), queryFn: () => api.getTopFundsVolume(period) })
  const { data: players } = useQuery({ queryKey: qk.players(period), queryFn: () => api.getPlayers(period) })
  const { data: topPlayer}= useQuery({ queryKey: qk.topPlayerInsight(period), queryFn: () => api.getTopPlayerInsight(period) })

  const kpiMap = Object.fromEntries((kpis ?? []).map(k => [k.code, k]))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Cenário Geral</h1>
        <PeriodFilter value={period} onChange={setPeriod} />
      </div>

      {/* Macro KPI comparison */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {['SELIC_META','CDI','IPCA_PROJ','IFIX'].map(code => {
          const k = kpiMap[code]
          return (
            <Card key={code} className="p-4">
              <p className="text-xs text-gray-500 font-medium">{k?.label ?? code}</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                {kpisLoading ? '—' : k?.display_value ?? 'N/D'}
              </p>
              <p className="text-xs text-gray-400 mt-1 truncate">{k?.source ?? ''}</p>
              {k?.metric_date && <p className="text-xs text-gray-400">{fmtDate(k.metric_date)}</p>}
            </Card>
          )
        })}
      </div>

      {/* CDI detail + Selic projetada */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {['CDI','CDI_PROJ','IPCA','IPCA_PROJ'].map(code => {
          const k = kpiMap[code]
          const labels: Record<string,string> = { CDI: 'CDI diário (anualizado)', CDI_PROJ: 'Selic projetada (Focus)', IPCA: 'IPCA mensal', IPCA_PROJ: 'IPCA projetado (Focus)' }
          return (
            <Card key={code} className="p-3">
              <p className="text-xs text-gray-500">{labels[code] ?? code}</p>
              <p className="text-xl font-bold text-gray-800 dark:text-gray-200 mt-1">{k?.display_value ?? 'N/D'}</p>
              <p className="text-xs text-gray-400 truncate mt-0.5">{k?.source}</p>
            </Card>
          )
        })}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* IPCA monthly */}
        <Card className="p-5">
          <SectionHeader title="IPCA mensal acumulado" subtitle="Fonte: IBGE via BCB/SGS série 433" />
          {!ipca ? <LoadingState /> : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={ipca.slice(-12)}>
                <XAxis dataKey="month" tick={{ fontSize: 10 }} axisLine={false} tickLine={false}
                  tickFormatter={v => v.substring(5)} />
                <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
                <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`, 'IPCA']} />
                <Bar dataKey="value" fill="#2563eb" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Offers by coordinator */}
        <Card className="p-5">
          <SectionHeader title="Distribuição de ofertas por coordenador" subtitle="Número de ofertas no período" />
          {!byCoord ? <LoadingState /> : byCoord.length === 0 ? <EmptyState /> : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={byCoord.slice(0,10)} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="coordinator" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} width={100} />
                <Tooltip formatter={(v: number) => [v, 'Ofertas']} />
                <Bar dataKey="count" radius={[0,3,3,0]}>
                  {byCoord.slice(0,10).map((_, i) => <Cell key={i} fill={COORD_COLORS[i % COORD_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Top funds volume */}
      <Card className="p-5">
        <SectionHeader title="Volume por fundo (Top 10)" subtitle="Vol. autorizado no período — Fonte: CVM" />
        {!topFunds ? <LoadingState /> : topFunds.length === 0 ? <EmptyState /> : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={topFunds.slice(0,10)} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false}
                tickFormatter={v => fmtVolume(v)} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} width={130} />
              <Tooltip formatter={(v: number) => [fmtVolume(v), 'Vol. autorizado']} />
              <Bar dataKey="total_volume" fill="#7c3aed" radius={[0,3,3,0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Top player + players table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Top player card */}
        {topPlayer && (
          <Card className="p-5">
            <SectionHeader title="Player top no período" />
            <div className="mt-3">
              <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{topPlayer.coordinator}</p>
              <p className="text-sm text-gray-500 mt-1">{topPlayer.share_vol_pct}% do volume · {topPlayer.offer_count} ofertas</p>
              <p className="text-xs text-gray-400 mt-1">Tipo predominante: {topPlayer.dominant_offer_type}</p>
              {topPlayer.status === 'not_generated' && (
                <Badge variant="gray" >Análise IA não gerada</Badge>
              )}
              {topPlayer.text && (
                <p className="text-xs text-gray-600 dark:text-gray-400 mt-3 leading-relaxed">{topPlayer.text}</p>
              )}
            </div>
          </Card>
        )}

        {/* Players table */}
        <div className="lg:col-span-2 overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          {!players ? <LoadingState /> : players.length === 0 ? <EmptyState /> : (
            <table className="w-full text-sm min-w-[600px]">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800 text-left">
                  {['Coordenador','Ofertas','Vol. total','Fundos únicos','Share qtd','Share vol','Última oferta'].map(h => (
                    <th key={h} className="px-4 py-3 text-xs font-semibold text-gray-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {players.map(p => (
                  <tr key={p.coordinator} className="border-b border-gray-50 dark:border-gray-800/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-2.5 font-medium text-gray-800 dark:text-gray-200 max-w-[150px] truncate">{p.coordinator}</td>
                    <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{p.total_offers}</td>
                    <td className="px-4 py-2.5 font-mono text-gray-700 dark:text-gray-300">{fmtVolume(p.total_volume)}</td>
                    <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{p.unique_funds}</td>
                    <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{fmtPct(p.share_qty_pct, 1)}</td>
                    <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{fmtPct(p.share_vol_pct, 1)}</td>
                    <td className="px-4 py-2.5 text-gray-500 text-xs">{fmtDate(p.last_offer_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
