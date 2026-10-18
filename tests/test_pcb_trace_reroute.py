"""Native fixtures for genuine A* rerouting, independent of old paths and pours."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import test_pcb_trace_cleanup as fixtures
import pcb_trace_reroute as rr
import pcbnew
from shapely.geometry import LineString, box


class FreshRouter(unittest.TestCase):
    def setUp(self):
        fixtures.NativeTopology.setUp(self)
        board = pcbnew.LoadBoard(str(self.before))
        points = [(-2000000,-2000000),(5000000,-2000000),(5000000,5000000),(-2000000,5000000)]
        for start, end in zip(points, points[1:]+points[:1]):
            edge = pcbnew.PCB_SHAPE(board); edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
            edge.SetStart(pcbnew.VECTOR2I(*start)); edge.SetEnd(pcbnew.VECTOR2I(*end))
            edge.SetLayer(pcbnew.Edge_Cuts); edge.SetWidth(50000); board.Add(edge)
        pcbnew.SaveBoard(str(self.before), board)
        self.before.with_suffix('.kicad_pro').write_text(json.dumps({'board':{'design_settings':{'rules':{'min_copper_edge_clearance':.2}}}}))
        self.chain = dict(self.patch['chain'],layer_name='F.Cu',length_mm=4.0)

    def tearDown(self):
        fixtures.NativeTopology.tearDown(self)

    def geometry(self, patch):
        return [(s['start'],s['end']) for s in patch['added']]

    def test_old_chain_is_absent_from_search(self):
        original = self.before.read_bytes(); first = rr.reroute(self.before,self.chain)
        self.assertEqual(self.before.read_bytes(),original)
        self.assertEqual(len(first['added']),1)
        board = pcbnew.LoadBoard(str(self.before)); tracks={t.m_Uuid.AsString():t for t in board.GetTracks()}
        changed=[(0,0),(0,1000000),(1000000,1000000),(1000000,2000000),(2000000,2000000)]
        for uid,a,b in zip(self.chain['ids'],changed,changed[1:]):
            tracks[uid].SetStart(pcbnew.VECTOR2I(*a));tracks[uid].SetEnd(pcbnew.VECTOR2I(*b))
        pcbnew.SaveBoard(str(self.before),board)
        other=dict(self.chain,points=changed)
        second=rr.reroute(self.before,other)
        self.assertEqual(self.geometry(first),self.geometry(second))
        self.after.write_text(rr.safety.apply_text(self.before.read_text(),second))
        self.assertEqual(rr.safety.audit(self.before,self.after,second)['status'],'PASS')

    def add_zone(self,keepout=False):
        board=pcbnew.LoadBoard(str(self.before));zone=pcbnew.ZONE(board)
        zone.SetLayer(pcbnew.F_Cu);zone.SetIsRuleArea(keepout)
        if keepout:zone.SetDoNotAllowTracks(True)
        else:
            net=pcbnew.NETINFO_ITEM(board,'OTHER');board.Add(net);zone.SetNet(net)
        outline=zone.Outline();outline.NewOutline()
        coords=[(.5,.5),(1.5,.5),(1.5,1.5),(.5,1.5)] if keepout else [(-1,-1),(3,-1),(3,3),(-1,3)]
        for x,y in coords:outline.Append(round(x*1e6),round(y*1e6))
        board.Add(zone);uid=zone.m_Uuid.AsString();pcbnew.SaveBoard(str(self.before),board)
        return uid

    def test_actual_foreign_fill_is_not_a_routing_obstacle(self):
        uid=self.add_zone()
        text=self.before.read_text()
        start,end,_,raw=next(b for b in rr.safety.blocks(text) if b[2]=='zone' and rr.safety.block_uuid(b[3])==uid)
        fill='(filled_polygon (layer "F.Cu") (pts (xy -1 -1) (xy 3 -1) (xy 3 3) (xy -1 3)))'
        self.before.write_text(text[:start]+raw[:-1]+fill+')'+text[end:])
        loaded=pcbnew.LoadBoard(str(self.before))
        self.assertGreater(next(iter(loaded.Zones())).GetFilledPolysList(pcbnew.F_Cu).OutlineCount(),0)
        patch=rr.reroute(self.before,self.chain)
        self.assertEqual(len(patch['added']),1)
        self.assertFalse(patch['router']['pours_in_search'])

    def test_authored_track_keepout_remains_an_obstacle(self):
        self.add_zone(keepout=True);patch=rr.reroute(self.before,self.chain)
        points=[patch['added'][0]['start']]+[s['end'] for s in patch['added']]
        line=LineString([(x/1e6,y/1e6) for x,y in points])
        self.assertGreaterEqual(line.distance(box(.5,.5,1.5,1.5)),.075-.000001)
        self.assertGreater(len(patch['added']),1)


if __name__=='__main__':unittest.main()
