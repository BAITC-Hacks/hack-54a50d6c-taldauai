"""Read-only readiness check for local ML inference; never downloads models."""

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil

from .pipeline import _local_open


def check() -> dict:
    checks = []
    def record(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    record("ffmpeg", shutil.which("ffmpeg"), "ffmpeg must be installed and available in PATH")
    for module in ("faster_whisper", "pyannote.audio", "torch", "onnxruntime"):
        try:
            present = importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            present = False
        record(module, present, "Install requirements-ml.txt in the active Python environment")
    engine = os.environ.get("TALDAU_ASR_ENGINE", "whisper")
    record("asr_engine", engine in {"whisper", "mixed-ctc"}, engine)
    root = Path(os.environ.get("TALDAU_ASR_MODEL", ""))
    required = ["asr/rukk/model.pt", "asr/rukk/tokens.lst"] if engine == "mixed-ctc" else ["model.bin", "config.json", "tokenizer.json"]
    record("asr_weights", all((root / p).is_file() for p in required),
           "TALDAU_ASR_MODEL must contain: " + ", ".join(required))
    root = Path(os.environ.get("TALDAU_DIARIZATION_MODEL", ""))
    record("diarization_weights", (root / "config.yaml").is_file()
           and (root / "segmentation/pytorch_model.bin").is_file()
           and (root / "embedding/pytorch_model.bin").is_file(),
           "Set TALDAU_DIARIZATION_MODEL to the complete downloaded pyannote pipeline")
    base = os.environ.get("TALDAU_OLLAMA_URL", "http://127.0.0.1:11434")
    local = re.fullmatch(r"http://(127\.0\.0\.1|localhost)(:\d+)?", base) is not None
    record("local_ollama_url", local, "Ollama must listen on a loopback HTTP address")
    if local:
        try:
            with _local_open(base + "/api/tags", timeout=5) as response:
                tags = json.load(response)
            models = {m["name"] for m in tags["models"]}
            for model in dict.fromkeys(filter(None, [os.environ.get("TALDAU_LLM_MODEL", "qwen2.5:7b"), os.environ.get("TALDAU_KAZLLM_MODEL"), os.environ.get("TALDAU_SUMMARY_MODEL")])):
                record("ollama_model:" + model, model in models or model + ":latest" in models,
                       "Install the local model in Ollama before running inference")
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            record("ollama", False, "Cannot inspect local Ollama; start it with OLLAMA_NO_CLOUD=1 ollama serve")
    return {"ready": all(c["ok"] for c in checks), "checks": checks,
            "note": "File presence only; run the documented smoke test to verify inference."}


def main():
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
