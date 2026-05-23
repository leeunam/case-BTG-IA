import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { fmtVolume, fmtPct, fmtNumber } from '../../lib/formatters'
import { Modal, LoadingState, NA, NotApplicable } from '../shared'

interface Props { open: boolean; offerIds: number[]; onClose: () => void }

type CellValue = string | React.ReactNode

interface CompareRow {
  label: string
  left: CellValue
  right: CellValue
}

function getCell(isIpo: boolean, value: number | null | undefined, format: (v: number) => string, ipoReason?: string): CellValue {
  if (isIpo) return <NA reason={ipoReason ?? 'Indisponível para IPO'} />
  if (value == null) return <NA />
  return format(value)
}

export default function CompareModal({ open, offerIds, onClose }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: qk.compareOffers(offerIds),
    queryFn:  () => api.compareOffers(offerIds),
    enabled:  open && offerIds.length === 2,
  })

  const [left, right] = data ?? []

  const ipoReasonDY = 'O DY depende de histórico de rendimentos. Por se tratar de IPO, não há histórico realizado.'
  const ipoReasonPVP = 'O P/VP depende de dados consolidados do fundo. Por se tratar de IPO, não há histórico realizado.'

  const rows: CompareRow[] = left && right ? [
    { label: 'Tipo',           left: left.offer.offer_type === 'ipo' ? 'IPO' : 'Follow-on',    right: right.offer.offer_type === 'ipo' ? 'IPO' : 'Follow-on' },
    { label: 'Status',         left: left.offer.status,                                          right: right.offer.status },
    { label: 'Vol. autorizado',left: fmtVolume(left.offer.total_volume),                        right: fmtVolume(right.offer.total_volume) },
    { label: 'Coordenador',    left: left.offer.lead_coordinator ?? '—',                        right: right.offer.lead_coordinator ?? '—' },
    { label: 'Segmento',       left: left.offer.segment ?? '—',                                 right: right.offer.segment ?? '—' },
    { label: 'Tipo de fundo',  left: left.offer.fund_type ?? '—',                               right: right.offer.fund_type ?? '—' },
    { label: 'DY 12m',         left: getCell(left.offer.offer_type === 'ipo', left.indicators.dy_12m, v => fmtPct(v), ipoReasonDY), right: getCell(right.offer.offer_type === 'ipo', right.indicators.dy_12m, v => fmtPct(v), ipoReasonDY) },
    { label: 'P/VP',           left: getCell(left.offer.offer_type === 'ipo', left.indicators.pvp,    v => fmtNumber(v), ipoReasonPVP), right: getCell(right.offer.offer_type === 'ipo', right.indicators.pvp, v => fmtNumber(v), ipoReasonPVP) },
    { label: 'Preço mercado',  left: getCell(left.offer.offer_type === 'ipo', left.indicators.market_price, v => `R$ ${fmtNumber(v, 2)}`), right: getCell(right.offer.offer_type === 'ipo', right.indicators.market_price, v => `R$ ${fmtNumber(v, 2)}`) },
    { label: 'Vacância',       left: left.offer.fund_type === 'papel' ? <NotApplicable /> : getCell(left.offer.offer_type === 'ipo', left.indicators.vacancy_rate, v => fmtPct(v)), right: right.offer.fund_type === 'papel' ? <NotApplicable /> : getCell(right.offer.offer_type === 'ipo', right.indicators.vacancy_rate, v => fmtPct(v)) },
    { label: 'PL total',       left: getCell(left.offer.offer_type === 'ipo', left.indicators.pl_total, v => fmtVolume(v)), right: getCell(right.offer.offer_type === 'ipo', right.indicators.pl_total, v => fmtVolume(v)) },
  ] : []

  return (
    <Modal open={open} onClose={onClose} title="Comparação de ofertas" width="max-w-3xl">
      {isLoading && <LoadingState />}

      {data && left && right && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-800">
                <th className="text-left pb-3 pr-4 text-gray-500 font-medium w-36">Indicador</th>
                <th className="text-left pb-3 pr-4 text-gray-900 dark:text-gray-100 font-semibold">
                  {left.offer.name}
                  {left.offer.ticker && <span className="ml-1 text-xs font-mono text-gray-400">[{left.offer.ticker}]</span>}
                </th>
                <th className="text-left pb-3 text-gray-900 dark:text-gray-100 font-semibold">
                  {right.offer.name}
                  {right.offer.ticker && <span className="ml-1 text-xs font-mono text-gray-400">[{right.offer.ticker}]</span>}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.label} className="border-b border-gray-50 dark:border-gray-800/50 last:border-0">
                  <td className="py-2.5 pr-4 text-gray-500 text-xs font-medium">{row.label}</td>
                  <td className="py-2.5 pr-4 text-gray-800 dark:text-gray-200">{row.left}</td>
                  <td className="py-2.5 text-gray-800 dark:text-gray-200">{row.right}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-4 text-xs text-gray-400">
            ⚠️ Indicadores de mercado secundário (DY, P/VP, preço) são do Fundamentus e não representam termos das ofertas primárias.
            Dados marcados como "Indisponível" ou "N/A" não estão disponíveis na fonte — não foram inventados.
            Não constitui recomendação de investimento.
          </p>
        </div>
      )}
    </Modal>
  )
}
