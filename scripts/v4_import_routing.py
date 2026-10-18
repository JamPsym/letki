#!/usr/bin/env python3
"""Import a local router session, retaining the reviewed manual matrix copper.

Freerouting may normalize fixed paths; restore the original cathode networks
and LED-side row buses rather than accepting gaps in previously checked copper.
Writes a development PCB only. KiCad DRC and geometry checks must follow.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import uuid
import pcbnew
from kicad_sexpr import Quoted as Q, child, children, prop, read, write

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'build/hardware/v4'


def net(node):return str(child(node,'net')[1])
def point(node,key):return tuple(map(float,child(node,key)[1:3]))
def near(a,b):return max(abs(x-y) for x,y in zip(a,b))<.002


def layout(board):
    return {f.GetReference():
            (f.GetLayer(),round(f.GetOrientationDegrees(),4),
             tuple(round(x,4) for x in pcbnew.ToMM(f.GetPosition())),
             sorted((p.GetNumber(),p.GetNetname(),tuple(round(x,4) for x in pcbnew.ToMM(p.GetPosition()))) for p in f.Pads()))
            for f in board.GetFootprints()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session',type=Path)
    parser.add_argument('--output',type=Path,default=ART/'hybrid-restored.kicad_pcb')
    args=parser.parse_args();baseline=ART/'matrix-locked.kicad_pcb'
    board=pcbnew.LoadBoard(str(baseline));expected=layout(board)
    assert expected==layout(pcbnew.LoadBoard(str(ROOT/'hw/ledkiv4/ledkiv4.kicad_pcb'))), 'Routing baseline is stale relative to source placement/nets; re-export before importing'
    assert pcbnew.ImportSpecctraSES(board,str(args.session))
    assert layout(board)==expected, 'Session changed placement/nets; refusing stale or moved routing'
    temporary=ART/'session-import.kicad_pcb';pcbnew.SaveBoard(str(temporary),board)
    imported=read(temporary);original=read(baseline)
    cathodes={'/S'+str(i) for i in range(1,9)}
    row_y={'Net-(D'+str(row*8+1)+'-A)':(40.64-5.08*row,39.24-5.08*row) for row in range(8)}
    # The second row uses KiCad's alphabetically chosen D10 anode name.
    row_y['Net-(D10-A)']=row_y.pop('Net-(D9-A)')
    manual=children(original,'segment')+children(original,'via')
    def original_row_segment(n):
        if n[0]!='segment' or net(n) not in row_y or child(n,'layer')[1]!='F.Cu':return False
        a,b=point(n,'start'),point(n,'end');y,bus=row_y[net(n)]
        if abs(a[1]-bus)<.002 and abs(b[1]-bus)<.002:
            return min(a[0],b[0])>=3.4775-.002 and max(a[0],b[0])<=39.0375+.002
        if abs(a[0]-b[0])<.002 and any(abs(a[0]-(3.4775+5.08*c))<.002 for c in range(8)):
            return min(a[1],b[1])>=bus-.002 and max(a[1],b[1])<=y+.002
        return False
    def is_same(a,b):
        if a[0]!=b[0] or net(a)!=net(b):return False
        if a[0]=='via':return near(point(a,'at'),point(b,'at'))
        if child(a,'layer')[1]!=child(b,'layer')[1]:return False
        return (near(point(a,'start'),point(b,'start')) and near(point(a,'end'),point(b,'end'))) or (near(point(a,'start'),point(b,'end')) and near(point(a,'end'),point(b,'start')))
    imported[:]=[n for n in imported if not(isinstance(n,list) and n[0] in ('segment','via') and (net(n) in cathodes or original_row_segment(n) or (n[0]=='via' and any(is_same(n,o) for o in manual if o[0]=='via' and net(o) in row_y))))]
    kept=children(imported,'segment')+children(imported,'via');restored=0
    for n in manual:
        if any(is_same(n,o) for o in kept):continue
        n=deepcopy(n);child(n,'uuid')[1]=Q(str(uuid.uuid4()));imported.append(n);kept.append(n);restored+=1
    write(temporary,imported);board=pcbnew.LoadBoard(str(temporary))
    schematic=read(ROOT/'hw/ledkiv4/ledkiv4.kicad_sch')
    instances={prop(i,'Reference')[2]:i for i in children(schematic,'symbol')}
    for f in board.GetFootprints():
        i=instances[f.GetReference()];f.SetValue(str(prop(i,'Value')[2]))
        for field in children(i,'property'):
            if field[1] not in ('Reference','Value','Footprint'):
                f.SetField(str(field[1]),str(field[2]));f.GetField(str(field[1])).SetVisible(False)
    for v in board.GetTracks():
        if isinstance(v,pcbnew.PCB_VIA):
            v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED);v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones());pcbnew.SaveBoard(str(args.output),board)
    shutil.copy2(ROOT/'hw/ledkiv4/ledkiv4.kicad_pro',args.output.with_suffix('.kicad_pro'))
    print(f'Restored {restored} manual copper objects; development output {args.output}')


if __name__=='__main__':main()
