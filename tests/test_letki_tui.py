import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('letki_tui', ROOT / 'scripts/letki_tui.py')
tui = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tui
spec.loader.exec_module(tui)


class ModelTests(unittest.TestCase):
    def test_brightness_edits_are_local_and_bounds_checked(self):
        model = tui.Model()
        model.line('speed_ms=75 paused=0 uptime_ms=10 uart_errors=0 tx_dropped=0 brightness_pct=40')
        self.assertEqual(model.brightness, 40)
        self.assertIsNone(model.key('b'))
        self.assertEqual(model.editor.kind, 'brightness')
        model.editor.text = '25'
        self.assertEqual(model.key('\n'), ('brightness', 25))
        self.assertEqual(model.ex('brightness 0'), ('brightness', 0))
        with self.assertRaises(ValueError): model.ex('brightness 101')

    def test_text_typing_is_local_and_polish_editing_is_character_based(self):
        model = tui.Model()
        self.assertIsNone(model.key('i'))
        model.editor.text = ''; model.editor.cursor = 0
        for key in 'zobacz adasiu już nie świeci': self.assertIsNone(model.key(key))
        self.assertIsNone(model.paused)
        self.assertEqual(model.key('\n'), ('text', 'zobacz adasiu już nie świeci'))
        editor = tui.Editor('text', 'Adaś', 4)
        editor.key('\x7f')
        self.assertEqual(editor.text, 'Ada')
        editor.key('ś'); editor.key('\x1b'); editor.key('h'); editor.key('x')
        self.assertEqual(editor.text, 'Ada')
        self.assertEqual(editor.key('q'), 'cancel')

    def test_all_playback_features(self):
        model = tui.Model()
        model.line('speed_ms=75 paused=0 uptime_ms=10')
        for key, action in [('p','pause'), ('r','resume'), ('a','arm'), ('0','reset'),
                            ('s','status'), ('+','faster'), ('-','slower')]:
            self.assertEqual(model.key(key), (action, None))
        self.assertEqual(model.key(' '), ('pause', None))
        model.line('speed_ms=75 paused=1 uptime_ms=20')
        self.assertEqual(model.key(' '), ('resume', None))
        self.assertEqual(model.ex('clear'), ('text', ''))
        self.assertEqual(model.ex('speed 55'), ('speed', 55))
        self.assertEqual(model.key('?'), ('help', None))

    def test_frames_use_column_bytes_and_host_mode_is_explicit(self):
        model = tui.Model(); model.key('2'); model.key('l'); model.key('j'); model.key(' ')
        self.assertEqual(model.frame[1], 2)
        self.assertEqual(model.key('w'), ('frame', [0,2,0,0,0,0,0,0]))
        model.completed('frame', model.frame)
        self.assertIn('host frame', model.display_mode)
        model.key('I'); self.assertEqual(model.frame[1], 253)
        model.key('c'); self.assertEqual(model.frame, [0]*8)
        self.assertEqual(model.ex('frame 0102040810204080'), ('frame', [1,2,4,8,16,32,64,128]))
        model.completed('reset', None); self.assertIn('scroll', model.display_mode)

    def test_validation_keeps_invalid_edit_open_and_cancel_does_not_send(self):
        model = tui.Model(); model.begin('text', 'a'*65)
        self.assertIsNone(model.key('\n')); self.assertIsNotNone(model.editor)
        model.key('\x1b'); model.key('\x1b')
        self.assertIsNone(model.editor); self.assertIsNone(model.current_text)
        for command in ('speed 9', 'speed 501', 'frame 123', 'text hello\np'):
            with self.assertRaises(ValueError): model.ex(command)

    def test_navigation_and_reset_does_not_claim_old_text(self):
        model = tui.Model(); model.key('g'); model.key('t'); self.assertEqual(model.tab, 1)
        model.key('g'); model.key('T'); self.assertEqual(model.tab, 0)
        model.completed('text', 'Adaś'); self.assertEqual(model.current_text, 'ADAŚ')
        model.line('speed_ms=75 paused=0 uptime_ms=1000')
        model.line('speed_ms=75 paused=0 uptime_ms=1')
        self.assertIsNone(model.current_text)


class WorkerTests(unittest.TestCase):
    def test_confirmations_and_queued_speed_steps(self):
        link = tui.DemoLink(); worker = tui.Worker(link)
        try:
            jobs = [('text','Adaś'), ('speed',11), ('faster',None), ('faster',None),
                    ('slower',None), ('pause',None), ('resume',None), ('arm',None)]
            for request in jobs:
                self.assertTrue(worker.submit(request))
                result = worker.results.get(timeout=2)
                self.assertTrue(result[0], result)
            self.assertEqual(link.speed, 15)
            self.assertTrue(worker.submit(('brightness', 25)))
            self.assertTrue(worker.results.get(timeout=2)[0])
            self.assertEqual(link.brightness, 25)
            self.assertTrue(link.paused)
            self.assertTrue(worker.submit(('frame',[1]*8)))
            self.assertTrue(worker.results.get(timeout=2)[0])
            self.assertTrue(worker.submit(('reset',None)))
            self.assertTrue(worker.results.get(timeout=2)[0])
            self.assertFalse(link.paused)
        finally: worker.close()


class Screen:
    def __init__(self, height, width): self.height=height; self.width=width; self.rows={}
    def getmaxyx(self): return self.height,self.width
    def erase(self): self.rows={}
    def addnstr(self,y,x,text,length,style): self.rows.setdefault(y,[]).append((x,text[:length]))
    def refresh(self): pass
    def move(self,*args): pass


class RenderTests(unittest.TestCase):
    def test_uart_header_names_the_selected_transport(self):
        model = tui.Model(); model.transport_label = 'UART · ttyACM2'
        screen = Screen(24, 100)
        with patch.object(tui.curses, 'color_pair', return_value=0), patch.object(tui.curses, 'curs_set'):
            tui.render(screen, model)
        self.assertIn('UART · ttyACM2', ' '.join(text for _, text in screen.rows[0]))

    def test_tabs_help_and_small_terminal_render(self):
        model = tui.Model()
        with patch.object(tui.curses,'color_pair',return_value=0), patch.object(tui.curses,'curs_set'):
            for height,width in ((24,76),(32,120),(10,40)):
                for tab in range(3):
                    model.tab=tab
                    screen=Screen(height,width); tui.render(screen,model,True)
                    self.assertTrue(screen.rows)
                model.help=True; tui.render(screen,model,True); model.help=False


if __name__ == '__main__': unittest.main()
