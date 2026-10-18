#!/usr/bin/env python3
"""Place the unrouted integrated tile; refuse any board with copper routing."""
from pathlib import Path
from copy import deepcopy
import json
import math
import pcbnew
from kicad_sexpr import Quoted as Q, child, children, prop, read, write

ROOT=Path(__file__).resolve().parents[1]
PROJ=ROOT/'hw/ledkiv3.1'
ART=ROOT/'build/hardware/v3_1-integration'


def vector(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))


def rectangles(fp):
    layer=pcbnew.F_CrtYd if fp.GetLayer()==pcbnew.F_Cu else pcbnew.B_CrtYd
    fp.BuildCourtyardCaches()
    courtyard=fp.GetCourtyard(layer)
    if not courtyard.OutlineCount():
        raise ValueError('Missing courtyard: '+fp.GetReference())
    boxes=[]
    for i in range(courtyard.OutlineCount()):
        outline=courtyard.COutline(i);box=outline.BBox()
        a=pcbnew.ToMM(box.GetOrigin());b=pcbnew.ToMM(box.GetEnd())
        boxes.append((a[0],a[1],b[0],b[1]))
    return boxes


def overlaps(a,b,gap=.1):
    return a[0]<b[2]+gap and a[2]>b[0]-gap and a[1]<b[3]+gap and a[3]>b[1]-gap


