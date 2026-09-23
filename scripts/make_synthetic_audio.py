"""Generate fictional macOS TTS fixtures; not a benchmark of human speech."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
manifest = root / "examples" / "shala_manifest.json"
for item in json.loads(manifest.read_text(encoding="utf-8")):
    target = (manifest.parent / item["audio"]).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    aiff = target.with_suffix(".aiff")
    subprocess.run(["say", "-v", item["voice"], "-o", str(aiff), item["reference"]], check=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(aiff),
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)], check=True)
    if target.stat().st_size < 1000:
        raise RuntimeError("macOS produced empty speech; allow access to system voices")
    print(target.name)
