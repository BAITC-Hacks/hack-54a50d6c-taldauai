# Запуск ML-модуля

> Этот документ описывает отдельный ML CLI и эксперименты. Для полного
> приложения используйте [README](README.md), [macOS](docs/SETUP_MACOS.md)
> или [Windows](docs/SETUP_WINDOWS.md): API и ML должны быть в одном окружении.
> Базовая приёмка использует Mixed CTC, pyannote и Qwen 7B; Whisper и KazLLM
> ниже — необязательные альтернативы. Зафиксированные ревизии и условия
> моделей: [MODELS.md](docs/MODELS.md).

Модуль предоставляет `from ml import process_meeting` и CLI `python -m ml`.
Для извлечения поручений используйте `TALDAU_LLM_MODEL=qwen2.5:7b`.
KazLLM остаётся необязательной моделью подсказок.
Он обрабатывает локальный аудиофайл и возвращает JSON по [ML_CONTRACT.md](ML_CONTRACT.md).
Входные аудио и транскрипты отправляются только локальному Ollama на `127.0.0.1`.

## Зависимости

- Python 3.11 или 3.12, `ffmpeg` в `PATH`.
- Зависимости из `requirements-ml.txt`.
- Скачанная локально multilingual-модель `faster-whisper`.
- Либо специализированный `alibiserikbay/kazakh-russian-mixed-stt` (ветка `asr/rukk`).
- Скачанный локально pipeline `pyannote/speaker-diarization-community-1`.
- Локальный Ollama с моделью `qwen2.5:7b` или другой моделью, дающей JSON по схеме.
- Опционально: ISSAI KazLLM 8B GGUF4 для подсказок по исправлению смешанной
  русско-казахской транскрипции. Модель принимает текст, а не аудио.

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
hf download alibiserikbay/kazakh-russian-mixed-stt asr/rukk/model.pt asr/rukk/tokens.lst --local-dir models/mixed-stt
hf auth login
hf download pyannote/speaker-diarization-community-1 --local-dir models/speaker-diarization-community-1
ollama pull qwen2.5:7b
```

Для KazLLM требуется принять условия доступа на [странице ISSAI](https://huggingface.co/issai/LLama-3.1-KazLLM-1.0-8B-GGUF4)
и войти через `hf auth login`. После этого скачайте GGUF и создайте локальную
модель Ollama:

```bash
hf download issai/LLama-3.1-KazLLM-1.0-8B-GGUF4 checkpoints_llama8b_031224_18900-Q4_K_M.gguf --local-dir models/kazllm
printf 'FROM %s\n' "$PWD/models/kazllm/checkpoints_llama8b_031224_18900-Q4_K_M.gguf" > models/kazllm/Modelfile
ollama create taldau-kazllm -f models/kazllm/Modelfile
export TALDAU_KAZLLM_MODEL=taldau-kazllm
```

ISSAI распространяет KazLLM под CC-BY-NC-4.0 для некоммерческого применения;
перед коммерческим развёртыванием нужны другие права. Без
`TALDAU_KAZLLM_MODEL` этап подсказок пропускается.

Для `pyannote` сначала примите условия доступа на странице модели Hugging Face.
Команда `hf auth login` использует личный токен; не добавляйте его в репозиторий.
Для развёртывания в закрытом контуре переносите заранее скачанные веса и
устанавливайте зависимости из доверенного внутреннего источника.

```bash
export TALDAU_ASR_MODEL="$PWD/models/faster-whisper-large-v3"
export TALDAU_ASR_ENGINE=whisper
export TALDAU_DIARIZATION_MODEL="$PWD/models/speaker-diarization-community-1"
export TALDAU_DEVICE=cpu  # на NVIDIA GPU с CUDA: cuda
OLLAMA_NO_CLOUD=1 ollama serve
```

Для специализированного ASR задайте `TALDAU_ASR_ENGINE=mixed-ctc` и
`TALDAU_ASR_MODEL="$PWD/models/mixed-stt"`. По умолчанию используется greedy
(`TALDAU_CTC_BEAM_SIZE=1`). Экспериментальный CTC prefix beam search включается
через `TALDAU_CTC_BEAM_SIZE=8`, без KenLM; допустимый диапазон — 1–64.
Он улучшил ASR на малом синтетическом наборе, но не улучшил извлечение
поручений, поэтому не включён по умолчанию. Поиск суммирует вероятности акустических путей,
а Viterbi-выравнивание сохраняет таймкоды выбранного текста. Таймкоды слов
приблизительные, из акустических кадров. Whisper сохраняется как
альтернатива. Сравнение на синтетических данных — в [ML_EVALUATION.md](ML_EVALUATION.md).
Для поручений задайте `TALDAU_LLM_MODEL=qwen2.5:7b`. KazLLM можно выбрать
для сравнения, но на контрольном наборе она допускала пропуски и лишние задачи.

В другом терминале:

```bash
source .venv/bin/activate
export TALDAU_LLM_MODEL=qwen2.5:7b
python -m ml.doctor
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
Для Whisper доступны `language="ru"` / `"kk"` / `"en"` и другие поддерживаемые
коды, а также `hotwords="имена, термины"` (до 1000 символов). Для смешанной
речи не задавайте язык: оставьте автоматическое определение. Mixed CTC
распознаёт только русско-казахскую речь и не поддерживает подсказки терминов.

