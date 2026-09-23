import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowRight, ArrowUpRight, AudioLines, Check, Clock3, FileAudio, Languages, ListChecks, Mic, ShieldCheck, Sparkles, Upload } from 'lucide-react'
import './landing.css'

const workflow = [
  {
    number: '01',
    label: 'Стенограмма',
    title: 'Речь становится структурой.',
    copy: 'Реплики привязаны ко времени, говорящим и языку. Неуверенные места можно найти и проверить по записи.',
    kind: 'transcript',
  },
  {
    number: '02',
    label: 'Решения',
    title: 'Главное отделяется от разговора.',
    copy: 'Краткое резюме и решения собраны рядом со стенограммой, чтобы выводы не отрывались от исходного разговора.',
    kind: 'decision',
  },
  {
    number: '03',
    label: 'Поручения',
    title: 'У каждого действия есть владелец и срок.',
    copy: 'Формулировку, ответственного и срок можно проверить и отредактировать в протоколе.',
    kind: 'task',
  },
  {
    number: '04',
    label: 'Проверка',
    title: 'Предположение не выдаётся за факт.',
    copy: 'Если имя или срок распознаны неуверенно, проверьте их до того, как отправить протокол команде.',
    kind: 'review',
  },
]

export function LandingPage() {
  const pageRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const page = pageRef.current
    if (!page || !('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    page.classList.add('landing-motion-ready')
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          observer.unobserve(entry.target)
        }
      })
    }, { threshold: 0.14 })

    page.querySelectorAll('.landing-reveal').forEach((element) => observer.observe(element))
    return () => {
      observer.disconnect()
      page.classList.remove('landing-motion-ready')
    }
  }, [])

  return <main className="landing" ref={pageRef}>
    <a className="landing-skip" href="#main-content">К содержанию</a>
    <nav className="landing-nav" aria-label="Навигация по странице">
      <div className="landing-wrap landing-nav-inner">
        <a className="landing-brand" href="#top" aria-label="TaldauAI, в начало">
          <AudioLines aria-hidden="true" />
          <span>TaldauAI</span>
        </a>
        <div className="landing-nav-links">
          <a href="#workflow">Как работает</a>
          <a href="#languages">RU / KK</a>
          <a href="#tasks">Поручения</a>
          <Link className="landing-nav-cta" to="/app/live"><Mic aria-hidden="true" />Записать встречу</Link>
        </div>
        <Link className="landing-mobile-cta" to="/app/live" aria-label="Записать встречу"><Mic aria-hidden="true" /></Link>
      </div>
    </nav>

    <section className="landing-hero" id="top" aria-labelledby="hero-title">
      <div className="landing-wrap landing-hero-inner" id="main-content">
        <div className="landing-eyebrow"><span className="landing-eyebrow-mark" />AI-помощник для протоколов встреч</div>
        <h1 id="hero-title">Совещание закончилось.<br /><span>Протокол почти готов.</span></h1>
        <div className="landing-hero-bottom">
          <p>Запишите встречу на русском и казахском. Получите стенограмму, решения и поручения, которые можно проверить по исходным репликам.</p>
          <div className="landing-actions">
            <Link className="landing-button landing-button-dark" to="/app/live"><Mic aria-hidden="true" />Записать встречу<ArrowUpRight aria-hidden="true" /></Link>
            <Link className="landing-button" to="/app/new"><Upload aria-hidden="true" />Загрузить запись</Link>
          </div>
        </div>

        <div className="landing-product landing-reveal" aria-label="Пример стенограммы и поручения после обработки встречи">
          <div className="landing-product-bar">
            <div className="landing-window-dots" aria-hidden="true"><span /><span /><span /></div>
            <span>ПРИМЕР ПРОТОКОЛА</span>
            <span className="landing-product-status"><i />Черновик готов</span>
          </div>
          <div className="landing-product-grid">
            <section className="landing-transcript" aria-label="Пример стенограммы">
              <div className="landing-panel-heading"><span>Стенограмма</span><span>12:04 — 12:08</span></div>
              <article className="landing-utterance">
                <time>12:04</time><div><strong>Айдар Садыков <span>RU</span></strong><p>Нужно закрыть вопрос по бюджету <mark>до конца месяца</mark>.</p></div>
              </article>
              <article className="landing-utterance">
                <time>12:06</time><div><strong>Алия Касымова <span>KK</span></strong><p>Жаңартылған нұсқасын ертең жібереміз.</p></div>
              </article>
              <article className="landing-utterance">
                <time>12:08</time><div><strong>Председатель <span>RU</span></strong><p>Айдар, тогда это за вами. Срок фиксируем в протоколе.</p></div>
              </article>
            </section>
            <section className="landing-task-preview" aria-label="Пример извлечённого поручения">
              <div className="landing-panel-heading"><span>Поручение</span><span className="landing-review-tag"><span />Проверьте срок</span></div>
              <h2>Обновить сводный бюджет</h2>
              <div className="landing-task-details">
                <div><span>Ответственный</span><strong>Айдар Садыков</strong></div>
                <div><span>Срок</span><strong>30 сентября <small>уточнить</small></strong></div>
              </div>
              <a className="landing-source-link" href="#workflow">Источник · 12:04–12:08 <ArrowUpRight aria-hidden="true" /></a>
            </section>
          </div>
        </div>
        <a className="landing-scroll" href="#workflow"><ArrowDown aria-hidden="true" />Листайте, чтобы увидеть процесс</a>
      </div>
    </section>

    <section className="landing-story" id="workflow" aria-labelledby="workflow-title">
      <div className="landing-wrap landing-story-grid">
        <header className="landing-story-intro">
          <p className="landing-eyebrow">От разговора к действию</p>
          <h2 id="workflow-title">Всё важное.<br />На своих местах.</h2>
          <p>Запись, стенограмма и будущие действия собраны в одном рабочем процессе: от первого слова до проверенного протокола.</p>
          <Link className="landing-text-link" to="/app">Открыть совещания <ArrowRight aria-hidden="true" /></Link>
        </header>
        <div className="landing-steps">
          {workflow.map((step) => <article className="landing-step landing-reveal" key={step.number}>
            <div className="landing-step-copy">
              <div className="landing-step-label"><span>{step.number}</span>{step.label}</div>
              <h3>{step.title}</h3>
              <p>{step.copy}</p>
            </div>
            <div className={`landing-mini-ui landing-mini-${step.kind}`}>
              {step.kind === 'transcript' && <><span className="landing-mini-label">12:18 · Алия Касымова · KK</span><strong>Барлық бөлімдерден соңғы деректерді жинап алу керек.</strong></>}
              {step.kind === 'decision' && <><span className="landing-mini-label">ШЕШЕНИЕ</span><strong>Завершить сверку бюджета и направить финальную версию.</strong><span className="landing-mini-source"><FileAudio aria-hidden="true" />Источник · 12:04–12:08</span></>}
              {step.kind === 'task' && <><span className="landing-mini-label">ПОРУЧЕНИЕ · ДО КОНЦА МЕСЯЦА</span><strong>Обновить сводный бюджет</strong><span className="landing-mini-assignee"><span className="landing-avatar">АС</span>Айдар Садыков</span></>}
              {step.kind === 'review' && <><span className="landing-mini-label"><ShieldCheck aria-hidden="true" />НУЖНО ПОДТВЕРДИТЬ</span><strong>30 сентября</strong><span className="landing-mini-source">В записи: «до конца месяца»</span></>}
            </div>
          </article>)}
        </div>
      </div>
    </section>

    <section className="landing-review" aria-labelledby="review-title">
      <div className="landing-wrap landing-review-grid">
        <div className="landing-review-copy landing-reveal">
          <p className="landing-eyebrow">Решение остаётся за вами</p>
          <h2 id="review-title">ИИ помогает.<br />Вы подтверждаете.</h2>
          <p>Автоматическая расшифровка ускоряет работу, но именно вы решаете, что войдёт в итоговый документ.</p>
          <Link className="landing-review-link" to="/app">Посмотреть протоколы <ArrowRight aria-hidden="true" /></Link>
        </div>
        <div className="landing-review-example landing-reveal">
          <div className="landing-review-example-top"><span><Sparkles aria-hidden="true" />Требует проверки</span><span>Поручение · 01</span></div>
          <h3>30 сентября</h3>
          <p>В записи сказано:<br /><strong>«Нужно закрыть вопрос до конца месяца»</strong></p>
          <div className="landing-review-source"><span><Clock3 aria-hidden="true" />12:04–12:08</span><span>Айдар Садыков · RU</span></div>
          <Link to="/app" className="landing-review-open">Проверить в приложении <ArrowUpRight aria-hidden="true" /></Link>
        </div>
      </div>
    </section>

    <section className="landing-languages" id="languages" aria-labelledby="languages-title">
      <div className="landing-wrap">
        <div className="landing-section-topline"><span><Languages aria-hidden="true" />РУССКИЙ / ҚАЗАҚША</span><span>ОБА ЯЗЫКА — ОДИН ПРОТОКОЛ</span></div>
        <h2 id="languages-title">Одна встреча.<br /><span>Два языка.</span></h2>
        <div className="landing-language-flow">
          <div className="landing-language-line"><span>RU</span><p>Нужно завершить сверку бюджета.</p><Check aria-hidden="true" /></div>
          <div className="landing-language-line"><span>KK</span><p>Жаңартылған нұсқасын ертең жібереміз.</p><Check aria-hidden="true" /></div>
          <div className="landing-language-line"><span>RU</span><p>Тогда фиксируем срок и ответственного.</p><Check aria-hidden="true" /></div>
        </div>
        <div className="landing-language-result">
          <p>Смена языка не разрывает разговор. Реплики остаются рядом с единым резюме, решениями и поручениями.</p>
          <div className="landing-result-note"><div><span className="landing-mini-label">ПОРУЧЕНИЕ</span><span className="landing-result-confidence">Источник найден <Check aria-hidden="true" /></span></div><h3>Обновить бюджет и направить финальную версию.</h3><p>Айдар Садыков · до конца месяца</p></div>
        </div>
      </div>
    </section>

    <section className="landing-tasks" id="tasks" aria-labelledby="tasks-title">
      <div className="landing-wrap">
        <div className="landing-tasks-heading">
          <div><p className="landing-eyebrow"><ListChecks aria-hidden="true" />После встречи</p><h2 id="tasks-title">Поручения не теряются.</h2></div>
          <p>Подтверждённые действия собраны в одном месте: с ответственными, сроками и статусом.</p>
        </div>
        <div className="landing-task-table-wrap">
          <table className="landing-task-table">
            <thead><tr><th>Поручение</th><th>Ответственный</th><th>Срок</th><th>Статус</th></tr></thead>
            <tbody>
              <tr><td>Обновить сводный бюджет</td><td>Айдар Садыков</td><td>30 сен</td><td><span className="landing-state landing-state-review">На проверке</span></td></tr>
              <tr><td>Подготовить письмо в министерство</td><td>Алия Касымова</td><td>Сегодня</td><td><span className="landing-state landing-state-done">Подтверждено</span></td></tr>
              <tr><td>Обновить список подрядчиков</td><td>Марат Нурпеисов</td><td>27 сен</td><td><span className="landing-state">В работе</span></td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section className="landing-final" aria-labelledby="final-title">
      <div className="landing-wrap landing-final-inner">
        <span className="landing-final-mark"><AudioLines aria-hidden="true" /></span>
        <p className="landing-eyebrow">Следующая встреча — проще</p>
        <h2 id="final-title">Будьте в разговоре.<br /><span>Протокол соберём после.</span></h2>
        <p>Запишите встречу или загрузите готовое аудио. Проверьте решения и поручения перед экспортом.</p>
        <div className="landing-actions landing-final-actions">
          <Link className="landing-button landing-button-dark" to="/app/live"><Mic aria-hidden="true" />Записать встречу<ArrowUpRight aria-hidden="true" /></Link>
          <Link className="landing-button" to="/app/new"><Upload aria-hidden="true" />Загрузить запись</Link>
        </div>
      </div>
    </section>

    <footer className="landing-footer">
      <div className="landing-wrap landing-footer-inner">
        <a className="landing-brand" href="#top"><AudioLines aria-hidden="true" /><span>TaldauAI</span></a>
        <span>Русский / Қазақша · Протоколы совещаний</span>
        <Link to="/app">Открыть приложение <ArrowUpRight aria-hidden="true" /></Link>
      </div>
    </footer>
  </main>
}
