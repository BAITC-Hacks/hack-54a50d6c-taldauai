"""CTC prefix beam search and acoustic Viterbi alignment (no language model).

Algorithm background: https://distill.pub/2017/ctc/
"""

import math


def _logadd(a: float, b: float) -> float:
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    return max(a, b) + math.log1p(math.exp(-abs(a - b)))


def prefix_beam_search(log_probs, blank: int, width: int = 8) -> tuple[int, ...]:
    """Sum blank/nonblank paths per prefix; prune prefixes and frame tokens.

    Inputs are normalized log probabilities with shape [frames, vocabulary].
    Width >= vocabulary considers every token at each frame. Smaller widths
    additionally prune frame candidates, while always retaining the blank.
    """
    if not 1 <= width <= 64:
        raise ValueError("CTC beam width must be between 1 and 64")
    beam = {(): (0.0, -math.inf)}
    for row in log_probs:
        candidates = sorted(set(sorted(range(len(row)), key=lambda i: row[i])[-width:]) | {blank})
        next_beam = {}
        for prefix, (p_blank, p_token) in beam.items():
            total = _logadd(p_blank, p_token)
            a, b = next_beam.get(prefix, (-math.inf, -math.inf))
            next_beam[prefix] = (_logadd(a, total + float(row[blank])), b)
            for token in candidates:
                if token == blank:
                    continue
                score = float(row[token])
                if prefix and token == prefix[-1]:
                    a, b = next_beam.get(prefix, (-math.inf, -math.inf))
                    next_beam[prefix] = (a, _logadd(b, p_token + score))
                    # Repeating a letter requires an intervening blank.
                    total_for_extension = p_blank
                else:
                    total_for_extension = total
                extended = prefix + (token,)
                a, b = next_beam.get(extended, (-math.inf, -math.inf))
                next_beam[extended] = (a, _logadd(b, total_for_extension + score))
        beam = dict(sorted(next_beam.items(), key=lambda item: _logadd(*item[1]), reverse=True)[:width])
    return max(beam, key=lambda prefix: _logadd(*beam[prefix]))


def align_tokens(log_probs, tokens: tuple[int, ...], blank: int) -> list[int]:
    """Return a highest-scoring frame path collapsing to exactly tokens."""
    import numpy as np

    frames = len(log_probs)
    if not frames:
        if tokens:
            raise ValueError("Cannot align tokens without acoustic frames")
        return []
    labels = np.full(2 * len(tokens) + 1, blank, dtype=np.int64)
    labels[1::2] = tokens
    scores = np.full(len(labels), -np.inf)
    scores[0] = log_probs[0, blank]
    if tokens:
        scores[1] = log_probs[0, tokens[0]]
    back = np.zeros((frames, len(labels)), dtype=np.int8)
    can_skip = np.zeros(len(labels), dtype=bool)
    can_skip[2:] = (labels[2:] != blank) & (labels[2:] != labels[:-2])
    for t in range(1, frames):
        moves = np.full((3, len(labels)), -np.inf)
        moves[0] = scores
        moves[1, 1:] = scores[:-1]
        moves[2, 2:] = scores[:-2]
        moves[2, ~can_skip] = -np.inf
        back[t] = moves.argmax(axis=0)
        scores = moves.max(axis=0) + log_probs[t, labels]
    end_states = [len(labels) - 1] + ([len(labels) - 2] if tokens else [])
    state = max(end_states, key=lambda s: scores[s])
    if not np.isfinite(scores[state]):
        raise ValueError("No valid CTC alignment for decoded tokens")
    path = [blank] * frames
    for t in range(frames - 1, -1, -1):
        path[t] = int(labels[state])
        if t:
            state -= int(back[t, state])
    return path
