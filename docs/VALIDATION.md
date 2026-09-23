# Проверка документации и воспроизводимости — 23.09.2026

[README](../README.md) · [macOS](SETUP_MACOS.md) · [Windows](SETUP_WINDOWS.md)

## Финальная интеграция после согласования

Финальная проверка после `5347a4d`: API перезапущен с настоящими локальными моделями и прежней PostgreSQL; незавершённых обработок перед остановкой не было. `scripts/check_acceptance_persistence.py` прошёл: транскрипт, участники, ручные правки, подтверждения, прочтение уведомления и DOCX сохранились. `/api/health` вернул `database: connected`, лендинг — HTTP 200. Автоматическая предварительная срочность по сроку проверена 11 backend-тестами; сборка прошла, lint — 0 ошибок и 2 прежних предупреждения. Полный inference после этого перезапуска повторно не запускался.

Объединены новый интерфейс и лендинг `dc4cd0f` с ML/backend. Повторно прошли 35 ML и 9 backend/PostgreSQL-тестов, сборка и lint (0 ошибок, 2 предупреждения). Полный браузерный прогон на реальных моделях прошёл: 9 сегментов, 2 ML-поручения, 1 ручное, проверка ошибки сохранения, повторное подтверждение, DOCX и автоматическое уведомление. Фикстуры выключены. Маршруты приложения перенесены под `/app`, старые адреса перенаправляются. Vite alias исправлен через `fileURLToPath`, добавлены необходимые `@types/node`; Windows всё ещё не проверена. Ниже сохранена история предшествующей документационной проверки; упоминания незавершённого merge относятся к тому моменту.

## Объект проверки

Код `6990bba`, ветка `kashyyn/ml`. `git fetch origin` выполнен. На момент начала: `origin/main=025e8d1`, `origin/almaz/backend=7c90196`, `origin/bekasil/frontend=a9273ec`. Более новые ML-изменения не откатывались. В исходной копии есть незавершённый merge frontend с конфликтами в `Layout.tsx`, `LiveMeetingPage.tsx`, `MeetingPage.tsx`, `TasksPage.tsx`. Документационная работа его не разрешает и не включает чужие изменения.

Прочитаны AGENTS, README, CASE_REQUIREMENTS, HACKATHON_PLAN, ML_RUN, ML_CONTRACT, ML_EVALUATION, BACKEND_HANDOFF, TRAINING, зависимости, Compose, backend config/main/processor/adapter, миграции и тесты, frontend API/types/pages/config, сценарий/эталон и сохранённые результаты. `BACKEND_HANDOFF.md` описывает старый `d28c107`: его default `stub` и ограничения путей не следует переносить на нынешний backend. Текущие команды приложения находятся в README и setup-документах.

Среда: macOS 26.5.2 (25F84), arm64, Apple M4 Pro, 25 769 803 776 байт RAM (24 GiB), Python 3.11.15, Node 25.8.0, npm 11.11.0, ffmpeg 9.0.2. PostgreSQL 16 — отдельный тестовый контейнер, порт 55433. Это не минимальные требования. Пиковое потребление памяти не измерялось.

## Повторено лично при подготовке README

Команды ниже записаны относительно корня репозитория с активированным проверяемым Python-окружением. Перед запуском тестов установите `python -m pip install -r backend/requirements-test.txt` в то же окружение. В фактическом прогоне использовано отдельное Python 3.11-окружение, подготовленное ранее в этой сессии из backend, ML и test requirements; локальные веса использованы повторно, без скачивания.

| Проверка | Результат |
|---|---|
| `python -m unittest discover -s tests -q` | 35 passed, 0 skipped, 0 failed |
| `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:55433/taldau PYTHONPATH=backend python -m unittest discover -s backend/tests -v` | 9 passed, 0 skipped, 0 failed |
| Из `backend/`: `python -m alembic current` с тестовым `DATABASE_URL` | `20260923_0003 (head)` |
| Из `backend/`: `python -m alembic check` с тем же URL | `No new upgrade operations detected` |
| Doctor без явно подготовленной конфигурации | `ready: false`: выбран default Whisper, пути не заданы. Это диагностированный сбой конфигурации |
| Doctor с backend config, Mixed CTC, установленной pyannote, Qwen 7B/14B | `ready: true`, все проверки прошли |
| Frontend `6990bba` из отдельного `git archive`, `npm ci --no-audit --no-fund`, `npm run build` | 292 пакета установлены, сборка успешна, Vite 6.4.3 |
| Там же `npm run lint` | 0 ошибок, 2 предупреждения `react-refresh/only-export-components` в button/toast |

PostgreSQL-тесты создают случайную схему `test_ml_<uuid>`, применяют миграции с её `search_path` и удаляют только эту схему. Пользовательские таблицы не очищаются. ML в этих API-тестах подменён внутри теста: проверяются контракт, транзакции, ручные правки, конфликты версий, подтверждение, DOCX, напоминания и сохранение `failed`, а не ASR.

Frontend проверялся на файлах закоммиченной версии, а не на конфликтующей рабочей копии. Сначала использован существующий `node_modules`, затем дополнительно выполнен `npm ci` в другой чистой копии и повторены build/lint. npm сообщил о deprecated ESLint 9.39.5; зависимости в этой задаче не менялись. Установка Python в чистое окружение выполнена ранее в текущей сессии, но не является доказательством запуска на чистой ОС. Реальная установленная транзитивная пара torch 2.14.0 / torchaudio 2.11.0 позволила выполнить этот smoke test; совместимость всех остальных сценариев этой парой не установлена.

