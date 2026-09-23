import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CalendarDays, CheckCircle2, Clock3, FileAudio, ListChecks, Plus } from 'lucide-react'
import { getMeetings } from '@/api'
import type { Meeting } from '@/types'
import { formatDate } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

export function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => { getMeetings().then(setMeetings).finally(() => setLoading(false)) }, [])
  const openTasks = meetings.reduce((sum, meeting) => sum + meeting.action_items.filter((item) => item.status === 'in_progress').length, 0)

  return <div className="space-y-7">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><p className="mb-2 text-xs font-semibold uppercase tracking-[.16em] text-teal-700">Рабочее пространство</p><h1 className="page-title">Совещания</h1><p className="mt-2 text-sm text-muted-foreground">Протоколы, решения и поручения в едином контуре</p></div>
      <Link to="/new"><Button className="w-full sm:w-auto"><Plus className="h-4 w-4" />Новое совещание</Button></Link>
    </div>

    <div className="grid gap-3 sm:grid-cols-3">
      <Card><CardContent className="flex items-center gap-4 p-4"><span className="rounded-lg bg-blue-50 p-2.5 text-blue-700"><FileAudio className="h-5 w-5" /></span><div><p className="text-2xl font-semibold">{meetings.length}</p><p className="text-xs text-muted-foreground">Всего совещаний</p></div></CardContent></Card>
      <Card><CardContent className="flex items-center gap-4 p-4"><span className="rounded-lg bg-amber-50 p-2.5 text-amber-700"><ListChecks className="h-5 w-5" /></span><div><p className="text-2xl font-semibold">{openTasks}</p><p className="text-xs text-muted-foreground">Поручений в работе</p></div></CardContent></Card>
      <Card><CardContent className="flex items-center gap-4 p-4"><span className="rounded-lg bg-emerald-50 p-2.5 text-emerald-700"><CheckCircle2 className="h-5 w-5" /></span><div><p className="text-2xl font-semibold">{meetings.filter((m) => m.status === 'Протокол готов').length}</p><p className="text-xs text-muted-foreground">Протоколов готово</p></div></CardContent></Card>
    </div>

    <section>
      <div className="mb-3 flex items-center justify-between"><h2 className="section-title">Последние совещания</h2><span className="text-xs text-muted-foreground">Сначала новые</span></div>
      <div className="space-y-3">
        {loading && [1, 2].map((item) => <div key={item} className="h-28 animate-pulse rounded-lg border bg-white" />)}
        {!loading && meetings.map((meeting) => <Link to={`/meetings/${meeting.id}`} key={meeting.id} className="group block rounded-lg border bg-white p-5 shadow-panel transition-all hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-md">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0"><div className="mb-2 flex flex-wrap items-center gap-2"><Badge variant={meeting.status === 'Протокол готов' ? 'success' : 'warning'}>{meeting.status}</Badge><span className="flex items-center gap-1 text-xs text-muted-foreground"><CalendarDays className="h-3.5 w-3.5" />{formatDate(meeting.date, true)}</span></div><h3 className="font-semibold text-slate-900 group-hover:text-teal-800">{meeting.title}</h3><div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground"><span>{meeting.participants.length} участников</span><span>{meeting.segments.length} реплик</span><span className="flex items-center gap-1"><Clock3 className="h-3.5 w-3.5" />{meeting.action_items.length} поручений</span></div></div>
            <ArrowRight className="mt-1 h-5 w-5 shrink-0 text-slate-300 transition-transform group-hover:translate-x-1 group-hover:text-teal-600" />
          </div>
        </Link>)}
      </div>
    </section>
  </div>
}
