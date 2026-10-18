import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('qualify',Path(__file__).resolve().parents[1]/'scripts/v3_1_qualify.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)


class Link:
    def __init__(self,profile=q.PROFILE,fail_frame=False):
        self.profile=profile;self.fail_frame=fail_frame;self.actions=[]
    def send(self,command):self.actions.append(('send',command));return command
    def wait(self,marker,*args):
        return self.profile if marker=='hw' else 'speed_ms=75 paused=0 uptime_ms=1 uart_errors=0 tx_dropped=0 brightness_pct=0'
    def set_brightness(self,value):self.actions.append(('brightness',value))
    def set_frame(self,value):
        self.actions.append(('frame',bytes(value)))
        if self.fail_frame and any(value):raise RuntimeError('simulated frame failure')


class QualificationTests(unittest.TestCase):
    def test_wrong_profile_cannot_change_display(self):
        link=Link('ordinary v3')
        with self.assertRaises(RuntimeError):q.exercise(link,q.patterns('all'),100,.1,sleep=lambda _:None)
        self.assertEqual(link.actions,[('send','hw')])

    def test_transport_failure_requests_blank_after_identity(self):
        link=Link(fail_frame=True)
        with self.assertRaises(RuntimeError):q.exercise(link,q.patterns('all'),100,.1,sleep=lambda _:None)
        self.assertEqual(link.actions[-2:],[('brightness',0),('frame',bytes(8))])

    def test_walk_exercises_all_positions_and_finishes_blank(self):
        frames=q.patterns('walk')
        self.assertEqual(len({frame for _,frame in frames}),64)
        self.assertTrue(all(sum(v.bit_count() for v in frame)==1 for _,frame in frames))
        link=Link();report=q.exercise(link,frames,25,.1,sleep=lambda _:None)
        self.assertEqual(report['patterns_exercised'],64)
        self.assertEqual(link.actions[-2:],[('brightness',0),('frame',bytes(8))])


if __name__=='__main__':unittest.main()
