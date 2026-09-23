from io import BytesIO
import unittest

from training.adapt_ctc import check_disjoint, encode_reference
from training.prepare_corpora import LimitedReader, clean_reference, member_key, pilot_split


class TrainingTests(unittest.TestCase):
    def test_test_audio_cannot_leak_into_training(self):
        with self.assertRaisesRegex(ValueError, "leakage"):
            check_disjoint({"train": [{"sha256": "same"}], "test": [{"sha256": "same"}]})
        check_disjoint({"train": [{"sha256": "a"}], "dev": [{"sha256": "b"}]})

    def test_ctc_targets_keep_kazakh_letters_and_reject_unsupported_digits(self):
        tokens = {"қ": 0, "а": 1, "з": 2, "|": 3, "_": 4}
        self.assertEqual(encode_reference("ҚАЗ, қазақ!", tokens), [4, 3, 0, 1, 2, 3, 0, 1, 2, 1, 0, 3, 4])
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            encode_reference("қаз 2026", tokens)

    def test_archive_split_mapping_and_unsafe_paths(self):
        self.assertEqual(member_key("ISSAI_KSC2/Train/radio/a.flac")[0], "train")
        self.assertEqual(member_key("ISSAI_KSC2/Valid/radio/a.txt")[0], "dev")
        self.assertEqual(member_key("ISSAI_KSC2/Test/radio/a.txt")[0], "test")
        self.assertIsNone(member_key("/ISSAI_KSC2/Train/radio/a.txt"))
        self.assertIsNone(member_key("ISSAI_KSC2/Train/../../a.txt"))
        self.assertEqual(pilot_split("test", "a"), "test")
        self.assertIsNone(pilot_split("dev", "a"))
        for index in range(30):
            stem = f"ISSAI_KSC2/Train/radio/{index}"
            self.assertIn(pilot_split("train", stem), {"train", "dev"})
            self.assertEqual(pilot_split("train", stem), pilot_split("train", stem))

    def test_annotation_cleanup_and_download_budget(self):
        self.assertEqual(clean_reference("шы-[false_start] шықты"), "шы- шықты")
        reader = LimitedReader(BytesIO(b"123456"), 4)
        self.assertEqual(reader.read(10), b"1234")
        with self.assertRaisesRegex(RuntimeError, "limit"):
            reader.read(1)


if __name__ == "__main__":
    unittest.main()
