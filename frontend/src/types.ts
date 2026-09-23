export interface Segment {
  start: number
  end: number
  speaker_label: string
  text: string
  lang: 'ru' | 'kk' | 'mixed'
}

export interface Participant {
  speaker_label: string
  name: string
  role: string
  auto_detected: boolean
}

export interface ActionItem {
  id: string
  meeting_id: string
  task: string
  assignee: string
  speaker_label: string
  deadline_raw: string
  deadline_date: string | null
  status: 'in_progress' | 'done'
  urgency: 'high' | 'medium' | 'low'
  quote: string
  timestamp: number
  reminded_at: string | null
}

export interface Meeting {
  id: string
  title: string
  date: string
  status: string
  summary: string
  participants: Participant[]
  segments: Segment[]
  action_items: ActionItem[]
}

export type NewMeetingInput = {
  title: string
  date: string
  source: 'upload' | 'recording'
  fileName?: string
}
