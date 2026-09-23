import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Bot, Check, CheckCircle2, Clock3, Download, FileText, Loader2, Pencil, Quote, Sparkles, Trash2, Users } from 'lucide-react'
import { createActionItem, deleteActionItem, exportMeetingDocx, getMeeting, updateActionItem, updateParticipant } from '@/api'
import type { ActionItem, Meeting, Participant } from '@/types'
import { formatDate, formatTime } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/ui/toast'

const steps = ['Конвертация', 'Распознавание речи', 'Разделение говорящих', 'Извлечение поручений', 'Саммари']
const speakerStyles = [
  'border-blue-200 bg-blue-50 text-blue-800', 'border-teal-200 bg-teal-50 text-teal-800', 'border-violet-200 bg-violet-50 text-violet-800', 'border-amber-200 bg-amber-50 text-amber-800', 'border-rose-200 bg-rose-50 text-rose-800',
]
const langLabels = { ru: 'RU', kk: 'KZ', mixed: 'Смеш.' }
const urgencyLabels = { high: 'Высокая', medium: 'Средняя', low: 'Низкая' }
const meetingStatusLabels: Record<string, string> = {
  converting: 'Конвертация', transcribing: 'Распознавание речи', diarizing: 'Разделение говорящих',
  extracting: 'Извлечение поручений', done: 'Черновик готов', failed: 'Ошибка обработки', error: 'Ошибка обработки',
  'Протокол готов': 'Протокол готов', 'Обрабатывается': 'Обрабатывается',
}
const processingStatuses = new Set(['converting', 'transcribing', 'diarizing', 'extracting', 'Обрабатывается'])

