export interface Segment {
  source_segment_id?: string | null
  start: number
  end: number
  speaker_label: string
  text: string
  suggested_text?: string | null
  lang: 'ru' | 'kk' | 'mixed'
}

export interface Participant {
  id?: number
  speaker_label: string
  name: string
  role: string
  auto_detected: boolean
}

export interface ActionItem {
  id: string
  meeting_id: string
  source_task_id?: string | null
  task: string
  assignee: string
  speaker_label: string
  assigner_speaker_label?: string | null
  deadline_raw: string
  deadline_date: string | null
  status: 'in_progress' | 'done'
  urgency: 'high' | 'medium' | 'low'
  quote: string
  timestamp: number
  needs_review?: boolean
  source_segment_ids?: string[]
  reminded_at: string | null
}

export interface Meeting {
  id: string
  title: string
  date: string
  status: string
  summary: string
  warnings?: string[]
  error_message?: string | null
  num_speakers?: number | null
  participants: Participant[]
  segments: Segment[]
  action_items: ActionItem[]
}

export type NewMeetingInput = {
  title: string
  date: string
  source: 'upload' | 'recording'
  fileName?: string
  file?: Blob
  consent_confirmed: boolean
  num_speakers?: number
}
