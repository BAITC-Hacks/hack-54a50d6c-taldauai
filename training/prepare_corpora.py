"""Download a pinned benchmark and a bounded streaming sample of official KSC2.

Only public datasets are fetched. No meeting files or transcripts are uploaded.
The default limits are a pilot, not a representative sample of the full corpus.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

TIM_REPO = "Tim2190/kazakh-codeswitch-asr"
TIM_REVISION = "753d6640b4b02daf6bb73307a8572c2a710c203e"
KSC_REPO = "issai/Kazakh_Speech_Corpus_2"
KSC_REVISION = "cececbec1049f93f34a7421552500da01971ead8"


def clean_reference(text):
    return " ".join(re.sub(r"\[[^\]]+\]", "", text).split())


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_codeswitch(root, download=True):
    if download:
        from huggingface_hub import snapshot_download
        snapshot_download(TIM_REPO, repo_type="dataset", revision=TIM_REVISION,
                          local_dir=str(root), max_workers=4)
    rows = []
    with (root / "metadata.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            audio = (root / row["file_name"]).resolve()
            if not audio.is_relative_to(root.resolve()) or not audio.is_file():
                raise ValueError("Invalid benchmark audio path")
            rows.append({"id": row["audio_id"], "audio": row["file_name"],
                         "reference": clean_reference(row["transcript_verbatim"]),
                         "normalized_reference": clean_reference(row["transcript_normalized_written"]),
                         "language": "mixed", "split": "test", "dataset": TIM_REPO,
                         "revision": TIM_REVISION, "source": row["audio_source_link"],
                         "sha256": hashlib.sha256(audio.read_bytes()).hexdigest()})
    write_json(root / "test.json", rows)
    return rows


def prepare_control(root, manifest):
    manifest = Path(manifest).resolve()
    rows = []
    for index, row in enumerate(json.loads(manifest.read_text(encoding="utf-8"))):
        source = (manifest.parent / row["audio"]).resolve()
        rows.append({**row, "id": f"synthetic_{index}", "audio": os.path.relpath(source, root.resolve()),
                     "split": "test", "dataset": "TaldauAI synthetic regression controls",
                     "revision": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                     "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    write_json(root / "test.json", rows)


def member_key(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) < 4:
        return None
    split = {"train": "train", "training": "train", "dev": "dev", "valid": "dev",
             "validation": "dev", "test": "test"}.get(path.parts[1].lower())
    if not split or path.suffix not in {".flac", ".wav", ".txt"}:
        return None
    return split, str(path.with_suffix("")), path.suffix


def pilot_split(official_split, stem):
    if official_split == "train":
        # KSC2's official validation directory follows the enormous Train
        # directory. For a bounded pilot hold out 20% of Train utterances by a
        # stable ID hash. Speaker identity is unavailable: NOT speaker-disjoint.
        return "dev" if int(hashlib.sha256(stem.encode()).hexdigest()[:8], 16) % 5 == 0 else "train"
    return "test" if official_split == "test" else None


class LimitedReader:
    def __init__(self, raw, maximum):
        self.raw, self.maximum, self.count = raw, maximum, 0

    def read(self, size=-1):
        remaining = self.maximum - self.count
        if remaining <= 0:
            raise RuntimeError("Download byte limit reached before all requested splits were collected")
        data = self.raw.read(min(size if size >= 0 else 65536, remaining))
        before = self.count // (128 * 1024**2)
        self.count += len(data)
        if self.count // (128 * 1024**2) > before:
            print(f"Archive read: {self.count // 1024**2} MiB", flush=True)
        return data


def prepare_ksc(root, targets, max_download_mb, max_pending_mb):
    import requests
    from huggingface_hub import hf_hub_url
    import av

    # The official archive is split into ten pieces of ONE gzip stream. A small
    # pilot is read from the first piece; never pretend each part is a dataset.
    url = hf_hub_url(KSC_REPO, "ISSAI_KSC2.tar.gz.partaa", repo_type="dataset", revision=KSC_REVISION)
    root.mkdir(parents=True, exist_ok=True)
    records = {split: [] for split in targets}
    pending = {}
    pending_bytes = 0
    seen_groups = set()
    with requests.get(url, stream=True, timeout=(30, 120)) as response:
        response.raise_for_status()
        reader = LimitedReader(response.raw, max_download_mb * 1024**2)
        with tarfile.open(fileobj=reader, mode="r|gz") as archive:
            for member in archive:
                key = member_key(member.name)
                if not key or not member.isfile() or member.size > 10 * 1024**2:
                    continue
                official_split, stem, suffix = key
                split = pilot_split(official_split, stem)
                if split not in targets or len(records[split]) >= targets[split]:
                    continue
                group = str(PurePosixPath(stem).parent)
                if group not in seen_groups:
                    print(f"Reading {group}", flush=True)
                    seen_groups.add(group)
                entry = pending.setdefault(stem, {"split": split})
                content = archive.extractfile(member).read()
                if suffix == ".txt":
                    entry["text"] = content.decode("utf-8-sig").strip()
                else:
                    # The destination name is derived from a hash, never an
                    # untrusted archive path. Symlinks are not extracted.
                    name = hashlib.sha256(stem.encode()).hexdigest() + suffix
                    dest = root / "audio" / name
                    dest.parent.mkdir(exist_ok=True)
                    dest.write_bytes(content)
                    entry.update(audio=dest, sha256=hashlib.sha256(content).hexdigest(), size=len(content))
                    pending_bytes += len(content)
                if "audio" in entry and "text" in entry:
                    with av.open(str(entry["audio"])) as audio:
                        duration = audio.duration / av.time_base if audio.duration is not None else 0
                    if 0.5 <= duration <= 20 and entry["text"]:
                        records[split].append({"id": stem, "audio": "audio/" + entry["audio"].name,
                            "reference": entry["text"], "language": "kk", "split": split,
                            "dataset": KSC_REPO, "revision": KSC_REVISION, "source": group,
                            "official_split": official_split,
                            "duration_seconds": duration, "sha256": entry["sha256"]})
                        if len(records[split]) % 32 == 0:
                            print(f"{split}: {len(records[split])}/{targets[split]}", flush=True)
                            write_json(root / f"{split}.json", records[split])
                    pending_bytes -= entry.get("size", 0)
                    del pending[stem]
                if pending_bytes > max_pending_mb * 1024**2:
                    raise RuntimeError("Unmatched audio exceeds the configured disk budget")
                if all(len(records[s]) >= n for s, n in targets.items()):
                    break
    for split, rows in records.items():
        write_json(root / f"{split}.json", rows)
    report = {"dataset": KSC_REPO, "revision": KSC_REVISION,
              "selection": "first matching pairs, 0.5–20 s; Train split 80/20 by stable utterance ID hash; official Test reserved; speaker separation unknown; biased pilot",
              "downloaded_bytes": reader.count, "counts": {s: len(r) for s, r in records.items()}}
    write_json(root / "preparation.json", report)
    if not all(len(records[s]) >= n for s, n in targets.items()):
        raise RuntimeError("First archive part did not contain enough data; full archive preparation is required")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/corpora")
    parser.add_argument("--codeswitch-only", action="store_true")
    parser.add_argument("--ksc-train", type=int, default=256)
    parser.add_argument("--ksc-dev", type=int, default=64)
    parser.add_argument("--ksc-test", type=int, default=64)
    parser.add_argument("--max-download-mb", type=int, default=4096)
    parser.add_argument("--max-pending-mb", type=int, default=2048)
    args = parser.parse_args()
    if min(args.ksc_train, args.ksc_dev, args.ksc_test, args.max_download_mb, args.max_pending_mb) < 1:
        parser.error("All sample and byte limits must be positive")
    root = Path(args.output)
    rows = prepare_codeswitch(root / "codeswitch")
    prepare_control(root / "synthetic_control", Path(__file__).resolve().parents[1] / "examples/shala_manifest.json")
    print(f"Code-switch held-out benchmark: {len(rows)} clips", flush=True)
    if not args.codeswitch_only:
        report = prepare_ksc(root / "ksc2", {"train": args.ksc_train, "dev": args.ksc_dev, "test": args.ksc_test},
                             args.max_download_mb, args.max_pending_mb)
        print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
