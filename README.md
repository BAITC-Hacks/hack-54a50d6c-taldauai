# TaldauAI

TaldauAI — прототип системы автоматического протоколирования совещаний для группы компаний «Самрук-Қазына». Система принимает запись совещания, формирует двуязычный транскрипт, определяет участников, выделяет поручения и помогает контролировать сроки исполнения. Прототип рассчитан на работу в закрытом контуре без внешних запросов в рантайме.

План работы и требования к сдаче: [HACKATHON_PLAN.md](HACKATHON_PLAN.md).

## Архитектура

Проект состоит из React SPA и FastAPI-сервиса с PostgreSQL. Компоненты фронтенда получают и изменяют данные только через `frontend/src/api.ts`; по умолчанию этот слой обращается к `/api`, а `VITE_USE_MOCKS=true` переключает его на локальные данные из `frontend/src/mocks.ts`.

FastAPI хранит совещания, участников, исходный транскрипт, подсказки KazLLM и поручения в PostgreSQL через SQLAlchemy 2. Структура базы управляется Alembic. Загруженные записи сохраняются в `backend/data/uploads`. По умолчанию `ASR_BACKEND=local_ml` и `LLM_BACKEND=local_ml`: фоновая задача вызывает `ml.process_meeting` (`ffmpeg → Mixed CTC/Whisper → pyannote → Qwen2.5/Ollama → JSON v1`). KazLLM — только необязательные подсказки. При исключении совещание получает статус `failed`, без подмены результата демоданными.

Обработчик работает внутри процесса FastAPI через `BackgroundTasks`, отдельная команда worker не нужна. Тяжёлые задачи сериализованы блокировкой; запускайте **один** Uvicorn worker. Это не долговечная очередь: при аварийном завершении процесса незавершённую запись нужно загрузить повторно. Готовые результаты и ручные правки сохраняются в PostgreSQL и переживают перезапуск.

Для реального ML результат считается черновиком. Backend сохраняет `warnings`, `source_segment_ids`, исходный ASR-текст и полный JSON ответа (включая исходный `needs_review`, `suggested_name`, `assignment_quote`). Все новые ML-поручения в интерфейсе требуют ручного подтверждения независимо от уверенности модели. Оператор может подтвердить, исправить или удалить ошибочное поручение; напоминание для непроверенного поручения и экспорт до подтверждения всех поручений заблокированы.

Основные маршруты:

- `/` — список совещаний;
- `/new` — загрузка файла или запись с микрофона;
- `/meetings/:id` — обработка, участники, транскрипт, саммари и поручения;
- `/tasks` — общий контроль поручений и напоминаний.

## Технологии

- React 18, Vite и TypeScript;
- Tailwind CSS;
- компоненты shadcn/ui на базе Radix UI;
- React Router;
- MediaRecorder и Web Audio API для записи и индикации уровня звука;
- Python 3.11+, FastAPI, SQLAlchemy 2, Alembic и psycopg;
- PostgreSQL 16;
- python-docx для экспорта протоколов;
- ffmpeg, faster-whisper, pyannote.audio, Mixed CTC и локальный Ollama/KazLLM для ML-пайплайна.

## Запуск

### Требования

- Node.js 18 или новее;
- npm 9 или новее;
- Python 3.11 или 3.12 для совместимости ML-зависимостей;
- PostgreSQL 16 локально или Docker Compose;
- `ffmpeg`; для реальной обработки — заранее скачанные локальные модели и Ollama;
- современный Chromium, Firefox или Safari для записи с микрофона;
- разрешение браузера на использование микрофона для сценария «Записать сейчас».

### База данных через Homebrew

Локальная конфигурация ожидает PostgreSQL 16 на порту `5433` и пользователя macOS без пароля:

```bash
brew services start postgresql@16
createdb -h localhost -p 5433 taldau
```

Строка подключения:

```text
postgresql+psycopg://almazbukayev@localhost:5433/taldau
```

Если база уже создана, повторно выполнять `createdb` не нужно.

### База данных через Docker

В корне репозитория находится `docker-compose.yml` с PostgreSQL 16:

```bash
docker compose up -d postgres
```

Для этого варианта укажите в `backend/.env`:

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/taldau
```

Контейнер публикует PostgreSQL на `localhost:5433` и сохраняет данные в именованном volume.

### Бэкенд

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r ../requirements-ml.txt
# Только при первоначальной настройке, не перезаписывайте существующий .env:
test -f .env || cp .env.example .env
# Настройте DATABASE_URL и пути моделей в .env перед продолжением.
alembic upgrade head
PYTHONPATH=.. python -c 'import app.config; from ml.doctor import main; raise SystemExit(main())'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Перед запуском backend скачайте Mixed STT и pyannote по [ML_RUN.md](ML_RUN.md) и в отдельном терминале запустите `OLLAMA_NO_CLOUD=1 ollama serve`; модель `qwen2.5:7b` должна быть установлена. Проверка `ml.doctor` обязана дать `ready: true`. Python backend должен содержать и серверные, и ML-зависимости. Для полного прогона не используйте `--reload`: перезапуск прервёт выполняющуюся задачу. После изменения `.env` перезапустите backend.

Демоданные не нужны для реальной обработки; `python -m app.seed` — только отдельный демонстрационный режим. Проверка API и соединения с базой: `http://localhost:8000/api/health` (не проверяет готовность моделей).

### Фронтенд

```bash
cd frontend
npm install
npm run dev
```

