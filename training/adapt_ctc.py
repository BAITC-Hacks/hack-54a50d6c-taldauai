"""Adapt only the Mixed CTC output head; keep both acoustic towers frozen.

Local manifests only. Model selection uses dev WER, including the unchanged
baseline. Test sets are scored once after selection, never used for updates.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import time

from ml.evaluate import _edit_distance, _normalize
from ml.mixed_asr import decode_words


def load_manifest(path, expected_split):
    path = Path(path).resolve()
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Manifest must contain a nonempty list")
    result = []
    for row in rows:
        if row.get("split") != expected_split:
            raise ValueError(f"Expected {expected_split} split, got {row.get('split')}")
        source = (path.parent / row["audio"]).resolve()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != row.get("sha256"):
            raise ValueError(f"Audio checksum mismatch: {source.name}")
        result.append({**row, "path": str(source)})
    return result


def check_disjoint(groups):
    seen = {}
    for split, rows in groups.items():
        for row in rows:
            key = row["sha256"]
            if key in seen and seen[key] != split:
                raise ValueError(f"Audio leakage between {seen[key]} and {split}")
            seen[key] = split


def encode_reference(text, token_ids):
    # Do not silently train against numeric/Latin/unsupported targets. A small
    # pilot may skip them, but must report every skipped row.
    text = " ".join(re.findall(r"\w+", text.casefold().replace("_", " ")))
    symbols = text.replace(" ", "|")
    missing = sorted(set(symbols) - set(token_ids))
    if missing:
        raise ValueError("Unsupported target symbols: " + "".join(missing))
    if not symbols:
        raise ValueError("Empty training target")
    # This checkpoint emits explicit silence/boundary labels _|text|_.
    # Omitting them forces a tiny adaptation set to relearn the output
    # convention and damages word boundaries despite correct acoustics.
    if "_" not in token_ids or "|" not in token_ids:
        raise ValueError("Mixed CTC adaptation requires silence and word-boundary tokens")
    symbols = "_|" + symbols + "|_"
    return [token_ids[symbol] for symbol in symbols]


def score(head, entries, tokens, blank, torch):
    totals = {"character_errors": 0, "reference_chars": 0, "word_errors": 0, "reference_words": 0}
    with torch.no_grad():
        for entry in entries:
            hypothesis = " ".join(w["text"] for w in decode_words(
                head(entry["features"].float())[0].argmax(-1).tolist(), tokens, blank, 0, 1))
            ref, hyp = _normalize(entry["reference"]), _normalize(hypothesis)
            totals["character_errors"] += _edit_distance(ref, hyp)
            totals["reference_chars"] += len(ref)
            totals["word_errors"] += _edit_distance(ref.split(), hyp.split())
            totals["reference_words"] += len(ref.split())
    return {**totals, "clips": len(entries),
            "cer": totals["character_errors"] / max(1, totals["reference_chars"]),
            "wer": totals["word_errors"] / max(1, totals["reference_words"])}


def cache_features(model, rows, root, model_hash, token_ids, torch, *, training):
    from faster_whisper.audio import decode_audio
    entries, skipped = [], []
    for index, row in enumerate(rows):
        try:
            targets = encode_reference(row["reference"], token_ids) if training else []
        except ValueError as exc:
            skipped.append({"id": row["id"], "reason": str(exc)})
            continue
        cache = root / f"{model_hash[:16]}-{row['sha256']}.pt"
        if cache.is_file():
            features = torch.load(cache, map_location="cpu", weights_only=True)
        else:
            samples = decode_audio(row["path"], sampling_rate=16000)
            if not 0.5 <= len(samples) / 16000 <= 20:
                raise ValueError(f"Audio outside 0.5–20 s pilot limit: {row['id']}")
            with torch.no_grad():
                waveform = torch.from_numpy(samples.copy()).unsqueeze(0)
                features = torch.cat([model.model1(waveform), model.model2(waveform)], dim=-1).cpu()
            torch.save(features, cache)
        minimum_frames = len(targets) + sum(a == b for a, b in zip(targets, targets[1:]))
        if training and minimum_frames > features.shape[1]:
            skipped.append({"id": row["id"], "reason": "CTC target requires more frames than available"})
            continue
        entries.append({"features": features, "targets": torch.tensor(targets, dtype=torch.long),
                        "reference": row["reference"], "language": row.get("language", "unknown")})
        if (index + 1) % 32 == 0:
            print(f"Features: {index + 1}/{len(rows)}", flush=True)
    if not entries:
        raise ValueError("No usable examples")
    return entries, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="models/mixed-stt")
    parser.add_argument("--train", default="data/corpora/ksc2/train.json")
    parser.add_argument("--dev", default="data/corpora/ksc2/dev.json")
    parser.add_argument("--test", nargs="+", default=["data/corpora/ksc2/test.json", "data/corpora/codeswitch/test.json",
                                                      "data/corpora/synthetic_control/test.json"])
    parser.add_argument("--output", default="models/mixed-stt-adapted")
    parser.add_argument("--cache", default="data/training/features")
    parser.add_argument("--report", default="data/training/adaptation.json")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=0.00001)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.epochs < 1 or args.learning_rate <= 0 or args.threads < 1:
        parser.error("Epochs, learning rate and threads must be positive")
    source = Path(args.model).resolve() / "asr" / "rukk"
    output = Path(args.output).resolve() / "asr" / "rukk"
    if source == output or output.is_relative_to(source):
        parser.error("Output must not overwrite the base model")
    if (output / "model.pt").exists():
        parser.error("Output checkpoint already exists; choose a new experiment directory")
    import torch
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)
    started = time.monotonic()
    groups = {"train": load_manifest(args.train, "train"), "dev": load_manifest(args.dev, "dev")}
    for index, path in enumerate(args.test):
        groups[f"test_{index}"] = load_manifest(path, "test")
    check_disjoint(groups)
    tokens = {}
    for line in (source / "tokens.lst").read_text().splitlines():
        symbol, index = line.split("\t")
        tokens[int(index)] = symbol
    token_ids, blank = {symbol: index for index, symbol in tokens.items()}, max(tokens) + 1
    model_hash = hashlib.sha256((source / "model.pt").read_bytes()).hexdigest()
    model = torch.jit.load(str(source / "model.pt"), map_location="cpu").eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    head = torch.nn.Linear(model.lm_head.weight.shape[1], model.lm_head.weight.shape[0])
    head.load_state_dict(model.lm_head.state_dict())
    baseline = {k: value.detach().clone() for k, value in head.state_dict().items()}
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    # No test labels or test scores are involved in model selection below.
    train, skipped = cache_features(model, groups["train"], cache, model_hash, token_ids, torch, training=True)
    dev, _ = cache_features(model, groups["dev"], cache, model_hash, token_ids, torch, training=False)
    baseline_dev = score(head, dev, tokens, blank, torch)
    print("Baseline dev: " + json.dumps(baseline_dev), flush=True)
    best, best_epoch, best_wer = baseline, 0, baseline_dev["wer"]
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.learning_rate)
    loss_fn = torch.nn.CTCLoss(blank=blank, zero_infinity=False)
    history = []
    for epoch in range(1, args.epochs + 1):
        rng.shuffle(train)
        loss_sum = 0.0
        for entry in train:
            optimizer.zero_grad(set_to_none=True)
            logits = head(entry["features"].float())
            loss = loss_fn(logits.log_softmax(-1).transpose(0, 1), entry["targets"],
                           torch.tensor([logits.shape[1]]), torch.tensor([len(entry["targets"])]))
            loss = loss + 0.001 * sum((p - baseline[name]).square().mean() for name, p in head.named_parameters())
            if not math.isfinite(loss.item()):
                raise RuntimeError("Non-finite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
            optimizer.step()
            loss_sum += loss.item()
        metrics = score(head, dev, tokens, blank, torch)
        history.append({"epoch": epoch, "train_loss": loss_sum / len(train), "dev": metrics})
        print(json.dumps(history[-1]), flush=True)
        if metrics["wer"] < best_wer:
            best, best_epoch, best_wer = {k: v.detach().clone() for k, v in head.state_dict().items()}, epoch, metrics["wer"]
    output.mkdir(parents=True, exist_ok=True)
    torch.save(head.state_dict(), output.parent.parent / "last_head.pt")
    head.load_state_dict(best)
    with torch.no_grad():
        model.lm_head.weight.copy_(head.weight)
        model.lm_head.bias.copy_(head.bias)
    model.save(str(output / "model.pt"))
    shutil.copyfile(source / "tokens.lst", output / "tokens.lst")
    restored = torch.jit.load(str(output / "model.pt"), map_location="cpu").eval()
    torch.testing.assert_close(restored.lm_head.weight, head.weight, rtol=0, atol=0)
    torch.testing.assert_close(restored.lm_head.bias, head.bias, rtol=0, atol=0)
    del restored
    baseline_head = torch.nn.Linear(head.in_features, head.out_features)
    baseline_head.load_state_dict(baseline)
    results = {}
    for group, rows in groups.items():
        if not group.startswith("test_"):
            continue
        entries, _ = cache_features(model, rows, cache, model_hash, token_ids, torch, training=False)
        results[group] = {"dataset": rows[0]["dataset"], "revision": rows[0]["revision"],
                          "baseline": score(baseline_head, entries, tokens, blank, torch),
                          "selected": score(head, entries, tokens, blank, torch),
                          "by_language": {language: {
                              "baseline": score(baseline_head, [e for e in entries if e["language"] == language], tokens, blank, torch),
                              "selected": score(head, [e for e in entries if e["language"] == language], tokens, blank, torch)}
                              for language in sorted({e["language"] for e in entries})}}
    report = {"method": "CTC head adaptation; frozen encoders; CPU; FP32 features and head; whole short clips without VAD",
              "base_sha256": model_hash, "trainable_parameters": sum(p.numel() for p in head.parameters()),
              "seed": args.seed, "epochs": args.epochs, "learning_rate": args.learning_rate,
              "target_convention": "_|transcript with | word separators|_",
              "exported_head_verified": True,
              "train_clips": len(train), "dev_clips": len(dev), "skipped_train": skipped,
              "baseline_dev": baseline_dev, "history": history, "selected_epoch": best_epoch,
              "tests": results, "elapsed_seconds": round(time.monotonic() - started, 2),
              "upstream_overlap_note": "Base model already used KSC2. Tim2190 was held out from this adaptation; upstream overlap is unknown.",
              "manifest_sha256": {str(path): hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                  for path in [args.train, args.dev, *args.test]},
              "manifests": {"train": args.train, "dev": args.dev, "test": args.test}}
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
