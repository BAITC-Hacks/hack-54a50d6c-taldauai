import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { AudioLines, CalendarDays, FileAudio, ListChecks, ShieldCheck, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'

const primaryNav = [
  { to: '/', label: 'Совещания', icon: CalendarDays, end: true },
  { to: '/live', label: 'Ассистент созвона', icon: AudioLines },
  { to: '/tasks', label: 'Поручения', icon: ListChecks },
]

const mobileNav = [
  ...primaryNav,
  { to: '/new', label: 'Загрузить', icon: Upload },
]

function Brand() {
  return <Link to="/" className="flex items-center gap-2.5 px-2 py-2">
    <span className="grid h-8 w-8 place-items-center rounded-md bg-emerald-800 text-sm font-bold text-white">T</span>
    <span className="min-w-0"><span className="block text-sm font-semibold text-slate-900">TaldauAI</span><span className="block text-[11px] text-slate-500">Ассистент совещаний</span></span>
  </Link>
}

function NavItems({ compact = false }: { compact?: boolean }) {
  const entries = compact ? mobileNav : primaryNav
  return <nav className={cn('flex', compact ? 'justify-around' : 'flex-col gap-1')} aria-label="Основная навигация">
    {entries.map(({ to, label, icon: Icon, end }) => <NavLink
      key={to}
      to={to}
      end={end}
      aria-label={label}
      className={({ isActive }) => cn(
        'flex items-center gap-2.5 rounded-md text-sm font-medium transition-colors',
        compact
          ? 'min-w-0 flex-1 flex-col justify-center gap-1 px-1 py-2 text-[10px]'
          : 'px-3 py-2.5',
        isActive ? 'bg-emerald-50 text-emerald-900' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
      )}
    >
      <Icon className={cn(compact ? 'h-5 w-5' : 'h-4 w-4')} />
      <span className={compact ? 'max-w-full truncate' : ''}>{label}</span>
    </NavLink>)}
  </nav>
}

export function Layout({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-background lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
    <aside className="sticky top-0 hidden h-screen flex-col border-r bg-white px-3 py-4 lg:flex">
      <Brand />
      <p className="mb-2 mt-8 px-3 text-[11px] font-semibold uppercase text-slate-400">Рабочее место</p>
      <NavItems />
      <Link to="/new" className="mt-5 flex min-h-10 items-center gap-2 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50">
        <FileAudio className="h-4 w-4" /> Загрузить запись
      </Link>
      <div className="mt-auto border-t px-2 pt-4">
        <div className="flex items-start gap-2.5 text-xs leading-5 text-slate-500">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
          <span><strong className="font-medium text-slate-700">Локальная обработка</strong><br />Аудио обрабатывается в закрытом контуре.</span>
        </div>
      </div>
    </aside>

    <div className="min-w-0">
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b bg-white/95 px-4 backdrop-blur lg:hidden">
        <Brand />
        <span className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-800"><ShieldCheck className="h-3.5 w-3.5" />Локально</span>
      </header>
      <main className="mx-auto min-h-[calc(100vh-3.5rem)] max-w-[1480px] px-4 py-6 pb-24 sm:px-6 sm:py-8 sm:pb-24 lg:px-8 lg:pb-10">
        {children}
      </main>
    </div>

    <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] pt-1 backdrop-blur lg:hidden">
      <NavItems compact />
    </div>
  </div>
}
