# TaldauAI

TaldauAI — прототип системы автоматического протоколирования совещаний для группы компаний «Самрук-Қазына». Система принимает запись совещания, формирует двуязычный транскрипт, определяет участников, выделяет поручения и помогает контролировать сроки исполнения. Прототип рассчитан на работу в закрытом контуре без внешних запросов в рантайме.

План работы и требования к сдаче: [HACKATHON_PLAN.md](HACKATHON_PLAN.md).

## Архитектура

Проект состоит из React SPA и FastAPI-сервиса с PostgreSQL. Компоненты фронтенда получают и изменяют данные только через `frontend/src/api.ts`; по умолчанию этот слой обращается к `/api`, а `VITE_USE_MOCKS=true` переключает его на локальные данные из `frontend/src/mocks.ts`.

FastAPI хранит совещания, участников, исходный транскрипт, подсказки KazLLM и поручения в PostgreSQL через SQLAlchemy 2. Структура базы управляется Alembic. Загруженные записи сохраняются в `backend/data/uploads`. По умолчанию локальные заглушки последовательно меняют статус `converting → transcribing → diarizing → extracting → done`. При заданном `TALDAU_ML_RESULT_FIXTURE`, `ASR_BACKEND=local` или `LLM_BACKEND=local` фоновая задача вызывает ML-адаптер/локальный `ml.process_meeting`, который выполняет `ffmpeg → Mixed CTC/Whisper → pyannote → KazLLM/Ollama → JSON v1`. При исключении совещание получает статус `failed`.

Для реального ML результат считается черновиком. Backend сохраняет `warnings`, `needs_review`, `source_segment_ids`, исходный ASR-текст и полный JSON ответа. Оператор может подтвердить, исправить или удалить ошибочное поручение; напоминание и экспорт заблокированы до подтверждения всех поручений.

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
- Python 3.11 или новее;
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
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Только для реального ML-прогона, а не режима готового JSON:
pip install -r ../requirements-ml.txt
cp .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Повторный запуск `python -m app.seed` безопасен и не создаёт дубли. Проверка API и соединения с базой: `http://localhost:8000/api/health`.

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
- `ASR_BACKEND=stub|local` — заглушка или локальный pipeline распознавания;
- `LLM_BACKEND=stub|ollama` — заглушка или OpenAI-совместимый локальный Ollama-клиент;
- `LLM_BASE_URL`, `LLM_MODEL` — OpenAI-совместимый адрес и модель локального Ollama;
- `TALDAU_TIMEZONE=Asia/Almaty` — часовой пояс для относительных сроков;
- `TALDAU_ML_RESULT_FIXTURE=examples/results/meeting_result.json` — необязательный режим проверки интеграции без весов, имеющий приоритет над заглушками. Удалите переменную для реального вызова `process_meeting`;
- `TALDAU_ASR_ENGINE`, `TALDAU_ASR_MODEL`, `TALDAU_DIARIZATION_MODEL`, `TALDAU_LLM_MODEL`, `TALDAU_KAZLLM_MODEL`, `TALDAU_OLLAMA_URL`, `TALDAU_DEVICE` — локальные ML-модели и runtime. Подробности: [ML_RUN.md](ML_RUN.md).

Frontend (`frontend/.env`, необязательно):

- `VITE_USE_MOCKS=false` — реальный API;
- `VITE_USE_MOCKS=true` — автономные моки с задержкой 300–800 мс.

Файлы `.env` исключены из Git, безопасные примеры находятся в `.env.example`.

### Проверка сборки

```bash
cd frontend
npm run build
npm run preview
```

Проверка логики ML и адаптера готового JSON:

```bash
python3 -m unittest discover -s tests -v
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
```

### Как проверить основной сценарий

1. Откройте главную страницу и выберите «Новое совещание».
2. Укажите название, дату и, если известно, число говорящих от 1 до 32.
3. Загрузите аудио/видео или откройте вкладку «Записать сейчас», разрешите микрофон, запишите и прослушайте фрагмент.
4. Подтвердите уведомление участников и отправьте запись на обработку. Без согласия API вернёт ошибку 400.
5. На странице совещания дождитесь появления ML-черновика. Проверьте исходный текст, подсказки KazLLM, границы говорящих и предупреждения.
6. Измените имя участника и перезагрузите страницу: имя должно сохраниться в транскрипте и связанных поручениях.
7. Исправьте или удалите дублирующиеся поручения. Для результата реального ML укажите ответственного и срок, затем нажмите «Подтвердить»; до подтверждения напоминания и экспорт заблокированы.
8. Скачайте протокол DOCX и проверьте заголовок, транскрипт, саммари и таблицу поручений.
9. Откройте «Контроль поручений», примените фильтры, создайте напоминание и отметьте поручение выполненным.

### Сторонние компоненты

Используются open-source библиотеки из `frontend/package.json`, `backend/requirements.txt` и `requirements-ml.txt`: React, Vite, TypeScript, Tailwind CSS, React Router, Radix UI, Lucide React, FastAPI, SQLAlchemy, Alembic, psycopg, python-docx, faster-whisper и pyannote.audio. ML использует локальные веса Mixed STT, Whisper, pyannote и Ollama/KazLLM; условия доступа и лицензии описаны в [ML_RUN.md](ML_RUN.md). Фактический сквозной результат и известные ошибки находятся в [ML_EVALUATION.md](ML_EVALUATION.md).
