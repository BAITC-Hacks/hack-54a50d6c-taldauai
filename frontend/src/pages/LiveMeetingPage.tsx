import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AudioLines,
  CalendarDays,
  Check,
  CircleAlert,
  CircleStop,
  Clock3,
  Headphones,
  Loader2,
  Mic,
  Monitor,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Upload,
} from 'lucide-react'
import { createMeeting } from '@/api'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useToast } from '@/components/ui/toast'
import { cn } from '@/lib/utils'

type CaptureMode = 'microphone' | 'tab'
type SessionState = 'setup' | 'recording' | 'paused' | 'review'

type CaptureResources = {
  streams: MediaStream[]
  context: AudioContext
}

const waveformHeights = [18, 28, 22, 34, 24, 39, 29, 18, 32, 23, 40, 27, 19, 36, 25, 31, 20, 38, 24, 17, 34, 27, 41, 22, 31, 19, 37, 25, 33, 18, 29, 39, 23, 32, 20, 36]

function supportedRecorderOptions(): MediaRecorderOptions | undefined {
  const formats = ['audio/webm;codecs=opus', 'audio/mp4']
  const mimeType = formats.find((format) => MediaRecorder.isTypeSupported(format))
  return mimeType ? { mimeType, audioBitsPerSecond: 128_000 } : undefined
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof DOMException && error.name === 'NotAllowedError') {
    return 'Разреши доступ к микрофону и записи вкладки в окне браузера.'
  }
  return error instanceof Error ? error.message : fallback
}

