"""Command line entry point: python -m ml AUDIO --started-at ISO_DATE."""

import argparse
import json
import sys

from .pipeline import process_meeting


def main() -> int:
    parser = argparse.ArgumentParser(description="Process a meeting recording locally")
    parser.add_argument("audio", help="Path to WAV, MP3, M4A, MP4, OGG, FLAC, WebM, Opus, or AAC")
    parser.add_argument("--started-at", required=True, help="ISO 8601 datetime with timezone")
    parser.add_argument("--speaker-names", help="JSON file mapping SPEAKER_00 to a name")
    parser.add_argument("--num-speakers", type=int, help="Known speaker count; improves short-recording diarization")
    parser.add_argument("--language", help="Language code (ru, kk, en, etc.); omit for mixed/automatic detection")
    parser.add_argument("--hotwords", help="Whisper terminology/name hints, up to 1000 characters")
    parser.add_argument("--output", help="Write JSON to a file; default stdout")
    args = parser.parse_args()
    names = None
    if args.speaker_names:
        with open(args.speaker_names, encoding="utf-8") as stream:
            names = json.load(stream)
    try:
        result = process_meeting(args.audio, args.started_at, names, num_speakers=args.num_speakers,
                                 language=args.language, hotwords=args.hotwords)
    except (ValueError, RuntimeError) as exc:
        print(f"ML processing failed: {exc}", file=sys.stderr)
        return 1
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            stream.write(output)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
