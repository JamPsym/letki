import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('player_words',Path(__file__).resolve().parents[1]/'scripts/player_words.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class Words(unittest.TestCase):
    def test_absolute_source_times_and_confidence(self):
        s=w.checked_segment({'start':1,'end':3,'text':'Grand piano','no_speech_prob':.1,'avg_logprob':-.1,'words':[{'word':'Grand','start':1,'end':1.5,'probability':.95},{'word':'piano','start':1.6,'end':3,'probability':.9}]},100,160)
        self.assertEqual(s['words'][0]['start'],101)
        self.assertEqual(s['end'],103);self.assertEqual(s['flags'],[])
        s=w.checked_segment({'start':0,'end':3,'text':'music','no_speech_prob':.9,'avg_logprob':-3},0,5)
        self.assertIn('possible_music_or_silence',s['flags'])
    def test_groups_fit_whole_strip(self):
        words=[dict(word=x,start=i*.5,end=i*.5+.4,probability=.9) for i,x in enumerate('Grand piano reed and pipe organ tubular bells'.split())]
        groups=w.cue_groups(words)
        self.assertGreater(len(groups),1)
        self.assertTrue(all(w.width(' '.join(x['word'] for x in group))<=40 for group in groups))
        self.assertEqual(w.clean_text('Zażółć, gęślą jaźń!'),'ZAŻÓŁĆ GĘŚLĄ JAŹŃ')
    def test_srt_clock(self):
        self.assertEqual(w.timestamp(3723.045),'01:02:03,045')
    def test_compile_and_recording_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'audio.wav').write_bytes(b'exact recording');(p/'show.json').write_text(json.dumps({'name':'test','audio':'audio.wav'}))
            segment=dict(id=0,start=10,end=12,text='Grand piano',flags=[],reviewed=False,words=[dict(word='Grand',start=10,end=11,probability=.9),dict(word='piano',start=11,end=12,probability=.9)])
            report=dict(schema=w.SCHEMA,sha256=w.digest(p/'audio.wav'),segments=[segment]);w.save(p/'words.json',report)
            args=argparse.Namespace(transcript=p/'words.json',show=p/'show.json',output=p/'derived.json',segment=None,reviewed_only=False,min_probability=.6,phrases=False,lead=.1,tail=.5,hold=1.2)
            w.cues(args);result=w.read_json(args.output)
            self.assertEqual(result['cues'][0]['at'],9.9);self.assertEqual(result['cues'][0]['mode'],'center');self.assertEqual(result['cues'][0]['text'],'GRAND PIANO')
            args.reviewed_only=True;w.cues(args);self.assertEqual(w.read_json(args.output)['cues'],[])
            (p/'audio.wav').write_bytes(b'wrong version')
            with self.assertRaises(ValueError):w.cues(args)
if __name__=='__main__':unittest.main()