def main():
    path=PROJ/'ledkiv3_1.kicad_pcb'
    board=pcbnew.LoadBoard(str(path))
    assert not list(board.GetTracks()), 'Do not re-place routed source.'
    # Restore deliberate rules after discovering that the initial blank-board
    # API save wrote defaults. Keep all severities and exclusions visible.
    settings=json.loads((ROOT/'hw/ledkiv4.1/ledkiv4_1.kicad_pro').read_text())
    settings['erc']=json.loads((ROOT/'archive/hw/ledkiv3.1-studies-20261015/pulse-study/ledkiv3_1_pulse.kicad_pro').read_text())['erc']
    settings['meta']['filename']='ledkiv3_1.kicad_pro'
    settings['board']['design_settings']['drc_exclusions']=[]
    assert 'ignore' not in settings['board']['design_settings']['rule_severities'].values()
    # The switch came from user v3 CAD without a courtyard and with thin silk.
    # Add the missing assembly envelope; leave all four inherited lands intact.
    switch_path=PROJ/'Letki31.pretty/SW_tactile_TS-1089S.kicad_mod'
    sw=read(switch_path)
    if not any(child(n,'layer')[1]=='B.CrtYd' for n in children(sw,'fp_rect')):
        sw.append(['fp_rect',['start','-3.0','-2.1'],['end','3.0','2.1'],
                   ['stroke',['width','0.05'],['type','default']],['fill','no'],['layer',Q('B.CrtYd')]])
    # Existing body silk intersects inherited solder lands; retain the full
    # physical body on Fab and use two short centre marks on printable silk.
    for shape in children(sw,'fp_rect'):
        if child(shape,'layer')[1]=='B.SilkS':child(shape,'layer')[1]=Q('B.Fab')
    if not children(sw,'fp_line'):
        for y in [-1.7,1.7]:
            sw.append(['fp_line',['start','-1.2',str(y)],['end','1.2',str(y)],
                       ['stroke',['width','0.15'],['type','default']],['layer',Q('B.SilkS')]])
    write(switch_path,sw)
    ast=read(path)
    for fp in children(ast,'footprint'):
        if prop(fp,'Reference')[2] not in ['SW1','SW2']:continue
        for shape in children(fp,'fp_rect'):
            if child(shape,'layer')[1]=='B.SilkS':child(shape,'layer')[1]=Q('B.Fab')
        if not any(child(n,'layer')[1]=='B.CrtYd' for n in children(fp,'fp_rect')):
            for shape in children(sw,'fp_rect')+children(sw,'fp_line'):
                if child(shape,'layer')[1] in ['B.CrtYd','B.SilkS']:fp.append(deepcopy(shape))
    write(path,ast)
    board=pcbnew.LoadBoard(str(path))
    fps={f.GetReference():f for f in board.GetFootprints()}
    for ref in ['H1','H2']:
        fp=fps[ref]
        if fp.GetLayer()!=pcbnew.F_Cu:fp.Flip(fp.GetPosition(),False)
    # Fixed short decoupling loops; two buttons remain below the LED grid.
    for ref,pos in {'C2':(13,41.2),'C5':(25,41.2),'C3':(14.5,24.525)}.items():fps[ref].SetPosition(vector(*pos))
    occupied=[]
    for ref,fp in fps.items():
        if fp.GetLayer()==pcbnew.B_Cu and not ref.startswith('R'):
            occupied.extend(rectangles(fp))
    # Deterministic nearest-legal placement of the hand-solderable resistors.
    # Exact native courtyard rectangles constrain both copper and body spacing.
    ordered=[f'R{i}' for i in list(range(1,9))+list(range(58,66))+
             list(range(15,31))+list(range(42,50))+list(range(31,39))+
             list(range(50,58))+[39,40,41,11,12,66,67,68,9,10,13,14]]
    assert len(set(ordered))==68
    report={}
    for ref in ordered:
        fp=fps[ref];ox,oy=pcbnew.ToMM(fp.GetPosition());original=fp.GetOrientationDegrees()
        candidates=[];local_boxes={}
        for angle in [original,(original+90)%180]:
            fp.SetPosition(vector(0,0));fp.SetOrientationDegrees(angle)
            local_boxes[angle]=rectangles(fp)
            for ix in range(12,150):
                x=ix*.25
                for iy in range(12,184):
                    y=iy*.25
                    dist=(x-ox)**2+(y-oy)**2
                    candidates.append((dist+(.08 if angle!=original else 0),x,y,angle))
        candidates.sort()
        for cost,x,y,angle in candidates:
            boxes=[(a+x,b+y,c+x,d+y) for a,b,c,d in local_boxes[angle]]
            if any(a[0]<.25 or a[1]<.25 or a[2]>40.39 or a[3]>49.02 for a in boxes):continue
            if any(overlaps(a,b) for a in boxes for b in occupied):continue
            occupied.extend(boxes)
            fp.SetPosition(vector(x,y));fp.SetOrientationDegrees(angle)
            report[ref]={'before':[ox,oy,original],'after':[x,y,angle],'move_mm':round(math.hypot(x-ox,y-oy),3)}
            break
        else:raise RuntimeError('No legal position for '+ref)
    # Explicitly clear reserved fields that the imported library set to '~'.
    schema=read(PROJ/'ledkiv3_1.kicad_sch')
    instances={str(prop(s,'Reference')[2]):s for s in children(schema,'symbol')}
    for ref,fp in fps.items():
        inst=instances[ref]
        for name in ['Datasheet','Description']:
            value=prop(inst,name)
            field=fp.GetField(name)
            text=str(value[2]) if value else ''
            if field:field.SetText('' if text=='~' else text)
        for value in children(inst,'property'):
            if value[1] in ['Reference','Value','Footprint','Datasheet','Description']:continue
            fp.SetField(str(value[1]),str(value[2]))
        for field in fp.GetFields():
            field.SetVisible(False)
            field.SetLayer(pcbnew.F_Fab if fp.GetLayer()==pcbnew.F_Cu else pcbnew.B_Fab)
            field.SetMirrored(fp.GetLayer()==pcbnew.B_Cu)
    pcbnew.SaveBoard(str(path),board)
    (PROJ/'ledkiv3_1.kicad_pro').write_text(json.dumps(settings,indent=2)+'\n')
    (ART/'placement-eco.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Placed 68 resistors around fixed interfaces, drivers and local decoupling; authored settings restored.')


if __name__=='__main__':main()
