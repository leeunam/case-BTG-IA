import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, Loader2, CheckCircle, XCircle } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { PDF_POLL_INTERVAL_MS } from '../../lib/constants'
import { Modal } from '../shared'

interface Props {
  open: boolean
  jobId: string
  onClose: () => void
  onFinish: () => void
}

export default function PdfGenerationModal({ open, jobId, onClose, onFinish }: Props) {
  const { data } = useQuery({
    queryKey: qk.reportJob(jobId),
    queryFn:  () => api.getReportJob(jobId),
    enabled:  !!jobId,  // continua polling mesmo com o modal fechado
    refetchInterval: (q) => {
      const status = q.state.data?.status
      return status === 'completed' || status === 'failed' ? false : PDF_POLL_INTERVAL_MS
    },
  })

  const status = data?.status ?? 'queued'
  const progress = data?.progress ?? 0
  const didAutoDownload = useRef(false)

  // Dispara o download automaticamente ao concluir — inclusive com o modal fechado
  useEffect(() => {
    if (status === 'completed' && data?.download_url && !didAutoDownload.current) {
      didAutoDownload.current = true
      const a = document.createElement('a')
      a.href = data.download_url
      a.download = ''
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      if (!open) onFinish()
    }
  }, [status, data?.download_url]) // eslint-disable-line react-hooks/exhaustive-deps

  // Quando o modal fecha em estado terminal, libera o componente
  const handleClose = () => {
    onClose()
    if (status === 'completed' || status === 'failed') onFinish()
  }

  return (
    <Modal open={open} onClose={handleClose} title="Gerando relatório analítico" width="max-w-sm">
      <div className="flex flex-col items-center gap-4 py-4">
        {(status === 'queued' || status === 'processing') && (
          <>
            <Loader2 className="w-10 h-10 text-brand-600 animate-spin" />
            <div className="w-full bg-gray-100 dark:bg-gray-800 rounded-full h-2">
              <div
                className="bg-brand-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {status === 'queued' ? 'Na fila...' : `Gerando... ${progress}%`}
            </p>
            <p className="text-xs text-gray-400 text-center">
              Você pode fechar esta janela. O download iniciará automaticamente ao concluir.
            </p>
          </>
        )}

        {status === 'completed' && data?.download_url && (
          <>
            <CheckCircle className="w-10 h-10 text-emerald-500" />
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Relatório pronto!</p>
            <a
              href={data.download_url}
              download
              onClick={onFinish}
              className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Download className="w-4 h-4" />
              Baixar relatório
            </a>
            <p className="text-xs text-gray-400 text-center">
              Este relatório é informativo e não constitui recomendação de investimento.
            </p>
          </>
        )}

        {status === 'failed' && (
          <>
            <XCircle className="w-10 h-10 text-red-500" />
            <p className="text-sm text-red-600 dark:text-red-400">Falha na geração do relatório.</p>
            {data?.error && (
              <p className="text-xs text-gray-500 text-center">{data.error}</p>
            )}
          </>
        )}
      </div>
    </Modal>
  )
}
