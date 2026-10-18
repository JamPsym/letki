#!/usr/bin/env python3
"""Check board containment, edge-contact orientation and regular LED geometry.

Independent of the placement generator. KiCad DRC must also run: a green DRC
alone did not catch the mirrored contact array extending outside the outline.
"""
import argparse
import json
import math
from pathlib import Path
import pcbnew

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcb',nargs='?',type=Path,default=ROOT/'hw/ledkiv4/ledkiv4.kicad_pcb')
    args=parser.parse_args();board=pcbnew.LoadBoard(str(args.pcb))
    assert board.GetCopperLayerCount()==4
    polygon=pcbnew.SHAPE_POLY_SET()
    assert board.GetBoardPolygonOutlines(polygon,False),'Outline missing or invalid; do not infer it'
    assert polygon.OutlineCount()==1,'Unexpected disconnected outlines'
    outline=polygon.BBox();lo=pcbnew.ToMM(outline.GetOrigin());hi=pcbnew.ToMM(outline.GetEnd())
    assert all(abs(a-b)<.01 for a,b in zip((*lo,*hi),(0,0,40.64,49.27))), (lo,hi)
    fps={f.GetReference():f for f in board.GetFootprints()}
    assert len(fps)==len(list(board.GetFootprints())),'Duplicate footprint references'
    count=0
    for ref,f in fps.items():
        for p in f.Pads():
            box=p.GetBoundingBox();a=pcbnew.ToMM(box.GetOrigin());z=pcbnew.ToMM(box.GetEnd())
            # Include unnumbered mechanical holes and all copper pads.
            assert a[0]>=lo[0]-.001 and a[1]>=lo[1]-.001 and z[0]<=hi[0]+.001 and z[1]<=hi[1]+.001,(ref,p.GetNumber(),a,z,'outside outline')
            if p.GetNumber():
                clearance=min(a[0]-lo[0],a[1]-lo[1],hi[0]-z[0],hi[1]-z[1])
                assert clearance>=.199,(ref,p.GetNumber(),clearance,'edge copper margin')
            count+=1
    def pad(ref,num):return next(p for p in fps[ref].Pads() if p.GetNumber()==str(num))
    mechanics=json.loads((ROOT/'config/v4-mechanics.json').read_text())
    wire=mechanics['edge_wire']
    for ref,x in (('J3',1.05),('J1',39.59)):
        assert fps[ref].GetLayer()==pcbnew.B_Cu
        for number in range(1,8):
            paired=[p for p in fps[ref].Pads() if p.GetNumber()==str(number)]
            assert len(paired)==2,'One rear land and one separate plated wire hole per contact'
            p=next(p for p in paired if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD)
            actual=pcbnew.ToMM(p.GetPosition());expected=(x,13.97+(number-1)*2.54)
            hole=next(p for p in paired if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH)
            hole_xy=wire['left_holes_mm' if ref=='J3' else 'right_holes_mm'][number-1]
            assert all(abs(a-b)<1e-4 for a,b in zip(pcbnew.ToMM(hole.GetPosition()),hole_xy))
            assert all(abs(v-.8)<1e-4 for v in pcbnew.ToMM(hole.GetDrillSize()))
            assert all(abs(v-1.3)<1e-4 for v in pcbnew.ToMM(hole.GetSize()))
            assert hole.GetNetname()==p.GetNetname()
            # Same-number pads can imply a component-internal connection in CAD.
            # Require an actual >=0.6 mm rear copper path for these bare pads.
            links=[t for t in board.GetTracks() if not isinstance(t,pcbnew.PCB_VIA)
                   and t.GetLayer()==pcbnew.B_Cu and t.GetNetCode()==p.GetNetCode()
                   and t.GetWidth()>=pcbnew.FromMM(.6)-1]
            start=tuple(pcbnew.ToMM(hole.GetPosition()));goal=tuple(pcbnew.ToMM(p.GetPosition()))
            pending=[start];seen=set();reached=False
            while pending:
                node=pending.pop()
                if node in seen:continue
                seen.add(node)
                if math.dist(node,goal)<.002:reached=True;break
                for t in links:
                    a=tuple(pcbnew.ToMM(t.GetStart()));z=tuple(pcbnew.ToMM(t.GetEnd()))
                    dx,dy=z[0]-a[0],z[1]-a[1];length2=dx*dx+dy*dy
                    fraction=max(0,min(1,((node[0]-a[0])*dx+(node[1]-a[1])*dy)/length2)) if length2 else 0
                    if math.hypot(node[0]-a[0]-fraction*dx,node[1]-a[1]-fraction*dy)<.002:
                        pending.extend((a,z))
            assert reached,(ref,number,'wire hole has no explicit wide rear copper path')
            assert not hole.IsOnLayer(pcbnew.F_Paste) and not hole.IsOnLayer(pcbnew.B_Paste)
            assert all(abs(a-b)<1e-4 for a,b in zip(actual,expected)),(ref,number,actual,expected)
        assert pad(ref,1).GetNetname()=='VCC' and pad(ref,2).GetNetname()=='VCC'
        assert pad(ref,3).GetNetname()=='/SDA' and pad(ref,4).GetNetname()=='/SCL'
        assert pad(ref,6).GetNetname()=='GND' and pad(ref,7).GetNetname()=='GND'
    assert pad('J1',5).GetNetname()=='/UTX' and pad('J3',5).GetNetname()=='/URX'
    for point in mechanics['testpoints']:
        ref=point['ref'];f=fps[ref];pins=list(f.Pads());assert len(pins)==1
        p=pins[0];assert f.GetLayer()==pcbnew.B_Cu and p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD
        assert p.GetNetname()==point['net']
        assert all(abs(a-b)<1e-4 for a,b in zip(pcbnew.ToMM(p.GetPosition()),point['xy_mm']))
        assert all(abs(v-1)<1e-4 for v in pcbnew.ToMM(p.GetSize()))
        assert not p.IsOnLayer(pcbnew.B_Paste) and p.IsOnLayer(pcbnew.B_Mask)
        labels=[g for g in board.GetDrawings() if isinstance(g,pcbnew.PCB_TEXT) and g.GetLayer()==pcbnew.B_SilkS and g.GetText()==ref[2:]]
        assert len(labels)==1 and labels[0].IsMirrored(),(ref,'numeric probe legend missing')
        assert all(abs(a-b)<1e-4 for a,b in zip(pcbnew.ToMM(labels[0].GetPosition()),point['silk_xy_mm']))
    assert fps['J2'].GetLayer()==pcbnew.B_Cu
    assert len(list(fps['J2'].Pads()))==6,'Header and three bare test pads required'
    for number,netname in enumerate(('+3V3','/SWDIO','GND'),1):
        paired=[p for p in fps['J2'].Pads() if p.GetNumber()==str(number)]
        assert len(paired)==2 and all(p.GetNetname()==netname for p in paired)
        through=next(p for p in paired if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH)
        test=next(p for p in paired if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD)
        expected=(7.62+(number-1)*1.25,46.75)
        assert all(abs(a-b)<1e-4 for a,b in zip(pcbnew.ToMM(through.GetPosition()),expected))
        assert all(abs(a-b)<1e-4 for a,b in zip(pcbnew.ToMM(test.GetPosition()),mechanics['swio_test_pads_mm'][number-1]))
        assert all(abs(v-.6)<1e-4 for v in pcbnew.ToMM(through.GetDrillSize())),'Prototype hole allowance for regular fabrication tolerance'
        assert all(abs(a-b)<1e-4 for a,b in zip(pcbnew.ToMM(through.GetSize()),(1,1.4)))
    # Check the fastener envelope independently of the drill clearance rule.
    # This includes exposed copper on either face and other mechanical holes.
    for index,point in enumerate(mechanics['mounting_holes_mm'],1):
        ref='H'+str(index)
        holes=list(fps[ref].Pads());assert len(holes)==1
        hole=holes[0];assert hole.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH
        assert all(abs(a-b)<1e-4 for a,b in zip(pcbnew.ToMM(hole.GetPosition()),point))
        assert all(abs(v-2.2)<1e-4 for v in pcbnew.ToMM(hole.GetDrillSize()))
        for other,f in fps.items():
            if other==ref:continue
            for p in f.Pads():
                # Keep the SWIG box alive while using its member-vector references.
                box=p.GetBoundingBox()
                a=pcbnew.ToMM(box.GetOrigin());z=pcbnew.ToMM(box.GetEnd())
                dx=max(a[0]-point[0],0,point[0]-z[0]);dy=max(a[1]-point[1],0,point[1]-z[1])
                clearance=math.hypot(dx,dy)
                if p.GetShape()==pcbnew.PAD_SHAPE_CIRCLE:
                    centre=pcbnew.ToMM(p.GetPosition());size=pcbnew.ToMM(p.GetSize())
                    assert abs(size[0]-size[1])<1e-4,'Circular pad has unequal dimensions'
                    clearance=math.hypot(centre[0]-point[0],centre[1]-point[1])-size[0]/2
                assert clearance>=2.45-.001,(ref,other,p.GetNumber(),'fastener envelope overlaps a pad')
    # HRO 2020-12-08 drawing, independently measured from the locator holes.
    # 1.64 mm locator-to-land-top minus half the 1.14 mm land length = 1.07 mm.
    for number in ('A1','A4','A5','A6','A7','A8','A9','A12','B1','B4','B5','B6','B7','B8','B9','B12'):
        p=pad('J4',number)
        assert abs(pcbnew.ToMM(p.GetPosition())[1]-42.41)<1e-4
        assert abs(pcbnew.ToMM(p.GetSize())[1]-1.14)<1e-4
    locators=[p for p in fps['J4'].Pads() if not p.GetNumber()]
    assert len(locators)==2
    for p in locators:
        x,y=pcbnew.ToMM(p.GetPosition())
        assert abs(abs(x-20.32)-2.89)<1e-4 and abs(y-43.48)<1e-4
        assert all(abs(v-.6)<1e-4 for v in pcbnew.ToMM(p.GetDrillSize()))
        assert abs(hi[1]-y-5.79)<1e-4,'USB PCB edge differs from manufacturer drawing'
    for row in range(8):
        for col in range(8):
            f=fps['D'+str(row*8+col+1)];actual=pcbnew.ToMM(f.GetPosition())
            assert f.GetLayer()==pcbnew.F_Cu and f.GetValue()=='XL-2012UOC'
            assert all(abs(a-b)<1e-4 for a,b in zip(actual,(2.54+5.08*col,40.64-5.08*row)))
            assert pcbnew.ToMM(pad(f.GetReference(),1).GetPosition())[0]<pcbnew.ToMM(pad(f.GetReference(),2).GetPosition())[0],'LED cathode orientation reversed'
    for t in board.GetTracks():
        if isinstance(t,pcbnew.PCB_VIA):
            assert t.GetViaType()==pcbnew.VIATYPE_THROUGH,'Unexpected blind/buried via cost'
            assert t.GetDrillValue()>=pcbnew.FromMM(.3)
            assert (t.GetWidth(pcbnew.F_Cu)-t.GetDrillValue())/2>=pcbnew.FromMM(.15)
    report={'status':'geometry checks passed; fabrication/physical qualification not established',
            'pcb':str(args.pcb),'footprints':len(fps),'pads_and_holes':count,
            'layers':4,'dimensions_mm':[40.64,49.27],
            'edge_contacts':'unchanged rear lands plus fourteen offset 0.8 mm PTH staple/probe holes; matching power/UART/I2C/GND nets',
            'testpoints':'ten numbered rear 1.0 mm copper probe pads, no paste/parts, explicit net/position/legend checks',
            'mounting':'two 2.2 mm NPTH M2 holes; 4.9 mm fastener envelopes checked',
            'swio':'rear vertical PicoBlade and original test pads; paired pin maps and 0.6 mm prototype finished holes checked',
            'leds':'64 orange LEDs at 5.08 mm pitch, cathodes to left'}
    output=ROOT/'build/hardware/v4'/f'{args.pcb.stem}-geometry.json'
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
