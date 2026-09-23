import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarDays, CircleStop, FileAudio, Loader2, Mic, Pause, Play, RotateCcw, ShieldCheck, UploadCloud } from 'lucide-react'
import { createMeeting } from '@/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

type RecorderState = 'idle' | 'recording' | 'paused' | 'stopped'

function Recorder({ onReady }: { onReady: (ready: boolean) => void }) {
  const [state, setState] = useState<RecorderState>('idle')
  const [seconds, setSeconds] = useState(0)
  const [level, setLevel] = useState(0)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [error, setError] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const animationRef = useRef<number>(0)

  useEffect(() => {
    if (state !== 'recording') return
    const interval = window.setInterval(() => setSeconds((value) => value + 1), 1000)
    return () => window.clearInterval(interval)
  }, [state])

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    if (animationRef.current) cancelAnimationFrame(animationRef.current)
    if (audioUrl) URL.revokeObjectURL(audioUrl)
  }, [audioUrl])

  const start = async () => {
    setError('')
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Браузер не поддерживает запись')
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        const url = URL.createObjectURL(blob)
        setAudioUrl(url)
        onReady(true)
      }
      const context = new AudioContext()
      const analyser = context.createAnalyser()
      analyser.fftSize = 64
      context.createMediaStreamSource(stream).connect(analyser)
      const values = new Uint8Array(analyser.frequencyBinCount)
      const draw = () => {
        analyser.getByteFrequencyData(values)
        setLevel(values.reduce((sum, value) => sum + value, 0) / values.length / 255)
        animationRef.current = requestAnimationFrame(draw)
      }
      draw()
      recorder.start(250)
      setSeconds(0)
      setState('recording')
    } catch (reason) {
      setError(reason instanceof Error && reason.message === 'Браузер не поддерживает запись' ? reason.message : 'Не удалось получить доступ к микрофону. Проверьте разрешение браузера.')
    }
  }

  const togglePause = () => {
    const recorder = recorderRef.current
    if (!recorder) return
    if (state === 'recording') { recorder.pause(); setState('paused') }
    else if (state === 'paused') { recorder.resume(); setState('recording') }
  }

  const stop = () => {
    recorderRef.current?.stop()
    streamRef.current?.getTracks().forEach((track) => track.stop())
    if (animationRef.current) cancelAnimationFrame(animationRef.current)
    setLevel(0)
    setState('stopped')
  }

  const reset = () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(null); setSeconds(0); setState('idle'); onReady(false)
  }

  const time = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  return <div className="rounded-lg border bg-slate-50 p-5">
    <div className="mb-5 flex flex-col items-center">
      <div className={cn('mb-3 flex h-16 w-16 items-center justify-center rounded-full transition-colors', state === 'recording' ? 'bg-red-100 text-red-600 ring-8 ring-red-50' : 'bg-slate-200 text-slate-600')}><Mic className="h-7 w-7" /></div>
      <p className="font-mono text-3xl font-semibold tabular-nums text-slate-900">{time}</p>
      <p className="mt-1 text-xs text-muted-foreground">{state === 'recording' ? 'Идёт запись' : state === 'paused' ? 'Запись приостановлена' : state === 'stopped' ? 'Запись завершена' : 'Микрофон готов'}</p>
    </div>
    <div className="mb-5 flex h-12 items-end justify-center gap-1 rounded-md border bg-white px-4 py-2" aria-label="Уровень звука">
      {Array.from({ length: 22 }, (_, index) => { const threshold = (index % 11) / 14; const active = state === 'recording' && level > threshold; return <span key={index} className={cn('w-1.5 rounded-full transition-all', active ? 'bg-teal-500' : 'bg-slate-200')} style={{ height: `${20 + ((index * 7) % 25)}px` }} /> })}
    </div>
    <div className="flex flex-wrap justify-center gap-2">
      {state === 'idle' && <Button type="button" onClick={start}><Mic className="h-4 w-4" />Начать запись</Button>}
      {(state === 'recording' || state === 'paused') && <><Button type="button" variant="outline" onClick={togglePause}>{state === 'paused' ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}{state === 'paused' ? 'Продолжить' : 'Пауза'}</Button><Button type="button" variant="destructive" onClick={stop}><CircleStop className="h-4 w-4" />Остановить</Button></>}
      {state === 'stopped' && <Button type="button" variant="outline" onClick={reset}><RotateCcw className="h-4 w-4" />Записать заново</Button>}
    </div>
    {audioUrl && <div className="mt-5 border-t pt-4"><Label className="mb-2 block">Прослушивание перед отправкой</Label><audio className="h-10 w-full" controls src={audioUrl} /></div>}
    {error && <p className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
  </div>
}

