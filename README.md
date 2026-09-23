# TaldauAI

Прототип локального ИИ-помощника для протоколирования совещаний. Он принимает
аудиозапись, распознаёт речь, отмечает говорящих, предлагает список поручений
с исполнителями и сроками и составляет краткое саммари. Результат — JSON,
который backend может показать секретарю для проверки и экспортировать в документ.

**Текущий статус:** ML-модуль и CLI реализованы, автоматические проверки логики
проходят. ASR проверен на пяти синтетических записях:
[результаты и повторение](ML_EVALUATION.md). Сквозной запуск Mixed CTC → pyannote →
KazLLM выполнен локально, но на коротком TTS-совещании есть ошибки разделения
голосов и дублирование поручения. Backend, интерфейс и экспорт в
текущей ветке отсутствуют. Не используйте неподтверждённые поручения для
автоматических уведомлений.

## Что реализовано

- Приём локального аудиофайла WAV/MP3/M4A/MP4/OGG/FLAC.
- Локальное декодирование через `ffmpeg`, распознавание через `faster-whisper`,
  диаризация через `pyannote.audio`.
- Специализированный Mixed CTC ASR для русско-казахской речи, переключаемый
  через `TALDAU_ASR_ENGINE`.
- Совмещение реплик с голосами по временным интервалам.
- Извлечение поручений и саммари через локальный Ollama с проверкой структуры
  JSON, ссылок на исходные реплики и календарных сроков.
- Необязательные подсказки локального ISSAI KazLLM для исправления смешанной
  русско-казахской речи; исходный ASR-текст сохраняется.
- Маркер `needs_review` для поручений с неуверенным исполнителем или сроком.
- Python API `process_meeting` и команда `python -m ml`.

## Архитектура

`аудиофайл → ffmpeg → faster-whisper → pyannote → совмещение по времени →
KazLLM (подсказки) → локальная LLM → проверка JSON → backend`.

Backend отвечает за загрузку и хранение файлов, ручное подтверждение,
экспорт PDF/DOCX и напоминания. Формат обмена приведён в
[ML_CONTRACT.md](ML_CONTRACT.md). Инструкция установки и запуска — в
[ML_RUN.md](ML_RUN.md).

## Установка и запуск ML-части

Нужны Python 3.11/3.12, `ffmpeg`, локально скачанные веса ASR и диаризации,
Ollama с импортированной KazLLM (`taldau-kazllm`) или `qwen2.5:7b`.
На Linux с NVIDIA GPU можно установить CUDA и
задать `TALDAU_DEVICE=cuda`; на macOS MVP работает на CPU.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-ml.txt
```

Скачивание моделей и настройка доступа к `pyannote` подробно описаны в
[ML_RUN.md](ML_RUN.md). После загрузки весов и запуска Ollama:

```bash
export TALDAU_ASR_ENGINE=mixed-ctc
export TALDAU_ASR_MODEL="$PWD/models/mixed-stt"
export TALDAU_DIARIZATION_MODEL="$PWD/models/speaker-diarization-community-1"
export TALDAU_DEVICE=cpu
export TALDAU_LLM_MODEL=taldau-kazllm
python -m ml ./data/meeting.wav --started-at '2026-09-23T14:00:00+05:00' --output ./data/result.json
```

`meeting_started_at` включает часовой пояс, потому что фразы вроде «до
пятницы» зависят от даты совещания. Переменные перечислены в `.env.example`.
Реальные файлы и веса храните вне репозитория или в исключённых папках `data/`
и `models/`.

## Как проверить

```bash
python3.11 -m unittest discover -s tests -v
python3.11 -m ml --help
```

После установки моделей запишите короткое тестовое совещание с двумя голосами
и поручением с явным сроком. Запустите команду выше, откройте `result.json` и
сверьте `segments`, `tasks`, `source_segment_ids` и `summary` с записью.
Отдельно проверьте русский, казахский и смешанную речь. Качество на живых
записях пока не измерено. Для смешанной речи есть отдельная команда оценки CER/WER:
`python -m ml.evaluate data/manifest.json`; формат файла описан в
[ML_RUN.md](ML_RUN.md).

## Данные, модели и ограничения

Тестовые протоколы предоставлены участником команды как ориентир для
поручений; они не добавлены в репозиторий и не заменяют аудиотест.
Внешние API не используются при обработке: все модели запускаются локально.
Веса требуется скачать заранее. Выбранные компоненты:
[faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[pyannote.audio](https://github.com/pyannote/pyannote-audio),
[Mixed STT](https://huggingface.co/alibiserikbay/kazakh-russian-mixed-stt) (Apache-2.0),
[Qwen2.5 7B через Ollama](https://ollama.com/library/qwen2.5:7b),
[ISSAI KazLLM 8B](https://huggingface.co/issai/LLama-3.1-KazLLM-1.0-8B-GGUF4)
(необязателен, лицензия CC-BY-NC-4.0).
Условия доступа и лицензии весов проверяйте перед распространением сборки.

Имена голосов и спорные сроки должен проверить человек. Подключение к
Teams/Zoom/Meet, голосовая идентификация, PDF/DOCX и СЭД пока не реализованы.
Развёрнутой версии пока нет.

Организационный план команды: [HACKATHON_PLAN.md](HACKATHON_PLAN.md).
