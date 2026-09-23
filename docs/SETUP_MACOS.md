# macOS: установка из чистого клона

[README](../README.md) · [Модели](MODELS.md) · [Проверки](VALIDATION.md)

Команды — Terminal, zsh/bash. Все пути ниже принадлежат вашему клону. Не запускайте их внутри копии с незавершённым merge. Используйте финальную объединённую `main`; историю проверенных версий см. в отчёте.

## 1. Системные зависимости и клон

Установите [Homebrew](https://brew.sh/) по официальной инструкции, [Docker Desktop для Mac](https://docs.docker.com/desktop/setup/install/mac-install/) и запустите Docker Desktop. Docker нужен только для PostgreSQL.

```bash
# Любой каталог; установка системных инструментов через Homebrew.
brew install git python@3.11 node ffmpeg ollama
git --version
python3.11 --version
node --version
npm --version
ffmpeg -version
docker compose version
docker info

# Каталог, где будут проекты. Для приватного GitHub нужен выданный доступ.
git clone --branch main https://github.com/BAITC-Hacks/hack-54a50d6c-taldauai.git TaldauAI
cd TaldauAI
git status --short
git log -1 --oneline
```

Homebrew устанавливает доступные ему версии Node/ffmpeg/Ollama, а не фиксирует версии проверенной машины. Сверьте их с [отчётом](VALIDATION.md). Не запускайте вторую PostgreSQL через Homebrew на том же порту; Compose — основной путь.

## 2. Единое Python-окружение и настройки

```bash
# Корень TaldauAI.
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt -r requirements-ml.txt
test -f backend/.env || cp backend/.env.example backend/.env
```

Откройте `backend/.env` в редакторе. Для настоящего запуска должны быть:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/taldau
ASR_BACKEND=local_ml
LLM_BACKEND=local_ml
TALDAU_TIMEZONE=Asia/Almaty
TALDAU_ASR_ENGINE=mixed-ctc
TALDAU_ASR_MODEL=models/mixed-stt
TALDAU_DIARIZATION_MODEL=models/speaker-diarization-community-1
TALDAU_LLM_MODEL=qwen2.5:7b
TALDAU_OLLAMA_URL=http://127.0.0.1:11434
TALDAU_DEVICE=cpu
```

`TALDAU_ML_RESULT_FIXTURE` и `TALDAU_KAZLLM_MODEL` оставьте незаданными. Не включайте `TALDAU_SUMMARY_MODEL`, пока соответствующая модель не установлена. Переменные процесса имеют приоритет над `.env`: проверьте старые exports; `unset TALDAU_ML_RESULT_FIXTURE TALDAU_KAZLLM_MODEL` убирает их только из текущего терминала. Не запускайте отдельное backend-окружение без ML-пакетов.

## 3. PostgreSQL и миграции

```bash
# Корень TaldauAI, Docker Desktop работает.
docker compose up -d postgres
docker compose exec postgres pg_isready -U postgres -d taldau
```

Дождитесь `accepting connections`. Если порт 5433 занят, сначала выберите другой порт для этого проекта: `export TALDAU_DB_PORT=55433`, затем выполните Compose и укажите `55433` в `DATABASE_URL`. Сохраняйте тот же порт при последующих запусках. Не останавливайте чужую базу.

```bash
# Переход из корня в backend; используется единая .venv из корня.
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic check
cd ..
```

Ожидается `20260923_0003 (head)` и `No new upgrade operations detected`. База пустая до загрузки записи; seed не требуется.

## 4. Модели и Ollama

Сначала прочитайте условия [моделей](MODELS.md). Для pyannote нужен собственный разрешённый Hugging Face-доступ либо заранее согласованный комплект. Не вставляйте токен в команды, README или Git.

```bash
# Корень, активная .venv. Интернет нужен только для подготовки.
hf download alibiserikbay/kazakh-russian-mixed-stt asr/rukk/model.pt asr/rukk/tokens.lst --revision 26298d2a61dc1573bfc11b7055c7d09a1e64b8a4 --local-dir models/mixed-stt
hf auth login
hf download pyannote/speaker-diarization-community-1 --revision 3533c8cf8e369892e6b79ff1bf80f7b0286a54ee --local-dir models/speaker-diarization-community-1
```

`hf` устанавливается транзитивно с ML-зависимостями; если команды нет, проверьте активную `.venv` и `python -m pip show huggingface-hub`. Загрузка уже имеющихся файлов использует кэш. Не скачивайте все альтернативные модели для базового запуска.

**Терминал Ollama, любой каталог**, оставить работающим:

```bash
OLLAMA_NO_CLOUD=1 ollama serve
```

Если Ollama уже запущена приложением, используйте существующий локальный сервер, не запускайте второй. Чтобы применить `OLLAMA_NO_CLOUD`, настройте окружение именно процесса сервера; переменная в терминале клиента не меняет уже запущенный сервер.

**Другой терминал, любой каталог**:

```bash
ollama pull qwen2.5:7b
ollama list
curl -fsS http://127.0.0.1:11434/api/tags
```

Для отдельного саммари можно заранее `ollama pull qwen2.5:14b` и затем задать `TALDAU_SUMMARY_MODEL=qwen2.5:14b`. Это необязательная дополнительная загрузка. На повторном запуске `pull` не нужен.

## 5. Готовность и API

**Терминал API, каталог `TaldauAI/backend`**:

```bash
PYTHONPATH=.. ../.venv/bin/python -c 'import app.config; from ml.doctor import main; raise SystemExit(main())'
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Doctor должен вернуть `ready: true`; это проверка наличия компонентов, не inference. Для длительной обработки не добавляйте `--reload`.

**Другой терминал, любой каталог**:

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

## 6. Frontend

**Отдельный терминал, каталог `TaldauAI/frontend`**:

```bash
npm ci
if [ ! -f .env ]; then
  printf '%s\n' 'VITE_USE_MOCKS=false' 'TALDAU_API_PROXY=http://127.0.0.1:8000' > .env
fi
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Если `.env` уже существует, проверьте значения вручную. Откройте `http://127.0.0.1:5173` и пройдите [сценарий README](../README.md#настоящий-сценарий-приёмки). Микрофон требует разрешения браузера; выбор аудио вкладки зависит от браузера/ОС, и UI должен сообщить, если звук не передан.

## 7. Независимая диагностика ML CLI

**Корень TaldauAI, отдельный терминал**. CLI не читает backend `.env`:

```bash
source .venv/bin/activate
export TALDAU_ASR_ENGINE=mixed-ctc
export TALDAU_ASR_MODEL="$PWD/models/mixed-stt"
export TALDAU_DIARIZATION_MODEL="$PWD/models/speaker-diarization-community-1"
export TALDAU_LLM_MODEL=qwen2.5:7b
export TALDAU_OLLAMA_URL=http://127.0.0.1:11434
export TALDAU_DEVICE=cpu
unset TALDAU_KAZLLM_MODEL TALDAU_ML_RESULT_FIXTURE
mkdir -p data
python -m ml.doctor
python -m ml examples/audio/acceptance_mixed.wav --started-at 2026-09-23T14:00:00+05:00 --num-speakers 2 --output data/real-smoke.json
```

CLI проверяет модели, но не UI/БД. Не запускайте одновременно тяжёлый CLI и обработку API: блокировка API не охватывает другой процесс.

Остановка: дождитесь обработки, Ctrl+C в API/Vite/Ollama, `docker compose stop postgres` из корня. Повторно запустите сервисы теми же командами, без повторной установки/скачивания. Volume и `backend/data/uploads` сохраняются. Удаление volume не является штатной остановкой.
