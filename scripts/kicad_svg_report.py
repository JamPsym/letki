#!/usr/bin/env python3
"""Build offline interactive PCB SVG review from pinned KiCad SVG Extras.

Runs the exporter on isolated copies. Records its duration and source hashes;
does not route, alter CAD, upload files, order parts or touch hardware.
"""
import argparse
import hashlib
from html import escape
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PIN=json.loads((ROOT/'config/kicad-svg-extras.json').read_text())
TOOL=ROOT/'.tools/kicad-svg-extras'
SVG_NS='http://www.w3.org/2000/svg'
ET.register_namespace('',SVG_NS)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def export(source,layer,name,output,work):
    copied=work/name;copied.mkdir(parents=True,exist_ok=True)
    board=copied/source.name
    for suffix in ('.kicad_pcb','.kicad_pro'):
        p=source.with_suffix(suffix)
        if p.exists():shutil.copy2(p,copied/p.name)
    svg=output/(name+'.svg');metadata=output/(name+'-nets.json')
    command=[sys.executable,'-m','kicad_svg_extras','--output',str(svg),
        '--layers',layer+',Edge.Cuts','--use-css-classes','--export-metadata',str(metadata),
        '--ignore-project-colors','--net-color','GND:#4f9467','--net-color','VCC:#da7c17',
        '--net-color','+3V3:#2685bf',str(board)]
    env=dict(os.environ);env['PYTHONPATH']=str(TOOL/'src')
    clock_start=time.monotonic()
    with(output/(name+'.log')).open('w')as log:subprocess.run(command,env=env,cwd=ROOT,stdout=log,stderr=log,check=True)
    print('SVG:',name,flush=True)
    return {'name':name,'layer':layer,'source':str(source),'source_sha256':digest(source),
        'duration_seconds':round(time.monotonic()-clock_start,3),'svg':svg.name,'metadata':metadata.name}


