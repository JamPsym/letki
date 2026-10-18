#!/usr/bin/env python3
"""Export a via-finish map that distinguishes routing vias from solder holes."""
import argparse
import csv
from pathlib import Path
import pcbnew
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pcb',type=Path,default=ROOT/'hw/ledkiv4.1/ledkiv4_1.kicad_pcb')
    parser.add_argument('--output',type=Path,default=ROOT/'hw/ledkiv4.1/exports/prototype')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    b=pcbnew.LoadBoard(str(args.pcb));vias=sorted((t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA)),key=lambda v:(v.GetPosition().y,v.GetPosition().x))
    im=Image.new('RGB',(1400,1380),'white');d=ImageDraw.Draw(im)
    fontpaths=['/usr/share/fonts/TTF/DejaVuSans.ttf','/usr/share/fonts/dejavu/DejaVuSans.ttf',
               '/usr/share/fonts/noto/NotoSans-Regular.ttf','/usr/share/fonts/liberation/LiberationSans-Regular.ttf']
    fontpath=next((p for p in fontpaths if Path(p).is_file()),None)
    font=ImageFont.truetype(fontpath,19) if fontpath else ImageFont.load_default(size=19)
    title=ImageFont.truetype(fontpath,28) if fontpath else ImageFont.load_default(size=28)
    scale=22;origin=(70,175)
    def xy(point):x,y=pcbnew.ToMM(point);return origin[0]+x*scale,origin[1]+y*scale
    d.text((60,35),'LETKI v4.1 — VIA FINISH MAP',fill='black',font=title)
    d.text((60,78),'Front-view coordinates; PCB origin top-left; ordinary through vias only.',fill='black',font=font)
    d.text((60,110),'HASL SnPb + solder-mask ink plugging where process allows; no epoxy/copper capping.',fill='black',font=font)
    d.rectangle([origin,(origin[0]+40.64*scale,origin[1]+49.27*scale)],fill='#eef4ee',outline='black',width=2)
    rows=[]
    for index,v in enumerate(vias,1):
        x,y=xy(v.GetPosition());a=pcbnew.ToMM(v.GetPosition())
        covered=v.IsTented(pcbnew.F_Cu) and v.IsTented(pcbnew.B_Cu)
        color='#294aca' if covered else '#d64c14';r=max(3,pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu))*scale/2)
        d.ellipse([x-r,y-r,x+r,y+r],fill=color)
        rows.append([index,*a,pcbnew.ToMM(v.GetDrillValue()),v.GetNetname(),'COVERED; ink plug where process allows' if covered else 'KEEP EXPOSED; do not plug'])
    for f in b.GetFootprints():
        for p in f.Pads():
            if not p.GetDrillSize().x:continue
            x,y=xy(p.GetPosition());drill=pcbnew.ToMM(p.GetDrillSize());r=max(4,max(drill)*scale/2)
            color='#000000' if p.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH else '#cc8a00'
            d.ellipse([x-r,y-r,x+r,y+r],outline=color,width=3)
    for ypos,text,color in [(235,'Blue: covered routing vias','#294aca'),(285,'Orange: exposed routing vias','#d64c14'),(335,'Gold rings: solderable PTH holes','#cc8a00'),(385,'Black rings: NPTH holes','#000000')]:
        d.text((995,ypos),text,fill=color,font=font)
    # Put long instructions below the PCB; do not obscure the via locations.
    for ypos,text in [(1285,'Keep ALL component/wire PTH holes, USB plated slots and NPTH holes open.'),(1315,'Follow mask openings; covered vias near pads may be covered without full ink plugging.'),(1345,'Confirm production files before fabrication; this image supplements Gerbers and via-finish.csv.')]:
        d.text((60,ypos),text,fill='black',font=font)
    im.save(args.output/'via-finish-map.png')
    with (args.output/'via-finish.csv').open('w',newline='')as f:
        w=csv.writer(f);w.writerow(['Index','Front_view_X_mm','Front_view_Y_mm','Drill_mm','Net','Finish_instruction']);w.writerows(rows)
    print('Exported via-finish map for',len(rows),'routing vias')


if __name__=='__main__':main()
