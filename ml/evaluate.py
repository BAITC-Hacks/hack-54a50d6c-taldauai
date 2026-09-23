"""Measure ASR character error rate for ru, kk, and mixed speech.

Manifest JSON: [{"audio": "path.wav", "language": "mixed", "reference": "..."}]
Audio and references stay on the local machine.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
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


def evaluate(manifest_path: str) -> dict:
    manifest_file = Path(manifest_path).resolve()
    entries = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a nonempty list")
    rows = []
    for item in entries:
        language = item["language"]
        if language not in {"ru", "kk", "mixed"}:
            raise ValueError("language must be ru, kk, or mixed")
        source = (manifest_file.parent / item["audio"]).resolve()
        if not source.is_file():
            raise ValueError(f"Audio file does not exist: {source}")
        with tempfile.TemporaryDirectory(prefix="taldau-eval-") as tmp:
            wav = Path(tmp) / "audio.wav"
            _convert_audio(source, wav)
            hypothesis = " ".join(part["text"] for part in _transcribe(wav))
        reference = _normalize(item["reference"])
        prediction = _normalize(hypothesis)
        rows.append({"audio": item["audio"], "language": language,
                     "reference_chars": len(reference),
                     "character_errors": _edit_distance(reference, prediction),
                     "hypothesis": hypothesis})
    by_language = {}
    for language in ("ru", "kk", "mixed"):
        subset = [row for row in rows if row["language"] == language]
        chars = sum(row["reference_chars"] for row in subset)
        errors = sum(row["character_errors"] for row in subset)
        by_language[language] = {"files": len(subset),
                                 "cer": round(errors / chars, 4) if chars else None}
    return {"by_language": by_language, "files": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local ASR by language")
    parser.add_argument("manifest", help="Local JSON manifest with reference transcripts")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
