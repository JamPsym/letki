"""Long-running PC streaming keeps bounded diagnostic memory."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from general_link import Driver,Simulation
from letki_general import stream
from general_program import compile_show

class StreamTest(unittest.TestCase):
    def test_stream_preserves_active_flash_show_and_play_resumes_without_writes(self):
        simulation=Simulation();driver=Driver(simulation);clock=[0.0]
        def monotonic():clock[0]+=.02;return clock[0]
        try:
            program=compile_show(dict(duration_ms=1000,tracks=[dict(type='fill',levels=[30,30])]))
            driver.load(program,storage='flash',replace='capacity')
            operations=simulation.lib.lg_sim_operations(simulation.context)
            with patch('letki_general.time.monotonic',side_effect=monotonic),patch('letki_general.time.sleep'),patch('letki_general.pwm_pixels',return_value=[bytes(64)]*5):
                report=stream(driver,dict(source='pwm-show',duration_ms=1000),fps=10)
            self.assertTrue(report['persistent_program_retained'])
            self.assertEqual(simulation.lib.lg_sim_operations(simulation.context),operations)
            self.assertTrue(all(driver.read(i)==program for i in range(5)))
            driver.play(lead=0);self.assertEqual(simulation.advance(10),[bytes([30])*64]*5)
        finally:simulation.close()
    def test_loaded_audio_rejects_stale_shared_clock_before_audio_starts(self):
        from general_audio import play_audio
        driver=SimpleNamespace(load=lambda *args:None,clocks={0:dict(clock_age_ms=65535)})
        sound=SimpleNamespace(OutputStream=lambda **kwargs: self.fail('Opened audio with stale clock'))
        file=SimpleNamespace(read=lambda *args,**kwargs:(None,48000))
        with patch.dict(sys.modules,dict(sounddevice=sound,soundfile=file)):
            with self.assertRaisesRegex(RuntimeError,'Stale I2C clock'):
                play_audio(driver,dict(duration_ms=1,tracks=[]),'unused.wav')
    def test_long_show_retains_bounded_samples_and_all_run_totals(self):
        simulation=Simulation();driver=Driver(simulation);clock=[0.0]
        def monotonic():
            clock[0]+=.01
            return clock[0]
        try:
            with patch('letki_general.time.monotonic',side_effect=monotonic),patch('letki_general.time.sleep'),patch('letki_general.pwm_pixels',return_value=[bytes(64)]*5):
                report=stream(driver,dict(source='pwm-show',duration_ms=100000),fps=50)
            self.assertEqual(report['status'],'completed')
            self.assertGreater(report['frame_count'],4096)
            self.assertEqual(len(report['frames']),4096)
            self.assertEqual(report['late_uploads'],0)
            self.assertEqual(report['audio_warning_count'],0)
            self.assertEqual(report['frames'][-1]['frame']+1,report['frame_count'])
        finally:simulation.close()

if __name__=='__main__':unittest.main()
