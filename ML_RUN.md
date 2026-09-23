# Запуск ML-модуля

Модуль предоставляет `from ml import process_meeting` и CLI `python -m ml`.
Он обрабатывает локальный аудиофайл и возвращает JSON по [ML_CONTRACT.md](ML_CONTRACT.md).
Входные аудио и транскрипты отправляются только локальному Ollama на `127.0.0.1`.

## Зависимости

- Python 3.11 или 3.12, `ffmpeg` в `PATH`.
- Зависимости из `requirements-ml.txt`.
- Скачанная локально multilingual-модель `faster-whisper`.
- Скачанный локально pipeline `pyannote/speaker-diarization-community-1`.
- Локальный Ollama с моделью `qwen2.5:7b` или другой моделью, дающей JSON по схеме.

На macOS `ffmpeg` можно установить через `brew install ffmpeg`; на Ubuntu —
через `sudo apt install ffmpeg`. Для Python:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-ml.txt
pip install huggingface_hub
```

Скачайте веса **до** запуска. Пример (пути можно поменять):

```bash
hf download Systran/faster-whisper-large-v3 --local-dir models/faster-whisper-large-v3
hf auth login
hf download pyannote/speaker-diarization-community-1 --local-dir models/speaker-diarization-community-1
ollama pull qwen2.5:7b
```

Для `pyannote` сначала примите условия доступа на странице модели Hugging Face.
Команда `hf auth login` использует личный токен; не добавляйте его в репозиторий.
Для развёртывания в закрытом контуре переносите заранее скачанные веса и
устанавливайте зависимости из доверенного внутреннего источника.

```bash
export TALDAU_ASR_MODEL="$PWD/models/faster-whisper-large-v3"
export TALDAU_DIARIZATION_MODEL="$PWD/models/speaker-diarization-community-1"
export TALDAU_DEVICE=cpu  # на NVIDIA GPU с CUDA: cuda
ollama serve
```

В другом терминале:

```bash
source .venv/bin/activate
python -m ml ./data/meeting.wav --started-at '2026-09-23T14:00:00+05:00' --output ./data/result.json
```

Backend может вызвать функцию напрямую:

```python
from ml import process_meeting

result = process_meeting(
    audio_path="/path/to/meeting.wav",
    meeting_started_at="2026-09-23T14:00:00+05:00",
    speaker_names={"SPEAKER_00": "Асхат Ерланович"},
)
```

`speaker_names` задаётся человеком после просмотра результата диаризации.
Если нет уверенной связи имени с голосом, `display_name` остаётся `null`.
Поручения без подтверждённого исполнителя и даты имеют `needs_review: true`.

## Проверка

```bash
python3.11 -m unittest discover -s tests -v
```

Эти тесты проверяют совмещение временных интервалов, нормализацию сроков и
валидацию поручений. Они не измеряют качество ASR, диаризации и LLM. Для этого
нужны записи с ручной разметкой: русская, казахская и смешанная речь, минимум
два говорящих и явные поручения. Оцените отдельно ошибки распознавания,
перепутанные голоса, пропущенные и ложные поручения, исполнителей и сроки.

На текущем этапе на машине разработчика нет `ffmpeg`, весов моделей и Ollama;
полный прогон аудио здесь ещё не выполнен.
