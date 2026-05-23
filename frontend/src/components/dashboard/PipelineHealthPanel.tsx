import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, ShieldAlert, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { fmtDateTime } from '../../lib/formatters'
import { Card, Badge } from '../shared'
import { clsx } from 'clsx'

export default function PipelineHealthPanel() {
  const [expanded, setExpanded] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: qk.pipelineHealth(),
    queryFn:  api.getPipelineHealth,
    refetchInterval: 5 * 60_000,
  })

  if (isLoading || !data) return null

  const hasIssues = data.failed_today > 0 || data.stale_sources > 0
  const Icon = hasIssues ? ShieldAlert : ShieldCheck
  const iconColor = hasIssues ? 'text-red-500' : 'text-emerald-500'

  return (
    <Card className="p-4">
      <button
        className="flex items-center gap-2 w-full text-left"
        onClick={() => setExpanded(e => !e)}
      >
        <Icon className={clsx('w-4 h-4', iconColor)} />
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Status do pipeline
        </span>
        {hasIssues && (
          <div className="flex gap-2">
            {data.failed_today > 0 && (
              <Badge variant="red">{data.failed_today} falha{data.failed_today > 1 ? 's' : ''}</Badge>
            )}
            {data.stale_sources > 0 && (
              <Badge variant="yellow">{data.stale_sources} desatualizada{data.stale_sources > 1 ? 's' : ''}</Badge>
            )}
          </div>
        )}
        {!hasIssues && (
          <Badge variant="green">Todos OK</Badge>
        )}
        <span className="ml-auto text-gray-400">
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </span>
      </button>

      {expanded && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400 border-b border-gray-100 dark:border-gray-800">
                <th className="pb-2 font-medium">Fonte</th>
                <th className="pb-2 font-medium">Último run</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.sources.map(s => (
                <tr key={s.source_code} className="border-b border-gray-50 dark:border-gray-800/50 last:border-0">
                  <td className="py-1.5 pr-3 text-gray-700 dark:text-gray-300 font-medium">{s.source_name}</td>
                  <td className="py-1.5 pr-3 text-gray-500">
                    {s.last_run_at ? fmtDateTime(s.last_run_at) : '—'}
                    {s.hours_since_update != null && (
                      <span className="ml-1 text-gray-400">({s.hours_since_update}h)</span>
                    )}
                  </td>
                  <td className="py-1.5">
                    {s.is_stale ? (
                      <Badge variant="yellow">Desatualizado</Badge>
                    ) : s.last_status === 'failed' ? (
                      <Badge variant="red">Falha</Badge>
                    ) : (
                      <Badge variant="green">OK</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
