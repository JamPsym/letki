#!/usr/bin/env python3
"""Create portable connector body envelopes and adjust prototype PTH lands.

These simple envelopes are clearance aids, not supplier CAD or exact contact
models. They avoid silently omitting SWIO/USB from the STEP assembly. The
PicoBlade holes allow ordinary fabrication tolerance; first-article soldering
and pin protrusion on the 1.6 mm PCB still need qualification.
"""
from pathlib import Path
import sys

from kicad_sexpr import Quoted as Q, child, children, prop, read, write

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'hw/ledkiv4'
HEADER='Molex_PicoBlade_53047-0310_1x03_P1.25mm_Vertical_SWIO_LetkiFab'
USB='USB_C_Receptacle_HRO_TYPE-C-31-M-12_Head'


def main():
    sys.path.append('/usr/lib/freecad/lib')
    import FreeCAD as App
    import Part
    model_dir=PROJECT/'Letki.3dshapes';model_dir.mkdir(exist_ok=True)
    envelopes=[
        (HEADER,'PicoBlade_53047-0310_body_envelope.step',(-1.5,-1.15,0),(5.5,3.2,4.2)),
        (USB,'USB_C_HRO_body_envelope.step',(-6.02,-3.65,0),(12.04,7.93,3.3))]
    paths={}
    for footprint,filename,origin,size in envelopes:
        shape=Part.makeBox(*size,App.Vector(*origin))
        assert shape.isValid() and len(shape.Solids)==1
        shape.exportStep(str(model_dir/filename))
        paths[footprint]='${KIPRJMOD}/Letki.3dshapes/'+filename
        f=read(PROJECT/'Letki.pretty'/(footprint+'.kicad_mod'))
        child(f,'model')[1]=Q(paths[footprint])
        if footprint==HEADER:
            # Molex recommends 0.5 +/-0.05 mm on its t=0.8 drawing. JLCPCB's
            # regular PTH tolerance is +0.13/-0.08 mm: a nominal 0.5 hole can
            # fall below that recommendation. Use a 0.6 mm prototype hole and
            # larger annulus, then qualify real fit/hole fill/pin protrusion.
            child(f,'descr')[1]=Q('Optional Molex 53047-0310 with bare SWIO pads; 0.6 mm prototype PTH holes adapted for regular fabrication tolerance')
            for p in children(f,'pad'):
                if p[2]=='thru_hole':
                    child(p,'drill')[1]='0.6';child(p,'size')[1:]=['1','1.4']
            # Internal pin-row silk was drawn for the smaller standard pads.
            f[:]=[n for n in f if not (isinstance(n,list) and n[0]=='fp_line'
                  and child(n,'layer')[1]=='F.SilkS'
                  and child(n,'start')[2]=='0.75' and child(n,'end')[2]=='0.75')]
        write(PROJECT/'Letki.pretty'/(footprint+'.kicad_mod'),f)
    pcb_path=PROJECT/'ledkiv4.kicad_pcb';pcb=read(pcb_path)
    for fp in children(pcb,'footprint'):
        ref=prop(fp,'Reference')[2]
        if ref in ('J2','J4'):
            name=HEADER if ref=='J2' else USB
            child(fp,'model')[1]=Q(paths[name])
            if ref=='J2':
                child(fp,'descr')[1]=Q('Optional Molex 53047-0310 with bare SWIO pads; 0.6 mm prototype PTH holes adapted for regular fabrication tolerance')
                for p in children(fp,'pad'):
                    if p[2]=='thru_hole':
                        child(p,'drill')[1]='0.6';child(p,'size')[1:]=['1','1.4']
                fp[:]=[n for n in fp if not (isinstance(n,list) and n[0]=='fp_line'
                       and child(n,'layer')[1]=='B.SilkS'
                       and abs(float(child(n,'start')[2])+.75)<1e-5
                       and abs(float(child(n,'end')[2])+.75)<1e-5)]
    write(pcb_path,pcb)
    print('Local SWIO/USB body envelopes added; 0.6 mm SWIO prototype holes require first-article fit/hole-fill review.')


if __name__=='__main__':main()
