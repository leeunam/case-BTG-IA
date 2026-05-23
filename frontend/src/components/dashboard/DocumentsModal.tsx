import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Download, FileText } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { Modal, LoadingState, EmptyState, Badge } from '../shared'
import type { Offer } from '../../types'

interface Props { offer: Offer | null; open: boolean; onClose: () => void }

const STATUS_VARIANT = {
  done:    'green',
  pending: 'yellow',
  failed:  'red',
  partial: 'yellow',
} as const

export default function DocumentsModal({ offer, open, onClose }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: qk.documents(offer?.id ?? 0),
    queryFn:  () => api.getDocuments(offer!.id),
    enabled:  open && offer != null,
  })

  const available = data?.filter(d => d.available) ?? []
  const unavailable = data?.filter(d => !d.available) ?? []

  return (
    <Modal open={open} onClose={onClose} title={`Documentos — ${offer?.name ?? ''}`}>
      {isLoading && <LoadingState />}

      {!isLoading && data?.length === 0 && (
        <EmptyState message="Nenhum documento registrado para esta oferta." />
      )}

      {!isLoading && data && data.length > 0 && (
        <div className="flex flex-col gap-6">
          {available.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Disponíveis
              </h4>
              <ul className="flex flex-col gap-2">
                {available.map(doc => (
                  <li key={doc.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800">
                    <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                    <span className="text-sm text-gray-700 dark:text-gray-300 flex-1">{doc.title}</span>
                    <Badge variant={STATUS_VARIANT[doc.extraction_status as keyof typeof STATUS_VARIANT] ?? 'gray'}>
                      {doc.extraction_status}
                    </Badge>
                    {doc.download_url && (
                      <a href={doc.download_url} download
                        className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                        title="Baixar">
                        <Download className="w-4 h-4 text-brand-600" />
                      </a>
                    )}
                    {doc.source_url && !doc.download_url && (
                      <a href={doc.source_url} target="_blank" rel="noopener noreferrer"
                        className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                        title="Abrir link">
                        <ExternalLink className="w-4 h-4 text-brand-600" />
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {unavailable.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Não disponíveis
              </h4>
              <ul className="flex flex-col gap-1">
                {unavailable.map(doc => (
                  <li key={doc.id} className="flex items-center gap-3 px-3 py-2 text-gray-400 text-sm">
                    <FileText className="w-4 h-4 shrink-0" />
                    <span>{doc.title}</span>
                    <span className="ml-auto text-xs">
                      {doc.extraction_status === 'pending'
                        ? 'Pendente'
                        : doc.extraction_status === 'failed'
                          ? 'Falha na extração'
                          : 'Indisponível'}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="text-xs text-gray-400 dark:text-gray-600 pt-2 border-t border-gray-100 dark:border-gray-800">
            Documentos públicos disponibilizados pela CVM. Para ofertas de esforços restritos (ICVM 476),
            o prospecto pode não estar disponível publicamente.
          </p>
        </div>
      )}
    </Modal>
  )
}
