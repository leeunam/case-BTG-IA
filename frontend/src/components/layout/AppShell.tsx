import { useState, createContext, useContext, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import SidebarMenu from './SidebarMenu'
import Header from './Header'

// ─── Theme context ────────────────────────────────────────────────────────────
interface ThemeCtx { theme: 'light' | 'dark'; toggle: () => void }
const ThemeContext = createContext<ThemeCtx>({ theme: 'light', toggle: () => {} })
export const useTheme = () => useContext(ThemeContext)

export default function AppShell() {
  const [theme, setTheme] = useState<'light' | 'dark'>(
    () => (localStorage.getItem('theme') as 'light' | 'dark') ?? 'light',
  )
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggle = () => setTheme(t => (t === 'light' ? 'dark' : 'light'))

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-950">
        <Header onMenuClick={() => setSidebarOpen(true)} />

        <SidebarMenu open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        {/* Overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        <main className="flex-1 container mx-auto max-w-screen-2xl px-4 py-6">
          <Outlet />
        </main>
      </div>
    </ThemeContext.Provider>
  )
}
