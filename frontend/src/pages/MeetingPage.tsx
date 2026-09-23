import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Bot, Check, CheckCircle2, Clock3, Download, FileText, Loader2, Pencil, Quote, Trash2 } from 'lucide-react'
import { deleteActionItem, exportMeetingDocx, getMeeting, updateActionItem, updateParticipant } from '@/api'
import type { ActionItem, Meeting, Participant } from '@/types'
import { formatDate, formatTime } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/ui/toast'

const steps = ['Конвертация', 'Распознавание речи', 'Разделение говорящих', 'Извлечение поручений', 'Саммари']
const speakerStyles = [
  'border-[#e5e5e5] bg-[#f7f7f7] text-[#444]', 'border-[#e5e5e5] bg-white text-[#555]', 'border-[#e5e5e5] bg-[#f1f1f1] text-[#444]',
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
  return <section className="td-processing">
      <div className="mb-4 flex items-center justify-between"><div><p className="font-medium text-[#252525]">Обработка записи</p><p className="mt-1 text-xs text-[#777]">Обычно занимает несколько минут</p></div><span className="text-xs text-[#777]">{progress}%</span></div>
      <div className="mb-5 h-1 overflow-hidden rounded-full bg-[#e8e8e8]"><div className="h-full bg-[#555] transition-all duration-700" style={{ width: `${progress}%` }} /></div>
      <div className="grid gap-2 sm:grid-cols-5">
        {steps.map((label, index) => { const done = index < step; const active = index === step && step < steps.length; return <div key={label} className="flex items-center gap-2 sm:block"><span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium ${done ? 'bg-[#171717] text-white' : active ? 'bg-[#e9e9e9] text-[#171717]' : 'bg-[#f5f5f5] text-[#999]'}`}>{done ? <Check className="h-4 w-4" /> : index + 1}</span><p className={`text-xs sm:mt-2 ${done || active ? 'font-medium text-[#444]' : 'text-[#999]'}`}>{label}</p></div> })}
      </div>
  </section>
}

function ParticipantEditor({ participant, open, onOpenChange, onSave }: { participant: Participant | null; open: boolean; onOpenChange: (open: boolean) => void; onSave: (name: string, role: string) => Promise<void> }) {
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => { if (participant) { setName(participant.name); setRole(participant.role) } }, [participant])
  const save = async () => { if (!name.trim() || !role.trim()) return; setSaving(true); try { await onSave(name.trim(), role.trim()); onOpenChange(false) } finally { setSaving(false) } }
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>Изменить участника</DialogTitle><DialogDescription>Имя обновится в транскрипте и связанных поручениях.</DialogDescription></DialogHeader><div className="space-y-4 py-2"><div className="space-y-2"><Label>Имя и фамилия</Label><Input value={name} onChange={(event) => setName(event.target.value)} /></div><div className="space-y-2"><Label>Должность</Label><Input value={role} onChange={(event) => setRole(event.target.value)} /></div></div><DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Отмена</Button><Button onClick={save} disabled={saving || !name.trim() || !role.trim()}>{saving && <Loader2 className="h-4 w-4 animate-spin" />}Сохранить</Button></DialogFooter></DialogContent></Dialog>
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

  useEffect(() => {
    let active = true
    let timer: number | undefined
    const load = async () => {
      try {
        const data = await getMeeting(id)
        if (!active) return
        setMeeting(data)
        if (data && processingStatuses.has(data.status)) timer = window.setTimeout(load, 2000)
      } finally { if (active) setLoading(false) }
    }
    load()
    return () => { active = false; if (timer) window.clearTimeout(timer) }
  }, [id])

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
    setMeeting({ ...meeting, action_items: meeting.action_items.map((item) => item.id === action.id ? { ...item, ...patch } : item) })
    try { await updateActionItem(meeting.id, action.id, patch) } catch { toast('Не удалось сохранить изменение') }
  }
  const removeAction = async (action: ActionItem) => {
    if (!meeting) return
    await deleteActionItem(meeting.id, action.id)
    setMeeting({ ...meeting, action_items: meeting.action_items.filter((item) => item.id !== action.id) })
    toast('Поручение удалено', 'Удалённый дубль не попадёт в протокол.')
  }
  const saveParticipant = async (name: string, role: string) => {
    if (!meeting || !editing) return
    const updated = await updateParticipant(meeting.id, editing.speaker_label, { name, role })
    setMeeting(updated)
    toast('Данные участника обновлены', 'Изменения применены к транскрипту и поручениям.')
  }
  const downloadProtocol = async () => {
    if (!meeting) return
    setDownloading(true)
    try { await exportMeetingDocx(meeting.id); toast('Протокол сформирован', 'Файл DOCX сохранён на устройство.') }
    catch (reason) { toast('Не удалось скачать протокол', reason instanceof Error ? reason.message : undefined) }
    finally { setDownloading(false) }
  }

  if (loading) return <div className="td-page td-page-wide space-y-5"><div className="h-8 w-64 animate-pulse rounded bg-[#eee]" /><div className="h-28 animate-pulse rounded bg-[#f5f5f5]" /><div className="h-52 animate-pulse rounded bg-[#f5f5f5]" /></div>
  if (!meeting) return <div className="td-page td-page-wide td-empty"><FileText className="mx-auto mb-4 h-8 w-8 text-[#aaa]" strokeWidth={1.4} /><p className="font-medium">Совещание не найдено</p><Link to="/app" className="mt-4 inline-flex items-center gap-1 text-sm text-[#666] hover:text-[#171717]"><ArrowLeft className="h-4 w-4" />К списку совещаний</Link></div>

  return <div className="td-page td-page-wide">
    <Link to="/app" className="mb-5 inline-flex items-center gap-1.5 text-[13px] text-[#666] hover:text-[#171717]"><ArrowLeft className="h-4 w-4" />Все совещания</Link>
    <header className="td-protocol-heading">
      <div className="min-w-0">
        <div className="mb-2 flex flex-wrap items-center gap-2"><Badge variant={reviewComplete ? 'success' : meeting.status === 'failed' || meeting.status === 'error' ? 'danger' : 'warning'}>{reviewComplete ? 'Проверено' : meetingStatusLabels[meeting.status] ?? meeting.status}</Badge><span className="text-xs text-[#777]">{formatDate(meeting.date, true)}</span></div>
        <h1 className="page-title">{meeting.title}</h1>
      </div>
      <Button variant="outline" onClick={downloadProtocol} disabled={!reviewComplete || downloading}>{downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}Скачать DOCX</Button>
    </header>

    {processingStatuses.has(meeting.status) && <ProcessingProgress step={processingStep} />}
    {isReady && <div className="td-inline-alert"><CheckCircle2 className="h-4 w-4 shrink-0" />Проверь участников, исходный текст и каждое поручение перед использованием.</div>}
    {(meeting.warnings ?? []).map((warning) => <div key={warning} className="td-inline-alert">{warning}</div>)}
    {(meeting.status === 'failed' || meeting.status === 'error') && <div className="td-inline-alert" role="alert">Обработка завершилась с ошибкой: {meeting.error_message ?? 'повторите загрузку или обратитесь к администратору.'}</div>}

    <section className="td-section">
      <div className="td-section-head"><h2 className="section-title">Участники <span className="ml-1 text-sm font-normal text-[#888]">{meeting.participants.length}</span></h2></div>
      <div className="td-participant-list">
        {meeting.participants.map((participant, index) => <div key={participant.speaker_label} className="td-participant-row">
          <span className={`td-initials ${speakerStyles[index % speakerStyles.length]}`}>{participant.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{participant.name}</p><p className="mt-0.5 text-xs text-[#777]">{participant.role}{participant.auto_detected ? ' · определено автоматически' : ''}</p></div>
          <Button size="icon" variant="ghost" aria-label={`Изменить ${participant.name}`} title="Изменить участника" onClick={() => setEditing(participant)}><Pencil className="h-4 w-4" /></Button>
        </div>)}
      </div>
    </section>

    <section className="td-section">
      <div className="td-section-head"><h2 className="section-title">Краткое содержание</h2></div>
      <p className="td-summary-text">{meeting.summary || 'Краткое содержание появится после обработки записи.'}</p>
      <p className="mt-3 flex items-center gap-1.5 text-xs text-[#777]"><Bot className="h-3.5 w-3.5" />Сформировано по транскрипции · проверь перед использованием</p>
    </section>

    <section className="td-section">
      <div className="td-section-head"><h2 className="section-title">Поручения <span className="ml-1 text-sm font-normal text-[#888]">{meeting.action_items.length}</span></h2></div>
      <div className="td-action-list">
        {meeting.action_items.map((action, index) => <article key={action.id} className="td-action-row">
          <span className="td-action-index">{String(index + 1).padStart(2, '0')}</span>
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">{action.needs_review && <Badge variant="secondary">Требует проверки</Badge>}{action.source_segment_ids?.length ? <span className="text-[11px] text-[#777]">Источников: {action.source_segment_ids.length}</span> : null}</div>
            <Input aria-label="Текст поручения" value={action.task} className="td-action-input" onChange={(event) => setMeeting({ ...meeting, action_items: meeting.action_items.map((item) => item.id === action.id ? { ...item, task: event.target.value } : item) })} onBlur={(event) => updateLocalAction(action, { task: event.target.value })} />
            <button onClick={() => jumpToTranscript(action.timestamp)} className="mt-2 flex max-w-2xl items-start gap-1.5 text-left text-xs leading-5 text-[#666] hover:text-[#171717]"><Quote className="mt-0.5 h-3 w-3 shrink-0" />«{action.quote}» · {formatTime(action.timestamp)}</button>

            <div className="td-action-fields">
              <label><span>Ответственный</span><Select value={action.assignee ?? undefined} onValueChange={(value) => { const selected = meeting.participants.find((p) => p.name === value); updateLocalAction(action, { assignee: value, speaker_label: selected?.speaker_label ?? action.speaker_label }) }}><SelectTrigger><SelectValue placeholder="Не определён" /></SelectTrigger><SelectContent>{meeting.participants.map((p) => <SelectItem key={p.speaker_label} value={p.name}>{p.name}</SelectItem>)}</SelectContent></Select></label>
              <label><span>Срок</span><Input type="date" value={action.deadline_date ?? ''} onChange={(event) => updateLocalAction(action, { deadline_date: event.target.value || null })} /></label>
              <label><span>Статус</span><Select value={action.status} onValueChange={(value: ActionItem['status']) => updateLocalAction(action, { status: value })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="in_progress">В работе</SelectItem><SelectItem value="done">Выполнено</SelectItem></SelectContent></Select></label>
              <label><span>Срочность</span><Select value={action.urgency} onValueChange={(value: ActionItem['urgency']) => updateLocalAction(action, { urgency: value })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{Object.entries(urgencyLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></label>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              {action.needs_review ? <Button size="sm" disabled={!action.assignee || !action.deadline_date} onClick={() => updateLocalAction(action, { needs_review: false })}><Check className="h-3.5 w-3.5" />Подтвердить поручение</Button> : <span className="text-xs text-[#777]">Проверено</span>}
              <Button size="icon" variant="ghost" aria-label="Удалить поручение" title="Удалить поручение" onClick={() => removeAction(action)}><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        </article>)}
        {meeting.action_items.length === 0 && <p className="border-t border-[#e7e7e7] py-5 text-sm text-[#777]">Поручения не найдены.</p>}
      </div>
    </section>

    <section className="td-section">
      <div className="td-section-head"><h2 className="section-title">Транскрипт <span className="ml-1 text-sm font-normal text-[#888]">{meeting.segments.length} реплик</span></h2></div>
      <div className="td-transcript-list">
        {meeting.segments.map((segment) => {
          const participant = participantByLabel.get(segment.speaker_label ?? '')
          const speakerIndex = Math.max(0, meeting.participants.findIndex((p) => p.speaker_label === segment.speaker_label))
          return <article id={`segment-${segment.start}`} key={segment.source_segment_id ?? `${segment.start}-${segment.speaker_label}`} className={`td-transcript-row ${highlighted === segment.start ? 'focus-row' : ''}`}>
            <div className="mb-2 flex flex-wrap items-center gap-2"><span className={`rounded-md border px-2 py-1 text-xs font-medium ${speakerStyles[speakerIndex % speakerStyles.length]}`}>{participant?.name ?? segment.speaker_label ?? 'Говорящий не определён'}</span><button className="flex items-center gap-1 font-mono text-xs text-[#777] hover:text-[#171717]"><Clock3 className="h-3 w-3" />{formatTime(segment.start)}</button><Badge variant="outline" className="text-[10px]">{segment.lang ? langLabels[segment.lang] : '—'}</Badge></div>
            <p className="text-sm leading-7 text-[#333]">{segment.text}</p>
            {segment.suggested_text && segment.suggested_text !== segment.text && <div className="mt-3 border-l-2 border-[#ddd] pl-3 text-sm leading-6 text-[#666]"><span className="mb-1 block text-[11px] text-[#888]">Предложенный вариант</span>{segment.suggested_text}</div>}
          </article>
        })}
      </div>
    </section>
    <div className="mt-8 flex items-center justify-between border-t border-[#e7e7e7] pt-5 text-xs text-[#888]"><span>TaldauAI · Протокол совещания</span><span>{formatDate(meeting.date, true)}</span></div>
    <ParticipantEditor participant={editing} open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)} onSave={saveParticipant} />
  </div>
}
