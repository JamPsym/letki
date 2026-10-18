#!/usr/bin/env python3
"""Summarize real routing trials; keep engine scores distinct from KiCad findings."""
import argparse
import csv
from html import escape
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def copper_metrics(path):
    if not path or not Path(path).is_file():return 'not recorded','not recorded'
    import pcbnew
    board=pcbnew.LoadBoard(str(path));tracks=list(board.GetTracks())
    return sum(isinstance(t,pcbnew.PCB_VIA)for t in tracks),round(sum(pcbnew.ToMM(t.GetLength())for t in tracks if not isinstance(t,pcbnew.PCB_VIA)),3)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'build/hardware/v4_1/routing-report')
    p.add_argument('--final-drc',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for folder in sorted((ROOT/'build/hardware').glob('v4_1-plugin-route*')):
        route=folder/'route.json'
        if not route.exists():continue
        r=json.loads(route.read_text());drc=folder/'kicad-drc.json';d=json.loads(drc.read_text())if drc.exists()else {}
        workflow=folder/'workflow.json';w=json.loads(workflow.read_text())if workflow.exists()else {}
        timing=folder/'command-metrics.json';t=json.loads(timing.read_text())if timing.exists()else {}
        vias,length=copper_metrics(w.get('candidate'))
        rows.append({'Trial':folder.name,'Source_SHA256':w.get('source_sha256','not recorded'),
            'Engine_successful':r.get('successful',''),'Engine_failed':r.get('failed',''),
            'Engine_reported_seconds':r.get('total_time',''),
            'Measured_route_command_seconds':t.get('route',{}).get('duration_seconds','not recorded'),
            'KiCad_DRC':len(d['violations'])if 'violations'in d else 'not recorded',
            'KiCad_open_connections':len(d['unconnected_items'])if 'unconnected_items'in d else 'not recorded',
            'Candidate_vias':vias,'Candidate_trace_length_mm':length,
            'Notes':'Different prepared input/placement/escapes per trial; no direct algorithm ranking'})
    history=ROOT/'docs/v4_1-routing-trials.csv'
    if not rows and history.is_file():
        with history.open()as f:rows=list(csv.DictReader(f))
    if a.final_drc:
        d=json.loads(a.final_drc.read_text())
        import hashlib
        board=ROOT/'hw/ledkiv4.1/ledkiv4_1.kicad_pcb'
        rows.append(dict(Trial='Final independently checked candidate',Source_SHA256=hashlib.sha256(board.read_bytes()).hexdigest(),Engine_successful='',Engine_failed='',
            Engine_reported_seconds='',Measured_route_command_seconds='',KiCad_DRC=len(d['violations']),KiCad_open_connections=len(d['unconnected_items']),Notes='Includes manual placement, terminal escapes, power/ground repair and reviewed In1 jumpers'))
        vias,length=copper_metrics(ROOT/'hw/ledkiv4.1/ledkiv4_1.kicad_pcb')
        rows[-1]['Candidate_vias']=vias;rows[-1]['Candidate_trace_length_mm']=length
    if not rows:raise SystemExit('No actual route trials found')
    with(a.output/'routing-trials.csv').open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    cells=''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>'for v in row.values())+'</tr>'for row in rows)
    headers=''.join('<th>'+escape(k)+'</th>'for k in rows[0])
    html='''<!doctype html><meta charset="utf-8"><title>Letki v4.1 routing review</title>
    <style>body{font:15px system-ui;margin:32px;color:#203028;background:#f5f6f2}table{border-collapse:collapse;background:white}
    td,th{padding:12px;border:1px solid #d5ddd7;text-align:left}th{background:#dcece1}td:nth-child(2){font:11px monospace;max-width:150px;overflow-wrap:anywhere}</style>
    <h1>Letki v4.1 — routing trials</h1><p>Actual recorded results, including unsuccessful attempts.
    Engine successes are not KiCad connectivity passes. Prepared PCB inputs differ between runs.</p>
    <p>Older runs contain engine-reported time only; complete command wall time was not captured and is not inferred.
    The wrapper now records elapsed wall time for each new command.</p>
    <table><thead><tr>'''+headers+'</tr></thead><tbody>'+cells+'''</tbody></table>
    <p>Manual work included component placement, stale copper removal, legal terminal via escapes,
    decoupling/power/ground routing and a scoped In1.Cu exception. Reports must not credit that work to the automatic router.</p>
    <p>PCB SVG drawings and CAD/DRC evidence accompany the final purchase package. Interactive net-highlight SVGs
    from KiCad SVG Extras would add inspection detail; they do not replace electrical or manufacturing checks.</p>'''
    (a.output/'index.html').write_text(html)
    print(a.output/'index.html')


if __name__=='__main__':main()
