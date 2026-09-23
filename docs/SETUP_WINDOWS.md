# Windows: PowerShell и отдельный вариант WSL2

[README](../README.md) · [Модели](MODELS.md) · [macOS](SETUP_MACOS.md)

**На Windows и WSL2 проект в этой проверке не запускался.** Ниже — инструкция по фактическим интерфейсам проекта, а не утверждение успешной Windows-приёмки. Нативный путь имеет известный риск: `frontend/vite.config.ts` формирует alias через `new URL(...).pathname`, что для Windows может дать `/C:/...`. Переносимая минимальная правка — `fileURLToPath(new URL('./src', import.meta.url))` из `node:url`; она не внесена в рамках документационной задачи. До проверки этой правки и совместимости ML нативный Windows нельзя считать готовым способом сдачи. Вариант WSL2 избегает Windows-путей, но тоже требует собственного smoke test.

## Вариант A: нативный Windows, PowerShell

### 1. Установка инструментов

Установите [Git for Windows](https://git-scm.com/downloads/win), Python **3.11** с [python.org](https://www.python.org/downloads/windows/), [Node.js](https://nodejs.org/en/download), [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) и [Ollama](https://ollama.com/download/windows). Установите ffmpeg по [ссылкам проекта](https://ffmpeg.org/download.html#build-windows), добавьте его `bin` в пользовательский PATH. Запустите Docker Desktop в режиме Linux containers. Для ML на иной архитектуре, чем x64, наличие wheels нужно проверить отдельно.

**Новый PowerShell, любой каталог:**

```powershell
git --version
py -3.11 --version
node --version
npm.cmd --version
ffmpeg -version
docker compose version
docker info
ollama --version
git clone --branch kashyyn/ml https://github.com/BAITC-Hacks/hack-54a50d6c-taldauai.git TaldauAI
Set-Location TaldauAI
git status --short
git log -1 --oneline
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r requirements-ml.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Активация через `Activate.ps1` не нужна; ExecutionPolicy не меняйте. `npm.cmd` обходит запуск npm PowerShell-скрипта. При отсутствии совместимого wheel torch/pyannote/torchcodec остановите этот путь и используйте отдельную Linux-среду; не считайте неполную установку готовым backend.

### 2. Конфигурация и PostgreSQL

В `backend/.env` сохраните следующие значения; не перезаписывайте существующий файл целиком:

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

Не задавайте `TALDAU_ML_RESULT_FIXTURE` и необязательную `TALDAU_KAZLLM_MODEL`. Прямые слеши в этих repo-relative путях принимает Python. При абсолютном пути используйте свой диск/каталог, например `C:/Projects/TaldauAI/models/mixed-stt`.

```powershell
# Корень TaldauAI.
Remove-Item Env:TALDAU_ML_RESULT_FIXTURE -ErrorAction SilentlyContinue
Remove-Item Env:TALDAU_KAZLLM_MODEL -ErrorAction SilentlyContinue
docker compose up -d postgres
docker compose exec postgres pg_isready -U postgres -d taldau
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic current
..\.venv\Scripts\python.exe -m alembic check
Set-Location ..
```

Если 5433 занят, до запуска Compose задайте `$env:TALDAU_DB_PORT = '55433'` и тот же порт в `DATABASE_URL`. Не останавливайте чужую БД. Ожидается `accepting connections`, миграция `20260923_0003 (head)` и отсутствие новых операций.

### 3. Веса и Ollama

Примите условия [pyannote](https://huggingface.co/pyannote/speaker-diarization-community-1). Эксперту нужен собственный разрешённый доступ или согласованный офлайн-комплект, не токен разработчика.

```powershell
# Корень TaldauAI; скачивание один раз, без импорта ml.
.\.venv\Scripts\hf.exe download alibiserikbay/kazakh-russian-mixed-stt asr/rukk/model.pt asr/rukk/tokens.lst --revision 26298d2a61dc1573bfc11b7055c7d09a1e64b8a4 --local-dir models/mixed-stt
.\.venv\Scripts\hf.exe auth login
.\.venv\Scripts\hf.exe download pyannote/speaker-diarization-community-1 --revision 3533c8cf8e369892e6b79ff1bf80f7b0286a54ee --local-dir models/speaker-diarization-community-1
```

**Отдельный PowerShell Ollama, любой каталог**, оставить работающим:

```powershell
$env:OLLAMA_NO_CLOUD = '1'
ollama serve
```

Если сервер уже работает через приложение, не запускайте второй. Настройка окружения клиента не меняет окружение уже работающего сервера.

**Другой PowerShell, любой каталог:**

```powershell
ollama pull qwen2.5:7b
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

Остальные модели необязательны, см. [MODELS.md](MODELS.md). Не включайте отсутствующую модель в `.env`.

### 4. API и frontend в отдельных терминалах

**PowerShell API, каталог `TaldauAI/backend`:**

```powershell
$env:PYTHONPATH = '..'
..\.venv\Scripts\python.exe -c "import app.config; from ml.doctor import main; raise SystemExit(main())"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Doctor должен дать `ready: true`. Не добавляйте `--reload`. Если `ZoneInfo` сообщает об отсутствии часовых поясов, проверьте наличие пакета `tzdata` в установленном ML-окружении; нативная Windows-поставка не является проверенной конфигурацией.

**PowerShell UI, каталог `TaldauAI/frontend`:**

```powershell
npm.cmd ci
if (-not (Test-Path .env)) {
  @('VITE_USE_MOCKS=false', 'TALDAU_API_PROXY=http://127.0.0.1:8000') | Set-Content -Encoding ascii .env
}
npm.cmd run build
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Если `@/api` не разрешается, сначала проверьте описанный в начале alias; не скрывайте Vite overlay. Этот блок не является доказательством исправления Windows-пути.

**Другой PowerShell:** `Invoke-RestMethod http://127.0.0.1:8000/api/health`. В браузере откройте `http://127.0.0.1:5173`, выполните [настоящую приёмку](../README.md#настоящий-сценарий-приёмки). Health не проверяет модели.

### 5. Отдельный ML CLI

```powershell
# Корень TaldauAI. CLI не читает backend/.env.
$env:TALDAU_ASR_ENGINE = 'mixed-ctc'
$env:TALDAU_ASR_MODEL = (Resolve-Path models/mixed-stt).Path
$env:TALDAU_DIARIZATION_MODEL = (Resolve-Path models/speaker-diarization-community-1).Path
$env:TALDAU_LLM_MODEL = 'qwen2.5:7b'
$env:TALDAU_OLLAMA_URL = 'http://127.0.0.1:11434'
$env:TALDAU_DEVICE = 'cpu'
New-Item -ItemType Directory -Force data | Out-Null
.\.venv\Scripts\python.exe -m ml.doctor
.\.venv\Scripts\python.exe -m ml examples/audio/acceptance_mixed.wav --started-at 2026-09-23T14:00:00+05:00 --num-speakers 2 --output data/real-smoke.json
```

Остановка после завершения задач: Ctrl+C у API/UI/Ollama, `docker compose stop postgres` из корня. Повторный запуск сохраняет volume и записи. Не используйте `down -v`.

## Вариант B: WSL2, отдельная Linux-среда

Это другой путь, а не продолжение нативной `.venv`. [Инструкция Microsoft](https://learn.microsoft.com/en-us/windows/wsl/install) описывает установку WSL. В административном PowerShell:

```powershell
wsl --install -d Ubuntu
```

После требуемой перезагрузки настройте пользователя Ubuntu. Установите Docker Desktop и включите WSL integration для этой дистрибуции. Проверяйте доступ к опубликованному PostgreSQL из WSL; настройки сети зависят от WSL/Docker Desktop. Backend, frontend, Python-окружение, файлы моделей и **Ollama должны находиться внутри одной Ubuntu**, например `~/TaldauAI`, не внутри `/mnt/c` и не в Windows `.venv`.

Следующие блоки — **bash в терминале Ubuntu**, не PowerShell. Системные зависимости:

```bash
sudo apt update
sudo apt install -y git ffmpeg curl ca-certificates
docker compose version
docker info
```

Установите Python 3.11 (например, через [uv](https://docs.astral.sh/uv/getting-started/installation/) и `uv python install 3.11`), Node.js/npm по [официальной инструкции](https://nodejs.org/en/download) и Ollama по [Linux-инструкции](https://docs.ollama.com/linux). Установка этих инструментов требует интернета; не подменяйте её Windows-исполняемыми файлами. После установки:

```bash
git clone --branch kashyyn/ml https://github.com/BAITC-Hacks/hack-54a50d6c-taldauai.git ~/TaldauAI
cd ~/TaldauAI
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -r backend/requirements.txt -r requirements-ml.txt
test -f backend/.env || cp backend/.env.example backend/.env
docker compose up -d postgres
docker compose exec postgres pg_isready -U postgres -d taldau
```

Проверьте `backend/.env` по значениям из варианта A. БД должна быть достижима из WSL по адресу в `DATABASE_URL`. Если loopback-публикация Docker Desktop не доступна из вашей конфигурации WSL, сначала настройте сеть Docker/WSL по документации, не открывайте PostgreSQL всему интернету.

```bash
# Корень ~/TaldauAI, активная .venv.
hf download alibiserikbay/kazakh-russian-mixed-stt asr/rukk/model.pt asr/rukk/tokens.lst --revision 26298d2a61dc1573bfc11b7055c7d09a1e64b8a4 --local-dir models/mixed-stt
hf auth login
hf download pyannote/speaker-diarization-community-1 --revision 3533c8cf8e369892e6b79ff1bf80f7b0286a54ee --local-dir models/speaker-diarization-community-1
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic check
```

**Отдельный Ubuntu-терминал Ollama:** `OLLAMA_NO_CLOUD=1 ollama serve`. Если установщик уже создал сервис, используйте один сервер и настройте его окружение. **Другой Ubuntu-терминал:** `ollama pull qwen2.5:7b`, `ollama list`, `curl -fsS http://127.0.0.1:11434/api/tags`. Не используйте Windows-host IP для Ollama: код ML принимает только loopback.

**Ubuntu-терминал API, `~/TaldauAI/backend`:**

```bash
PYTHONPATH=.. ../.venv/bin/python -c 'import app.config; from ml.doctor import main; raise SystemExit(main())'
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

**Ubuntu-терминал UI, `~/TaldauAI/frontend`:**

```bash
npm ci
if [ ! -f .env ]; then
  printf '%s\n' 'VITE_USE_MOCKS=false' 'TALDAU_API_PROXY=http://127.0.0.1:8000' > .env
fi
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

В Ubuntu проверьте `curl -fsS http://127.0.0.1:8000/api/health`. В Windows-браузере откройте `http://localhost:5173` через localhost forwarding WSL. Если он отключён, настройте доступ по документации WSL, не выставляя незащищённый API наружу. Затем пройдите сценарий README, включая DOCX и перезапуск. Отдельная CLI-диагностика использует bash-команды раздела 7 macOS-инструкции из Linux-корня проекта, без Homebrew. В рамках этой проверки весь WSL-путь остаётся **непроверенным**.
