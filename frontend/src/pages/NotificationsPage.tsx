import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getNotifications, readNotification, type Notification } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([])
  const [error, setError] = useState('')
  const [assignee, setAssignee] = useState('')
  useEffect(() => {
    let active = true
    const load = async () => {
      try { const data = await getNotifications(); if (active) { setItems(data); setError('') } }
      catch { if (active) setError('Не удалось загрузить напоминания') }
    }
    void load()
    const timer = window.setInterval(load, 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  const markRead = async (id: number) => {
    try { await readNotification(id); setItems(await getNotifications()) }
    catch { setError('Не удалось сохранить отметку о прочтении') }
  }
  return <div className="space-y-5"><h1 className="page-title">Напоминания</h1>
    <p>Автоматические напоминания ответственным за два дня до срока и при просрочке. Общий локальный журнал; обновляется каждые 15 секунд.</p>
    <Input aria-label="Поиск ответственного" placeholder="Имя ответственного или отдел" value={assignee} onChange={e => setAssignee(e.target.value)} />
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!error && !items.length && <p>Актуальных напоминаний пока нет.</p>}
    {items.filter(n => n.assignee.toLowerCase().includes(assignee.toLowerCase())).map(n => <article key={n.id} className="space-y-3 rounded-lg border bg-white p-5"><p className={n.read_at ? 'text-slate-500' : 'font-semibold'}>{n.message}</p><div className="flex items-center gap-4"><Link className="text-teal-700" to={`/meetings/${n.meeting_id}`}>Открыть совещание</Link>{n.read_at ? <span>Прочитано</span> : <Button variant="outline" onClick={() => markRead(n.id)}>Прочитано</Button>}</div></article>)}
  </div>
}