### Настоящий ML inference, без фикстур

Из корня, bash с активным Python-окружением:

```bash
export TALDAU_ASR_ENGINE=mixed-ctc
export TALDAU_ASR_MODEL=models/mixed-stt
export TALDAU_DIARIZATION_MODEL=models/speaker-diarization-community-1
export TALDAU_LLM_MODEL=qwen2.5:7b
export TALDAU_SUMMARY_MODEL=qwen2.5:14b
export TALDAU_DEVICE=cpu
mkdir -p data
/usr/bin/time -p python -m ml examples/audio/acceptance_mixed.wav --started-at 2026-09-23T14:00:00+05:00 --num-speakers 2 --output data/real-smoke.json
python -m ml.evaluate_meeting examples/acceptance_reference.json --result data/real-smoke.json --output data/real-evaluation.json
```

Фактический результат: код возврата 0, **wall time 71.06 s**, user 102.27 s, sys 49.77 s. User/sys — суммарное процессорное время, не время ожидания пользователя. На входе около 59 секунд синтетического WAV. Получены **2/2 ожидаемых поручения, 0 лишних/пропущенных**, **4/4 преобладающих голоса после сопоставления меток**. Это не DER, не независимый holdout и не гарантия скорости следующих запусков. КазLLM отключена, Qwen 14B использована только для саммари; базовый вариант только с 7B этим временем не измерялся. Эталон использовался после inference для сверки, не подавался модели.

В stderr были предупреждения о deprecated `torch.jit.load` и `std()` в pyannote на коротком фрагменте; выполнение завершилось успешно. Сырые локальные результаты сохранены вне Git; отчёт не публикует частные записи. Один успешный запуск не доказывает отсутствие утечек/сетевых обращений всех зависимостей — отдельного сетевого аудита не было.

## Ранее в этой же сессии, до документационного задания

С новым интерфейсом в отдельной временной копии прошёл настоящий браузерный цикл: загрузка синтетического WAV → ML → PostgreSQL → просмотр → имена/внешний ответственный → отказ API при сохранении → повторная проверка → ручное поручение → подтверждение → DOCX → локальное автоматическое уведомление. Итог: 9 сегментов, 2 ML-поручения, 1 ручное. Проверка невалидного WAV сохранила `failed`. Эта копия содержала подготовленное объединение дизайна `a9273ec` и логики `6990bba`, **не финальный закоммиченный merge**. Переносить её успешный результат на `main` нельзя.

Ранее также проверялись сохранность после перезапуска API/PostgreSQL и управление записью Chromium с синтетическим микрофоном. Системное окно выбора звука вкладки и реальный Teams/Zoom/Meet этим тестом не проверены. Артефакты находятся в игнорируемом `data/acceptance/`; повторите на согласованной финальной версии.

Для повторения браузерной приёмки на **отдельной тестовой БД**, после запуска всех компонентов (из `frontend/`):

```bash
npx playwright install chromium
npm run test:acceptance
npm run test:recording
```

Для другого адреса: `ACCEPTANCE_UI_URL=http://127.0.0.1:15173 npm run test:acceptance`. PowerShell: `$env:ACCEPTANCE_UI_URL = 'http://127.0.0.1:15173'`, затем `npm.cmd run test:acceptance`. Устанавливайте Playwright/browser только для тестов, не для обычного пользователя. После завершения приёмки и перезапуска API/БД из корня: `python scripts/check_acceptance_persistence.py --api http://127.0.0.1:8000`. Скрипт требует созданный браузерной приёмкой `data/acceptance/state.json`.

## Сохранённые отчёты и исторические результаты

- [tasks-qwen-evaluation.json](../examples/results/tasks-qwen-evaluation.json): 6/6 текстовых сценариев. Не аудиотест.
- [acceptance-evaluation.json](../examples/results/acceptance-evaluation.json): 2/2 поручения, 4/4 преобладающих голоса на синтетике; прежнее саммари. Набор использовался при разработке.
- [Пилот 1](../examples/results/ctc-adaptation-pilot-v1.json), [пилот 2](../examples/results/ctc-adaptation-pilot-v2.json), [TRAINING](../TRAINING.md): Dev WER исходной модели 6.88%, пилотов 13.30% и 7.03%; улучшение не получено, сохранены исходные веса.
- Переданный результат другого ноутбука: 6 backend passed; 27 ML passed, 3 skipped; build/lint успешны с 2 предупреждениями. Это историческая информация другого участника, не результат текущего запуска.

## Что ещё не подтверждено

Windows/WSL2/Linux/CUDA; чистая ОС; весь путь из финального `main`; текущий незавершённый merge; автономность с полностью отключённой внешней сетью; пиковая RAM/минимальное железо; промышленная безопасность; качество длинных живых совещаний; персональная доставка уведомлений. Блокеры сдачи: согласование и завершение интеграции, итоговая приёмка `main`, доступ эксперта к приватному GitHub и gated-моделям, проверка прав передачи офлайн-комплекта и актуального формата подачи у организаторов.
