"""Evaluate synthetic meeting tasks and majority speaker per reference turn.

Speaker IDs are matched by best permutation. This is NOT standard frame-level
DER: reference turn spans also contain TTS pauses. Expected tasks/transcripts
are never passed to inference. Only the known speaker count is provided.
"""
import argparse
import itertools
import json
from pathlib import Path

from .evaluate_tasks import compare_tasks
from .pipeline import process_meeting


def compare_speakers(segments, reference):
    expected = sorted({s["speaker"] for s in reference})
    predicted = sorted({s["speaker_id"] for s in segments if s.get("speaker_id")})
    if len(expected) > 6 or len(predicted) > 6:
        raise ValueError("This small-fixture evaluator supports at most six speakers")
    majority = []
    for turn in reference:
        overlaps = {speaker: sum(max(0, min(s["end_ms"], turn["end_ms"]) - max(s["start_ms"], turn["start_ms"]))
                                  for s in segments if s.get("speaker_id") == speaker) for speaker in predicted}
        ranked = sorted(overlaps, key=overlaps.get, reverse=True)
        speaker = ranked[0] if ranked and overlaps[ranked[0]] > 0 else None
        if len(ranked) > 1 and overlaps[ranked[0]] == overlaps[ranked[1]]:
            speaker = None
        majority.append(speaker)
    # Pad both sides so differing cluster counts cannot hide missed speakers.
    size = max(len(expected), len(predicted))
    labels = expected + [None] * (size - len(expected))
    clusters = predicted + [None] * (size - len(predicted))
    best, mapping = 0, {}
    for permutation in itertools.permutations(labels):
        candidate = dict(zip(clusters, permutation))
        score = sum(p is not None and candidate.get(p) == r["speaker"] for p, r in zip(majority, reference))
        if score > best:
            best, mapping = score, {k: v for k, v in candidate.items() if k is not None}
    return {"correct_turns": best, "total_turns": len(reference), "mapping": mapping,
            "expected_speakers": len(expected), "predicted_speakers": len(predicted),
            "passed": best == len(reference) and len(expected) == len(predicted),
            "note": "Majority speaker per synthetic turn, not DER"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("--result", help="Evaluate a saved result instead of running inference")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = Path(args.reference).resolve()
    reference = json.loads(path.read_text(encoding="utf-8"))
    if args.result:
        result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    else:
        result = process_meeting(str(path.parent / reference["audio"]), reference["started_at"],
                                 num_speakers=len({s["speaker"] for s in reference["segments"]}))
    speakers = compare_speakers(result["segments"], reference["segments"])
    tasks = compare_tasks(result["tasks"], reference["expected_tasks"])
    report = {"synthetic": reference.get("synthetic", False), "speakers": speakers, "tasks": tasks,
              "passed": speakers["passed"] and tasks["passed"], "result": result}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "result"}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
