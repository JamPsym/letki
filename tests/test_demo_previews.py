"""Check explicit blackout handling without requiring media or hardware."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_demo_previews import longest_unintended_blackout

class Blackouts(unittest.TestCase):
    def test_declared_silent_tail(self):
        show = {'intro_seconds': 0, 'cues': [{'at': 2, 'duration': 10, 'effect': 'bells-monoliths', 'level': 0}]}
        self.assertEqual(longest_unintended_blackout(show, [0]*120, 10), 2)
    def test_unplanned_blackout_is_not_hidden(self):
        show = {'intro_seconds': 0, 'cues': [{'at': 8, 'duration': 4, 'effect': 'bells-monoliths', 'level': 0}]}
        self.assertEqual(longest_unintended_blackout(show, [0]*120, 10), 8)
    def test_intro_and_text_do_not_authorize_other_darkness(self):
        show = {'intro_seconds': 1, 'cues': [{'at': 0, 'duration': 9, 'text': 'TITLE', 'level': 0}]}
        self.assertEqual(longest_unintended_blackout(show, [0]*100, 10), 9)
    def test_lit_frames_split_dark_runs(self):
        self.assertEqual(longest_unintended_blackout({'cues': []}, [0]*20+[1]+[0]*30, 10), 3)

if __name__ == '__main__': unittest.main()
