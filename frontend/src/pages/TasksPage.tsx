import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Check, CheckCircle2, ChevronRight, ListChecks, Loader2 } from 'lucide-react'
import { getAllActionItems, remindActionItem, updateActionItem } from '@/api'
import type { ActionItem } from '@/types'
import { daysUntil, formatDate, formatTime } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/ui/toast'

type EnrichedAction = ActionItem & { meeting_title: string }
type StatusFilter = 'all' | 'in_progress' | 'soon' | 'overdue' | 'done'

const statusFilters: Array<{ id: StatusFilter; label: string }> = [
  { id: 'all', label: 'Все' },
  { id: 'in_progress', label: 'В работе' },
  { id: 'soon', label: 'Срок скоро' },
  { id: 'overdue', label: 'Просрочено' },
  { id: 'done', label: 'Выполнено' },
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

  useEffect(() => { getAllActionItems().then(setTasks).catch(() => toast('Не удалось загрузить поручения')).finally(() => setLoading(false)) }, [toast])
  const assignees = useMemo(() => Array.from(new Set(tasks.map((task) => task.assignee).filter((name): name is string => Boolean(name)))).sort(), [tasks])
  const meetings = useMemo(() => Array.from(new Map(tasks.map((task) => [task.meeting_id, task.meeting_title])).entries()), [tasks])
  const counts = useMemo(() => Object.fromEntries(statusFilters.map(({ id }) => [id, tasks.filter((item) => matchesStatus(item, id)).length])), [tasks])
  const filtered = tasks.filter((task) => matchesStatus(task, status) && (assignee === 'all' || task.assignee === assignee) && (meetingId === 'all' || task.meeting_id === meetingId))

  const markDone = async (task: EnrichedAction) => {
    const next = task.status === 'done' ? 'in_progress' : 'done'
    if (saving) return
    setSaving(true)
    try {
      const saved = await updateActionItem(task.meeting_id, task.id, { status: next, expected_revision: task.revision ?? 1 })
      setTasks(current => current.map(item => item.id === saved.id ? { ...item, ...saved } : item))
      toast('Статус сохранён')
    } catch (error) { toast('Не удалось сохранить', error instanceof Error ? error.message : undefined) }
    finally { setSaving(false) }
  }

  const saveReminder = async () => {
    if (!reminding) return
    setSaving(true)
    try {
      const updated = await remindActionItem(reminding.meeting_id, reminding.id)
      setTasks((current) => current.map((item) => item.id === updated.id ? { ...item, reminded_at: updated.reminded_at } : item))
      setReminding(null)
      toast('Напоминание зафиксировано', 'Сохранена ручная отметка. Внешняя отправка не выполняется.')
    } catch { toast('Не удалось сохранить отметку') } finally { setSaving(false) }
  }

  const reminderText = reminding ? `Здравствуйте, ${reminding.assignee ?? 'ответственный'}!\n\nНапоминаем о поручении: ${reminding.task}\nСрок исполнения: ${reminding.deadline_date ? formatDate(reminding.deadline_date) : 'не указан'}\nСовещание: ${reminding.meeting_title}\n\nСсылка: ${window.location.origin}/meetings/${reminding.meeting_id}?t=${reminding.timestamp}` : ''

  return <div className="td-page">
    <header className="td-page-heading">
      <div>
        <h1 className="page-title">Поручения</h1>
        <p className="td-page-subtitle">Единый список решений и сроков исполнения</p>
      </div>
      <span className="hidden items-center gap-1.5 text-xs text-[#777] sm:flex"><ListChecks className="h-4 w-4" />{tasks.length} всего</span>
    </header>

    <div className="td-task-filters" role="group" aria-label="Фильтр по статусу">
      {statusFilters.map(({ id, label }) => <button key={id} type="button" aria-pressed={status === id} onClick={() => setStatus(id)}>
        {label}<span className="ml-1.5 text-[11px] text-[#888]">{counts[id] ?? 0}</span>
      </button>)}
    </div>

    <div className="td-toolbar td-task-toolbar">
      <Select value={assignee} onValueChange={setAssignee}><SelectTrigger aria-label="Фильтр по ответственному"><SelectValue placeholder="Ответственный" /></SelectTrigger><SelectContent><SelectItem value="all">Все ответственные</SelectItem>{assignees.map((name) => <SelectItem key={name} value={name}>{name}</SelectItem>)}</SelectContent></Select>
      <Select value={meetingId} onValueChange={setMeetingId}><SelectTrigger aria-label="Фильтр по совещанию"><SelectValue placeholder="Совещание" /></SelectTrigger><SelectContent><SelectItem value="all">Все совещания</SelectItem>{meetings.map(([id, title]) => <SelectItem key={id} value={id}>{title}</SelectItem>)}</SelectContent></Select>
      <span className="ml-auto text-xs text-[#858585]">Найдено: {filtered.length}</span>
    </div>

    <div className="td-task-list">
      {loading && [1, 2, 3].map((item) => <div key={item} className="flex gap-4 border-t border-[#e7e7e7] py-6"><div className="h-5 w-5 animate-pulse rounded border bg-[#f5f5f5]" /><div className="space-y-2"><div className="h-3 w-64 animate-pulse rounded bg-[#eee]" /><div className="h-3 w-40 animate-pulse rounded bg-[#f3f3f3]" /></div></div>)}
      {!loading && filtered.length === 0 && <div className="td-empty">
        <ListChecks className="mx-auto mb-4 h-8 w-8 text-[#aaa]" strokeWidth={1.4} />
        <h3 className="text-[17px] font-medium">Поручения не найдены</h3>
        <p className="mt-2 text-[13px] leading-7 text-[#777]">Измени фильтры или сначала подготовь протокол совещания.</p>
      </div>}
      {!loading && filtered.map((task) => <article key={task.id} className={`td-task-row ${task.status === 'done' ? 'td-task-complete' : ''}`}>
        <button type="button" className="td-task-toggle" aria-label={task.status === 'done' ? 'Вернуть поручение в работу' : 'Отметить поручение выполненным'} aria-pressed={task.status === 'done'} onClick={() => markDone(task)} disabled={saving || task.needs_review}>
          {task.status === 'done' && <Check className="h-3.5 w-3.5" />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">{deadlineBadge(task)}{task.needs_review && <Badge variant="secondary">Требует проверки</Badge>}{task.reminded_at && <span className="text-[11px] text-[#777]">Напоминание {formatDate(task.reminded_at, true)}</span>}</div>
          <h2 className="text-[15px] font-medium leading-6 text-[#252525]">{task.task}</h2>
          <div className="mt-1.5 flex flex-wrap gap-x-2 gap-y-1 text-xs text-[#707070]">
            <span>{task.assignee ?? 'Ответственный не определён'}</span><span className="text-[#bbb]">·</span>
            <span>{task.deadline_date ? formatDate(task.deadline_date) : 'Срок не указан'}</span><span className="text-[#bbb]">·</span>
            <span>{task.urgency === 'high' ? 'Высокая срочность' : task.urgency === 'medium' ? 'Средняя срочность' : 'Низкая срочность'}</span>
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <Link to={`/meetings/${task.meeting_id}?t=${task.timestamp}`} className="inline-flex min-w-0 items-center gap-1 text-xs text-[#666] hover:text-[#171717] hover:underline hover:underline-offset-4">
              <span className="truncate">{task.meeting_title}</span><span className="shrink-0">· {formatTime(task.timestamp)}</span><ChevronRight className="h-3.5 w-3.5 shrink-0" />
            </Link>
            <div className="flex items-center gap-1">
              <Button size="sm" variant="ghost" onClick={() => setReminding(task)} disabled={task.status === 'done' || task.needs_review} title={task.needs_review ? 'Сначала проверь поручение' : 'Подготовить напоминание'}><Bell className="h-3.5 w-3.5" /><span>Напомнить</span></Button>
              {task.status === 'done' && <span className="inline-flex items-center gap-1 text-[11px] text-[#777]"><CheckCircle2 className="h-3.5 w-3.5" />Готово</span>}
            </div>
          </div>
        </div>
      </article>)}
    </div>

    <Dialog open={Boolean(reminding)} onOpenChange={(open) => !open && setReminding(null)}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Напоминание об исполнении</DialogTitle><DialogDescription>Текст будет сохранён вместе с отметкой о напоминании.</DialogDescription></DialogHeader><div className="rounded-[10px] bg-[#f7f7f7] p-4"><pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-[#555]">{reminderText}</pre></div><DialogFooter><Button variant="outline" onClick={() => setReminding(null)}>Отмена</Button><Button onClick={saveReminder} disabled={saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}Напомнить</Button></DialogFooter></DialogContent></Dialog>
  </div>
}