def interactive_svg(path,metadata):
    tree=ET.parse(path);svg=tree.getroot()
    mapping={css:name for name,data in metadata['nets'].items()for css in data['css_classes'].values()}
    def walk(node,ancestor=None):
        names={mapping[c]for c in node.get('class','').split()if c in mapping}
        own=next(iter(names))if len(names)==1 else None
        if own and own!=ancestor:node.set('data-net',own)
        for sub in node:walk(sub,own or ancestor)
    walk(svg)
    # Native SVG is read-only; sizes are responsive while viewBox keeps the exact geometry.
    svg.attrib.pop('width',None);svg.attrib.pop('height',None)
    return ET.tostring(svg,encoding='unicode')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board',type=Path,default=ROOT/'hw/ledkiv4.1/ledkiv4_1.kicad_pcb')
    parser.add_argument('--output',type=Path,default=ROOT/'hw/ledkiv4.1/exports/prototype/routing-review')
    parser.add_argument('--with-trials',action='store_true',help='Include actual per-attempt rear copper SVGs')
    parser.add_argument('--reuse-verified',action='store_true',help='Reuse SVGs only when their source/tool/output hashes match')
    args=parser.parse_args()
    revision=subprocess.check_output(['git','-C',str(TOOL),'rev-parse','HEAD'],text=True).strip()
    assert revision==PIN['commit'],'Run scripts/setup_kicad_svg.py for the pinned exporter'
    assert not subprocess.check_output(['git','-C',str(TOOL),'status','--porcelain'],text=True).strip(),'Modified third-party exporter'
    args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    svgdir=args.output/'svg';svgdir.mkdir(exist_ok=True)
    work=ROOT/'build/hardware/v4_1/svg-render-inputs';work.mkdir(parents=True,exist_ok=True)
    sources={args.board.resolve()}
    descriptions=[]
    for name,layer in [('final-front','F.Cu'),('final-back','B.Cu'),('final-ground','In1.Cu'),('final-inner','In2.Cu')]:
        descriptions.append((name,layer,args.board.resolve(),'Końcowa v4.1 — '+layer))
    old=ROOT/'hw/ledkiv4/ledkiv4.kicad_pcb'
    if old.exists():
        sources.add(old);descriptions.append(('previous-v4','B.Cu',old,'Poprzednia v4 — B.Cu'))
    if args.with_trials:
        for folder in sorted((ROOT/'build/hardware').glob('v4_1-plugin-route*')):
            w=folder/'workflow.json'
            if not w.exists():continue
            data=json.loads(w.read_text());candidate=Path(data['candidate'])
            if not candidate.exists():continue
            sources.add(candidate)
            trial=folder.name.replace('v4_1-plugin-route','') or '1'
            descriptions.append((folder.name,'B.Cu',candidate,'Próba '+trial+' — B.Cu (robocza)'))
    monitored={p for source in sources for p in [source,source.with_suffix('.kicad_pro')]if p.is_file()}
    before={str(p):digest(p)for p in monitored};metrics=[];panels=[];all_nets=set()
    cached={}
    previous=args.output/'svg-export-manifest.json'
    if args.reuse_verified and previous.exists():
        data=json.loads(previous.read_text())
        if data['tool']==PIN:
            cached={item['name']:item for item in data['exports']
                if item.get('svg_sha256') and item.get('metadata_sha256')}
    for name,layer,source,label in descriptions:
        old=cached.get(name)
        if (old and old['source']==str(source) and old['source_sha256']==digest(source)
                and old['layer']==layer and (svgdir/old['svg']).is_file()
                and (svgdir/old['metadata']).is_file()
                and old['svg_sha256']==digest(svgdir/old['svg'])
                and old['metadata_sha256']==digest(svgdir/old['metadata'])):
            metric=dict(old);metric['cache_reused']=True
        else:
            metric=export(source,layer,name,svgdir,work);metric['cache_reused']=False
        metric['svg_sha256']=digest(svgdir/metric['svg']);metric['metadata_sha256']=digest(svgdir/metric['metadata'])
        metrics.append(metric)
        metadata=json.loads((svgdir/metric['metadata']).read_text());all_nets.update(metadata['nets'])
        graphic=interactive_svg(svgdir/metric['svg'],metadata)
        panels.append(f'<section class="pcb-panel" data-panel="{escape(name)}" hidden><h3>{escape(label)}</h3><div class="svgbox">{graphic}</div></section>')
    assert before=={str(p):digest(p)for p in monitored},'SVG exporter changed an input source'
    (args.output/'svg-export-manifest.json').write_text(json.dumps({'tool':PIN,'source_sha256':before,'exports':metrics,'scope':'SVG review only; KiCad manufacturing/CAD checks are independent'},indent=2)+'\n')
    options=''.join(f'<option value="{escape(name)}">{escape(label)}</option>'for name,layer,source,label in descriptions)
    net_options='<option value="">Wszystkie połączenia</option>'+''.join(f'<option value="{escape(n)}">{escape(n)}</option>'for n in sorted(all_nets))
    stats_path=args.output/'index.html'
    # The statistics generator owns the original index; keep a separate standalone viewer.
    viewer='''<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
    <title>Letki v4.1 — interaktywny raport PCB</title>
    <style>body{margin:24px;font:15px system-ui;background:#f3f6f3;color:#193629}h1{font-size:26px}a{color:#176194}
    .controls{display:flex;gap:16px;flex-wrap:wrap;align-items:center;padding:16px;background:white;border-radius:12px;margin:16px 0}
    label{display:grid;gap:5px}select,input{font:inherit;padding:7px;max-width:370px}button{font:inherit;padding:9px;cursor:pointer}
    .pcb-panel{background:white;border-radius:12px;padding:16px;max-width:820px}.svgbox{overflow:auto;max-height:760px}
    .svgbox svg{width:640px;max-width:none;height:auto;display:block;transform-origin:center}.svgbox [data-net]{cursor:pointer}
    .picked{filter:brightness(1.15) saturate(1.5)}#current{font:16px monospace}summary{cursor:pointer;font-size:20px;padding:14px}
    iframe{width:100%;min-height:560px;border:0}small{display:block;color:#587264}</style>
    <h1>Letki v4.1 — interaktywny raport PCB</h1>
    <p>Kliknij ścieżkę lub pad, aby podświetlić jego połączenie. Widoki zachowują współrzędne od przodu płytki;
    opcja lustra ułatwia oglądanie tylnej warstwy. Wersje robocze mogą zawierać błędy wskazane w tabeli prób.</p>
    <div class="controls"><label>Wersja / warstwa<select id="panel">'''+options+'''</select></label>
    <label>Filtr nazw<input id="search" placeholder="np. GND, MCU_UTX, COL_GATE"></label>
    <label>Połączenie<select id="net">'''+net_options+'''</select></label>
    <label>Zoom<input id="zoom" type="range" min="0.65" max="2.8" step="0.05" value="1"></label>
    <label><span>Widok od tyłu</span><input id="mirror" type="checkbox"></label>
    <button id="reset">Pokaż wszystkie</button></div>
    <p id="current" aria-live="polite">Wszystkie połączenia</p>'''+''.join(panels)+'''
    <details><summary>Wyniki prób routingu i ograniczenia</summary><iframe src="index.html" title="Statystyki prób"></iframe></details>
    <p><a href="routing-trials.csv" download>CSV prób</a> · <a href="svg-export-manifest.json">Źródła, wersja narzędzia i czasy eksportu</a> ·
    <a href="../manifest.json">Manifest paczki do zamówienia</a></p>
    <small>SVG: KiCad SVG Extras, przypięta wersja MIT. To podgląd połączeń; ocena elektryczna, DRC i kwalifikacja fizyczna są osobnymi sprawdzeniami.</small>
    <script>
    const panels=[...document.querySelectorAll('.pcb-panel')], panel=document.getElementById('panel'), net=document.getElementById('net');
    const nodes=[...document.querySelectorAll('[data-net]')], text=document.getElementById('current');
    function highlight(value){net.value=value;nodes.forEach(n=>{n.style.opacity=(!value||n.dataset.net===value)?'1':'0.06';n.classList.toggle('picked',!!value&&n.dataset.net===value)});const visible=panels.find(p=>!p.hidden);const matches=visible?[...visible.querySelectorAll('[data-net]')].filter(n=>n.dataset.net===value).length:0;text.textContent=value?(value+(matches?'':' — brak elementów na tej warstwie')):'Wszystkie połączenia'}
    function show(){panels.forEach(p=>p.hidden=p.dataset.panel!==panel.value);resize();highlight(net.value)}
    function resize(){const scale=Number(document.getElementById('zoom').value),mirror=document.getElementById('mirror').checked;panels.forEach(p=>{const s=p.querySelector('svg');s.style.width=(640*scale)+'px';s.style.transform=mirror?'scaleX(-1)':''})}
    panel.addEventListener('change',show);net.addEventListener('change',()=>highlight(net.value));
    document.getElementById('search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();[...net.options].forEach(o=>o.hidden=!!o.value&&!o.value.toLowerCase().includes(q))});
    nodes.forEach(n=>{n.addEventListener('click',e=>{e.stopPropagation();highlight(n.dataset.net)});n.addEventListener('mouseenter',()=>n.setAttribute('title',n.dataset.net))});
    document.getElementById('reset').addEventListener('click',()=>highlight(''));document.getElementById('zoom').addEventListener('input',resize);document.getElementById('mirror').addEventListener('change',resize);show();
    </script></html>'''
    (args.output/'viewer.html').write_text(viewer)
    print('Interactive report:',args.output/'viewer.html',flush=True)


if __name__=='__main__':main()
