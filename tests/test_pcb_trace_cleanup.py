"""Native safety regressions; run with .tools/kicad-routing-env/bin/python."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pcb_trace_cleanup as cleanup
import pcbnew


class SourcePreservation(unittest.TestCase):
    def test_quoted_parentheses_do_not_change_spans(self):
        text = '(kicad_pcb (version 1) (property "a (b)" "c \\\" d") (segment (uuid "old")))'
        self.assertEqual([x[2] for x in cleanup.blocks(text)], ['version', 'property', 'segment'])

    def test_preservation_rejects_unrelated_metadata_change(self):
        before = '(kicad_pcb (property "owner" "human") (segment (uuid "old")))'
        after = '(kicad_pcb (property "owner" "agent") (segment (uuid "new")))'
        with self.assertRaisesRegex(AssertionError, 'Unrelated authored'):
            cleanup.preserve(before, after, {'old'}, {'new'})

    def test_refill_is_allowed_but_zone_definition_change_is_not(self):
        before = '(kicad_pcb (zone (net "GND") (clearance 0.2) (filled_polygon (pts (xy 1 2)))))'
        after = before.replace('(xy 1 2)', '(xy 2 3)')
        cleanup.preserve(before, after, set(), set())
        with self.assertRaises(AssertionError):
            cleanup.preserve(before, after.replace('0.2', '0.1'), set(), set())


class NativeTopology(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        board = pcbnew.BOARD()
        net = pcbnew.NETINFO_ITEM(board, '/SIG'); board.Add(net)
        points = [(0, 0), (1000000, 0), (1000000, 1000000),
                  (2000000, 1000000), (2000000, 2000000)]
        ids = []
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(*start)); track.SetEnd(pcbnew.VECTOR2I(*end))
            track.SetLayer(pcbnew.F_Cu); track.SetWidth(150000); track.SetNet(net)
            board.Add(track); ids.append(track.m_Uuid.AsString())
        anchors = []
        for point in (points[0], points[-1]):
            via = pcbnew.PCB_VIA(board); via.SetPosition(pcbnew.VECTOR2I(*point))
            via.SetWidth(600000); via.SetDrill(300000); via.SetNet(net)
            board.Add(via); anchors.append(via.m_Uuid.AsString())
        self.before = self.root / 'before.kicad_pcb'; pcbnew.SaveBoard(str(self.before), board)
        self.patch = dict(chain=dict(ids=ids, points=points, anchors=anchors,
            layer=pcbnew.F_Cu, width=150000, net='/SIG'), removed=ids,
            added=[dict(uuid=str(uuid.uuid4()), start=list(points[0]), end=list(points[-1]),
                        width=150000, layer='F.Cu', net='/SIG')])
        self.after = self.root / 'after.kicad_pcb'
        self.after.write_text(cleanup.apply_text(self.before.read_text(), self.patch))

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_shortcut_keeps_fixed_anchors(self):
        report = cleanup.audit(self.before, self.after, self.patch)
        self.assertEqual(report['segments_after'], 1)
        self.assertEqual(report['preserved_vias'], 2)

    def test_rejects_new_same_net_contact_even_though_connected(self):
        # Both boards contain the same third via. Only the new diagonal touches it.
        board = pcbnew.LoadBoard(str(self.before)); via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(500000, 500000)); via.SetWidth(600000)
        via.SetDrill(300000); via.SetNet(board.FindNet('/SIG'))
        board.Add(via); uid = via.m_Uuid.AsString()
        pcbnew.SaveBoard(str(self.before), board)
        raw = next(raw for _, _, tag, raw in cleanup.blocks(self.before.read_text())
                   if tag == 'via' and cleanup.block_uuid(raw) == uid)
        text = self.after.read_text(); end = text.rfind(')')
        self.after.write_text(text[:end] + raw + '\n' + text[end:])
        with self.assertRaisesRegex(AssertionError, 'External contact'):
            cleanup.audit(self.before, self.after, self.patch)

    def test_sibling_meeting_inside_fixed_terminal_is_allowed(self):
        board = pcbnew.LoadBoard(str(self.before)); track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(0, 0)); track.SetEnd(pcbnew.VECTOR2I(-1000000, 0))
        track.SetLayer(pcbnew.F_Cu); track.SetWidth(150000); track.SetNet(board.FindNet('/SIG'))
        board.Add(track); uid = track.m_Uuid.AsString()
        pcbnew.SaveBoard(str(self.before), board)
        raw = next(raw for _, _, tag, raw in cleanup.blocks(self.before.read_text())
                   if tag == 'segment' and cleanup.block_uuid(raw) == uid)
        text = self.after.read_text(); end = text.rfind(')')
        self.after.write_text(text[:end] + raw + '\n' + text[end:])
        self.assertEqual(cleanup.audit(self.before, self.after, self.patch)['status'], 'PASS')

    def test_reroute_cannot_request_unbounded_length_increase(self):
        patch = dict(self.patch, max_length_increase_mm=1.0)
        with self.assertRaisesRegex(AssertionError, 'Excessive length allowance'):
            cleanup.audit(self.before, self.after, patch)

    def test_rejects_endpoint_rounding_or_movement(self):
        patch = json.loads(json.dumps(self.patch)); patch['added'][0]['end'][0] += 1
        self.after.write_text(cleanup.apply_text(self.before.read_text(), patch))
        with self.assertRaises(AssertionError):
            cleanup.audit(self.before, self.after, patch)


class ApplicationGuards(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        import shutil
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.project = self.root / 'project'; self.project.mkdir()
        self.source = self.project / 'test.kicad_pcb'
        self.source.write_text('(kicad_pcb (property "owner" "human") (segment (uuid "old")))')
        self.work = self.root / 'run'; self.work.mkdir()
        shutil.copytree(self.project, self.work / 'initial')
        shutil.copytree(self.project, self.work / 'current')
        self.final = self.work / 'current/test.kicad_pcb'
        self.final.write_text(self.source.read_text().replace('"old"', '"new"'))
        self.trial = self.work / 'trial-000'; self.trial.mkdir()
        self.image = self.trial / 'comparison.png'; self.image.write_bytes(b'reviewed pixels')
        cleanup.write_json(self.trial / 'patch.json', {'removed':['old'], 'added':[{'uuid':'new'}]})
        cleanup.write_json(self.trial / 'report.json', {'status':'CHECKED_CANDIDATE'})
        cleanup.write_json(self.work / 'source.json', {'board':str(self.source)})
        cleanup.write_json(self.work / 'report.json', {'input_sha256':cleanup.digest(self.source),
            'final_sha256':cleanup.digest(self.final), 'accepted_trials':[str(self.trial)]})
        self.review = self.root / 'review.json'
        cleanup.write_json(self.review, {'run':str(self.work), 'status':'VISUALLY_REVIEWED',
            'images':{str(self.trial):cleanup.digest(self.image)}})
        self.args = SimpleNamespace(run=self.work, review=self.review)

    def tearDown(self):
        self.temp.cleanup()

    def test_stale_source_is_never_overwritten(self):
        self.source.write_text(self.source.read_text() + '\n')
        before = self.source.read_bytes()
        with self.assertRaisesRegex(AssertionError, 'Source has changed'):
            cleanup.apply_reviewed(self.args)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse((self.work / 'source-before-apply.kicad_pcb').exists())

    def test_changed_review_image_is_never_applied(self):
        before = self.source.read_bytes(); self.image.write_bytes(b'new pixels')
        with self.assertRaisesRegex(AssertionError, 'Reviewed image changed'):
            cleanup.apply_reviewed(self.args)
        self.assertEqual(self.source.read_bytes(), before)

    def test_checked_patch_has_exact_backup_and_preserves_metadata(self):
        before = self.source.read_bytes(); cleanup.apply_reviewed(self.args)
        self.assertEqual((self.work / 'source-before-apply.kicad_pcb').read_bytes(), before)
        self.assertEqual(self.source.read_bytes(), self.final.read_bytes())
        self.assertIn('"owner" "human"', self.source.read_text())


if __name__ == '__main__':
    unittest.main()
