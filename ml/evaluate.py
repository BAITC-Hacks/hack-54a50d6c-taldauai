"""Measure ASR character error rate for ru, kk, and mixed speech.

Manifest JSON: [{"audio": "path.wav", "language": "mixed", "reference": "..."}]
Audio and references stay on the local machine.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
from pathlib import Path

from .pipeline import _convert_audio, _transcribe


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, 1):
        current = [i]
        for j, char_right in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (char_left != char_right)))
        previous = current
    return previous[-1]


def evaluate(manifest_path: str, *, language: str | None = None, hotwords: str | None = None) -> dict:
    manifest_file = Path(manifest_path).resolve()
    entries = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a nonempty list")
    rows = []
    started = time.monotonic()
    for item in entries:
        group = item["language"]
        if not isinstance(group, str) or not re.fullmatch(r"(?:[a-z]{2,3}|mixed)", group):
            raise ValueError("Manifest language must be a language code or mixed")
        source = (manifest_file.parent / item["audio"]).resolve()
        if not source.is_file():
            raise ValueError(f"Audio file does not exist: {source}")
        with tempfile.TemporaryDirectory(prefix="taldau-eval-") as tmp:
            wav = Path(tmp) / "audio.wav"
            _convert_audio(source, wav)
            hypothesis = " ".join(part["text"] for part in _transcribe(wav, language=language, hotwords=hotwords))
        reference = _normalize(item["reference"])
        prediction = _normalize(hypothesis)
        rows.append({"audio": item["audio"], "language": group,
                     "reference_chars": len(reference),
                     "reference_words": len(reference.split()),
                     "word_errors": _edit_distance(reference.split(), prediction.split()),
                     "character_errors": _edit_distance(reference, prediction),
                     "hypothesis": hypothesis})
    by_language = {}
    for group in dict.fromkeys(["ru", "kk", "mixed"] + [row["language"] for row in rows]):
        subset = [row for row in rows if row["language"] == group]
        chars = sum(row["reference_chars"] for row in subset)
        errors = sum(row["character_errors"] for row in subset)
        by_language[group] = {"files": len(subset),
                                 "cer": round(errors / chars, 4) if chars else None,
                                 "wer": (round(sum(r["word_errors"] for r in subset) /
                                               sum(r["reference_words"] for r in subset), 4)
                                         if sum(r["reference_words"] for r in subset) else None)}
    return {"engine": os.environ.get("TALDAU_ASR_ENGINE", "whisper"),
            "model": os.environ.get("TALDAU_ASR_MODEL"),
            "language": language, "hotwords": hotwords,
            "ctc_beam_size": int(os.environ.get("TALDAU_CTC_BEAM_SIZE", "1")) if os.environ.get("TALDAU_ASR_ENGINE") == "mixed-ctc" else None,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "by_language": by_language, "files": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local ASR by language")
    parser.add_argument("manifest", help="Local JSON manifest with reference transcripts")
    parser.add_argument("--output", help="Save evaluation JSON locally")
    parser.add_argument("--language", help="Force ASR language; omit for mixed/automatic detection")
    parser.add_argument("--hotwords", help="Whisper names/terminology hints")
    args = parser.parse_args()
    output = json.dumps(evaluate(args.manifest, language=args.language, hotwords=args.hotwords), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