export function NewMeetingPage() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [tab, setTab] = useState('upload')
  const [file, setFile] = useState<File | null>(null)
  const [recordingReady, setRecordingReady] = useState(false)
  const [consent, setConsent] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const pickFile = (candidate?: File) => {
    if (!candidate) return
    if (!candidate.type.startsWith('audio/') && !candidate.type.startsWith('video/')) return
    setFile(candidate)
  }
  const sourceReady = tab === 'upload' ? Boolean(file) : recordingReady
  const canSubmit = title.trim() && date && consent && sourceReady && !submitting
  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    try {
      const meeting = await createMeeting({ title: title.trim(), date, source: tab === 'upload' ? 'upload' : 'recording', fileName: file?.name })
      navigate(`/meetings/${meeting.id}`)
    } finally { setSubmitting(false) }
  }

  return <div className="mx-auto max-w-4xl space-y-6">
    <div><p className="mb-2 text-xs font-semibold uppercase tracking-[.16em] text-teal-700">Создание протокола</p><h1 className="page-title">Новое совещание</h1><p className="mt-2 text-sm text-muted-foreground">Загрузите запись или зафиксируйте совещание с микрофона</p></div>
    <Card><CardContent className="space-y-6 p-5 sm:p-7">
      <div className="grid gap-5 sm:grid-cols-[1fr_210px]">
        <div className="space-y-2"><Label htmlFor="meeting-title">Название совещания</Label><Input id="meeting-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Например, Оперативное совещание" /></div>
        <div className="space-y-2"><Label htmlFor="meeting-date">Дата</Label><div className="relative"><CalendarDays className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input id="meeting-date" type="date" className="pl-9" value={date} onChange={(event) => setDate(event.target.value)} /></div></div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid w-full grid-cols-2"><TabsTrigger value="upload"><UploadCloud className="mr-2 h-4 w-4" />Загрузить файл</TabsTrigger><TabsTrigger value="record"><Mic className="mr-2 h-4 w-4" />Записать сейчас</TabsTrigger></TabsList>
        <TabsContent value="upload">
          <button type="button" onClick={() => fileInput.current?.click()} onDragEnter={(event) => { event.preventDefault(); setDragging(true) }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); pickFile(event.dataTransfer.files[0]) }} className={cn('flex min-h-56 w-full flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors', dragging ? 'border-teal-500 bg-teal-50' : file ? 'border-emerald-400 bg-emerald-50/50' : 'border-slate-300 bg-slate-50 hover:border-teal-400 hover:bg-teal-50/40')}>
            <span className="mb-4 rounded-full bg-white p-3 shadow-sm">{file ? <FileAudio className="h-7 w-7 text-emerald-600" /> : <UploadCloud className="h-7 w-7 text-teal-700" />}</span>
            {file ? <><span className="max-w-full truncate font-medium text-slate-900">{file.name}</span><span className="mt-1 text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(1)} МБ · нажмите, чтобы заменить</span></> : <><span className="font-medium text-slate-900">Перетащите аудио или видео сюда</span><span className="mt-1 text-sm text-muted-foreground">или нажмите для выбора файла</span><span className="mt-4 text-xs text-muted-foreground">MP3, WAV, M4A, MP4, WEBM</span></>}
          </button>
          <input ref={fileInput} type="file" accept="audio/*,video/*" className="hidden" onChange={(event) => pickFile(event.target.files?.[0])} />
        </TabsContent>
        <TabsContent value="record"><Recorder onReady={setRecordingReady} /></TabsContent>
      </Tabs>

      <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50/70 p-4">
        <Checkbox id="consent" checked={consent} onCheckedChange={(checked) => setConsent(checked === true)} />
        <div><Label htmlFor="consent" className="cursor-pointer leading-5 text-slate-900">Участники уведомлены, что ведётся запись и транскрибация с помощью ИИ</Label><p className="mt-1 flex items-center gap-1.5 text-xs text-blue-700"><ShieldCheck className="h-3.5 w-3.5" />Подтверждение обязательно для начала обработки</p></div>
      </div>
      <div className="flex justify-end"><Button size="lg" disabled={!canSubmit} onClick={submit}>{submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileAudio className="h-4 w-4" />}{submitting ? 'Создаём совещание…' : 'Отправить на обработку'}</Button></div>
    </CardContent></Card>
  </div>
}
