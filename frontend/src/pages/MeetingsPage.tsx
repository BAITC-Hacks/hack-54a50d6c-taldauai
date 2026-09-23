import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CalendarDays, Clock3, FileAudio, Mic, Search, Upload } from 'lucide-react'
import { getMeetings } from '@/api'
import type { Meeting } from '@/types'
import { formatDate } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const statusLabels: Record<string, string> = {
  done: 'Черновик готов', converting: 'Конвертация', transcribing: 'Распознавание речи',
  diarizing: 'Разделение говорящих', extracting: 'Извлечение поручений',
  failed: 'Ошибка обработки', error: 'Ошибка обработки',
}

export function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    let active = true
    getMeetings().then((items) => { if (active) setMeetings(items) })
      .catch((reason: unknown) => { if (active) setLoadError(reason instanceof Error ? reason.message : 'Не удалось загрузить совещания') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const filtered = useMemo(() => meetings.filter((meeting) => meeting.title.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())), [meetings, query])

  return <div className="td-page">
    <header className="td-page-heading">
      <div className="min-w-0">
        <h1 className="page-title">Совещания</h1>
        <p className="td-page-subtitle">Протоколы, записи и поручения команды</p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Link to="/new"><Button variant="outline"><Upload className="h-4 w-4" /><span className="hidden sm:inline">Загрузить запись</span><span className="sm:hidden">Загрузить</span></Button></Link>
        <Link to="/live"><Button><Mic className="h-4 w-4" /><span className="hidden sm:inline">Запустить ассистента</span><span className="sm:hidden">Ассистент</span></Button></Link>
      </div>
    </header>

    <section aria-labelledby="meetings-heading">
      <div className="td-section-head">
        <h2 id="meetings-heading" className="text-base font-semibold">Недавние совещания</h2>
        <span className="text-xs text-[#858585]">{meetings.length} всего</span>
      </div>
      <div className="td-toolbar">
        <label className="td-search">
          <Search className="h-4 w-4 shrink-0" />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти совещание" aria-label="Найти совещание" />
        </label>
        {query && <button type="button" onClick={() => setQuery('')} className="text-xs text-[#707070] underline-offset-4 hover:underline">Очистить поиск</button>}
      </div>

      <div>
        {loading && [1, 2, 3].map((item) => <div key={item} className="flex h-[76px] items-center gap-4 border-b border-[#e7e7e7] first:border-t"><div className="h-5 w-5 animate-pulse rounded bg-[#eee]" /><div className="space-y-2"><div className="h-3 w-48 animate-pulse rounded bg-[#eee]" /><div className="h-3 w-28 animate-pulse rounded bg-[#f3f3f3]" /></div></div>)}
        {!loading && loadError && <div className="border-y border-[#e7e7e7] py-5 text-sm text-[#555]" role="alert">Не удалось загрузить совещания: {loadError}</div>}
        {!loading && !loadError && filtered.length === 0 && <div className="td-empty">
          <FileAudio className="mx-auto mb-4 h-8 w-8 text-[#aaa]" strokeWidth={1.4} />
          <h3 className="text-[17px] font-medium">{query ? 'Ничего не найдено' : 'Здесь пока пусто'}</h3>
          <p className="mb-5 mt-2 text-[13px] leading-7 text-[#777]">{query ? 'Попробуй изменить запрос.' : 'Создай первое совещание: запусти ассистента или загрузи готовую запись.'}</p>
          {!query && <Link to="/live"><Button><Mic className="h-4 w-4" />Запустить ассистента</Button></Link>}
        </div>}
        {!loading && !loadError && filtered.map((meeting) => {
          const complete = meeting.status === 'done' || meeting.status === 'Протокол готов'
          const failed = meeting.status === 'failed' || meeting.status === 'error'
          return <Link to={`/meetings/${meeting.id}`} key={meeting.id} className="td-meeting-row group">
            <FileAudio className="h-5 w-5 shrink-0 text-[#858585]" strokeWidth={1.6} />
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                <h3 className="truncate text-sm font-medium text-[#252525]">{meeting.title}</h3>
                <Badge variant={failed ? 'danger' : 'secondary'}>{complete ? 'Черновик готов' : statusLabels[meeting.status] ?? meeting.status}</Badge>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#858585]">
                <span className="flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{formatDate(meeting.date, true)}</span>
                <span>{meeting.participants.length} участников</span>
                <span>{meeting.segments.length} реплик</span>
                <span className="flex items-center gap-1"><Clock3 className="h-3.5 w-3.5" />{meeting.action_items.length} поручений</span>
              </div>
            </div>
            <ArrowRight className="row-arrow h-4 w-4 shrink-0 text-[#b4b4b4] transition-transform group-hover:translate-x-0.5 group-hover:text-[#555]" />
          </Link>
        })}
      </div>
    </section>
  </div>
}
