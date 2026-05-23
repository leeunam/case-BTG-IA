import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  useReactTable, getCoreRowModel, flexRender,
  createColumnHelper,
} from '@tanstack/react-table'
import { BarChart2, FileText, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { fmtVolume, fmtDate } from '../../lib/formatters'
import { OFFER_TYPE_LABELS, OFFER_STATUS_OPTIONS } from '../../lib/constants'
import {
  PeriodFilter, StatusFilter, Badge, LoadingState, ErrorState, EmptyState,
} from '../shared'
import IndicatorsDrawer from './IndicatorsDrawer'
import DocumentsModal from './DocumentsModal'
import SelectedOffersActionBar from './SelectedOffersActionBar'
import type { Offer, Period } from '../../types'
import { clsx } from 'clsx'

const col = createColumnHelper<Offer>()

function StatusBadge({ status }: { status: string }) {
  const variant = status === 'active' ? 'green' : status === 'closed' ? 'gray' : status === 'cancelled' ? 'red' : 'yellow'
  const label = { active: 'Ativo', pending: 'Pendente', closed: 'Encerrado', cancelled: 'Cancelado' }[status] ?? status
  return <Badge variant={variant}>{label}</Badge>
}

export default function OffersTable() {
  const [period, setPeriod] = useState<Period>('1m')
  const [statusFilter, setStatusFilter] = useState('ongoing')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 50

  const [indicatorsOffer, setIndicatorsOffer] = useState<Offer | null>(null)
  const [documentsOffer, setDocumentsOffer] = useState<Offer | null>(null)
  const [selected, setSelected] = useState<Offer[]>([])

  const { data, isLoading, isError } = useQuery({
    queryKey: qk.offers(period, statusFilter, page),
    queryFn:  () => api.getOffers(period, statusFilter, page, PAGE_SIZE),
    placeholderData: prev => prev,
  })

  const toggleSelect = (offer: Offer) => {
    setSelected(prev => {
      const exists = prev.find(o => o.id === offer.id)
      if (exists) return prev.filter(o => o.id !== offer.id)
      if (prev.length >= 2) return [prev[1], offer]  // replace oldest
      return [...prev, offer]
    })
  }

  const columns = [
    col.display({
      id: 'select',
      header: '',
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={!!selected.find(o => o.id === row.original.id)}
          onChange={() => toggleSelect(row.original)}
          className="rounded border-gray-300 dark:border-gray-600 text-brand-600 cursor-pointer"
        />
      ),
    }),
    col.accessor('offer_type', {
      header: 'Tipo',
      cell: info => (
        <Badge variant={info.getValue() === 'ipo' ? 'purple' : 'blue'}>
          {OFFER_TYPE_LABELS[info.getValue()] ?? info.getValue()}
        </Badge>
      ),
    }),
    col.accessor('name', {
      header: 'Fundo',
      cell: info => (
        <div>
          <span className="font-medium text-gray-900 dark:text-gray-100 text-sm">{info.getValue()}</span>
          {info.row.original.ticker && (
            <span className="ml-1 text-xs text-gray-400 font-mono">[{info.row.original.ticker}]</span>
          )}
        </div>
      ),
    }),
    col.accessor('total_volume', {
      header: 'Vol. autorizado',
      cell: info => <span className="text-sm font-mono">{fmtVolume(info.getValue())}</span>,
    }),
    col.accessor('fund_type', {
      header: 'Tipo fundo',
      cell: info => <span className="text-sm text-gray-600 dark:text-gray-400">{info.getValue() ?? '—'}</span>,
    }),
    col.accessor('manager', {
      header: 'Gestor',
      cell: info => <span className="text-sm text-gray-600 dark:text-gray-400 max-w-[120px] truncate block">{info.getValue() ?? '—'}</span>,
    }),
    col.accessor('administrator', {
      header: 'Administrador',
      cell: info => <span className="text-sm text-gray-600 dark:text-gray-400 max-w-[120px] truncate block">{info.getValue() ?? '—'}</span>,
    }),
    col.accessor('lead_coordinator', {
      header: 'Coordenador',
      cell: info => <span className="text-sm text-gray-600 dark:text-gray-400 max-w-[120px] truncate block">{info.getValue() ?? '—'}</span>,
    }),
    col.accessor('status', {
      header: 'Status',
      cell: info => <StatusBadge status={info.getValue()} />,
    }),
    col.accessor('registered_at', {
      header: 'Registro',
      cell: info => <span className="text-sm text-gray-500">{fmtDate(info.getValue())}</span>,
    }),
    col.display({
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <div className="flex gap-1">
          <button
            onClick={() => setIndicatorsOffer(row.original)}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-brand-900/30 dark:hover:text-brand-400 transition-colors"
          >
            <BarChart2 className="w-3 h-3" />
            Indicadores
          </button>
          <button
            onClick={() => setDocumentsOffer(row.original)}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-brand-900/30 dark:hover:text-brand-400 transition-colors"
          >
            <FileText className="w-3 h-3" />
            Documentos
          </button>
        </div>
      ),
    }),
  ]

  const table = useReactTable({
    data: data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: data ? Math.ceil(data.total_count / PAGE_SIZE) : 0,
  })

  const totalPages = data ? Math.ceil(data.total_count / PAGE_SIZE) : 0

  return (
    <div className="flex flex-col gap-3">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <PeriodFilter value={period} onChange={p => { setPeriod(p); setPage(1) }} />
        <StatusFilter
          value={statusFilter}
          onChange={s => { setStatusFilter(s); setPage(1) }}
          options={OFFER_STATUS_OPTIONS}
        />
        {data && (
          <span className="text-xs text-gray-400 ml-auto">
            {data.total_count.toLocaleString('pt-BR')} ofertas encontradas
          </span>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        {isLoading && <LoadingState />}
        {isError && <ErrorState message="Erro ao carregar ofertas." />}
        {!isLoading && !isError && data?.items.length === 0 && (
          <EmptyState message="Nenhuma oferta encontrada com os filtros selecionados." />
        )}
        {!isLoading && !isError && data && data.items.length > 0 && (
          <table className="w-full text-sm min-w-[900px]">
            <thead>
              {table.getHeaderGroups().map(hg => (
                <tr key={hg.id} className="border-b border-gray-100 dark:border-gray-800">
                  {hg.headers.map(h => (
                    <th key={h.id} className="text-left px-3 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map(row => (
                <tr
                  key={row.id}
                  className={clsx(
                    'border-b border-gray-50 dark:border-gray-800/50 last:border-0',
                    'hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors',
                    selected.find(o => o.id === row.original.id) && 'bg-brand-50 dark:bg-brand-900/10',
                  )}
                >
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-3 py-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">
            Página {page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Drawers / Modals */}
      <IndicatorsDrawer
        offer={indicatorsOffer}
        open={indicatorsOffer !== null}
        onClose={() => setIndicatorsOffer(null)}
      />
      <DocumentsModal
        offer={documentsOffer}
        open={documentsOffer !== null}
        onClose={() => setDocumentsOffer(null)}
      />
      <SelectedOffersActionBar selected={selected} onClear={() => setSelected([])} />
    </div>
  )
}
