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
    parser.add_argument('--revision',choices=['v4','v4.1'],default='v4')
    parser.add_argument('--config',type=Path)
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
    tme=args.revision=='v4.1'
    mechanics=json.loads((args.config or ROOT/('config/v4_1-mechanics.json' if tme else 'config/v4-mechanics.json')).read_text())
    wire=mechanics['edge_wire']
    # Identical seven-pad footprints mirrored about the board centreline.
    # Each single PTH pad combines the hole and rear solder land; no offset
    # pad pair or implicit component-internal connection is permitted.
    rows_y=sorted({round(pcbnew.ToMM(f.GetPosition())[1],5) for ref,f in fps.items()
                   if ref.startswith('D') and ref[1:].isdigit()})
    assert len(rows_y)==8
    expected_y=[(a+b)/2 for a,b in zip(rows_y,rows_y[1:])]
    for ref,x in (('J3',1.27),('J1',39.37)):
        assert fps[ref].GetLayer()==pcbnew.B_Cu
        assert fps[ref].GetFPID().GetLibItemName()==wire['footprint']
        assert len(list(fps[ref].Pads()))==7
        for number in range(1,8):
            p=pad(ref,number);actual=tuple(pcbnew.ToMM(p.GetPosition()))
            expected=(x,expected_y[number-1]);recorded=wire['left_holes_mm' if ref=='J3' else 'right_holes_mm'][number-1]
            assert all(abs(a-b)<1e-4 for a,b in zip(actual,expected)),(ref,number,actual,expected)
            assert all(abs(a-b)<1e-4 for a,b in zip(actual,recorded))
            assert p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH
            assert all(abs(v-.8)<1e-4 for v in pcbnew.ToMM(p.GetDrillSize()))
            assert all(abs(a-b)<1e-4 for a,b in zip(pcbnew.ToMM(p.GetSize(pcbnew.B_Cu)),(2.04,1.6)))
            assert p.GetShape(pcbnew.B_Cu)==pcbnew.PAD_SHAPE_OVAL
            for layer in (pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu):
                assert all(abs(v-1.4)<1e-4 for v in pcbnew.ToMM(p.GetSize(layer)))
                assert p.GetShape(layer)==pcbnew.PAD_SHAPE_CIRCLE
            assert not p.IsOnLayer(pcbnew.F_Paste) and not p.IsOnLayer(pcbnew.B_Paste)
        assert pad(ref,1).GetNetname()=='VCC' and pad(ref,2).GetNetname()=='VCC'
        assert pad(ref,3).GetNetname()=='/SDA' and pad(ref,4).GetNetname()=='/SCL'
        assert pad(ref,6).GetNetname()=='GND' and pad(ref,7).GetNetname()=='GND'
    for number in range(1,8):
        left=tuple(pcbnew.ToMM(pad('J3',number).GetPosition()))
        right=tuple(pcbnew.ToMM(pad('J1',number).GetPosition()))
        assert abs(left[1]-right[1])<1e-5
        assert abs(left[0]+right[0]-40.64)<1e-5
        assert abs(40.64-right[0]+left[0]-2.54)<1e-5,'Staples do not have a uniform span'
    # Chain supply must use the deliberately wide rails, not a signal escape.
    def rear_power_path(start,goal):
        links=[t for t in board.GetTracks() if not isinstance(t,pcbnew.PCB_VIA)
               and t.GetLayer()==pcbnew.B_Cu and t.GetNetname()=='VCC'
               and t.GetWidth()>=pcbnew.FromMM(1.2)-1]
        pending=[start];seen=set()
        while pending:
            node=pending.pop()
            if node in seen:continue
            seen.add(node)
            if math.dist(node,goal)<.002:return True
            for t in links:
                a=tuple(pcbnew.ToMM(t.GetStart()));z=tuple(pcbnew.ToMM(t.GetEnd()))
                dx,dy=z[0]-a[0],z[1]-a[1];length2=dx*dx+dy*dy
                u=max(0,min(1,((node[0]-a[0])*dx+(node[1]-a[1])*dy)/length2)) if length2 else 0
                if math.hypot(node[0]-a[0]-u*dx,node[1]-a[1]-u*dy)<.002:pending.extend((a,z))
        return False
    for ref,x in (('J3',2.8),('J1',38.2)):
        for number in (1,2):
            assert rear_power_path(tuple(pcbnew.ToMM(pad(ref,number).GetPosition())),(x,1.5)),(ref,number,'narrow/broken supply feed')
    assert any(not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.F_Cu
               and t.GetNetname()=='VCC' and t.GetWidth()>=pcbnew.FromMM(2)
               and {tuple(pcbnew.ToMM(t.GetStart())),tuple(pcbnew.ToMM(t.GetEnd()))}=={(2.8,1.5),(38.2,1.5)}
               for t in board.GetTracks()),'Main 2 mm VCC bus missing'
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
    # Manufacturer drawings, independent of the footprint transformation:
    # HRO locator-to-land centre 1.07 mm; GCT USB4105 centre y=-3.68,
    # locators y=-2.605, PCB edge y=+3.675 relative to footprint origin.
    # The GCT "PCB Edge" text anchor is at +3.1; it is not the edge line.
    manufacturer_findings=[]
    for number in ('A1','A4','A5','A6','A7','A8','A9','A12','B1','B4','B5','B6','B7','B8','B9','B12'):
        p=pad('J4',number)
        assert abs(pcbnew.ToMM(p.GetPosition())[1]-(42.49 if tme else 42.41))<1e-4
        length=1.13 if tme and number in ('A1','A12','B1','B12') else 1.15 if tme else 1.14
        assert abs(pcbnew.ToMM(p.GetSize())[1]-length)<1e-4
    locators=[p for p in fps['J4'].Pads() if not p.GetNumber()]
    assert len(locators)==2
    for p in locators:
        x,y=pcbnew.ToMM(p.GetPosition())
        assert abs(abs(x-20.32)-2.89)<1e-4 and abs(y-(43.565 if tme else 43.48))<1e-4
        assert all(abs(v-(.65 if tme else .6))<1e-4 for v in pcbnew.ToMM(p.GetDrillSize()))
    locator_y=pcbnew.ToMM(locators[0].GetPosition())[1]
    manufacturer_edge_y=locator_y+(6.28 if tme else 5.79)
    edge_offset=hi[1]-manufacturer_edge_y
    if abs(edge_offset)>1e-4:
        manufacturer_findings.append({
            'ref':'J4','kind':'manufacturer PCB-edge placement deviation',
            'actual_edge_y_mm':hi[1],
            'manufacturer_edge_y_mm':manufacturer_edge_y,
            'actual_minus_manufacturer_mm':round(edge_offset,6),
            'source':'GCT USB4105 product drawing Rev B3' if tme else 'HRO TYPE-C-31-M-12 drawing',
            'qualification':'requires engineering acceptance and physical fit verification'})
    if tme:
        assert fps['U2'].GetFPID().GetLibItemName()=='SOIC-16_3.9x9.9mm_P1.27mm_LetkiFab'
        assert fps['U4'].GetFPID().GetLibItemName()=='SOT-363_SC-70-6_LetkiFab'
        assert fps['U6'].GetFPID().GetLibItemName()=='SOT-23-5_LetkiFab'
        for ref in ('SW1','SW2'):
            f=fps[ref];assert f.GetValue()=='SKRPABE010' and len(list(f.Pads()))==4
            cx,cy=pcbnew.ToMM(f.GetPosition());by_num={n:[]for n in ('1','2')}
            for p in f.Pads():
                x,y=pcbnew.ToMM(p.GetPosition());by_num[p.GetNumber()].append((x,y))
                assert abs(abs(x-cx)-2.075)<1e-4 and abs(abs(y-cy)-1.075)<1e-4
                assert tuple(round(v,4)for v in pcbnew.ToMM(p.GetSize()))==(1.05,.65)
            assert len(by_num['1'])==len(by_num['2'])==2
            assert by_num['1'][0][1]==by_num['1'][1][1] and by_num['2'][0][1]==by_num['2'][1][1]
            assert pad(ref,1).GetNetname()=='+3V3' and pad(ref,2).GetNetname() in ('/BUTT1','/BUTT2')
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
    # Hand assembly needs legible rear references for every fitted passive.
    passive_labels=0
    for ref,f in fps.items():
        if ref[0] not in 'RC' or not ref[1:].isdigit():continue
        label=f.Reference()
        assert label.IsVisible() and label.GetLayer()==pcbnew.B_SilkS,(ref,'rear assembly label missing')
        assert label.IsMirrored(),(ref,'rear label must read correctly from the back')
        assert all(v>=pcbnew.FromMM(1) for v in label.GetTextSize()),(ref,'unprintable label size')
        assert label.GetTextThickness()>=pcbnew.FromMM(.15),(ref,'unprintable stroke')
        assert math.dist(tuple(pcbnew.ToMM(label.GetPosition())),tuple(pcbnew.ToMM(f.GetPosition())))<=4.1,(ref,'label too far from its part')
        passive_labels+=1
    report={'status':('geometry checks found manufacturer PCB-edge deviation; physical qualification not established'
                      if manufacturer_findings else 'geometry checks passed; fabrication/physical qualification not established'),
            'pcb':str(args.pcb),'footprints':len(fps),'pads_and_holes':count,
            'layers':4,'dimensions_mm':[40.64,49.27],
            'edge_contacts':'seven identical PTH pads per side, at LED-row midpoints; 5.08 mm pitch; mirrored positions; every staple spans 2.54 mm',
            'edge_padstack':'rear oval 2.04x1.6 mm, front/inner circle 1.4 mm, ordinary 0.8 mm drill',
            'testpoints':'ten numbered rear 1.0 mm copper probe pads, no paste/parts, explicit net/position/legend checks',
            'mounting':'two 2.2 mm NPTH M2 holes; 4.9 mm fastener envelopes checked',
            'swio':'rear vertical PicoBlade and original test pads; paired pin maps and 0.6 mm prototype finished holes checked',
            'leds':'64 orange LEDs at 5.08 mm pitch, cathodes to left',
            'rear_passive_labels':passive_labels,
            'usb_manufacturer_edge_y_mm':manufacturer_edge_y,
            'manufacturer_drawing_findings':manufacturer_findings}
    output=ROOT/('build/hardware/v4_1' if tme else 'build/hardware/v4')/f'{args.pcb.stem}-geometry.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if manufacturer_findings:
        raise SystemExit(1)


if __name__=='__main__':main()
