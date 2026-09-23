import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CircleStop, FileAudio, Loader2, Mic, Pause, Play, RotateCcw, ShieldCheck, UploadCloud } from 'lucide-react'
import { createMeeting } from '@/api'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/components/ui/toast'
import { cn } from '@/lib/utils'

type RecorderState = 'idle' | 'recording' | 'paused' | 'stopped'

function Recorder({ onReady }: { onReady: (recording: Blob | null) => void }) {
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
        onReady(blob)
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
    setAudioUrl(null); setSeconds(0); setState('idle'); onReady(null)
  }

  const time = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  return <div className="td-record-panel">
    <div className="mb-4 flex flex-col items-center">
      <p className="mb-3 flex items-center gap-2 text-xs text-[#777]">{state === 'recording' && <span className="recording-indicator" />}{state === 'recording' ? 'Идёт запись' : state === 'paused' ? 'Запись на паузе' : state === 'stopped' ? 'Запись завершена' : 'Микрофон готов'}</p>
      <p className="font-mono text-[29px] font-normal tabular-nums text-[#171717]">{time}</p>
    </div>
    <div className="mb-5 flex h-10 items-center justify-center gap-1.5" role="img" aria-label="Уровень звука">
      {Array.from({ length: 24 }, (_, index) => { const threshold = (index % 11) / 14; const active = state === 'recording' && level > threshold; return <span key={index} className={cn('w-1 rounded-full transition-all sm:w-1.5', active ? 'bg-[#555]' : 'bg-[#dedede]')} style={{ height: `${active ? 16 + level * ((index * 7) % 24 + 8) : 12 + ((index * 7) % 17)}px` }} /> })}
    </div>
    <div className="flex flex-wrap justify-center gap-2">
      {state === 'idle' && <Button type="button" onClick={start}><Mic className="h-4 w-4" />Начать запись</Button>}
      {(state === 'recording' || state === 'paused') && <><Button type="button" variant="outline" onClick={togglePause}>{state === 'paused' ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}{state === 'paused' ? 'Продолжить' : 'Пауза'}</Button><Button type="button" variant="destructive" onClick={stop}><CircleStop className="h-4 w-4" />Остановить</Button></>}
      {state === 'stopped' && <Button type="button" variant="outline" onClick={reset}><RotateCcw className="h-4 w-4" />Записать заново</Button>}
    </div>
    {audioUrl && <div className="mt-5 w-full border-t border-[#e7e7e7] pt-4"><Label className="mb-2 block text-xs text-[#777]">Прослушивание перед отправкой</Label><audio className="h-10 w-full" controls src={audioUrl} /></div>}
    {error && <p className="mt-4 rounded-md border border-[#ddd] bg-white p-3 text-sm text-[#444]">{error}</p>}
  </div>
}

