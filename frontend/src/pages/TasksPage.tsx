import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Bell, CalendarClock, Check, CheckCircle2, ChevronRight, CircleDot, Filter, ListChecks, Loader2 } from 'lucide-react'
import { getAllActionItems, remindActionItem, updateActionItem } from '@/api'
import type { ActionItem } from '@/types'
import { daysUntil, formatDate, formatTime } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/ui/toast'

type EnrichedAction = ActionItem & { meeting_title: string }
type StatusFilter = 'all' | 'in_progress' | 'soon' | 'overdue' | 'done'

const statusCards: Array<{ id: StatusFilter; label: string; icon: typeof CircleDot; color: string; active: string }> = [
  { id: 'in_progress', label: 'В работе', icon: CircleDot, color: 'text-blue-700 bg-blue-50', active: 'ring-blue-400 border-blue-300' },
  { id: 'soon', label: 'Срок скоро', icon: CalendarClock, color: 'text-amber-700 bg-amber-50', active: 'ring-amber-400 border-amber-300' },
  { id: 'overdue', label: 'Просрочено', icon: AlertTriangle, color: 'text-red-700 bg-red-50', active: 'ring-red-400 border-red-300' },
  { id: 'done', label: 'Выполнено', icon: CheckCircle2, color: 'text-emerald-700 bg-emerald-50', active: 'ring-emerald-400 border-emerald-300' },
]

function matchesStatus(item: EnrichedAction, filter: StatusFilter) {
  const days = daysUntil(item.deadline_date)
  if (filter === 'all') return true
  if (filter === 'done') return item.status === 'done'
  if (filter === 'in_progress') return item.status === 'in_progress'
  if (filter === 'overdue') return item.status === 'in_progress' && days !== null && days < 0
  return item.status === 'in_progress' && days !== null && days >= 0 && days <= 2
}

function deadlineBadge(item: EnrichedAction) {
  if (item.status === 'done') return <Badge variant="success">Выполнено</Badge>
  const days = daysUntil(item.deadline_date)
  if (days === null) return <Badge variant="secondary">Без срока</Badge>
  if (days < 0) return <Badge variant="danger">Просрочено на {Math.abs(days)} дн.</Badge>
  if (days === 0) return <Badge variant="warning">Сегодня</Badge>
  if (days <= 2) return <Badge variant="warning">Осталось {days} дн.</Badge>
  return <Badge variant="info">Осталось {days} дн.</Badge>
}

