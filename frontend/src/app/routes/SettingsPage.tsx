import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Moon, Sun, RefreshCw, Trash2, User } from 'lucide-react'
import { useTheme } from '../../components/layout/AppShell'
import { api } from '../../lib/api'
import { Card, SectionHeader } from '../../components/shared'

const SOURCE_OPTIONS = [
  { value: 'regulatory', label: 'Regulatório — CVM + BCB + B3 + Status Invest (~10 min)' },
  { value: 'market',     label: 'Mercado (pregão) — IFIX + Fundamentus + FundsExplorer (~2 min)' },
  { value: 'cvm_dados_abertos', label: 'CVM Dados Abertos (~2 min)' },
  { value: 'bcb_sgs',          label: 'BCB SGS + Focus (~30s)' },
  { value: 'fundamentus',      label: 'Fundamentus (~1 min)' },
  { value: 'b3_listings',      label: 'B3 Listings (~10s)' },
  { value: 'b3_ifix',          label: 'IFIX / Yahoo Finance (~10s)' },
  { value: 'status_invest',    label: 'Status Invest (~5 min)' },
  { value: 'funds_explorer',   label: 'Funds Explorer (~5 min)' },
]

export default function SettingsPage() {
  const { theme, toggle } = useTheme()
  const [userName, setUserName] = useState(() => localStorage.getItem('user_name') ?? '')
  const [selectedSource, setSelectedSource] = useState('all')
  const [refreshDone, setRefreshDone] = useState(false)
  const [cacheDone, setCacheDone] = useState(false)

  const refreshMutation = useMutation({
    mutationFn: (source: string) => api.triggerRefresh(source),
    onSuccess: () => { setRefreshDone(true); setTimeout(() => setRefreshDone(false), 3000) },
  })

  const saveUserName = () => {
    localStorage.setItem('user_name', userName)
    alert('Nome salvo!')
  }

  const clearCache = () => {
    // Invalidate all TanStack Query cache by reloading
    setCacheDone(true)
    setTimeout(() => {
      setCacheDone(false)
      window.location.reload()
    }, 800)
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Configurações</h1>

      {/* Profile */}
      <Card className="p-5">
        <SectionHeader title="Perfil" />
        <div className="flex items-end gap-3 mt-4">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1.5">Nome de exibição</label>
            <div className="flex items-center gap-2 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-800">
              <User className="w-4 h-4 text-gray-400" />
              <input
                value={userName}
                onChange={e => setUserName(e.target.value)}
                placeholder="Seu nome"
                className="flex-1 bg-transparent text-sm text-gray-800 dark:text-gray-200 outline-none"
              />
            </div>
          </div>
          <button
            onClick={saveUserName}
            className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition-colors"
          >
            Salvar
          </button>
        </div>
      </Card>

      {/* Appearance */}
      <Card className="p-5">
        <SectionHeader title="Aparência" />
        <div className="flex items-center gap-4 mt-4">
          <span className="text-sm text-gray-600 dark:text-gray-400">Tema:</span>
          <button
            onClick={toggle}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            {theme === 'dark' ? (
              <><Moon className="w-4 h-4" /> Escuro</>
            ) : (
              <><Sun className="w-4 h-4" /> Claro</>
            )}
          </button>
          <span className="text-xs text-gray-400">Clique para alternar</span>
        </div>
      </Card>

      {/* Data refresh */}
      <Card className="p-5">
        <SectionHeader
          title="Atualização de dados"
          subtitle="Regulatório roda automaticamente às 06:30. Mercado roda às 10:30, 14:00 e 17:00 (pregão B3)."
        />
        <div className="flex items-end gap-3 mt-4">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1.5">Fonte</label>
            <select
              value={selectedSource}
              onChange={e => setSelectedSource(e.target.value)}
              className="w-full border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-sm text-gray-700 dark:text-gray-300"
            >
              {SOURCE_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => refreshMutation.mutate(selectedSource)}
            disabled={refreshMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition-colors disabled:opacity-60"
          >
            <RefreshCw className={`w-4 h-4 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
            {refreshMutation.isPending ? 'Iniciando...' : refreshDone ? 'Iniciado ✓' : 'Atualizar'}
          </button>
        </div>
        <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
          ⚠️ A atualização roda em segundo plano. Você pode continuar usando a aplicação.
        </p>
      </Card>

      {/* Cache */}
      <Card className="p-5">
        <SectionHeader
          title="Cache"
          subtitle="Limpa os dados em memória do browser. Os dados do banco não são alterados."
        />
        <button
          onClick={clearCache}
          disabled={cacheDone}
          className="flex items-center gap-2 mt-4 px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-700 dark:text-gray-300 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20 dark:hover:text-red-400 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
          {cacheDone ? 'Cache limpo — recarregando...' : 'Limpar cache local'}
        </button>
      </Card>
    </div>
  )
}
