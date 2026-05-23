import { useState } from 'react'
import { GitCompare, FileText, X } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { PDF_POLL_INTERVAL_MS } from '../../lib/constants'
import PdfGenerationModal from '../reports/PdfGenerationModal'
import CompareModal from './CompareModal'
import type { Offer } from '../../types'

interface Props {
  selected: Offer[]
  onClear: () => void
}

export default function SelectedOffersActionBar({ selected, onClear }: Props) {
  const [pdfModalOpen, setPdfModalOpen] = useState(false)
  const [compareOpen, setCompareOpen] = useState(false)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)

  const createReport = useMutation({
    mutationFn: (offerId: number) => api.createReport(offerId),
    onSuccess: (job) => {
      setActiveJobId(job.job_id)
      setPdfModalOpen(true)
    },
  })

  if (selected.length === 0) return null

  return (
    <>
      <div className="fixed bottom-0 left-0 right-0 z-30 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 shadow-lg px-6 py-3 flex items-center gap-4">
        <span className="text-sm text-gray-600 dark:text-gray-400">
          {selected.length} oferta{selected.length > 1 ? 's' : ''} selecionada{selected.length > 1 ? 's' : ''}
        </span>

        <div className="flex gap-2 ml-auto">
          <button
            onClick={() => setCompareOpen(true)}
            disabled={selected.length < 2}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
              disabled:opacity-40 disabled:cursor-not-allowed
              bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300
              hover:bg-gray-200 dark:hover:bg-gray-700 disabled:hover:bg-gray-100"
            title={selected.length < 2 ? 'Selecione 2 ofertas para comparar' : 'Comparar lado a lado'}
          >
            <GitCompare className="w-4 h-4" />
            Comparar {selected.length >= 2 ? '' : '(aguardando 2ª)'}
          </button>

          <button
            onClick={() => selected.length === 1 && createReport.mutate(selected[0].id)}
            disabled={createReport.isPending || selected.length !== 1}
            title={
              selected.length === 0 ? 'Selecione 1 oferta para gerar PDF'
              : selected.length > 1  ? 'Selecione apenas 1 oferta — 1 PDF por ativo'
              : 'Gerar relatório analítico em PDF'
            }
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
              bg-brand-600 hover:bg-brand-700 text-white transition-colors
              disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-brand-600"
          >
            <FileText className="w-4 h-4" />
            {createReport.isPending ? 'Iniciando...' : 'Gerar PDF'}
          </button>

          <button onClick={onClear} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      {activeJobId && (
        <PdfGenerationModal
          open={pdfModalOpen}
          jobId={activeJobId}
          onClose={() => { setPdfModalOpen(false); setActiveJobId(null) }}
        />
      )}

      <CompareModal
        open={compareOpen && selected.length === 2}
        offerIds={selected.slice(0, 2).map(o => o.id)}
        onClose={() => setCompareOpen(false)}
      />
    </>
  )
}
