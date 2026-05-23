import { clsx } from 'clsx'
import { AlertCircle, Inbox, Loader2 } from 'lucide-react'
import type { Period } from '../../types'
import { PERIOD_OPTIONS } from '../../lib/constants'

// ─── Card wrapper ─────────────────────────────────────────────────────────────
export function Card({
  children, className,
}: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx(
      'rounded-xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 shadow-sm',
      className,
    )}>
      {children}
    </div>
  )
}

// ─── Section header ───────────────────────────────────────────────────────────
export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-1">
      <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
      {subtitle && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{subtitle}</p>}
    </div>
  )
}

// ─── Loading state ────────────────────────────────────────────────────────────
export function LoadingState({ label = 'Carregando...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-400">
      <Loader2 className="w-6 h-6 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

// ─── Error state ──────────────────────────────────────────────────────────────
export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-red-500">
      <AlertCircle className="w-6 h-6" />
      <span className="text-sm">{message}</span>
    </div>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────
export function EmptyState({ message = 'Nenhum dado disponível.' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-400">
      <Inbox className="w-6 h-6" />
      <span className="text-sm">{message}</span>
    </div>
  )
}

// ─── Badge ────────────────────────────────────────────────────────────────────
type BadgeVariant = 'green' | 'yellow' | 'red' | 'blue' | 'gray' | 'purple'
const BADGE_STYLES: Record<BadgeVariant, string> = {
  green:  'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  yellow: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  red:    'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  blue:   'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  gray:   'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  purple: 'bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
}

export function Badge({
  children, variant = 'gray',
}: { children: React.ReactNode; variant?: BadgeVariant }) {
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium', BADGE_STYLES[variant])}>
      {children}
    </span>
  )
}

// ─── Period filter ────────────────────────────────────────────────────────────
export function PeriodFilter({
  value, onChange,
}: { value: Period; onChange: (p: Period) => void }) {
  return (
    <div className="flex gap-1">
      {PERIOD_OPTIONS.map(opt => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={clsx(
            'px-3 py-1 rounded-lg text-xs font-medium transition-colors',
            value === opt.value
              ? 'bg-brand-600 text-white'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ─── Status filter ────────────────────────────────────────────────────────────
export function StatusFilter({
  value, onChange, options,
}: { value: string; onChange: (s: string) => void; options: { label: string; value: string }[] }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300"
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

// ─── Modal wrapper ────────────────────────────────────────────────────────────
export function Modal({
  open, onClose, title, children, width = 'max-w-2xl',
}: {
  open: boolean; onClose: () => void; title: string
  children: React.ReactNode; width?: string
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className={clsx('relative bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full', width)}>
        <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none">&times;</button>
        </div>
        <div className="p-5 max-h-[70vh] overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}

// ─── Drawer (slide from right) ────────────────────────────────────────────────
export function Drawer({
  open, onClose, title, children,
}: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode
}) {
  return (
    <>
      {open && <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" onClick={onClose} />}
      <aside className={clsx(
        'fixed top-0 right-0 h-full w-full max-w-md z-50 bg-white dark:bg-gray-900 shadow-2xl',
        'transform transition-transform duration-300 ease-in-out',
        open ? 'translate-x-0' : 'translate-x-full',
      )}>
        <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl">&times;</button>
        </div>
        <div className="p-5 overflow-y-auto h-[calc(100vh-65px)]">{children}</div>
      </aside>
    </>
  )
}

// ─── Unavailable indicator ────────────────────────────────────────────────────
export function NA({ reason }: { reason?: string }) {
  return (
    <span className="text-gray-400 dark:text-gray-600 text-sm" title={reason}>
      Indisponível
    </span>
  )
}

export function NotApplicable() {
  return (
    <span className="text-gray-300 dark:text-gray-700 text-sm">
      N/A
    </span>
  )
}
