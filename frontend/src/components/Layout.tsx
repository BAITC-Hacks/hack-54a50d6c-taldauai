import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Bell, AudioLines, CalendarDays, FileAudio, ListChecks, Menu, Mic, Plus, ShieldCheck, X } from 'lucide-react'
import { getMeetings, getNotifications } from '@/api'
import type { Meeting } from '@/types'
import { cn } from '@/lib/utils'

const primaryNav = [
  { to: '/app', label: 'Совещания', icon: CalendarDays, end: true },
  { to: '/app/live', label: 'Ассистент созвона', icon: AudioLines },
  { to: '/app/notifications', label: 'Напоминания', icon: Bell },
  { to: '/app/tasks', label: 'Поручения', icon: ListChecks },
]

function Brand() {
  return <Link to="/app" className="flex items-center gap-[9px] px-[13px] text-[19px] font-semibold text-[#171717]">
    <AudioLines className="h-[22px] w-[22px]" strokeWidth={1.8} />
    <span>TaldauAI</span>
  </Link>
}

function pageTitle(pathname: string) {
  if (pathname.startsWith('/app/meetings/')) return 'Протокол'
  if (pathname === '/app/notifications') return 'Напоминания'
  if (pathname === '/app/tasks') return 'Поручения'
  if (pathname === '/app/live') return 'Ассистент созвона'
  if (pathname === '/app/new') return 'Новое совещание'
  return 'Совещания'
}

export function Layout() {
  const [unread, setUnread] = useState(0)
  useEffect(() => {
    let active = true
    const load = async () => {
      try { const items = await getNotifications(); if (active) setUnread(items.filter(n => !n.read_at).length) }
      catch { /* Errors appear on the notification page. */ }
    }
    void load()
    const timer = window.setInterval(load, 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  const location = useLocation()
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [recent, setRecent] = useState<Meeting[]>([])

  useEffect(() => {
    let active = true
    getMeetings().then((meetings) => { if (active) setRecent(meetings.slice(0, 5)) }).catch(() => undefined)
    return () => { active = false }
  }, [])

  useEffect(() => setNavigationOpen(false), [location.pathname])

  return <div className="min-h-screen bg-white text-[#171717]">
    {navigationOpen && <button type="button" aria-label="Закрыть меню" onClick={() => setNavigationOpen(false)} className="fixed inset-0 z-50 bg-black/35 md:hidden" />}

    <aside className={cn(
      'fixed inset-y-0 left-0 z-[60] flex w-[244px] flex-col bg-[#f9f9f9] px-[14px] pb-[15px] pt-6 transition-transform duration-200',
      navigationOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
    )}>
      <div className="mb-[34px] flex items-center justify-between">
        <Brand />
        <button type="button" aria-label="Закрыть меню" onClick={() => setNavigationOpen(false)} className="grid h-8 w-8 place-items-center rounded-lg text-[#777] hover:bg-[#efefef] md:hidden"><X className="h-4 w-4" /></button>
      </div>

      <Link to="/app/new" className="mb-1 flex min-h-[43px] items-center gap-[11px] rounded-[10px] px-[13px] text-sm font-medium text-[#171717] transition-colors hover:bg-[#eee]">
        <Plus className="h-[19px] w-[19px]" strokeWidth={1.8} /> Новое совещание
      </Link>
      <nav className="flex flex-col gap-[5px]" aria-label="Основная навигация">
        {primaryNav.map(({ to, label, icon: Icon, end }) => <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => cn(
            'flex min-h-[43px] items-center gap-[11px] rounded-[10px] px-[13px] text-sm text-[#424242] transition-colors hover:bg-[#eee]',
            isActive && 'bg-[#ebebeb] font-medium text-[#171717]',
          )}
        >
          <Icon className="h-[19px] w-[19px]" strokeWidth={1.7} /> {label}{to === '/app/notifications' && unread > 0 && <span aria-label={`Непрочитанных напоминаний: ${unread}`} className="ml-auto rounded-full bg-red-600 px-1.5 text-xs text-white">{unread}</span>}
        </NavLink>)}
      </nav>

      <div className="mt-8">
        <p className="mb-2 px-[13px] text-xs text-[#7b7b7b]">Недавние</p>
        <div className="flex flex-col gap-0.5">
          {recent.map((meeting) => <Link key={meeting.id} to={`/app/meetings/${meeting.id}`} title={meeting.title} className="truncate rounded-[9px] px-[13px] py-[9px] text-[13px] text-[#555] hover:bg-[#ededed] hover:text-[#171717]">{meeting.title}</Link>)}
          {recent.length === 0 && <span className="px-[13px] py-2 text-xs text-[#888]">Пока нет совещаний</span>}
        </div>
      </div>

      <div className="mt-auto border-t border-[#e7e7e7] pt-5">
        <Link to="/app/new" className="flex items-center gap-2 rounded-[9px] px-[13px] py-[10px] text-xs text-[#777] hover:bg-[#eee] hover:text-[#171717]">
          <FileAudio className="h-[15px] w-[15px]" /> Загрузить запись
        </Link>
        <p className="px-[13px] pt-2 text-[11px] leading-5 text-[#888]"><ShieldCheck className="mr-1 inline h-3.5 w-3.5 align-[-2px]" />Записывай только с согласия участников</p>
      </div>
    </aside>

    <div className="min-h-screen md:ml-[244px]">
      <header className="sticky top-0 z-40 flex h-[61px] items-center gap-2 bg-white/95 px-[14px] backdrop-blur md:h-[70px] md:gap-3 md:px-7">
        <button type="button" aria-label="Открыть меню" title="Открыть меню" onClick={() => setNavigationOpen(true)} className="grid h-9 w-9 shrink-0 place-items-center rounded-[9px] text-[#666] hover:bg-[#efefef] md:hidden"><Menu className="h-5 w-5" /></button>
        <span className="min-w-0 truncate text-sm font-medium text-[#555]">{pageTitle(location.pathname)}</span>
        <div className="ml-auto flex shrink-0 items-center gap-1">
          <Link to="/app/live" aria-label="Запустить ассистента" title="Запустить ассистента" className="grid h-9 w-9 place-items-center rounded-[9px] text-[#666] hover:bg-[#efefef] hover:text-[#171717]"><Mic className="h-[18px] w-[18px]" /></Link>
        </div>
      </header>
      <main id="main" className="min-h-[calc(100vh-61px)] px-0 md:min-h-[calc(100vh-70px)]">
        <Outlet />
      </main>
    </div>
  </div>
}
