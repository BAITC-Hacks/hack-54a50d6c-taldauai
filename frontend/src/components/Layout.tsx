import { useEffect, useState, type ReactNode } from 'react'
import { getNotifications } from '@/api'
import { Link, NavLink } from 'react-router-dom'
import { Bell, Building2, ClipboardCheck, FileAudio, ListChecks, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', label: 'Совещания', icon: FileAudio, end: true },
  { to: '/new', label: 'Новое совещание', icon: ClipboardCheck },
  { to: '/notifications', label: 'Напоминания', icon: Bell },
  { to: '/tasks', label: 'Контроль поручений', icon: ListChecks },
]

export function Layout({ children }: { children: ReactNode }) {
  const [unread, setUnread] = useState(0)
  useEffect(() => {
    let active = true
    const load = async () => {
      try { const items = await getNotifications(); if (active) setUnread(items.filter(n => !n.read_at).length) }
      catch { /* The notification page displays connection errors. */ }
    }
    void load()
    const timer = window.setInterval(load, 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  return <div className="min-h-screen">
    <header className="sticky top-0 z-40 border-b bg-[#0b2036] text-white shadow-sm">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-teal-500/15 ring-1 ring-teal-400/30"><Building2 className="h-5 w-5 text-teal-300" /></span>
          <div className="min-w-0"><p className="truncate text-sm font-semibold tracking-wide sm:text-base">TaldauAI</p><p className="hidden text-[11px] text-slate-300 sm:block">Протоколы совещаний</p></div>
        </Link>
        <nav className="hidden h-full items-center md:flex">
          {nav.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => cn('flex h-full items-center gap-2 border-b-2 px-4 text-sm text-slate-300 transition-colors hover:text-white', isActive ? 'border-teal-400 text-white' : 'border-transparent')}><Icon className="h-4 w-4" />{label}{to === '/notifications' && unread > 0 && <span aria-label={`Непрочитанных напоминаний: ${unread}`} className="rounded-full bg-red-600 px-1.5 text-xs text-white">{unread}</span>}</NavLink>)}
        </nav>
        <div className="flex shrink-0 items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1.5 text-[11px] font-medium text-emerald-200 sm:text-xs"><ShieldCheck className="h-3.5 w-3.5" /><span className="hidden sm:inline">Данные обрабатываются локально</span><span className="sm:hidden">Локально</span></div>
      </div>
      <nav className="flex overflow-x-auto border-t border-white/10 px-2 md:hidden">
        {nav.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => cn('flex min-w-max flex-1 items-center justify-center gap-1.5 border-b-2 px-3 py-3 text-xs text-slate-300', isActive ? 'border-teal-400 text-white' : 'border-transparent')}><Icon className="h-3.5 w-3.5" />{label}{to === '/notifications' && unread > 0 && <span aria-label={`Непрочитанных напоминаний: ${unread}`} className="rounded-full bg-red-600 px-1.5 text-xs text-white">{unread}</span>}</NavLink>)}
      </nav>
    </header>
    <main className="mx-auto max-w-[1440px] px-4 py-7 sm:px-6 sm:py-9 lg:px-8">{children}</main>
    <footer className="mx-auto max-w-[1440px] border-t px-4 py-5 text-xs text-muted-foreground sm:px-6 lg:px-8">TaldauAI · Локальный прототип</footer>
  </div>
}
