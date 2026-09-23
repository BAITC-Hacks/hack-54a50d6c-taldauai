import { initialMeetings } from './mocks'
import type { ActionItem, Meeting, NewMeetingInput, Participant } from './types'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'
const STORAGE_KEY = 'taldauai-meetings-v2'
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T

function loadMockMeetings(): Meeting[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) as Meeting[] : clone(initialMeetings)
  } catch { return clone(initialMeetings) }
}

let mockMeetings = loadMockMeetings()

function persistMocks() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(mockMeetings)) } catch { /* закрытый режим браузера */ }
}

function mockWait<T>(value: T): Promise<T> {
  return new Promise((resolve) => window.setTimeout(() => resolve(clone(value)), 300 + Math.floor(Math.random() * 501)))
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let message = `Ошибка API: ${response.status}`
    try { const detail = (await response.json()).detail; message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join('; ') : message } catch { /* ответ без JSON */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export async function getMeetings(): Promise<Meeting[]> {
  return USE_MOCKS ? mockWait(mockMeetings) : apiFetch<Meeting[]>('/api/meetings')
}

export async function getMeeting(id: string): Promise<Meeting | null> {
  if (!USE_MOCKS) {
    const response = await fetch(`/api/meetings/${encodeURIComponent(id)}`)
    if (response.status === 404) return null
    if (!response.ok) throw new Error(`Ошибка API: ${response.status}`)
    return response.json() as Promise<Meeting>
  }
  const meeting = mockMeetings.find((item) => item.id === id)
  if (!meeting) return mockWait(null)
  const result = clone(meeting)
  const stages = ['converting', 'transcribing', 'diarizing', 'extracting', 'done']
  const index = stages.indexOf(meeting.status)
  if (index >= 0 && index < stages.length - 1) {
    meeting.status = stages[index + 1]
    if (meeting.status === 'done' && !meeting.summary) {
      meeting.summary = 'На совещании рассмотрены текущие вопросы исполнения планов. Система выделила ключевые решения и поручения для дальнейшего контроля.'
    }
    persistMocks()
  }
  return mockWait(result)
}

export async function getAllActionItems(): Promise<Array<ActionItem & { meeting_title: string; state?: string }>> {
  if (!USE_MOCKS) return apiFetch('/api/action-items')
  return mockWait(mockMeetings.flatMap((meeting) => meeting.action_items.map((item) => ({ ...item, meeting_title: meeting.title }))))
}

export async function createMeeting(input: NewMeetingInput): Promise<Meeting> {
  if (!USE_MOCKS) {
    if (!input.file) throw new Error('Выберите файл или завершите запись')
    const form = new FormData()
    form.append('file', input.file, input.fileName || (input.source === 'recording' ? 'recording.webm' : 'meeting.bin'))
    form.append('title', input.title)
    form.append('date', input.date)
    form.append('consent_confirmed', String(input.consent_confirmed))
    if (input.num_speakers) form.append('num_speakers', String(input.num_speakers))
    return apiFetch<Meeting>('/api/meetings', { method: 'POST', body: form })
  }
  const id = `meeting-${Date.now()}`
  const meeting: Meeting = {
    id, title: input.title, date: new Date(`${input.date}T09:00:00`).toISOString(), status: 'converting', summary: '',
    participants: [
      { id: Date.now(), speaker_label: 'SPEAKER_00', name: 'Спикер 1', role: 'Должность не определена', auto_detected: true },
      { id: Date.now() + 1, speaker_label: 'SPEAKER_01', name: 'Спикер 2', role: 'Должность не определена', auto_detected: true },
    ],
    segments: [
      { start: 8, end: 25, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Коллеги, обсудим текущий статус задач и зафиксируем решения по итогам совещания.' },
      { start: 28, end: 48, speaker_label: 'SPEAKER_01', lang: 'mixed', text: 'Основные показатели собраны. Қалған мәселелер бойынша ақпаратты ертең дайындаймыз.' },
      { start: 52, end: 70, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Подготовьте итоговую справку в течение недели и направьте её всем участникам.' },
    ],
    action_items: [{ id: `${id}-a1`, meeting_id: id, task: 'Подготовить итоговую справку и направить участникам', assignee: 'Спикер 2', speaker_label: 'SPEAKER_01', deadline_raw: 'в течение недели', deadline_date: new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10), status: 'in_progress', urgency: 'medium', quote: 'Подготовьте итоговую справку и направьте её всем участникам.', timestamp: 52, needs_review: true, source_segment_ids: [], reminded_at: null }],
  }
  mockMeetings = [meeting, ...mockMeetings]
  persistMocks()
  return mockWait(meeting)
}

export async function completeMeetingProcessing(id: string): Promise<Meeting | null> {
  if (!USE_MOCKS) return getMeeting(id)
  const meeting = mockMeetings.find((item) => item.id === id)
  if (!meeting) return mockWait(null)
  meeting.status = 'done'
  meeting.summary ||= 'На совещании рассмотрены текущие вопросы исполнения планов. Система выделила ключевые решения и поручения для дальнейшего контроля.'
  persistMocks()
  return mockWait(meeting)
}

export async function updateParticipant(meetingId: string, speakerLabel: string, patch: Pick<Participant, 'name' | 'role'>): Promise<Meeting> {
  if (!USE_MOCKS) {
    const meeting = await getMeeting(meetingId)
    const participant = meeting?.participants.find((item) => item.speaker_label === speakerLabel)
    if (!participant?.id) throw new Error('Участник не найден')
    await apiFetch(`/api/participants/${participant.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) })
    const updated = await getMeeting(meetingId)
    if (!updated) throw new Error('Совещание не найдено')
    return updated
  }
  const meeting = mockMeetings.find((item) => item.id === meetingId)
  const participant = meeting?.participants.find((item) => item.speaker_label === speakerLabel)
  if (!meeting || !participant) throw new Error('Участник не найден')
  const previousName = participant.name
  Object.assign(participant, patch, { auto_detected: false })
  meeting.action_items.forEach((item) => { if (item.speaker_label === speakerLabel || item.assignee === previousName) { item.assignee = patch.name; item.needs_review = true; item.revision = (item.revision ?? 1) + 1 } })
  persistMocks()
  return mockWait(meeting)
}

export async function updateActionItem(meetingId: string, actionId: string, patch: Partial<Pick<ActionItem, 'task' | 'assignee' | 'speaker_label' | 'deadline_date' | 'status' | 'urgency' | 'needs_review'>> & { expected_revision?: number }): Promise<ActionItem> {
  if (!USE_MOCKS) return apiFetch(`/api/action-items/${encodeURIComponent(actionId)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) })
  const action = mockMeetings.find((item) => item.id === meetingId)?.action_items.find((item) => item.id === actionId)
  if (!action) throw new Error('Поручение не найдено')
  if (patch.expected_revision !== (action.revision ?? 1)) throw new Error('Поручение изменилось. Обновите страницу')
  const reviewChanged = ['task', 'assignee', 'speaker_label', 'deadline_date', 'urgency'].some(key => key in patch && patch[key as keyof typeof patch] !== action[key as keyof ActionItem])
  Object.assign(action, patch)
  if (reviewChanged) action.needs_review = true
  action.revision = (action.revision ?? 1) + 1
  persistMocks()
  return mockWait(action)
}

export async function deleteActionItem(meetingId: string, actionId: string): Promise<void> {
  if (!USE_MOCKS) {
    const response = await fetch(`/api/action-items/${encodeURIComponent(actionId)}`, { method: 'DELETE' })
    if (!response.ok) throw new Error(`Не удалось удалить поручение: ${response.status}`)
    return
  }
  const meeting = mockMeetings.find((item) => item.id === meetingId)
  if (!meeting) throw new Error('Совещание не найдено')
  meeting.action_items = meeting.action_items.filter((item) => item.id !== actionId)
  persistMocks()
}

export async function remindActionItem(meetingId: string, actionId: string): Promise<ActionItem> {
  if (!USE_MOCKS) {
    const result = await apiFetch<{ text: string; action_item: ActionItem }>(`/api/action-items/${encodeURIComponent(actionId)}/remind`, { method: 'POST' })
    return result.action_item
  }
  const action = mockMeetings.find((item) => item.id === meetingId)?.action_items.find((item) => item.id === actionId)
  if (!action) throw new Error('Поручение не найдено')
  action.reminded_at = new Date().toISOString()
  persistMocks()
  return mockWait(action)
}

export async function exportMeetingDocx(meetingId: string): Promise<void> {
  if (USE_MOCKS) throw new Error('Экспорт DOCX доступен при подключённом API')
  const response = await fetch(`/api/meetings/${encodeURIComponent(meetingId)}/export.docx`)
  if (!response.ok) throw new Error(`Не удалось сформировать протокол: ${response.status}`)
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/)?.[1]
  const filename = encodedName ? decodeURIComponent(encodedName) : 'Протокол совещания.docx'
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}


export async function createActionItem(meetingId: string, payload: { task: string; assignee: string | null; speaker_label: string | null; deadline_date: string | null }): Promise<ActionItem> {
  if (USE_MOCKS) throw new Error('Добавление поручений доступно при подключённом API')
  return apiFetch(`/api/meetings/${encodeURIComponent(meetingId)}/action-items`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
}

export interface Notification {
  id: number; meeting_id: string; assignee: string; kind: string; message: string; created_at: string; read_at: string | null
}
export async function getNotifications(): Promise<Notification[]> {
  return USE_MOCKS ? [] : apiFetch('/api/notifications')
}
export async function readNotification(id: number): Promise<void> {
  await apiFetch(`/api/notifications/${id}/read`, { method: 'PATCH' })
}
