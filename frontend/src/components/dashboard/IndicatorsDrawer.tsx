import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { fmtPct, fmtVolume, fmtNumber, fmtDate } from '../../lib/formatters'
import { Drawer, LoadingState, NA, NotApplicable } from '../shared'
import type { Offer } from '../../types'

interface Props {
  offer: Offer | null
  open: boolean
  onClose: () => void
}

interface Row {
  label: string
  value: React.ReactNode
  tooltip?: string
  forFollowOnly?: boolean
}

export default function IndicatorsDrawer({ offer, open, onClose }: Props) {
  const isIpo = offer?.offer_type === 'ipo'

  const { data, isLoading } = useQuery({
    queryKey: qk.indicators(offer?.id ?? 0),
    queryFn:  () => api.getIndicators(offer!.id),
    enabled:  open && offer != null,
  })

  const rows: Row[] = [
    {
      label: 'Tipo de oferta',
      value: isIpo ? 'IPO — primeiro lançamento' : 'Follow-on — emissão subsequente',
    },
    {
      label: 'Volume autorizado',
      value: fmtVolume(offer?.total_volume ?? null),
    },
    {
      label: 'Rito',
      value: offer?.distribution_rite ?? '—',
    },
    {
      label: 'Preço da oferta (CVM)',
      value: offer?.financial_terms_available && data?.unit_price
        ? `R$ ${fmtNumber(data.unit_price, 2)}`
        : <NA reason="Dado não publicado (oferta restrita ou não disponível na fonte)" />,
    },
    {
      label: 'DY 12m (mercado secundário)',
      value: isIpo
        ? <NA reason="O dividend yield depende de histórico de rendimentos. Por se tratar de IPO, não há histórico realizado suficiente." />
        : data?.dy_12m != null
          ? fmtPct(data.dy_12m)
          : <NA />,
      tooltip: isIpo
        ? 'O dividend yield depende de histórico de rendimentos. Por se tratar de IPO, não há histórico realizado suficiente.'
        : 'Fonte: Fundamentus (mercado secundário) — não são termos da oferta primária.',
    },
    {
      label: 'P/VP (mercado secundário)',
      value: isIpo
        ? <NA reason="O P/VP depende de dados consolidados do fundo no mercado. Por se tratar de IPO, não há histórico realizado suficiente." />
        : data?.pvp != null
          ? fmtNumber(data.pvp)
          : <NA />,
      tooltip: isIpo
        ? 'O P/VP depende de dados consolidados do fundo no mercado. Por se tratar de IPO, não há histórico realizado suficiente.'
        : 'Fonte: Fundamentus (mercado secundário).',
    },
    {
      label: 'Preço de mercado (secundário)',
      value: isIpo
        ? <NotApplicable />
        : data?.market_price != null
          ? `R$ ${fmtNumber(data.market_price, 2)}`
          : <NA />,
    },
    {
      label: 'Spread oferta vs. mercado',
      value: isIpo
        ? <NotApplicable />
        : data?.spread_pct != null
          ? <span className={data.spread_pct < 0 ? 'text-emerald-600' : 'text-red-500'}>
              {data.spread_pct > 0 ? '+' : ''}{fmtPct(data.spread_pct)}
            </span>
          : <NA reason="Requer preço da oferta e preço de mercado" />,
      tooltip: 'Spread = (preço da oferta − preço de mercado) / preço de mercado × 100. Negativo = oferta com desconto.',
    },
    {
      label: 'PL total',
      value: isIpo ? <NotApplicable /> : fmtVolume(data?.pl_total),
    },
    {
      label: 'Vacância (fundo de tijolo)',
      value: isIpo
        ? <NotApplicable />
        : offer?.fund_type === 'papel'
          ? <NotApplicable />
          : data?.vacancy_rate != null
            ? fmtPct(data.vacancy_rate)
            : <NA />,
    },
    {
      label: 'Volume diário negociado',
      value: isIpo ? <NotApplicable /> : fmtVolume(data?.volume_daily),
    },
    {
      label: 'Valor patrimonial da cota (NAV)',
      value: isIpo ? <NotApplicable /> : data?.nav_per_unit != null ? `R$ ${fmtNumber(data.nav_per_unit)}` : <NA />,
    },
    {
      label: 'Retorno no mês',
      value: isIpo ? <NotApplicable /> : fmtPct(data?.monthly_return),
    },
    {
      label: 'Cap rate',
      value: <NA reason="Disponível após parsing de PDF dos prospectos (Fase 2)" />,
    },
    {
      label: 'LTV',
      value: <NA reason="Disponível após parsing de PDF dos prospectos (Fase 2)" />,
    },
    {
      label: 'Duration (fundos de papel)',
      value: offer?.fund_type === 'papel'
        ? <NA reason="Disponível após parsing de informes mensais (Fase 2)" />
        : <NotApplicable />,
    },
  ]

  return (
    <Drawer open={open} onClose={onClose} title={`Indicadores — ${offer?.name ?? ''}`}>
      {isLoading && <LoadingState />}

      {!isLoading && data && (
        <>
          {isIpo && (
            <div className="mb-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 text-xs">
              ⚠️ IPO: indicadores de mercado são indisponíveis, pois o fundo não possui histórico realizado.
            </div>
          )}

          <div className="text-xs text-gray-400 dark:text-gray-600 mb-3">
            Snapshot de {fmtDate(data.snapshot_date)} · Fonte secundária: {data.source}
          </div>

          <dl className="flex flex-col gap-3">
            {rows.map(row => (
              <div key={row.label} className="flex flex-col gap-0.5">
                <dt className="text-xs text-gray-500 dark:text-gray-400 font-medium" title={row.tooltip}>
                  {row.label}
                  {row.tooltip && <span className="ml-1 cursor-help">ℹ</span>}
                </dt>
                <dd className="text-sm text-gray-900 dark:text-gray-100">{row.value}</dd>
              </div>
            ))}
          </dl>

          <p className="mt-6 text-xs text-gray-400 dark:text-gray-600 border-t border-gray-100 dark:border-gray-800 pt-4">
            ⚠️ Indicadores de mercado secundário (DY, P/VP, preço) são do Fundamentus e não representam termos da oferta primária.
            Este painel é informativo. Não constitui recomendação de investimento.
          </p>
        </>
      )}
    </Drawer>
  )
}
