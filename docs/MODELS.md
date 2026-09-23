# Локальные модели и условия доступа

[README](../README.md) · [macOS](SETUP_MACOS.md) · [Windows](SETUP_WINDOWS.md)

Для базового приложения обязательны Mixed STT, полный локальный pipeline pyannote и Qwen 7B в Ollama. KazLLM, Whisper и отдельная Qwen 14B необязательны. Наличие аккаунта участника не даёт эксперту доступ автоматически. Pyannote требует принятия условий и авторизации Hugging Face; заранее согласуйте доступ эксперта либо офлайн-комплект с сохранённой атрибуцией и проверенными правами распространения. Личный токен участника не передавайте.

## Проверенные источники и версии

Карточки первичных источников проверены 23.09.2026. Размеры ниже — местные измерения, не требования RAM и не объём полного установочного комплекта.

| Назначение | Источник / условия | Локальные файлы и размер |
|---|---|---|
| Основной ASR | [alibiserikbay/kazakh-russian-mixed-stt](https://huggingface.co/alibiserikbay/kazakh-russian-mixed-stt/raw/main/README.md), карточка Apache-2.0 | `models/mixed-stt/asr/rukk/model.pt`, `tokens.lst`; каталог около 721 MiB |
| Диаризация | [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1), CC-BY-4.0, gated: принять условия и предоставить сведения для доступа | Полный каталог `models/speaker-diarization-community-1`, около 32 MiB |
| Поручения / саммари | [Ollama qwen2.5:7b](https://ollama.com/library/qwen2.5:7b), [Qwen 7B Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/LICENSE), Apache-2.0 | Ollama хранит manifest/blobs; API сообщает 4 683 087 332 байт, Q4_K_M |
| Отдельное саммари, опционально | [Ollama qwen2.5:14b](https://ollama.com/library/qwen2.5:14b) | 8 988 124 069 байт, Q4_K_M; перед распространением сверить лицензию именно выбранного manifest |
| Альтернативный ASR | [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3), карточка MIT | Полный `models/faster-whisper-large-v3`, около 2.9 GiB |
| Коррекция, опционально | [issai/LLama-3.1-KazLLM-1.0-8B-GGUF4](https://huggingface.co/issai/LLama-3.1-KazLLM-1.0-8B-GGUF4) | `models/kazllm/checkpoints_llama8b_031224_18900-Q4_K_M.gguf`, около 4.6 GiB; Ollama-модель `taldau-kazllm` |

Карточка ISSAI прямо указывает CC-BY-NC-4.0, принятие условий Llama 3.1 и gated-доступ. Перед распространением проверьте выполнение условий ISSAI/Meta и сохранение атрибуции; коммерческое использование не покрывается некоммерческой лицензией. В базовой приёмке KazLLM отключена.

Зафиксированные версии скачанных обязательных файлов (из HF metadata):

```text
Mixed STT revision: 26298d2a61dc1573bfc11b7055c7d09a1e64b8a4
pyannote revision: 3533c8cf8e369892e6b79ff1bf80f7b0286a54ee
Ollama qwen2.5:7b digest:
845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e
Ollama qwen2.5:14b digest:
7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6
```

Теги Ollama могут обновляться; после `pull` сверяйте digest через `/api/tags`. Несовпадение означает другую версию, требующую повторной проверки. Digest не является обещанием доступности скачивания старой версии. Ревизии необязательных Whisper/KazLLM здесь не зафиксированы; основной воспроизводимый сценарий на них не опирается.

## Содержимое каталогов

У pyannote нужны `config.yaml`, `segmentation/pytorch_model.bin`, `embedding/pytorch_model.bin` и остальные файлы snapshot, включая `plda/*`. Один `config.yaml` недостаточен. Загружайте весь snapshot указанной ревизии. Whisper doctor проверяет `model.bin`, `config.json`, `tokenizer.json`; для работы скачивайте весь репозиторий модели. Mixed STT в этом проекте загружает TorchScript, не `transformers.AutoModel`; дополнительные KenLM-веса не нужны.

Команды скачивания для каждой ОС находятся в её setup-инструкции; они не импортируют `ml`, поэтому `HF_HUB_OFFLINE=1`, выставляемый runtime, не мешает подготовке в новом процессе. Если вы сами экспортировали offline-переменную в shell, уберите её на время разрешённого скачивания. После подготовки повторное скачивание не требуется.

Ollama: запускается отдельным процессом `ollama serve`, желательно с `OLLAMA_NO_CLOUD=1`. `ollama pull qwen2.5:7b` — первоначальная подготовка; `ollama list` и `/api/tags` — проверка. Расположение blobs управляется Ollama и её `OLLAMA_MODELS`; не помещайте их в Git. Приложению нужен тег, а не путь к GGUF. Облачного fallback в реальном ML нет.

## Необязательные альтернативы

Из корня клона с активным Python-окружением (команда `hf` одинаковая, в PowerShell используйте `.\.venv\Scripts\hf.exe`):

```text
hf download Systran/faster-whisper-large-v3 --local-dir models/faster-whisper-large-v3
hf download issai/LLama-3.1-KazLLM-1.0-8B-GGUF4 checkpoints_llama8b_031224_18900-Q4_K_M.gguf --local-dir models/kazllm
ollama pull qwen2.5:14b
```

Whisper: `TALDAU_ASR_ENGINE=whisper`, `TALDAU_ASR_MODEL=models/faster-whisper-large-v3`. KazLLM: после принятия условий создайте `models/kazllm/Modelfile` с одной строкой `FROM ./checkpoints_llama8b_031224_18900-Q4_K_M.gguf`, выполните `ollama create taldau-kazllm -f models/kazllm/Modelfile`, затем задайте `TALDAU_KAZLLM_MODEL=taldau-kazllm`. Саммари 14B: `TALDAU_SUMMARY_MODEL=qwen2.5:14b`. Эти дополнительные загрузки не обязательны.

## Закрытый контур

Скопируйте заранее разрешённые полные веса, образ PostgreSQL, пакеты Python/npm и Ollama в контролируемую среду; сохраните источники, версии и лицензии. Не переносите чужое Python-окружение между разными ОС. API и Ollama должны находиться в одной loopback-среде: `localhost` хоста, контейнера и WSL различаются. После установки пройдите doctor и настоящий сценарий без внешней сети. Проверка наличия локальной Ollama сама по себе не доказывает полной автономности.

Датасеты для экспериментов, не необходимые для inference: [Tim2190](https://huggingface.co/datasets/Tim2190/kazakh-codeswitch-asr/raw/main/README.md) указывает CC BY для исходного аудио и MIT для разметки/кода; сохраняйте атрибуцию исходных каналов. [Официальная ISSAI KSC2](https://issai.nu.edu.kz/kz-speech-corpus/) и [TRAINING.md](../TRAINING.md) описывают источник и ограничения выборок. Не распространяйте их как собственные данные команды.