export function NewMeetingPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => {
    const now = new Date()
    return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
  })
  const [tab, setTab] = useState('upload')
  const [file, setFile] = useState<File | null>(null)
  const [recording, setRecording] = useState<Blob | null>(null)
  const [consent, setConsent] = useState(false)
  const [numSpeakers, setNumSpeakers] = useState('')
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const pickFile = (candidate?: File) => {
    if (!candidate) return
    if (!candidate.type.startsWith('audio/') && !candidate.type.startsWith('video/')) return
    setFile(candidate)
  }
  const sourceReady = tab === 'upload' ? Boolean(file) : Boolean(recording)
  const canSubmit = title.trim() && date && consent && sourceReady && !submitting
  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    try {
      const source = tab === 'upload' ? 'upload' : 'recording'
      const payload = source === 'upload' ? file : recording
      const meeting = await createMeeting({ title: title.trim(), date, source, fileName: file?.name ?? 'recording.webm', file: payload ?? undefined, consent_confirmed: consent, num_speakers: numSpeakers ? Number(numSpeakers) : undefined })
      navigate(`/meetings/${meeting.id}`)
    } catch (reason) {
      toast('Не удалось создать совещание', reason instanceof Error ? reason.message : 'Повторите попытку')
    } finally { setSubmitting(false) }
  }

  return <div className="td-page td-page-new">
    <header className="mb-8 text-center">
      <h1 className="page-title">Новое совещание</h1>
      <p className="td-page-subtitle mx-auto max-w-[520px]">Загрузи запись или запиши встречу с микрофона, чтобы подготовить протокол.</p>
    </header>
    <div className="space-y-6">
      <div className="td-field-grid">
        <div className="td-field"><Label htmlFor="meeting-title">Название совещания</Label><Input id="meeting-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Например, Оперативное совещание" /></div>
        <div className="td-field"><Label htmlFor="meeting-date">Дата</Label><Input id="meeting-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></div>
      </div>
      <div className="td-field max-w-xs"><Label htmlFor="num-speakers">Количество говорящих <span className="font-normal text-[#777]">(необязательно)</span></Label><Input id="num-speakers" type="number" min="1" max="32" value={numSpeakers} onChange={(event) => setNumSpeakers(event.target.value)} placeholder="Например, 2" /><p className="td-field-hint">Подсказка для разделения голосов.</p></div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid h-10 w-full grid-cols-2 rounded-[10px] bg-[#f0f0f0] p-1"><TabsTrigger value="upload" className="rounded-[8px] text-[13px] text-[#777] data-[state=active]:bg-white data-[state=active]:text-[#171717] data-[state=active]:shadow-sm"><UploadCloud className="mr-2 h-4 w-4" />Загрузить файл</TabsTrigger><TabsTrigger value="record" className="rounded-[8px] text-[13px] text-[#777] data-[state=active]:bg-white data-[state=active]:text-[#171717] data-[state=active]:shadow-sm"><Mic className="mr-2 h-4 w-4" />Записать сейчас</TabsTrigger></TabsList>
        <TabsContent value="upload">
          <button type="button" onClick={() => fileInput.current?.click()} onDragEnter={(event) => { event.preventDefault(); setDragging(true) }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); pickFile(event.dataTransfer.files[0]) }} className={cn('td-dropzone', dragging && 'td-dropzone-active', file && 'td-dropzone-selected')}>
            <span className="mb-4 grid h-11 w-11 place-items-center rounded-[13px] bg-[#f1f1f1]">{file ? <FileAudio className="h-6 w-6 text-[#555]" strokeWidth={1.5} /> : <UploadCloud className="h-6 w-6 text-[#555]" strokeWidth={1.5} />}</span>
            {file ? <><span className="max-w-full overflow-hidden text-ellipsis font-medium text-[#171717]">{file.name}</span><span className="mt-1 text-xs text-[#777]">{(file.size / 1024 / 1024).toFixed(1)} МБ · нажми, чтобы заменить</span></> : <><span className="font-medium text-[#333]">Перетащи аудио или видео сюда</span><span className="mt-1 text-sm text-[#777]">или нажми, чтобы выбрать файл</span><span className="mt-3 text-[11px] text-[#888]">MP3, WAV, M4A, MP4, WEBM</span></>}
          </button>
          <input ref={fileInput} type="file" accept="audio/*,video/*" className="hidden" onChange={(event) => pickFile(event.target.files?.[0])} />
        </TabsContent>
        <TabsContent value="record"><Recorder onReady={setRecording} /></TabsContent>
      </Tabs>

      <div className="td-consent-row">
        <Checkbox id="consent" checked={consent} onCheckedChange={(checked) => setConsent(checked === true)} />
        <div><Label htmlFor="consent" className="cursor-pointer leading-5 text-[#333]">Участники предупреждены о записи и обработке речи с помощью ИИ.</Label><p className="mt-1 flex items-center gap-1.5 text-xs text-[#777]"><ShieldCheck className="h-3.5 w-3.5" />Согласие обязательно перед началом обработки.</p></div>
      </div>
      <div className="flex justify-end border-t border-[#e7e7e7] pt-5"><Button size="lg" className="w-full sm:w-auto" disabled={!canSubmit} onClick={submit}>{submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileAudio className="h-4 w-4" />}{submitting ? 'Создаём совещание…' : 'Отправить на обработку'}</Button></div>
    </div>
  </div>
}