```bash
TALDAU_ASR_ENGINE=whisper TALDAU_ASR_MODEL=models/faster-whisper-large-v3 \
  python -m ml ./data/meeting.webm --started-at '2026-09-23T14:00:00+05:00' \
  --language ru --hotwords 'Айдана, Данияр, TaldauAI' --output ./data/result.json
```

Поддерживаются также браузерный WebM, Opus и AAC. Запись без речи возвращает
пустой результат с предупреждением без запуска диаризации и LLM.
`python -m ml.evaluate` также принимает `--language` и `--hotwords` для
сравнения распознавания на собственных эталонах. Метки языков в manifest
служат только для подсчёта метрик и не передаются модели как подсказка.

Известное число участников можно передать аргументом `num_speakers=2` либо
CLI-флагом `--num-speakers 2`. На коротких записях число и принадлежность
голосов всё равно нужно проверять. Pyannote получает декодированный PCM
в памяти, что устраняет несовместимость второго декодера с FFmpeg на macOS.
Если нет уверенной связи имени с голосом, `display_name` остаётся `null`.
Поручения без подтверждённого исполнителя и даты имеют `needs_review: true`.

Явные самопредставления могут дать `speakers[].suggested_name`; это отдельное
неподтверждённое поле, а не `display_name`. Адресат проверяется вторым локальным
запросом по сегменту назначения. Для длинных транскриптов выполняется проверка
пропущенных поручений. Это не гарантирует полноту на любой записи.
Сроки «за две недели», «екі апта ішінде», «к пятнадцатому октября»
нормализуются кодом; рабочие дни и неопределённые периоды остаются на проверку.

## Приёмка по ТЗ и экспорт

ТЗ сохранено в `CASE_REQUIREMENTS.md`. После установки моделей:

```bash
mkdir -p data
python -m ml.doctor
python -m ml.evaluate_tasks examples/task_cases.json --output data/tasks-check.json
python -m ml.evaluate_meeting examples/acceptance_reference.json --output data/acceptance-check.json
python -m ml examples/audio/acceptance_mixed.wav --started-at '2026-09-23T14:00:00+05:00' --num-speakers 2 --output data/protocol.json
python -m ml.export data/protocol.json --output data/protocol.docx
```

`evaluate_tasks` проверяет текстовое извлечение без ASR; эталонные ответы
не передаются модели. `evaluate_meeting` запускает реальные модели с аудио;
из эталона передаётся только известное число говорящих. Сравнение говорящих
по преобладающему голосу в каждой тестовой реплике не заменяет стандартный DER.
Эти сценарии используются при разработке и не являются независимым тестом.
Исходный сценарий и генератор TTS входят в репозиторий; воспроизведение
готового WAV не требует macOS.

DOCX-экспорт работает локально без Word/LibreOffice и дополнительных
Python-зависимостей. Для интеграции: `from ml.export import docx_bytes`.
Документ содержит исходный транскрипт, саммари, сроки, исполнителей и ссылки
на сегменты; неподтверждённый результат обозначен как черновик.

## Проверка

```bash
python3.11 -m unittest discover -s tests -v
```

Эти тесты проверяют совмещение временных интервалов, нормализацию сроков и
валидацию поручений. Они не измеряют качество ASR, диаризации и LLM. Для этого
нужны записи с ручной разметкой: русская, казахская и смешанная речь, минимум
два говорящих и явные поручения. Оцените отдельно ошибки распознавания,
перепутанные голоса, пропущенные и ложные поручения, исполнителей и сроки.

Для ASR положите тестовые записи и файл `manifest.json` в `data/`:

```json
[
  {"audio": "ru.wav", "language": "ru", "reference": "Проведите совещание до пятницы"},
  {"audio": "kk.wav", "language": "kk", "reference": "Жұмаға дейін есеп беріңіз"},
  {"audio": "mixed.wav", "language": "mixed", "reference": "Жұмаға дейін отчетты дайындаңыз"}
]
```

```bash
python -m ml.evaluate data/manifest.json
```

Команда выводит CER (долю ошибок по символам) отдельно для `ru`, `kk` и
`mixed`; это позволяет видеть качество шала-казахского отдельно. В ASR
включено определение языка по сегментам и отключено влияние предыдущих окон.
Это помогает при смене языка между репликами, но качество смешанной речи
внутри одной фразы надо проверить на записи; метрика пока не измерена.

На машине разработчика установлены ffmpeg, Ollama и Python-зависимости;
скачаны Whisper, Mixed CTC, pyannote и KazLLM. Сквозной запуск выполнен на
синтетической записи. Ошибки диаризации и поручений описаны в
[ML_EVALUATION.md](ML_EVALUATION.md); качество живой речи ещё не измерено.
