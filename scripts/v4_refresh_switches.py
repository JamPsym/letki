#!/usr/bin/env python3
"""Apply the reviewed XUNPU land pattern to a routed development copy.

Preserves all copper and component identities. SMD pad shifts are small; DRC,
connectivity and geometry checks must still run after this operation.
"""
import argparse
from pathlib import Path
import shutil
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v4_buffer_rows import field

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcb',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();s=read(args.pcb)
    for f in children(s,'footprint'):
        if prop(f,'Reference')[2] not in ('SW1','SW2'):continue
        prop(f,'Value')[2]=Q('TS-1089S-AR02516')
        for pad in children(f,'pad'):
            at=child(pad,'at');at[1]=str(2.175 if float(at[1])>0 else -2.175);at[2]=str(.95 if float(at[2])>0 else -.95)
            child(pad,'size')[1:]=['1.25','1.20']
        for n in children(f,'fp_rect'):
            layer=child(n,'layer')[1]
            if layer=='B.Fab':child(n,'start')[1:]=['-2.1','1.675'];child(n,'end')[1:]=['2.1','-1.675']
            if layer=='B.CrtYd':child(n,'start')[1:]=['-3.05','-1.925'];child(n,'end')[1:]=['3.05','1.925']
        for name,value in [('MPN','TS-1089S-AR02516'),('Manufacturer','XUNPU'),('LCSC','C720479'),('Datasheet','https://datasheet.lcsc.com/datasheet/pdf/c6651ef0d35056b6421502c57daea130.pdf?productCode=C720479')]:
            p=prop(f,name)
            if p:p[2]=Q(value)
            else:
                p=field(name,value);p.insert(3,['layer',Q('B.Fab')]);f.append(p)
    write(args.output,s)
    shutil.copy2(args.pcb.with_suffix('.kicad_pro'),args.output.with_suffix('.kicad_pro'))
    print('Updated SW1/SW2 land pattern and MPN; copper retained.')


if __name__=='__main__':main()
