"""Generate a fictional multi-turn fixture and exact TTS turn boundaries on macOS.

These boundaries are reference data for evaluation only, never inference input.
Existing WAVs can be evaluated on other operating systems without macOS TTS.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import wave

root = Path(__file__).resolve().parents[1]
scenario = json.loads((root / "examples/acceptance_scenario.json").read_text(encoding="utf-8"))
output_path = root / "examples/audio/acceptance_mixed.wav"
segments = []
offset = 0
with tempfile.TemporaryDirectory(prefix="taldau-acceptance-") as tmp, wave.open(str(output_path), "wb") as output:
    output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
    for index, turn in enumerate(scenario["turns"]):
        aiff, wav = Path(tmp) / "voice.aiff", Path(tmp) / "voice.wav"
        subprocess.run(["say", "-v", turn["voice"], "-r", "160", "-o", str(aiff), turn["text"]], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], check=True)
        with wave.open(str(wav), "rb") as source:
            count = source.getnframes()
            if count < 16000:
                raise RuntimeError("TTS produced no usable speech; check system voice access")
            output.writeframes(source.readframes(count))
        segments.append({"id": f"reference_{index+1}", "speaker": turn["speaker"],
                         "start_ms": round(offset / 16), "end_ms": round((offset + count) / 16), "text": turn["text"]})
        output.writeframes(b"\0" * 32000)
        offset += count + 16000
reference = {"audio": "audio/acceptance_mixed.wav", "started_at": scenario["started_at"],
             "segments": segments, "expected_tasks": scenario["expected"], "synthetic": True}
(root / "examples/acceptance_reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Generated {output_path.name}: {offset / 16000:.1f}s")
