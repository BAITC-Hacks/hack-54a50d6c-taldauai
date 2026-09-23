import { initialMeetings } from './mocks'
import type { ActionItem, Meeting, NewMeetingInput, Participant } from './types'

const STORAGE_KEY = 'taldauai-meetings-v1'

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T

function loadMeetings(): Meeting[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) as Meeting[] : clone(initialMeetings)
  } catch {
    return clone(initialMeetings)
  }
}

let meetings = loadMeetings()

function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(meetings)) } catch { /* закрытый режим браузера */ }
}

function wait<T>(value: T): Promise<T> {
  const delay = 300 + Math.floor(Math.random() * 501)
  return new Promise((resolve) => window.setTimeout(() => resolve(clone(value)), delay))
}

export async function getMeetings(): Promise<Meeting[]> {
  return wait(meetings)
}

export async function getMeeting(id: string): Promise<Meeting | null> {
  return wait(meetings.find((meeting) => meeting.id === id) ?? null)
}

export async function getAllActionItems(): Promise<Array<ActionItem & { meeting_title: string }>> {
  return wait(meetings.flatMap((meeting) => meeting.action_items.map((item) => ({ ...item, meeting_title: meeting.title }))))
}

export async function createMeeting(input: NewMeetingInput): Promise<Meeting> {
  const id = `meeting-${Date.now()}`
  const meeting: Meeting = {
    id,
    title: input.title,
    date: new Date(`${input.date}T09:00:00`).toISOString(),
    status: 'Обрабатывается',
    summary: 'На совещании рассмотрены текущие вопросы исполнения планов. Система выделила ключевые решения и поручения для дальнейшего контроля.',
    participants: [
      { speaker_label: 'SPEAKER_00', name: 'Спикер 1', role: 'Должность не определена', auto_detected: true },
      { speaker_label: 'SPEAKER_01', name: 'Спикер 2', role: 'Должность не определена', auto_detected: true },
    ],
    segments: [
      { start: 8, end: 25, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Коллеги, обсудим текущий статус задач и зафиксируем решения по итогам совещания.' },
      { start: 28, end: 48, speaker_label: 'SPEAKER_01', lang: 'mixed', text: 'Основные показатели собраны. Қалған мәселелер бойынша ақпаратты ертең дайындаймыз.' },
      { start: 52, end: 70, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Подготовьте итоговую справку в течение недели и направьте её всем участникам.' },
    ],
    action_items: [
      { id: `${id}-a1`, meeting_id: id, task: 'Подготовить итоговую справку и направить участникам', assignee: 'Спикер 2', speaker_label: 'SPEAKER_01', deadline_raw: 'в течение недели', deadline_date: new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10), status: 'in_progress', urgency: 'medium', quote: 'Подготовьте итоговую справку в течение недели и направьте её всем участникам.', timestamp: 52, reminded_at: null },
    ],
  }
  meetings = [meeting, ...meetings]
  persist()
  return wait(meeting)
}

export async function completeMeetingProcessing(id: string): Promise<Meeting | null> {
  const meeting = meetings.find((item) => item.id === id)
  if (!meeting) return wait(null)
  meeting.status = 'Протокол готов'
  persist()
  return wait(meeting)
}

export async function updateParticipant(meetingId: string, speakerLabel: string, patch: Pick<Participant, 'name' | 'role'>): Promise<Meeting> {
  const meeting = meetings.find((item) => item.id === meetingId)
  if (!meeting) throw new Error('Совещание не найдено')
  const participant = meeting.participants.find((item) => item.speaker_label === speakerLabel)
  if (!participant) throw new Error('Участник не найден')
  const previousName = participant.name
  Object.assign(participant, patch, { auto_detected: false })
  meeting.action_items.forEach((item) => {
    if (item.speaker_label === speakerLabel || item.assignee === previousName) item.assignee = patch.name
  })
  persist()
  return wait(meeting)
}

export async function updateActionItem(meetingId: string, actionId: string, patch: Partial<Pick<ActionItem, 'task' | 'assignee' | 'speaker_label' | 'deadline_date' | 'status' | 'urgency'>>): Promise<ActionItem> {
  const meeting = meetings.find((item) => item.id === meetingId)
  const action = meeting?.action_items.find((item) => item.id === actionId)
  if (!action) throw new Error('Поручение не найдено')
  Object.assign(action, patch)
  persist()
  return wait(action)
}

export async function remindActionItem(meetingId: string, actionId: string): Promise<ActionItem> {
  const meeting = meetings.find((item) => item.id === meetingId)
  const action = meeting?.action_items.find((item) => item.id === actionId)
  if (!action) throw new Error('Поручение не найдено')
  action.reminded_at = new Date().toISOString()
  persist()
  return wait(action)
}
