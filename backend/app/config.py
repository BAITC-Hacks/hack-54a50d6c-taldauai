from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent


def _optional_project_path(name: str) -> Path | None:
    value = os.getenv(name)
    if not value:
        return None
    path = Path(value).expanduser()
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BACKEND_DIR / ".env")

# The API is often started from backend/, while ML paths are repo-relative.
for _name in ("TALDAU_ASR_MODEL", "TALDAU_DIARIZATION_MODEL"):
    _path = _optional_project_path(_name)
    if _path is not None:
        os.environ[_name] = str(_path)


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://almazbukayev@localhost:5433/taldau",
    )
    asr_backend: str = os.getenv("ASR_BACKEND", "local_ml")
    llm_backend: str = os.getenv("LLM_BACKEND", "local_ml")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:7b")
    uploads_dir: Path = BACKEND_DIR / "data" / "uploads"
    ml_result_fixture: Path | None = _optional_project_path("TALDAU_ML_RESULT_FIXTURE")
    timezone: str = os.getenv("TALDAU_TIMEZONE", "Asia/Almaty")


settings = Settings()