export function LiveMeetingPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => {
    const now = new Date()
    return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
  })
  const [speakerCount, setSpeakerCount] = useState('')
  const [mode, setMode] = useState<CaptureMode>('tab')
  const [sessionState, setSessionState] = useState<SessionState>('setup')
  const [seconds, setSeconds] = useState(0)
  const [level, setLevel] = useState(0)
  const [consent, setConsent] = useState(false)
  const [recording, setRecording] = useState<Blob | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const resourcesRef = useRef<CaptureResources | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const previewUrlRef = useRef<string | null>(null)

  const releaseCapture = useCallback(() => {
    const resources = resourcesRef.current
    resourcesRef.current = null
    resources?.streams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()))
    if (resources && resources.context.state !== 'closed') void resources.context.close()
    analyserRef.current = null
  }, [])

  useEffect(() => {
    if (sessionState !== 'recording') return
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000)
    let frame = 0
    let lastSample = 0
    const data = new Uint8Array(analyserRef.current?.frequencyBinCount ?? 0)
    const sample = (timestamp: number) => {
      const analyser = analyserRef.current
      if (analyser && timestamp - lastSample >= 100) {
        analyser.getByteTimeDomainData(data)
        const energy = data.reduce((sum, value) => sum + Math.abs(value - 128), 0) / Math.max(data.length, 1)
        setLevel(Math.min(1, energy / 45))
        lastSample = timestamp
      }
      frame = requestAnimationFrame(sample)
    }
    sample(performance.now())
    return () => {
      window.clearInterval(timer)
      cancelAnimationFrame(frame)
    }
  }, [sessionState])

  useEffect(() => {
    if (!recording) {
      setPreviewUrl(null)
      previewUrlRef.current = null
      return
    }
    const url = URL.createObjectURL(recording)
    previewUrlRef.current = url
    setPreviewUrl(url)
    return () => {
      URL.revokeObjectURL(url)
      if (previewUrlRef.current === url) previewUrlRef.current = null
    }
  }, [recording])

  useEffect(() => () => {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    releaseCapture()
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
  }, [releaseCapture])

  const stopCapture = () => {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
  }

  const startCapture = async () => {
    setError('')
    setRecording(null)
    setSeconds(0)

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError('Этот браузер не поддерживает запись. Открой страницу в актуальной версии Chrome, Edge или Safari.')
      return
    }
    if (mode === 'tab' && !navigator.mediaDevices.getDisplayMedia) {
      setError('Запись звука вкладки недоступна в этом браузере. Выбери режим «Только микрофон».')
      return
    }

    const microphoneRequest = navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    const tabRequest = mode === 'tab'
      ? navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
      : Promise.resolve(null)

    const [microphoneResult, tabResult] = await Promise.allSettled([microphoneRequest, tabRequest])
    const streams: MediaStream[] = []
    if (microphoneResult.status === 'fulfilled') streams.push(microphoneResult.value)
    if (tabResult.status === 'fulfilled' && tabResult.value) streams.push(tabResult.value)

    if (microphoneResult.status === 'rejected' || tabResult.status === 'rejected') {
      streams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()))
      const denied = microphoneResult.status === 'rejected' ? microphoneResult.reason : tabResult.status === 'rejected' ? tabResult.reason : null
      setError(getErrorMessage(denied, 'Не удалось начать запись. Проверь разрешения браузера.'))
      return
    }

    const microphone = microphoneResult.value
    const tabAudio = tabResult.value
    if (tabAudio && tabAudio.getAudioTracks().length === 0) {
      streams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()))
      setError('Вкладка передана без звука. Повтори запуск и включи «Передавать звук вкладки» в окне браузера.')
      return
    }

    let context: AudioContext | null = null
    try {
      context = new AudioContext()
      await context.resume()
      const destination = context.createMediaStreamDestination()
      streams.push(destination.stream)
      const analyser = context.createAnalyser()
      analyser.fftSize = 256

      for (const stream of [microphone, ...(tabAudio ? [tabAudio] : [])]) {
        if (stream.getAudioTracks().length === 0) continue
        const source = context.createMediaStreamSource(stream)
        const gain = context.createGain()
        gain.gain.value = tabAudio && stream === microphone ? 0.85 : 1
        source.connect(gain)
        gain.connect(destination)
        gain.connect(analyser)
      }

      const options = supportedRecorderOptions()
      const recorder = options
        ? new MediaRecorder(destination.stream, options)
        : new MediaRecorder(destination.stream)
      recorderRef.current = recorder
      resourcesRef.current = { streams, context }
      analyserRef.current = analyser
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        releaseCapture()
        setLevel(0)
        if (blob.size === 0) {
          setError('Запись пустая. Проверь выбранный источник звука и попробуй ещё раз.')
          setSessionState('setup')
          return
        }
        setRecording(blob)
        setSessionState('review')
      }
      tabAudio?.getVideoTracks()[0]?.addEventListener('ended', stopCapture, { once: true })
      recorder.start(1000)
      setSessionState('recording')
    } catch (reason) {
      streams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()))
      if (context && context.state !== 'closed') void context.close()
      resourcesRef.current = null
      recorderRef.current = null
      analyserRef.current = null
      setError(getErrorMessage(reason, 'Не удалось настроить запись аудио.'))
    }
  }

  const togglePause = () => {
    const recorder = recorderRef.current
    if (!recorder) return
    if (recorder.state === 'recording') {
      recorder.pause()
      setSessionState('paused')
    } else if (recorder.state === 'paused') {
      recorder.resume()
      setSessionState('recording')
    }
  }

  const resetSession = () => {
    if (recording && !window.confirm('Удалить запись и начать заново?')) return
    setRecording(null)
    setSeconds(0)
    setError('')
    setSessionState('setup')
  }

  const submitRecording = async () => {
    if (!recording || !title.trim() || !consent || submitting) return
    setSubmitting(true)
    setError('')
    try {
      const extension = recording.type.includes('mp4') ? 'm4a' : 'webm'
      const meeting = await createMeeting({
        title: title.trim(),
        date,
        source: 'recording',
        fileName: `taldau-meeting.${extension}`,
        file: recording,
        consent_confirmed: true,
        num_speakers: speakerCount ? Number(speakerCount) : undefined,
      })
      navigate(`/meetings/${meeting.id}`)
    } catch (reason) {
      const message = getErrorMessage(reason, 'Повтори отправку записи.')
      setError(message)
      toast('Не удалось отправить запись', message)
    } finally {
      setSubmitting(false)
    }
  }

  const time = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
  const isCapturing = sessionState === 'recording' || sessionState === 'paused'

  return <div className="mx-auto max-w-[1320px] space-y-7 pb-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-emerald-800">
          <span className="h-2 w-2 rounded-full bg-emerald-600" /> Помощник встречи
        </div>
        <h1 className="page-title">Ассистент созвона</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Запиши встречу здесь. После завершения TaldauAI подготовит стенограмму, резюме и поручения для проверки.
        </p>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <ShieldCheck className="h-4 w-4 text-emerald-700" /> Локальная обработка аудио
      </div>
    </div>

    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-5">
        <section className="rounded-lg border bg-white p-5 sm:p-7">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h2 className="section-title">{isCapturing ? 'Текущий созвон' : sessionState === 'review' ? 'Запись готова' : 'Подготовка созвона'}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{isCapturing ? title || 'Без названия' : 'Название и дата попадут в протокол'}</p>
            </div>
            {isCapturing && <span className="inline-flex items-center gap-2 rounded-md bg-red-50 px-2.5 py-1.5 text-xs font-semibold text-red-700"><span className="h-2 w-2 animate-pulse rounded-full bg-red-600" />{sessionState === 'paused' ? 'Пауза' : 'Запись'}</span>}
            {sessionState === 'review' && <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-800"><Check className="h-3.5 w-3.5" />Готово к обработке</span>}
          </div>

          {sessionState === 'setup' ? (
            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_190px]">
              <div className="space-y-2">
                <Label htmlFor="live-title">Название встречи</Label>
                <Input id="live-title" autoComplete="off" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Например, Планирование на неделю" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="live-date">Дата</Label>
                <div className="relative">
                  <CalendarDays className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input id="live-date" type="date" className="pl-9" value={date} onChange={(event) => setDate(event.target.value)} />
                </div>
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="speaker-count">Ожидаемое число участников <span className="font-normal text-muted-foreground">(необязательно)</span></Label>
                <Input id="speaker-count" className="max-w-40" type="number" min="1" max="32" value={speakerCount} onChange={(event) => setSpeakerCount(event.target.value)} placeholder="Например, 4" />
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t pt-4 text-sm">
              <span className="flex items-center gap-2"><CalendarDays className="h-4 w-4 text-muted-foreground" />{new Date(`${date}T12:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}</span>
              {speakerCount && <span className="flex items-center gap-2"><Headphones className="h-4 w-4 text-muted-foreground" />До {speakerCount} участников</span>}
            </div>
          )}
        </section>

        <section className="rounded-lg border bg-white p-5 sm:p-7">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="section-title">Источник звука</h2>
              <p className="mt-1 text-sm text-muted-foreground">Выбери, что записывать во время встречи.</p>
            </div>
            <div className="inline-flex w-full rounded-md border bg-slate-50 p-1 sm:w-auto" aria-label="Источник звука">
              <button type="button" aria-pressed={mode === 'tab'} disabled={isCapturing || sessionState === 'review'} onClick={() => setMode('tab')} className={cn('flex min-h-9 flex-1 items-center justify-center gap-2 rounded px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 sm:flex-none', mode === 'tab' ? 'bg-white text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
                <Monitor className="h-4 w-4" /> Вкладка + микрофон
              </button>
              <button type="button" aria-pressed={mode === 'microphone'} disabled={isCapturing || sessionState === 'review'} onClick={() => setMode('microphone')} className={cn('flex min-h-9 flex-1 items-center justify-center gap-2 rounded px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 sm:flex-none', mode === 'microphone' ? 'bg-white text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
                <Mic className="h-4 w-4" /> Только микрофон
              </button>
            </div>
          </div>
          <p className="mt-3 max-w-3xl text-xs leading-5 text-muted-foreground">
            {mode === 'tab'
              ? 'Выбери вкладку с созвоном и включи передачу звука в окне браузера. Видео экрана не сохраняется; запись содержит звук вкладки и микрофона.'
              : 'Записывается микрофон этого устройства. Участники созвона будут слышны, если звук встречи воспроизводится рядом с микрофоном.'}
          </p>

          <div className="mt-6 flex min-h-40 flex-col items-center justify-center border-y py-6">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
              {sessionState === 'recording' ? <><span className="h-2 w-2 animate-pulse rounded-full bg-red-600" /> Идёт запись</> : sessionState === 'paused' ? 'Запись на паузе' : sessionState === 'review' ? 'Запись завершена' : 'Готов к записи'}
            </div>
            <div className={cn('font-mono text-4xl font-semibold tabular-nums text-slate-900 sm:text-5xl', isCapturing && 'text-emerald-900')} aria-live="off">{time}</div>
            <div className="mt-4 flex h-10 w-full max-w-md items-center justify-center gap-1.5" role="img" aria-label={isCapturing ? 'Уровень входящего звука' : 'Индикатор уровня звука появится во время записи'}>
              {waveformHeights.map((height, index) => {
                const active = isCapturing && level > ((index % 9) + 1) / 16
                return <span key={index} className={cn('w-1 rounded-full transition-all duration-100 sm:w-1.5', active ? 'bg-emerald-600' : 'bg-slate-200')} style={{ height: `${active ? Math.min(height + level * 16, 46) : height * 0.55}px` }} />
              })}
            </div>
          </div>

          {sessionState === 'setup' && (
            <div className="mt-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <label className="flex max-w-xl items-start gap-3 text-sm leading-5">
                <Checkbox id="meeting-consent" checked={consent} onCheckedChange={(checked) => setConsent(checked === true)} />
                <span>Участники предупреждены о записи и обработке речи с помощью ИИ.</span>
              </label>
              <Button size="lg" onClick={startCapture} disabled={!title.trim() || !consent}>
                <Mic className="h-4 w-4" /> Начать созвон
              </Button>
            </div>
          )}

          {isCapturing && (
            <div className="mt-5 flex flex-wrap justify-center gap-2 sm:justify-end">
              <Button variant="outline" onClick={togglePause}>
                {sessionState === 'paused' ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                {sessionState === 'paused' ? 'Продолжить' : 'Пауза'}
              </Button>
              <Button variant="destructive" onClick={stopCapture}><CircleStop className="h-4 w-4" />Завершить созвон</Button>
            </div>
          )}

          {sessionState === 'review' && (
            <div className="mt-5 space-y-4">
              {previewUrl && <audio className="h-10 w-full" controls src={previewUrl} aria-label="Прослушать запись встречи" />}
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <Button variant="outline" onClick={resetSession}><RotateCcw className="h-4 w-4" />Записать заново</Button>
                <Button size="lg" onClick={submitRecording} disabled={submitting}>
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  {submitting ? 'Отправляем аудио…' : 'Подготовить стенограмму'}
                </Button>
              </div>
              <p className="text-right text-xs text-muted-foreground">{recording ? `${(recording.size / 1024 / 1024).toFixed(1)} МБ · ${time}` : ''}</p>
            </div>
          )}

          {error && <div className="mt-5 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
        </section>

        {isCapturing && (
          <section className="flex items-start gap-3 border-l-2 border-emerald-600 py-1 pl-4" aria-live="polite">
            <AudioLines className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
            <div>
              <p className="text-sm font-medium">Ассистент сохраняет аудио встречи</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Стенограмма, решения и поручения появятся после завершения записи и обработки.</p>
            </div>
          </section>
        )}
      </div>

      <aside className="space-y-5">
        <section className="rounded-lg border bg-white p-5">
          <div className="mb-4 flex items-center gap-2"><Sparkles className="h-4 w-4 text-emerald-700" /><h2 className="section-title">Что делает TaldauAI</h2></div>
          <ol className="space-y-4">
            <li className="flex gap-3"><span className={cn('mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold', isCapturing || sessionState === 'review' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500')}>{isCapturing || sessionState === 'review' ? <Check className="h-3.5 w-3.5" /> : '1'}</span><div><p className="text-sm font-medium">Сохраняет аудио</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{mode === 'tab' ? 'Звук вкладки и микрофона записываются вместе.' : 'Записывается микрофон устройства.'}</p></div></li>
            <li className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-500">2</span><div><p className="text-sm font-medium">Расшифровывает после встречи</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Локальная модель обработает русскую, казахскую и смешанную речь.</p></div></li>
            <li className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-500">3</span><div><p className="text-sm font-medium">Готовит результат для проверки</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Участники, резюме и поручения со сроками.</p></div></li>
          </ol>
        </section>

        <section className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-950"><ShieldCheck className="h-4 w-4" /> Конфиденциальность</div>
          <p className="mt-2 text-xs leading-5 text-emerald-950/75">Передаётся аудиозапись встречи. При выборе вкладки браузер не сохраняет видео экрана. Начинай запись только после уведомления участников.</p>
        </section>

        <div className="flex items-start gap-2 text-xs leading-5 text-muted-foreground">
          <Clock3 className="mt-0.5 h-4 w-4 shrink-0" />
          <p>Во время созвона запись идёт локально в браузере. Распознавание и сбор поручений запускаются после отправки аудио.</p>
        </div>
      </aside>
    </div>
  </div>
}
