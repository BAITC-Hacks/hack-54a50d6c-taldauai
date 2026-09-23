import itertools
import math
import unittest
from collections import defaultdict

from ml.ctc import align_tokens, prefix_beam_search

try:
    import numpy as np
except ImportError:
    np = None


def collapse(path, blank):
    return tuple(token for i, token in enumerate(path)
                 if token != blank and (i == 0 or token != path[i - 1]))


@unittest.skipIf(np is None, "Install ML dependencies to test acoustic alignment")
class CTCTests(unittest.TestCase):
    def test_beam_and_alignment_match_exhaustive_search(self):
        rng = np.random.default_rng(42)
        for _ in range(15):
            probs = rng.dirichlet([1, 1, 1], size=4)
            log_probs = np.log(probs)
            totals, best_paths = defaultdict(float), {}
            for path in itertools.product(range(3), repeat=4):
                label = collapse(path, 2)
                probability = math.prod(probs[t, token] for t, token in enumerate(path))
                totals[label] += probability
                best_paths[label] = max(best_paths.get(label, 0), probability)
            expected = max(totals, key=totals.get)
            decoded = prefix_beam_search(log_probs, 2, width=64)
            self.assertEqual(decoded, expected)
            aligned = align_tokens(log_probs, decoded, 2)
            self.assertEqual(collapse(aligned, 2), decoded)
            score = math.prod(probs[t, token] for t, token in enumerate(aligned))
            self.assertAlmostEqual(score, best_paths[decoded])

    def test_repeated_letters_require_blank(self):
        probs = np.log([[0.99, 0.01], [0.01, 0.99], [0.99, 0.01]])
        decoded = prefix_beam_search(probs, 1, width=8)
        self.assertEqual(decoded, (0, 0))
        self.assertEqual(align_tokens(probs, decoded, 1), [0, 1, 0])
        with self.assertRaises(ValueError):
            align_tokens(probs[:2], (0, 0), 1)

    def test_silence_and_empty_audio(self):
        probs = np.log([[0.01, 0.99]] * 10)
        self.assertEqual(prefix_beam_search(probs, 1), ())
        self.assertEqual(align_tokens(probs, (), 1), [1] * 10)
        self.assertEqual(prefix_beam_search(np.empty((0, 2)), 1), ())
        self.assertEqual(align_tokens(np.empty((0, 2)), (), 1), [])


if __name__ == "__main__":
    unittest.main()