export function TasksPage() {
  const { toast } = useToast()
  const [tasks, setTasks] = useState<EnrichedAction[]>([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<StatusFilter>('all')
  const [assignee, setAssignee] = useState('all')
  const [meetingId, setMeetingId] = useState('all')
  const [reminding, setReminding] = useState<EnrichedAction | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => { getAllActionItems().then(setTasks).finally(() => setLoading(false)) }, [])
  const assignees = useMemo(() => Array.from(new Set(tasks.map((task) => task.assignee))).sort(), [tasks])
  const meetings = useMemo(() => Array.from(new Map(tasks.map((task) => [task.meeting_id, task.meeting_title])).entries()), [tasks])
  const counts = useMemo(() => Object.fromEntries(statusCards.map((card) => [card.id, tasks.filter((item) => matchesStatus(item, card.id)).length])), [tasks])
  const filtered = tasks.filter((task) => matchesStatus(task, status) && (assignee === 'all' || task.assignee === assignee) && (meetingId === 'all' || task.meeting_id === meetingId))

  const markDone = async (task: EnrichedAction) => {
    const next = task.status === 'done' ? 'in_progress' : 'done'
    setTasks((current) => current.map((item) => item.id === task.id ? { ...item, status: next } : item))
    await updateActionItem(task.meeting_id, task.id, { status: next })
    toast(next === 'done' ? 'Поручение выполнено' : 'Поручение возвращено в работу')
  }

  const saveReminder = async () => {
    if (!reminding) return
    setSaving(true)
    try {
      const updated = await remindActionItem(reminding.meeting_id, reminding.id)
      setTasks((current) => current.map((item) => item.id === updated.id ? { ...item, reminded_at: updated.reminded_at } : item))
      setReminding(null)
      toast('Напоминание зафиксировано', 'Время отправки сохранено в карточке поручения.')
    } finally { setSaving(false) }
  }

  const reminderText = reminding ? `Здравствуйте, ${reminding.assignee}!\n\nНапоминаем о поручении: ${reminding.task}\nСрок исполнения: ${reminding.deadline_date ? formatDate(reminding.deadline_date) : 'не указан'}\nСовещание: ${reminding.meeting_title}\n\nСсылка: ${window.location.origin}/meetings/${reminding.meeting_id}?t=${reminding.timestamp}` : ''

  return <div className="space-y-7">
    <div><p className="mb-2 text-xs font-semibold uppercase tracking-[.16em] text-teal-700">Единый реестр</p><h1 className="page-title">Контроль поручений</h1><p className="mt-2 text-sm text-muted-foreground">Поручения из всех протоколов и контроль сроков исполнения</p></div>

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{statusCards.map((card) => { const Icon = card.icon; return <button key={card.id} onClick={() => setStatus(status === card.id ? 'all' : card.id)} className={`rounded-lg border bg-white p-4 text-left shadow-panel transition-all hover:-translate-y-0.5 hover:shadow-md ${status === card.id ? `ring-2 ${card.active}` : ''}`}><div className="flex items-center justify-between"><span className={`rounded-lg p-2.5 ${card.color}`}><Icon className="h-5 w-5" /></span><span className="text-3xl font-semibold text-slate-900">{counts[card.id] ?? 0}</span></div><p className="mt-3 text-sm font-medium text-slate-700">{card.label}</p></button> })}</div>

    <Card><CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center"><div className="flex items-center gap-2 text-sm font-medium text-slate-700"><Filter className="h-4 w-4 text-teal-700" />Фильтры</div><div className="grid flex-1 gap-3 sm:grid-cols-2"><Select value={assignee} onValueChange={setAssignee}><SelectTrigger><SelectValue placeholder="Ответственный" /></SelectTrigger><SelectContent><SelectItem value="all">Все ответственные</SelectItem>{assignees.map((name) => <SelectItem key={name} value={name}>{name}</SelectItem>)}</SelectContent></Select><Select value={meetingId} onValueChange={setMeetingId}><SelectTrigger><SelectValue placeholder="Совещание" /></SelectTrigger><SelectContent><SelectItem value="all">Все совещания</SelectItem>{meetings.map(([id, title]) => <SelectItem key={id} value={id}>{title}</SelectItem>)}</SelectContent></Select></div><div className="text-xs text-muted-foreground">Найдено: {filtered.length}</div></CardContent></Card>

    <div className="space-y-3">
      {loading && [1, 2, 3].map((item) => <div key={item} className="h-36 animate-pulse rounded-lg border bg-white" />)}
      {!loading && filtered.length === 0 && <Card><CardContent className="p-10 text-center"><ListChecks className="mx-auto mb-3 h-8 w-8 text-slate-300" /><p className="font-medium">Поручения не найдены</p><p className="mt-1 text-sm text-muted-foreground">Измените выбранные фильтры</p></CardContent></Card>}
      {!loading && filtered.map((task) => <Card key={task.id} className={`overflow-hidden ${task.status === 'done' ? 'bg-slate-50/60' : ''}`}><CardContent className="p-0"><div className="grid lg:grid-cols-[minmax(0,1fr)_230px]">
        <div className="p-5"><div className="mb-3 flex flex-wrap items-center gap-2">{deadlineBadge(task)}<Badge variant="outline">{task.urgency === 'high' ? 'Высокая срочность' : task.urgency === 'medium' ? 'Средняя срочность' : 'Низкая срочность'}</Badge>{task.reminded_at && <span className="flex items-center gap-1 text-[11px] text-violet-700"><Bell className="h-3 w-3" />Напоминание {formatDate(task.reminded_at, true)}</span>}</div><h3 className={`font-semibold leading-6 ${task.status === 'done' ? 'text-slate-500 line-through decoration-slate-300' : 'text-slate-900'}`}>{task.task}</h3><div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground"><span><span className="font-medium text-slate-600">Ответственный:</span> {task.assignee}</span><span><span className="font-medium text-slate-600">Срок:</span> {task.deadline_date ? formatDate(task.deadline_date) : 'не указан'}</span></div><Link to={`/meetings/${task.meeting_id}?t=${task.timestamp}`} className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-teal-700 hover:text-teal-900">{task.meeting_title} · {formatTime(task.timestamp)}<ChevronRight className="h-3.5 w-3.5" /></Link></div>
        <div className="flex items-center gap-2 border-t bg-slate-50/70 p-4 lg:flex-col lg:items-stretch lg:justify-center lg:border-l lg:border-t-0"><Button variant="outline" className="flex-1" onClick={() => setReminding(task)} disabled={task.status === 'done'}><Bell className="h-4 w-4" />Напомнить</Button><Button variant={task.status === 'done' ? 'secondary' : 'default'} className="flex-1" onClick={() => markDone(task)}><Check className="h-4 w-4" />{task.status === 'done' ? 'Вернуть в работу' : 'Выполнено'}</Button></div>
      </div></CardContent></Card>)}
    </div>

    <Dialog open={Boolean(reminding)} onOpenChange={(open) => !open && setReminding(null)}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Напоминание об исполнении</DialogTitle><DialogDescription>Проверьте готовый текст. В прототипе сохраняется отметка о напоминании.</DialogDescription></DialogHeader><div className="rounded-lg border bg-slate-50 p-4"><pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-slate-700">{reminderText}</pre></div><DialogFooter><Button variant="outline" onClick={() => setReminding(null)}>Отмена</Button><Button onClick={saveReminder} disabled={saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}Напомнить</Button></DialogFooter></DialogContent></Dialog>
  </div>
}
