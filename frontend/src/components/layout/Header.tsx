import { Menu, Sun, Moon } from 'lucide-react'
import { useTheme } from './AppShell'

interface Props { onMenuClick: () => void }

export default function Header({ onMenuClick }: Props) {
  const { theme, toggle } = useTheme()
  return (
    <header className="sticky top-0 z-30 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-4 h-14 flex items-center gap-4 shadow-sm">
      <button
        onClick={onMenuClick}
        className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        aria-label="Abrir menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      <span className="font-bold text-brand-700 dark:text-brand-400 text-base tracking-tight">
        BTG FII Analyzer
      </span>

      <div className="ml-auto flex items-center gap-2">
        <span className="text-xs text-gray-400 dark:text-gray-500 hidden sm:block">
          Dados informativos · Sem recomendação de investimento
        </span>
        <button
          onClick={toggle}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          aria-label="Alternar tema"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  )
}
