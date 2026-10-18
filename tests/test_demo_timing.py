import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from demo_timing import scene_timing


class TimingTests(unittest.TestCase):
    def test_short_speech_does_not_accelerate_display(self):
        steps, scroll, delay, total = scene_timing("ZOBACZ", 75, .7)
        self.assertEqual(steps, 52)
        self.assertEqual(scroll, 3.9)
        self.assertEqual(delay, .45)
        self.assertEqual(total, 3.9)

    def test_long_speech_is_not_truncated(self):
        _, scroll, delay, total = scene_timing("ADAŚ", 30, 3)
        self.assertEqual(scroll, 1.08)
        self.assertEqual(total, 3 + delay)

    def test_speed_changes_preserve_display_geometry(self):
        slow = scene_timing("DZIAŁA", 75, 1)
        fast = scene_timing("DZIAŁA", 30, 1)
        self.assertEqual(slow[0], fast[0])
        self.assertAlmostEqual(slow[1] / fast[1], 2.5)

    def test_limits(self):
        for text, duration in [("", 1), ("A" * 65, 1), ("A", 0), ("A", float("nan"))]:
            with self.assertRaises(ValueError):
                scene_timing(text, 30, duration)
        for interval in [9, 501, 10.5]:
            with self.assertRaises(ValueError):
                scene_timing("A", interval, 1)


if __name__ == "__main__":
    unittest.main()
