#!/usr/bin/env python3
"""Apply explicit BOM identity and stocked-switch land/model ECO in a new copy.

No source promotion. Copper, placements, other pad geometry and rules persist.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pcbnew
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v3_1_bom import expand
from v3_1_transistor_study import field

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    source,work=args.source.resolve(),args.work.resolve()
    assert not work.exists()
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    shutil.copytree(source.parent,work/'context')
    boardpath=work/'context'/source.name
    settings=boardpath.with_suffix('.kicad_pro').read_bytes()
    config=json.loads((ROOT/'config/v3_1-bom.json').read_text())
    schematic=read(boardpath.with_suffix('.kicad_sch'))
    instances={str(prop(s,'Reference')[2]):s for s in children(schematic,'symbol')}
    board=pcbnew.LoadBoard(str(boardpath))
    fps={f.GetReference():f for f in board.GetFootprints()}
    changes=[]
    for group in config['groups']:
        for ref in expand(group['refs']):
            values={'MPN':group['MPN'],'Supplier':group['supplier'],'Supplier code':group['code']}
            if group['MPN']=='0805S8F1001T5E':
                values['Sourcing']='Reviewed TME 0805 1%125mW fallback; unregistered user stock not credited'
            if ref=='R49':
                values['Assembly']='DNP for first provisioning; R38 fitted. Fit R49 only after verified pulse image and separately authorized/readback-confirmed PD7 GPIO, power OFF.'
            for name,value in values.items():
                node=prop(instances[ref],name)
                if node is None:instances[ref].append(field(name,value))
                else:node[2]=Q(value)
                fps[ref].SetField(name,value)
                metadata=fps[ref].GetField(name)
                metadata.SetVisible(False)
                metadata.SetLayer(pcbnew.B_Fab if fps[ref].GetLayer()==pcbnew.B_Cu else pcbnew.F_Fab)
                metadata.SetMirrored(fps[ref].GetLayer()==pcbnew.B_Cu)
    write(boardpath.with_suffix('.kicad_sch'),schematic)
    # Exact XUNPU drawing recommended pads: outer5.5x2.8, inner3.1x1.5.
    # Lands1.2x.65, centres(+/-2.15,+/-1.075). Archives remain untouched.
    library=work/'context/Letki31.pretty/SW_tactile_TS-1089S.kicad_mod'
    footprint=read(library)
    child(footprint,'descr')[1]=Q('XUNPU TS-1089S-02526; manufacturer recommended1.2x0.65mm lands; conservative maximum envelope model')
    for pad in children(footprint,'pad'):
        at=child(pad,'at');at[2]='1.075' if float(at[2])>0 else '-1.075'
        child(pad,'size')[1:]=['1.2','0.65']
    modelname='${KIPRJMOD}/Letki.3dshapes/TS-1089S_max_envelope.step'
    assert not children(footprint,'model')
    footprint.append(['model',Q(modelname),['offset',['xyz','0','0','0']],
                      ['scale',['xyz','1','1','1']],['rotate',['xyz','0','0','0']]])
    write(library,footprint)
    for ref in ['SW1','SW2']:
        fp=fps[ref]
        for pad in fp.Pads():
            old=pcbnew.ToMM(pad.GetFPRelativePosition())
            pad.SetFPRelativePosition(pcbnew.VECTOR2I(pcbnew.FromMM(old[0]),pcbnew.FromMM(1.075 if old[1]>0 else -1.075)))
            pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.2),pcbnew.FromMM(.65)))
            changes.append({'reference':ref,'pin':pad.GetNumber(),'pad_uuid':pad.m_Uuid.AsString(),
                            'from_local_mm':old,'to_local_mm':pcbnew.ToMM(pad.GetFPRelativePosition()),
                            'from_size_mm':[1.2,1.5],'to_size_mm':[1.2,.65]})
        assert not list(fp.Models())
        model=pcbnew.FP_3DMODEL();model.m_Filename=modelname;fp.Add3DModel(model)
    modeldir=work/'context/Letki.3dshapes';modeldir.mkdir(exist_ok=True)
    target=modeldir/'TS-1089S_max_envelope.step'
    code="""import sys
sys.path.append('/usr/lib/freecad/lib')
import FreeCAD as App
import Part
# Drawing general tolerance+/-0.2mm: lead span5.1+0.2, body3.25+0.2,
# overall height2.5+0.2. This box intentionally overbounds empty corners.
shape=Part.makeBox(5.3,3.45,2.7,App.Vector(-2.65,-1.725,0))
assert shape.isValid() and len(shape.Solids)==1
shape.exportStep(sys.argv[1])
"""
    subprocess.run([sys.executable,'-c',code,str(target)],check=True,stdout=subprocess.DEVNULL)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(boardpath),board)
    boardpath.with_suffix('.kicad_pro').write_bytes(settings)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    report={'source_sha256':before,'candidate_sha256':hashlib.sha256(boardpath.read_bytes()).hexdigest(),
            'BOM_config_sha256':hashlib.sha256((ROOT/'config/v3_1-bom.json').read_bytes()).hexdigest(),
            'switch_pad_changes':changes,'model_scope':'Maximum conservative5.3x3.45x2.7mm switch envelope, not contact/solder details',
            'drawing':'https://atta.szlcsc.com/upload/public/pdf/source/20191118/C455282_2E86A26A9CC4FEF4662951C4D45ED672.pdf',
            'note':'Routing/placement untouched; changed lands require fresh native checks. New stock identity annotations are explicit, not inventory changes.'}
    (work/'assembly-eco.json').write_text(json.dumps(report,indent=2)+'\n')
    print(boardpath)


if __name__=='__main__':main()
