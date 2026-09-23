"""Generate fictional macOS TTS fixtures; not a benchmark of human speech."""
import json
from pathlib import Path
import subprocess
import argparse
import tempfile
import wave

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--meeting", action="store_true", help="Create a two-voice fictional meeting")
args = parser.parse_args()
manifest = root / "examples" / ("meeting_manifest.json" if args.meeting else "shala_manifest.json")
frames = []
with tempfile.TemporaryDirectory(prefix="taldau-tts-") as temp:
    for item in json.loads(manifest.read_text(encoding="utf-8")):
        target = (manifest.parent / item["audio"]).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        aiff = Path(temp) / "speech.aiff"
        subprocess.run(["say", "-v", item["voice"], "-o", str(aiff), item["reference"]], check=True)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(aiff),
                        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)], check=True)
        if target.stat().st_size < 1000:
            raise RuntimeError("macOS produced empty speech; allow access to system voices")
        with wave.open(str(target), "rb") as source:
            frames.append(source.readframes(source.getnframes()))
        print(target.name)
if args.meeting:
    target = root / "examples" / "audio" / "meeting_demo.wav"
    with wave.open(str(target), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes((b"\0" * 16000).join(frames))
    print(target.name)
