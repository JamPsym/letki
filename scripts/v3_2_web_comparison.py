#!/usr/bin/env python3
"""Build a static SVG comparison without changing or publishing CAD."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pcbnew
import kicad_svg_report as svg

ROOT = Path(__file__).resolve().parents[1]
LAYERS = dict(front='F.Cu', back='B.Cu', inner1='In1.Cu', inner2='In2.Cu')


def stats(board):
    loaded = pcbnew.LoadBoard(str(board))
    tracks = [t for t in loaded.GetTracks() if type(t) == pcbnew.PCB_TRACK]
    return dict(sha256=svg.digest(board), segments=len(tracks),
        vias=sum(type(t) == pcbnew.PCB_VIA for t in loaded.GetTracks()),
        footprints=len(loaded.GetFootprints()),
        nets=len({p.GetNetname() for f in loaded.GetFootprints() for p in f.Pads() if p.GetNetname()}),
        layers={layer:dict(segments=sum(loaded.GetLayerName(t.GetLayer()) == layer for t in tracks),
            length_mm=sum(t.GetLength() for t in tracks if loaded.GetLayerName(t.GetLayer()) == layer) / 1e6)
            for layer in LAYERS.values()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--site-source', type=Path,
        default=Path('/home/pies/local_network/pieslab0/websites/psym.pl/zobaczadas'))
    args = parser.parse_args()
    work = args.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    site = work / 'site'; page = site / 'v3.2-comparison'
    assert not (page / 'manifest.json').exists(), 'Use a fresh work directory'
    assert subprocess.check_output(['git','-C',str(svg.TOOL),'rev-parse','HEAD'],text=True).strip() == svg.PIN['commit']
    assert not subprocess.check_output(['git','-C',str(svg.TOOL),'status','--porcelain'],text=True).strip()
    shutil.copytree(args.site_source, site, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns('README.md','check-browser.py','desktop.png','mobile.png','*.log','__pycache__'))
    page.mkdir(parents=True, exist_ok=True)
    for p in (ROOT / 'scripts/templates/v3_2-comparison').iterdir():
        shutil.copy2(p, page / p.name)
    boards = dict(robot=ROOT/'archive/hw/ledkiv3.2-routed-milestone-20261017/ledkiv3_2.kicad_pcb',
                  now=ROOT/'hw/ledkiv3.2/ledkiv3_2.kicad_pcb')
    monitored = {p:svg.digest(p) for board in boards.values() for p in board.parent.rglob('*')
                 if p.is_file() and not any(x in p.parts for x in ['exports']) and p.suffix in ('.kicad_pcb','.kicad_pro','.kicad_sch','.kicad_dru','.kicad_mod','.kicad_sym')}
    data = {key:stats(p) for key,p in boards.items()}
    assert data['robot']['sha256'] == '95e637adfd28457655d82f0a1dd962e2be7f0e28f83b4336a712ecc885cd78f2'
    assert data['now']['sha256'] == '1eff241854ad1150e82d46467debfce957d2cee92d66f088e6502791e266cd22'
    cache = args.site_source / 'v3.2/nets'
    cached = json.loads((cache/'manifest.json').read_text())
    assert cached['tool'] == svg.PIN and cached['source_sha256'] == data['robot']['sha256']
    exports = []
    for entry in cached['exports']:
        assert svg.digest(cache/entry['svg']) == entry['svg_sha256']
        assert svg.digest(cache/(entry['name']+'-inline.svg')) == entry['inline_sha256']
        target = page/'robot'; target.mkdir(exist_ok=True)
        for name in [entry['svg'],entry['name']+'-inline.svg',entry['metadata']]:
            shutil.copy2(cache/name,target/name)
        exports.append(dict(version='robot',layer=entry['layer'],svg='robot/'+entry['svg'],
            svg_sha256=entry['svg_sha256'],inline_sha256=entry['inline_sha256'],cache_verified=True))
    current = page/'now'; current.mkdir(exist_ok=True)
    def render(item):
        name,layer=item
        metric=svg.export(boards['now'],layer,name,current,work/'svg-inputs')
        metadata=json.loads((current/(name+'-nets.json')).read_text())
        (current/(name+'-inline.svg')).write_text(svg.interactive_svg(current/(name+'.svg'),metadata))
        return dict(version='now',layer=layer,svg='now/'+name+'.svg',duration_seconds=metric['duration_seconds'],
            svg_sha256=svg.digest(current/(name+'.svg')),inline_sha256=svg.digest(current/(name+'-inline.svg')))
    with ThreadPoolExecutor(max_workers=4) as pool:
        exports.extend(pool.map(render,LAYERS.items()))
    for name in LAYERS:
        frames=[ET.parse(page/key/(name+'-inline.svg')).getroot().get('viewBox') for key in boards]
        assert frames[0] == frames[1], ('Inconsistent coordinate frames',name,frames)
    assert all(svg.digest(p)==sha for p,sha in monitored.items()), 'SVG export changed source CAD'
    # Compare placements and all native via properties, including user edits.
    loaded={key:pcbnew.LoadBoard(str(p)) for key,p in boards.items()}
    def placements(b):
        return sorted((f.m_Uuid.AsString(),f.GetReference(),f.GetPosition().x,f.GetPosition().y,f.GetOrientationDegrees(),int(f.GetLayer())) for f in b.GetFootprints())
    assert placements(loaded['robot']) == placements(loaded['now'])
    def vias(b):
        return {t.m_Uuid.AsString():dict(net=t.GetNetname(),position_mm=[t.GetPosition().x/1e6,t.GetPosition().y/1e6],diameter_mm=t.GetWidth(pcbnew.F_Cu)/1e6,drill_mm=t.GetDrillValue()/1e6,layers=[int(t.TopLayer()),int(t.BottomLayer())]) for t in b.GetTracks() if type(t)==pcbnew.PCB_VIA}
    before,after=vias(loaded['robot']),vias(loaded['now'])
    via_changes=dict(removed=[before[i] for i in before.keys()-after.keys()],added=[after[i] for i in after.keys()-before.keys()],modified=[dict(before=before[i],after=after[i]) for i in before.keys()&after.keys() if before[i]!=after[i]])
    evidence=ROOT/'build/hardware/v3_2-point-reroute-checked-20261017/promoted-check'
    check=json.loads((evidence/'summary.json').read_text())
    assert check['status']=='PASS' and check['board_sha256']==data['now']['sha256']
    shutil.copy2(args.site_source/'v3.2/drc.json',page/'robot-drc.json')
    shutil.copy2(evidence/'drc.json',page/'now-drc.json')
    data.update(tool=svg.PIN,date='2026-10-17',exports=exports,source_unchanged=True,
        same_component_placements=True,via_changes=via_changes,
        change_note='Track objects: 2,015 → 1,490 (525 fewer). All 159 component placements match. Both states have 299 vias; one SCL via moved from (4.85, 14.30) to (4.80, 14.30) mm during the manual work before cleanup. The two cleanup passes preserved all via positions.',
        checks=dict(robot=dict(violations=0,opens=0,parity=0),now=dict(violations=1,opens=0,parity=0,connected_nets=76)),
        scope='Saved-state CAD comparison, including manual changes and both trace cleanup passes; no physical or EMC qualification')
    (page/'manifest.json').write_text(json.dumps(data,indent=2)+'\n')
    for log in current.glob('*.log'):
        shutil.move(log,work/log.name)
    # Keep the existing historical work index and add a direct comparison link.
    index=site/'index.html';text=index.read_text()
    text=text.replace('<a href="viewer.html">Routing comparison ↗</a>','<a href="v3.2-comparison/">v3.2: robot → now ↗</a>')
    if 'class="comparison-link"' not in text:
        text=text.replace('<div class="work">','<aside class="comparison-link"><a href="v3.2-comparison/"><strong>v3.2 · first robot version vs. now ↗</strong><span>2,015 → 1,490 track objects · linked net highlighting, zoom, and wipe view</span></a></aside>\n    <div class="work">',1)
    text=text.replace('Letki v3.2 <span class="tag">Latest</span>','Letki v3.2 <span class="tag">First route</span>').replace('A new board, fully routed','The original robot-routed snapshot')
    text=text.replace('id="preview-title">Letki v3.2</h2>','id="preview-title">v3.2 · first robot version</h2>')
    text=text.replace('style.css?v=20261017-nets','style.css?v=20261017-compare').replace('app.js?v=20261017-nets','app.js?v=20261017-compare')
    index.write_text(text)
    app=site/'app.js';text=app.read_text().replace("number:'01',title:'Letki v3.2'","number:'01',title:'v3.2 · first robot version'")
    text=text.replace('Routed CAD prototype. Native ERC, DRC, open-connection and schematic-parity checks report zero findings. Physical testing and new firmware are still pending.','Original robot-routed snapshot, saved on 17 October. Its native checks report zero findings. Use the v3.2 comparison above to inspect the current board after manual work and trace cleanup. Physical testing and new firmware remain pending.')
    app.write_text(text)
    css=site/'style.css'
    if '.comparison-link{' not in css.read_text():
        css.write_text(css.read_text()+'\n.comparison-link{margin:0 0 30px;padding:17px 20px;border:1px solid #c8d1bf;background:#edf0e7}.comparison-link a{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}.comparison-link strong{font-size:13px;font-weight:550}.comparison-link span{font:11px/1.8 ui-monospace,monospace;color:#656d5f}\n')
    publish=[str(p.relative_to(site)) for p in sorted(page.rglob('*')) if p.is_file()]+['style.css','app.js','index.html']
    (work/'publish-files.json').write_text(json.dumps({name:svg.digest(site/name) for name in publish},indent=2)+'\n')
    print('Comparison ready:',page,flush=True)


if __name__=='__main__':main()
