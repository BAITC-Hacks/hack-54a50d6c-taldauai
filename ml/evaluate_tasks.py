"""Evaluate local task extraction against fictional annotated transcripts.

This tests extraction, not ASR or diarization. Expected answers never enter
the model prompt. Keyword checks are a narrow regression gate, not a semantic
quality metric for arbitrary meetings.
"""

import argparse
import json
import os
import time
from pathlib import Path

from .pipeline import _extract, _meeting_date, _validate_extraction


def compare_tasks(tasks: list[dict], expected: list[dict]) -> dict:
    def matches(task, target):
        text = task["description"].casefold()
        return (task["assignee_name"] == target["assignee_name"]
                and task["due_date"] == target["due_date"]
                and target["source"] in task["source_segment_ids"]
                and all(any(word in text for word in group.casefold().split("|"))
                        for group in target["keywords"]))

    # Maximum bipartite matching: never count one prediction twice.
    assigned = {}
    def assign(target_index, visited):
        for index, task in enumerate(tasks):
            if index in visited or not matches(task, expected[target_index]):
                continue
            visited.add(index)
            if index not in assigned or assign(assigned[index], visited):
                assigned[index] = target_index
                return True
        return False
    for index in range(len(expected)):
        assign(index, set())
    correct = len(assigned)
    return {"expected": len(expected), "predicted": len(tasks), "matched": correct,
            "extra_or_incorrect": len(tasks) - correct, "missed": len(expected) - correct,
            "passed": correct == len(expected) == len(tasks)}


def evaluate(path: str) -> dict:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        started = time.monotonic()
        try:
            raw = _extract(case["segments"], case["started_at"], case["speakers"])
            tasks, summary, warnings = _validate_extraction(raw, case["segments"], case["speakers"],
                                                            _meeting_date(case["started_at"]))
            row = {"id": case["id"], "language": case["language"],
                   **compare_tasks(tasks, case["expected"]),
                   "tasks": tasks, "summary": summary, "warnings": warnings}
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            row = {"id": case["id"], "language": case["language"], "passed": False, "error": str(exc)}
        row["elapsed_seconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        print(f"{case['id']}: {'PASS' if row['passed'] else 'FAIL'}", flush=True)
    return {"model": os.environ.get("TALDAU_LLM_MODEL", "qwen2.5:7b"),
            "scope": "task extraction from annotated synthetic text; no ASR or diarization",
            "passed": sum(r["passed"] for r in rows), "total": len(rows), "cases": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate(args.manifest)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Passed {result['passed']}/{result['total']}")
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