Vite запускает приложение на `http://localhost:5173` и проксирует `/api` на `http://localhost:8000`. Все зависимости устанавливаются локально через npm; CDN и внешние сетевые запросы в приложении не используются.

### Переменные окружения

Backend (`backend/.env`):

- `DATABASE_URL` — строка подключения SQLAlchemy к PostgreSQL;
- `ASR_BACKEND=local_ml`, `LLM_BACKEND=local_ml` — реальный pipeline; оба значения обязательны для этого режима;
- `ASR_BACKEND=stub`, `LLM_BACKEND=stub|ollama` — только явный демонстрационный режим, не использовать для приёмки;
- `LLM_BASE_URL`, `LLM_MODEL` — OpenAI-совместимый адрес и модель локального Ollama;
- `TALDAU_TIMEZONE=Asia/Almaty` — часовой пояс для относительных сроков;
- `TALDAU_ML_RESULT_FIXTURE=examples/results/meeting_result.json` — необязательный режим проверки интеграции без весов, имеющий приоритет над заглушками. Удалите переменную для реального вызова `process_meeting`;
- `TALDAU_ASR_ENGINE=mixed-ctc`, `TALDAU_ASR_MODEL=models/mixed-stt`, `TALDAU_DIARIZATION_MODEL=models/speaker-diarization-community-1` — пути относительно корня репозитория или абсолютные пути этого компьютера;
- `TALDAU_LLM_MODEL=qwen2.5:7b`, `TALDAU_OLLAMA_URL=http://127.0.0.1:11434`, `TALDAU_DEVICE=cpu` — runtime;
- `TALDAU_KAZLLM_MODEL` — необязателен; не задавайте без установленных весов. Подробности: [ML_RUN.md](ML_RUN.md).

Frontend (`frontend/.env`, необязательно):

- `VITE_USE_MOCKS=false` — реальный API;
- `VITE_USE_MOCKS=true` — автономные моки с задержкой 300–800 мс.

Файлы `.env` исключены из Git, безопасные примеры находятся в `.env.example`.

### Проверка сборки

```bash
cd frontend
npm run build
npm run lint
npm run preview
```

Проверка логики ML и адаптера готового JSON:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-test.txt
backend/.venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

PostgreSQL-интеграционные тесты требуют явного разрешения через `TEST_DATABASE_URL`:

```bash
TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5433/taldau' \
  PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

Подставьте своё подключение. Тесты создают случайную отдельную схему, применяют обе миграции, проверяют загрузку, сохранение исходного JSON/сегментов/поручений/предупреждений, `failed`, откат частичного результата, правки, подтверждение и DOCX. В конце удаляется только эта тестовая схема. ML-вызов в этих тестах подменён контролируемым ответом: это **не** проверка реального распознавания и не включает фикстуру в приложении.

### Как проверить основной сценарий

1. Откройте главную страницу и выберите «Новое совещание».
2. Укажите название, дату и, если известно, число говорящих от 1 до 32.
3. Для приёмки загрузите `examples/audio/acceptance_mixed.wav`, число участников — `2`. Эталон `examples/acceptance_reference.json` используйте только для проверки, не как вход модели. Также можно загрузить собственное аудио/видео или записать микрофон.
4. Подтвердите уведомление участников и отправьте запись на обработку. Без согласия API вернёт ошибку 400.
5. На странице совещания дождитесь появления ML-черновика. Проверьте исходный текст, подсказки KazLLM, границы говорящих и предупреждения.
6. Измените имя участника и перезагрузите страницу: имя должно сохраниться в транскрипте и связанных поручениях.
7. Исправьте или удалите дублирующиеся поручения. Для результата реального ML укажите ответственного и срок, затем нажмите «Подтвердить»; до подтверждения напоминания и экспорт заблокированы.
8. Скачайте протокол DOCX и проверьте заголовок, транскрипт, саммари и таблицу поручений.
9. Откройте «Контроль поручений», примените фильтры, создайте напоминание и отметьте поручение выполненным.
10. Перезапустите backend и обновите страницу: исходный текст, предупреждения и ручные правки должны сохраниться.

## Статус ML и ограничения

Интегрирован ML `4efd70f`. В отчётах ML-разработчика: 2/2 поручения и 4/4 реплики по преобладающему голосу на минутной синтетической записи, 6/6 текстовых сценариев. Это не независимая оценка качества живых совещаний; на длинных записях остаются пропуски и ошибки ответственных. Два пилота дообучения не улучшили Dev WER, используются исходные веса. См. [ML_EVALUATION.md](ML_EVALUATION.md), [TRAINING.md](TRAINING.md), [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md).

Без локальных весов, ML-зависимостей и Ollama реальный прогон невозможен: задача завершится `failed`, а не демонстрационным результатом. Проверка адаптера/БД не заменяет приёмку с моделями. Напоминание сейчас формирует текст, но не отправляется по расписанию; PDF, СЭД и подключение Teams/Zoom/Meet не реализованы.

### Сторонние компоненты

Используются open-source библиотеки из `frontend/package.json`, `backend/requirements.txt` и `requirements-ml.txt`: React, Vite, TypeScript, Tailwind CSS, React Router, Radix UI, Lucide React, FastAPI, SQLAlchemy, Alembic, psycopg, python-docx, faster-whisper и pyannote.audio. ML использует локальные веса Mixed STT, Whisper, pyannote и Ollama/KazLLM; условия доступа и лицензии описаны в [ML_RUN.md](ML_RUN.md). Фактический сквозной результат и известные ошибки находятся в [ML_EVALUATION.md](ML_EVALUATION.md).
