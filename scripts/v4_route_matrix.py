#!/usr/bin/env python3
"""Route the regular v4 LED matrix in a development PCB copy.

Keeps the authoritative PCB untouched until complete schematic/BOM review.
Uses ordinary through vias outside LED mask openings; no blind/via-in-pad work.
The result still needs control routing, planes, DRC and visual review.
"""
from pathlib import Path
import math
import shutil
import pcbnew

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'hw/ledkiv4/ledkiv4.kicad_pcb'
OUTPUT=ROOT/'build/hardware/v4/matrix-routed.kicad_pcb'


def vector(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))


def main():
    board=pcbnew.LoadBoard(str(SOURCE))
    assert not list(board.GetTracks()), 'Source already routed; refusing to duplicate matrix'
    fps={f.GetReference():f for f in board.GetFootprints()}
    def pad(ref,number):
        return next(p for p in fps[ref].Pads() if p.GetNumber()==str(number))
    def track(net,layer,a,b,width=.2):
        if a==b:return
        t=pcbnew.PCB_TRACK(board);t.SetNetCode(net);t.SetLayer(layer)
        t.SetWidth(pcbnew.FromMM(width));t.SetStart(vector(*a));t.SetEnd(vector(*b));board.Add(t)
    def via(net,x,y):
        v=pcbnew.PCB_VIA(board);v.SetPosition(vector(x,y));v.SetWidth(pcbnew.FromMM(.7));v.SetDrill(pcbnew.FromMM(.3))
        v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net)
        v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED);v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        board.Add(v)
    def pos(p):return pcbnew.ToMM(p.GetPosition())
    # Place direct short bypass leads before general routing. A nearby
    # capacitor with a long routed detour is not adequate placement evidence.
    for chip,pin,cap,cap_pin,width in (
        ('U1',9,'C3',2,.3),('U2',16,'C1',2,.3),
        ('U3',20,'C6',1,.3),('U4',8,'C7',1,.2),
        ('U6',3,'C8',1,.3),('U6',2,'C9',1,.3)):
        a=pad(chip,pin);c=pad(cap,cap_pin);assert a.GetNetCode()==c.GetNetCode()
        track(a.GetNetCode(),pcbnew.B_Cu,pos(a),pos(c),width)
    pads=[p for f in board.GetFootprints() for p in f.Pads()]
    def clear_via(net,x,y):
        # Conservative rectangle envelope for rear pads. DRC remains
        # authoritative for real shapes, holes, masks and all copper layers.
        for p in pads:
            if p.GetNetCode()==net or not p.IsOnLayer(pcbnew.B_Cu):continue
            box=p.GetBoundingBox();lo=pcbnew.ToMM(box.GetOrigin());hi=pcbnew.ToMM(box.GetEnd())
            dx=max(lo[0]-x,0,x-hi[0]);dy=max(lo[1]-y,0,y-hi[1])
            if math.hypot(dx,dy)<.55+1e-5:return False
        return True
    # Anodes: eight front buses. Each bus has a separate via for rear routing.
    for row in range(8):
        y=40.64-5.08*row;bus_y=round(y-1.4,6)
        anodes=[pad('D'+str(row*8+c+1),2) for c in range(8)]
        net=anodes[0].GetNetCode();assert all(p.GetNetCode()==net for p in anodes)
        assert pad('R'+str(row+1),1).GetNetCode()==net
        xs=sorted([4.25]+[pos(p)[0] for p in anodes])
        assert clear_via(net,4.25,bus_y),(row,'anode via blocked')
        via(net,4.25,bus_y)
        for a,b in zip(xs,xs[1:]):track(net,pcbnew.F_Cu,(a,bus_y),(b,bus_y))
        for p in anodes:
            x,py=pos(p);assert abs(py-y)<1e-5
            track(net,pcbnew.F_Cu,(x,py),(x,bus_y))
    # Cathodes: eight inner-layer buses with through vias beside each LED.
    for col in range(8):
        x=2.54+5.08*col;bus_x=round(x-1.9,6)
        cathodes=[pad('D'+str(row*8+col+1),1) for row in range(8)]
        drain=pad('Q'+str(col+1),3);net=drain.GetNetCode()
        assert all(p.GetNetCode()==net for p in cathodes)
        ys=[32.0]
        for p in cathodes:
            px,py=pos(p)
            vy=next((round(py+offset,6) for offset in (0,.6,1.2,1.8,2.4,2.9)
                     if clear_via(net,bus_x,py+offset)),None)
            assert vy is not None,(col,px,py,'cathode via blocked')
            ys.append(vy);via(net,bus_x,vy)
            track(net,pcbnew.F_Cu,(px,py),(bus_x,vy))
        ys=sorted(ys)
        for a,b in zip(ys,ys[1:]):track(net,pcbnew.In2_Cu,(bus_x,a),(bus_x,b))
        dx,dy=pos(drain);via(net,dx,32.0)
        track(net,pcbnew.B_Cu,(dx,dy),(dx,32.0))
        track(net,pcbnew.In2_Cu,(bus_x,32.0),(dx,32.0))
        source=pad('Q'+str(col+1),2);sx,sy=pos(source)
        via(source.GetNetCode(),sx,33.3)
        track(source.GetNetCode(),pcbnew.B_Cu,(sx,sy),(sx,33.3))
    # A single inner ground plane connects all eight sink-source vias.
    # Control/supply vias and copper connectivity still need later completion.
    ground=board.FindNet('GND');assert ground
    zone=pcbnew.ZONE(board);zone.SetNet(ground);zone.SetLayer(pcbnew.In1_Cu)
    zone.SetLocalClearance(pcbnew.FromMM(.2));zone.SetMinThickness(pcbnew.FromMM(.2))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetThermalReliefGap(pcbnew.FromMM(.3));zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(.3))
    outline=zone.Outline();outline.NewOutline()
    for x,y in ((.5,.5),(40.14,.5),(40.14,49.23),(.5,49.23)):
        outline.Append(pcbnew.FromMM(x),pcbnew.FromMM(y))
    board.Add(zone)
    # A deliberate wide pass-through bus carries chain current. Do not leave
    # that job to the autorouter's ordinary 0.2 mm signal traces or rely on
    # the column-split inner pour as the only left-to-right supply path.
    power=pad('J3',1).GetNetCode()
    for ref,x in (('J3',2.8),('J1',38.2)):
        for number in (1,2):
            p=pad(ref,number);assert p.GetNetCode()==power
            px,py=pos(p);track(power,pcbnew.B_Cu,(px,py),(x,py),1.2)
        track(power,pcbnew.B_Cu,(x,1.5),(x,pos(pad(ref,2))[1]),1.2)
        via(power,x,1.5)
    track(power,pcbnew.F_Cu,(2.8,1.5),(38.2,1.5),2.0)
    # Short, wide current-switch output to its plane via.
    output=pad('U5',6);assert output.GetNetCode()==power
    ox,oy=pos(output)
    track(power,pcbnew.B_Cu,(ox,oy),(34.15,oy),.5)
    track(power,pcbnew.B_Cu,(34.15,oy),(35.0,44.8),.5)
    via(power,35.0,44.8)
    pzone=pcbnew.ZONE(board);pzone.SetNet(board.FindNet('VCC'));pzone.SetLayer(pcbnew.In2_Cu)
    pzone.SetLocalClearance(pcbnew.FromMM(.2));pzone.SetMinThickness(pcbnew.FromMM(.2))
    pzone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    pzone.SetThermalReliefGap(pcbnew.FromMM(.3));pzone.SetThermalReliefSpokeWidth(pcbnew.FromMM(.3))
    outline=pzone.Outline();outline.NewOutline()
    for x,y in ((.5,.5),(40.14,.5),(40.14,49.23),(.5,49.23)):
        outline.Append(pcbnew.FromMM(x),pcbnew.FromMM(y))
    board.Add(pzone)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(OUTPUT),board)
    shutil.copy2(SOURCE.with_suffix('.kicad_pro'),OUTPUT.with_suffix('.kicad_pro'))
    table=(SOURCE.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(SOURCE.parent))
    (OUTPUT.parent/'fp-lib-table').write_text(table)
    print(f'Matrix development copy: {len(list(board.GetTracks()))} tracks/vias; planes/control routing still pending.')


if __name__=='__main__':main()
