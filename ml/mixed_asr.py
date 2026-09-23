"""Local wav2vec2 CTC adapter for alibiserikbay/kazakh-russian-mixed-stt.

Uses rukk with greedy or optional prefix beam decoding. KenLM is not loaded.
"""

from pathlib import Path
import os
import wave


def decode_words(ids: list[int], tokens: dict[int, str], blank: int,
                 start_ms: int, duration_ms: int) -> list[dict]:
    """Collapse CTC repeats while retaining approximate acoustic word intervals."""
    words, chars, first, last = [], [], 0, 0
    previous = None
    step = duration_ms / max(1, len(ids))

    def flush():
        if chars:
            words.append({"text": "".join(chars), "start_ms": round(start_ms + first * step),
                          "end_ms": round(start_ms + (last + 1) * step)})
            chars.clear()

    for frame, token_id in enumerate(ids):
        symbol = tokens.get(token_id, "")
        if token_id != blank and token_id != previous:
            if symbol in {"|", "_", " "}:
                flush()
            elif symbol:
                if not chars:
                    first = frame
                chars.append(symbol)
                last = frame
        elif token_id == previous and token_id != blank and chars:
            last = frame
        previous = token_id
    flush()
    return words


def transcribe(path: Path, model_dir: str, device: str) -> list[dict]:
    import numpy as np
    import torch
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    from .ctc import align_tokens, prefix_beam_search

    beam_size = int(os.environ.get("TALDAU_CTC_BEAM_SIZE", "1"))
    if not 1 <= beam_size <= 64:
        raise ValueError("TALDAU_CTC_BEAM_SIZE must be between 1 and 64")

    root = Path(model_dir) / "asr" / "rukk"
    if not (root / "model.pt").is_file() or not (root / "tokens.lst").is_file():
        raise RuntimeError("Mixed ASR requires asr/rukk/model.pt and tokens.lst in TALDAU_ASR_MODEL")
    tokens = {}
    for line in (root / "tokens.lst").read_text(encoding="utf-8").splitlines():
        if line.strip():
            symbol, index = line.split("\t")
            tokens[int(index)] = symbol
    blank = max(tokens) + 1
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getframerate(), stream.getsampwidth()) != (1, 16000, 2):
            raise ValueError("Mixed ASR requires mono 16 kHz PCM16 WAV")
        audio = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(np.float32) / 32768
    regions = get_speech_timestamps(audio, vad_options=VadOptions(max_speech_duration_s=15))
    if not regions:
        return []
    model = torch.jit.load(str(root / "model.pt"), map_location=device).eval()
    result = []
    with torch.inference_mode():
        for region in regions:
            start, end = region["start"], region["end"]
            chunk = torch.from_numpy(audio[start:end].copy()).unsqueeze(0).to(device)
            logits = model(chunk)[0]
            if beam_size == 1:
                ids = logits[0].argmax(-1).cpu().tolist()
            else:
                log_probs = logits[0].log_softmax(-1).cpu().numpy()
                decoded = prefix_beam_search(log_probs, blank, beam_size)
                ids = align_tokens(log_probs, decoded, blank)
            words = decode_words(ids, tokens, blank, round(start / 16), round((end - start) / 16))
            if words:
                result.append({"start_ms": words[0]["start_ms"], "end_ms": words[-1]["end_ms"],
                               "text": " ".join(w["text"] for w in words), "words": words})
    return result