function ProcessingProgress({ step }: { step: number }) {
  const progress = Math.min(100, Math.round((step / steps.length) * 100))
  return <Card className="overflow-hidden border-blue-200 bg-gradient-to-r from-blue-50 to-teal-50">
    <CardContent className="p-5 sm:p-6">
      <div className="mb-4 flex items-center justify-between"><div><p className="font-semibold text-slate-900">Обработка записи</p><p className="mt-1 text-xs text-muted-foreground">Обычно занимает несколько минут</p></div><span className="text-sm font-semibold text-blue-700">{progress}%</span></div>
      <div className="mb-5 h-2 overflow-hidden rounded-full bg-white"><div className="h-full rounded-full bg-gradient-to-r from-blue-600 to-teal-500 transition-all duration-700" style={{ width: `${progress}%` }} /></div>
      <div className="grid gap-2 sm:grid-cols-5">
        {steps.map((label, index) => { const done = index < step; const active = index === step && step < steps.length; return <div key={label} className="flex items-center gap-2 sm:block"><span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${done ? 'bg-emerald-600 text-white' : active ? 'bg-blue-700 text-white ring-4 ring-blue-100' : 'bg-white text-slate-400'}`}>{done ? <Check className="h-4 w-4" /> : index + 1}</span><p className={`text-xs sm:mt-2 ${done || active ? 'font-medium text-slate-800' : 'text-slate-400'}`}>{label}</p></div> })}
      </div>
    </CardContent>
  </Card>
}

function ParticipantEditor({ participant, open, onOpenChange, onSave }: { participant: Participant | null; open: boolean; onOpenChange: (open: boolean) => void; onSave: (name: string, role: string) => Promise<void> }) {
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => { if (participant) { setName(participant.name); setRole(participant.role) } }, [participant])
  const save = async () => { if (!name.trim() || !role.trim()) return; setSaving(true); setError(''); try { await onSave(name.trim(), role.trim()); onOpenChange(false) } catch (error) { setError(error instanceof Error ? error.message : 'Не удалось сохранить') } finally { setSaving(false) } }
  return <Dialog open={open} onOpenChange={value => { if (!saving) onOpenChange(value) }}><DialogContent><DialogHeader><DialogTitle>Изменить участника</DialogTitle><DialogDescription>Имя обновится в транскрипте и связанных поручениях.</DialogDescription></DialogHeader><div className="space-y-4 py-2"><div className="space-y-2"><Label>Имя и фамилия</Label><Input value={name} onChange={(event) => setName(event.target.value)} /></div><div className="space-y-2"><Label>Должность</Label><Input value={role} onChange={(event) => setRole(event.target.value)} /></div></div><DialogFooter>{error && <p role="alert" className="text-red-700">{error}</p>}<Button disabled={saving} variant="outline" onClick={() => onOpenChange(false)}>Отмена</Button><Button onClick={save} disabled={saving || !name.trim() || !role.trim()}>{saving && <Loader2 className="h-4 w-4 animate-spin" />}Сохранить</Button></DialogFooter></DialogContent></Dialog>
}

export function MeetingPage() {
  const { id = '' } = useParams()
  const [searchParams] = useSearchParams()
  const { toast } = useToast()
  const [meeting, setMeeting] = useState<Meeting | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Participant | null>(null)
  const [highlighted, setHighlighted] = useState<number | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [taskEditor, setTaskEditor] = useState<ActionItem | 'new' | null>(null)
  const [busy, setBusy] = useState(false)
  const savingRef = useRef(false)

  useEffect(() => {
    let active = true
    let timer: number | undefined
    const load = async () => {
      try {
        const data = await getMeeting(id)
        if (!active) return
        setMeeting(data)
        if (data && processingStatuses.has(data.status)) timer = window.setTimeout(load, 2000)
      } catch { if (active) toast('Не удалось загрузить совещание') } finally { if (active) setLoading(false) }
    }
    load()
    return () => { active = false; if (timer) window.clearTimeout(timer) }
  }, [id, toast])

  const jumpToTranscript = (timestamp: number) => {
    setHighlighted(timestamp)
    document.getElementById(`segment-${timestamp}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => setHighlighted(null), 2300)
  }

  useEffect(() => {
    if (!meeting) return
    const target = Number(searchParams.get('t'))
    if (!Number.isFinite(target) || !target) return
    const timer = window.setTimeout(() => jumpToTranscript(target), 450)
    return () => window.clearTimeout(timer)
  }, [meeting, searchParams])

  const participantByLabel = useMemo(() => new Map(meeting?.participants.map((p) => [p.speaker_label, p]) ?? []), [meeting])
  const processingStep = meeting ? ({ converting: 0, transcribing: 1, diarizing: 2, extracting: 3, 'Обрабатывается': 0 }[meeting.status] ?? steps.length) : steps.length
  const isReady = meeting?.status === 'done' || meeting?.status === 'Протокол готов'
  const reviewComplete = Boolean(isReady && meeting?.action_items.every((item) => !item.needs_review))
  const updateLocalAction = async (action: ActionItem, patch: Parameters<typeof updateActionItem>[2]) => {
    if (!meeting) return
    if (savingRef.current) return
    savingRef.current = true; setBusy(true)
    try {
      const saved = await updateActionItem(meeting.id, action.id, { ...patch, expected_revision: action.revision ?? 1 })
      setMeeting(current => current && ({ ...current, action_items: current.action_items.map(item => item.id === saved.id ? saved : item) }))
    } catch (error) { toast('Изменение не сохранено', error instanceof Error ? error.message : undefined) }
    finally { savingRef.current = false; setBusy(false) }
  }
  const removeAction = async (action: ActionItem) => {
    if (!meeting || savingRef.current) return
    savingRef.current = true; setBusy(true)
    try {
      await deleteActionItem(meeting.id, action.id)
      setMeeting(current => current && ({ ...current, action_items: current.action_items.filter(item => item.id !== action.id) }))
      toast('Поручение удалено')
    } catch { toast('Не удалось удалить поручение') }
    finally { savingRef.current = false; setBusy(false) }
  }
  const saveParticipant = async (name: string, role: string) => {
    if (!meeting || !editing || savingRef.current) throw new Error('Дождитесь сохранения')
    savingRef.current = true; setBusy(true)
    try {
      const updated = await updateParticipant(meeting.id, editing.speaker_label, { name, role })
      setMeeting(updated)
      toast('Участник сохранён', 'Связанные поручения требуют повторной проверки.')
    } finally { savingRef.current = false; setBusy(false) }
  }
  const saveTask = async (payload: Parameters<typeof createActionItem>[1]) => {
    if (!meeting || !taskEditor || savingRef.current) throw new Error('Дождитесь сохранения')
    savingRef.current = true; setBusy(true)
    try {
      const saved = taskEditor === 'new' ? await createActionItem(meeting.id, payload)
        : await updateActionItem(meeting.id, taskEditor.id, { ...payload, expected_revision: taskEditor.revision ?? 1 })
      setMeeting(current => current && ({ ...current, action_items: taskEditor === 'new' ? [...current.action_items, saved] : current.action_items.map(item => item.id === saved.id ? saved : item) }))
      setTaskEditor(null)
      toast('Поручение сохранено', 'Проверьте данные и подтвердите поручение.')
    } finally { savingRef.current = false; setBusy(false) }
  }
  const downloadProtocol = async () => {
    if (!meeting) return
    setDownloading(true)
    try { await exportMeetingDocx(meeting.id); toast('Протокол сформирован', 'Файл DOCX сохранён на устройство.') }
    catch (reason) { toast('Не удалось скачать протокол', reason instanceof Error ? reason.message : undefined) }
    finally { setDownloading(false) }
  }

  if (loading) return <div className="space-y-4"><div className="h-20 animate-pulse rounded-lg bg-white" /><div className="h-52 animate-pulse rounded-lg bg-white" /></div>
  if (!meeting) return <Card><CardContent className="p-8 text-center"><FileText className="mx-auto mb-3 h-8 w-8 text-slate-400" /><p className="font-semibold">Совещание не найдено</p><Button variant="outline" className="mt-4" onClick={() => history.back()}>Вернуться</Button></CardContent></Card>

  return <div className="space-y-6">
    <div>
      <Link to="/" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary"><ArrowLeft className="h-4 w-4" />К списку совещаний</Link>
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start"><div><div className="mb-2 flex flex-wrap items-center gap-2"><Badge variant={reviewComplete ? 'success' : meeting.status === 'failed' || meeting.status === 'error' ? 'danger' : 'warning'}>{reviewComplete ? 'Протокол проверен' : meetingStatusLabels[meeting.status] ?? meeting.status}</Badge><span className="text-xs text-muted-foreground">{formatDate(meeting.date, true)}</span></div><h1 className="max-w-4xl text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">{meeting.title}</h1></div><Button variant="outline" onClick={downloadProtocol} disabled={!reviewComplete || downloading}>{downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}Скачать протокол (DOCX)</Button></div>
    </div>

    {processingStatuses.has(meeting.status) && <ProcessingProgress step={processingStep} />}
    {isReady && <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><CheckCircle2 className="h-4 w-4" />ML-обработка завершена. Проверьте говорящих, исходный текст и каждое поручение перед использованием.</div>}
    {(meeting.warnings ?? []).map((warning) => <div key={warning} className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">{warning}</div>)}
    {(meeting.status === 'failed' || meeting.status === 'error') && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">Обработка завершилась с ошибкой: {meeting.error_message ?? 'повторите загрузку или обратитесь к администратору.'}</div>}

    <section><div className="mb-3 flex items-center gap-2"><Users className="h-5 w-5 text-teal-700" /><h2 className="section-title">Участники</h2><Badge variant="secondary">{meeting.participants.length}</Badge></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{meeting.participants.map((participant, index) => <Card key={participant.speaker_label}><CardContent className="flex items-start gap-3 p-4"><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-sm font-semibold ${speakerStyles[index % speakerStyles.length]}`}>{participant.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{participant.name}</p><p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{participant.role}</p>{participant.auto_detected && <span className="mt-2 inline-flex items-center gap-1 text-[11px] text-violet-700"><Bot className="h-3 w-3" />определено ИИ</span>}</div><Button size="icon" variant="ghost" aria-label={`Изменить ${participant.name}`} disabled={busy} onClick={() => setEditing(participant)}><Pencil className="h-4 w-4" /></Button></CardContent></Card>)}</div></section>

    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,.75fr)]">
      <section className="min-w-0"><div className="mb-3 flex items-center gap-2"><FileText className="h-5 w-5 text-teal-700" /><h2 className="section-title">Транскрипт</h2><Badge variant="secondary">{meeting.segments.length} реплик</Badge></div><Card><CardContent className="divide-y p-0">{meeting.segments.map((segment) => { const participant = participantByLabel.get(segment.speaker_label ?? ''); const speakerIndex = Math.max(0, meeting.participants.findIndex((p) => p.speaker_label === segment.speaker_label)); return <article id={`segment-${segment.start}`} key={segment.source_segment_id ?? `${segment.start}-${segment.speaker_label}`} className={`scroll-mt-32 p-4 transition-all sm:p-5 ${highlighted === segment.start ? 'focus-row' : ''}`}><div className="mb-2 flex flex-wrap items-center gap-2"><span className={`rounded-md border px-2 py-1 text-xs font-semibold ${speakerStyles[speakerIndex % speakerStyles.length]}`}>{participant?.name ?? segment.speaker_label ?? 'Говорящий не определён'}</span><button className="flex items-center gap-1 font-mono text-xs text-slate-500 hover:text-teal-700"><Clock3 className="h-3 w-3" />{formatTime(segment.start)}</button><Badge variant="outline" className="text-[10px]">{segment.lang ? langLabels[segment.lang] : '—'}</Badge></div><p className="text-sm leading-6 text-slate-700">{segment.text}</p>{segment.suggested_text && segment.suggested_text !== segment.text && <div className="mt-3 rounded-md border border-violet-100 bg-violet-50/70 p-3"><p className="text-[11px] font-semibold uppercase tracking-wide text-violet-700">Подсказка KazLLM</p><p className="mt-1 text-sm text-violet-950">{segment.suggested_text}</p></div>}</article>})}</CardContent></Card></section>
      <section><div className="mb-3 flex items-center gap-2"><Sparkles className="h-5 w-5 text-violet-700" /><h2 className="section-title">Саммари совещания</h2></div><Card className="sticky top-24 border-violet-100 bg-gradient-to-br from-white to-violet-50/50"><CardContent className="p-5"><p className="text-sm leading-7 text-slate-700">{meeting.summary}</p><div className="mt-5 border-t pt-4"><p className="flex items-center gap-1.5 text-xs font-medium text-violet-700"><Bot className="h-3.5 w-3.5" />Сформировано ИИ по полной транскрипции</p></div></CardContent></Card></section>
    </div>

    <section>
      <div className="mb-3 flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-teal-700" /><h2 className="section-title">Поручения</h2><Badge variant="secondary">{meeting.action_items.length}</Badge><Button disabled={!isReady || busy} variant="outline" onClick={() => setTaskEditor('new')}>Добавить поручение</Button></div>
      <Card className="overflow-hidden"><div className="overflow-x-auto"><table className="w-full min-w-[1120px] text-left text-sm">
        <thead className="border-b bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="w-[32%] px-4 py-3 font-medium">Суть поручения</th><th className="px-3 py-3 font-medium">Ответственный</th><th className="px-3 py-3 font-medium">Срок</th><th className="px-3 py-3 font-medium">Статус</th><th className="px-3 py-3 font-medium">Срочность</th><th className="w-36 px-3 py-3">Проверка</th></tr></thead>
        <tbody className="divide-y">{meeting.action_items.map((action) => <tr key={action.id} className="align-top hover:bg-slate-50/70">
          <td className="px-4 py-3"><div className="flex items-center gap-2">{action.needs_review && <Badge variant="warning">Требует проверки</Badge>}{action.source_segment_ids?.length ? <span className="text-[11px] text-muted-foreground">Источников: {action.source_segment_ids.length}</span> : null}</div><p className="mt-2 font-medium">{action.task}</p><Button size="sm" variant="outline" disabled={busy} onClick={() => setTaskEditor(action)}>Изменить поручение</Button><button onClick={() => jumpToTranscript(action.timestamp)} className="mt-2 flex max-w-md items-start gap-1.5 px-2 text-left text-xs leading-5 text-slate-500 hover:text-teal-700"><Quote className="mt-0.5 h-3 w-3 shrink-0" />«{action.quote}» · {formatTime(action.timestamp)}</button></td>
          <td className="px-3 py-3">{action.assignee || 'Не определён'}</td>
          <td className="px-3 py-3">{action.deadline_date ? formatDate(action.deadline_date) : 'Не указан'}</td>
          <td className="px-3 py-3"><Select disabled={busy} value={action.status} onValueChange={(value: ActionItem['status']) => updateLocalAction(action, { status: value })}><SelectTrigger className={action.status === 'done' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : ''}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="in_progress">В работе</SelectItem><SelectItem value="done">Выполнено</SelectItem></SelectContent></Select></td>
          <td className="px-3 py-3"><Select disabled={busy} value={action.urgency} onValueChange={(value: ActionItem['urgency']) => updateLocalAction(action, { urgency: value })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{Object.entries(urgencyLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></td>
          <td className="space-y-2 px-3 py-3">{action.needs_review ? <Button size="sm" className="w-full" disabled={busy || !action.assignee || !action.deadline_date} onClick={() => updateLocalAction(action, { needs_review: false })}><Check className="h-4 w-4" />Подтвердить</Button> : <Badge variant="success">Проверено</Badge>}<Button size="sm" variant="ghost" className="w-full text-red-600 hover:bg-red-50 hover:text-red-700" disabled={busy} onClick={() => removeAction(action)}><Trash2 className="h-4 w-4" />Удалить</Button></td>
        </tr>)}</tbody>
      </table></div></Card>
    </section>
    {taskEditor && <TaskEditor key={taskEditor === 'new' ? 'new' : taskEditor.id} action={taskEditor === 'new' ? null : taskEditor} participants={meeting.participants} onSave={saveTask} onClose={() => setTaskEditor(null)} />}
    <ParticipantEditor participant={editing} open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)} onSave={saveParticipant} />
  </div>
}

function TaskEditor({ action, participants, onSave, onClose }: { action: ActionItem | null; participants: Participant[]; onSave: (payload: Parameters<typeof createActionItem>[1]) => Promise<void>; onClose: () => void }) {
  const [task, setTask] = useState(action?.task ?? '')
  const [assignee, setAssignee] = useState(action?.assignee ?? '')
  const [deadline, setDeadline] = useState(action?.deadline_date ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const save = async () => {
    setSaving(true); setError('')
    try {
      await onSave({ task: task.trim(), assignee: assignee.trim() || null, deadline_date: deadline || null,
        speaker_label: participants.find(p => p.name === assignee.trim())?.speaker_label ?? null })
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Изменения не сохранены') }
    finally { setSaving(false) }
  }
  return <Dialog open onOpenChange={open => { if (!open && !saving) onClose() }}><DialogContent><DialogHeader><DialogTitle>{action ? 'Изменить поручение' : 'Добавить поручение'}</DialogTitle><DialogDescription>После сохранения поручение нужно проверить и подтвердить. Можно указать человека или отдел вне списка участников.</DialogDescription></DialogHeader>
    <div className="space-y-3"><Label htmlFor="task-text">Суть поручения</Label><Input id="task-text" value={task} disabled={saving} onChange={e => setTask(e.target.value)} />
    <Label htmlFor="task-assignee">Ответственный</Label><Input id="task-assignee" list="task-participants" value={assignee} disabled={saving} onChange={e => setAssignee(e.target.value)} /><datalist id="task-participants">{participants.map(p => <option key={p.speaker_label} value={p.name} />)}</datalist>
    <Label htmlFor="task-deadline">Срок</Label><Input id="task-deadline" type="date" value={deadline} disabled={saving} onChange={e => setDeadline(e.target.value)} />
    {error && <p role="alert" className="text-sm text-red-700">Не сохранено: {error}</p>}</div><DialogFooter><Button variant="outline" disabled={saving} onClick={onClose}>Отмена</Button><Button disabled={saving || !task.trim()} onClick={save}>{saving ? 'Сохранение…' : 'Сохранить'}</Button></DialogFooter></DialogContent></Dialog>
}
