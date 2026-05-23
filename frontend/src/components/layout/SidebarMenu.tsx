import { NavLink } from 'react-router-dom'
import { LayoutDashboard, TrendingUp, Bell, Bot, Settings, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { DEFAULT_PERIOD } from '../../lib/constants'
import { clsx } from 'clsx'

const NAV = [
  { to: '/',             icon: LayoutDashboard, label: 'Dashboard'      },
  { to: '/cenario-geral',icon: TrendingUp,      label: 'Cenário Geral'  },
  { to: '/alertas',      icon: Bell,            label: 'Alertas'        },
  { to: '/agent-ia',     icon: Bot,             label: 'Agent IA'       },
  { to: '/configuracoes',icon: Settings,        label: 'Configurações'  },
]

interface Props { open: boolean; onClose: () => void }

export default function SidebarMenu({ open, onClose }: Props) {
  const { data: summary } = useQuery({
    queryKey: qk.alertSummary(DEFAULT_PERIOD),
    queryFn:  () => api.getAlertSummary(DEFAULT_PERIOD),
    refetchInterval: 60_000,
  })
  const unseen = summary?.unseen ?? 0

  return (
    <aside
      className={clsx(
        'fixed top-0 left-0 h-full w-64 z-50 bg-white dark:bg-gray-900 shadow-2xl',
        'transform transition-transform duration-300 ease-in-out',
        open ? 'translate-x-0' : '-translate-x-full',
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
        <span className="font-semibold text-brand-700 dark:text-brand-400 text-lg">BTG FII</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 p-3 mt-2">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800',
              )
            }
          >
            <Icon className="w-5 h-5 shrink-0" />
            <span className="flex-1">{label}</span>
            {label === 'Alertas' && unseen > 0 && (
              <span className="text-xs bg-red-500 text-white px-1.5 py-0.5 rounded-full">
                {unseen > 99 ? '99+' : unseen}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="absolute bottom-4 left-0 right-0 px-5">
        <p className="text-xs text-gray-400 dark:text-gray-600">
          BTG FII Analyzer · v1.0
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-600 mt-0.5">
          Não constitui recomendação de investimento.
        </p>
      </div>
    </aside>
  )
}
