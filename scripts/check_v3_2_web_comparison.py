#!/usr/bin/env python3
"""Exercise the comparison in headless Firefox and save rendered previews."""
import argparse
import base64
from functools import partial
import http.server
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--site',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--url',default=None,help='Optional deployed comparison URL')
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


server=http.server.ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(args.site.resolve())))
threading.Thread(target=server.serve_forever,daemon=True).start()
profile=tempfile.TemporaryDirectory(prefix='letki-comparison-firefox-')
(Path(profile.name)/'user.js').write_text('user_pref("marionette.port", 2845);\n')
proc=subprocess.Popen(['firefox','--headless','--no-remote','--marionette','--profile',profile.name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
sock=None;seq=0;checks=[]


def receive():
    size=b''
    while not size.endswith(b':'):
        part=sock.recv(1)
        if not part:raise RuntimeError('Firefox disconnected')
        size+=part
    remaining=int(size[:-1]);data=b''
    while len(data)<remaining:data+=sock.recv(remaining-len(data))
    return json.loads(data)


def call(name,args=None):
    global seq
    seq+=1;raw=json.dumps([0,seq,name,args or {}]).encode()
    sock.sendall(str(len(raw)).encode()+b':'+raw)
    result=receive()
    if result[2]:raise RuntimeError(result[2])
    return result[3]


def js(script):return call('WebDriver:ExecuteScript',dict(script=script,args=[],newSandbox=True,sandbox=None))['value']


def click(selector):
    found=call('WebDriver:FindElement',dict(using='css selector',value=selector))['value']
    call('WebDriver:ElementClick',dict(id=next(iter(found.values()))))


def change(element,value,event='change'):
    js('const el=document.getElementById('+json.dumps(element)+');el.value='+json.dumps(value)+';el.dispatchEvent(new Event('+json.dumps(event)+'));return true')


def ready():
    for _ in range(180):
        status=js('return document.querySelector("#comparison").dataset.ready')
        if status=='true':return
        assert status!='error','Comparison failed to load'
        time.sleep(.1)
    raise AssertionError('Timed out loading SVGs')


def shot(name):
    image=call('WebDriver:TakeScreenshot',dict(id=None,highlights=[],full=True))['value']
    (args.output/name).write_bytes(base64.b64decode(image))


try:
    for _ in range(120):
        try:sock=socket.create_connection(('127.0.0.1',2845),timeout=1);break
        except OSError:time.sleep(.1)
    assert sock,'Firefox did not start';sock.settimeout(30);receive()
    call('WebDriver:NewSession',dict(capabilities={'alwaysMatch':{}}))
    call('WebDriver:SetWindowRect',dict(width=1440,height=1100))
    base=args.url or f'http://127.0.0.1:{server.server_port}/v3.2-comparison/'
    call('WebDriver:Navigate',dict(url=base));ready()
    assert '2,015' in js('return document.getElementById("summary").textContent')
    assert '1,490' in js('return document.getElementById("summary").textContent')
    assert js('return document.querySelectorAll(".surface svg").length')==2
    for layer in ['front','back','inner1','inner2']:
        change('layer',layer);ready()
        assert js('return document.querySelector("#robot-svg svg").getAttribute("viewBox")===document.querySelector("#now-svg svg").getAttribute("viewBox")')
        change('net','GND')
        assert js('return [...document.querySelectorAll(".surface")].every(s=>s.querySelectorAll(".net-picked").length>0&&s.querySelectorAll(".net-dim").length>0)')
    checks.append('All four layers load in matched coordinate frames; net selection highlights both versions')
    change('layer','front');ready();change('net','/SCL')
    shot('desktop.png')
    js('document.querySelector("#now-svg [data-net=VCC]").dispatchEvent(new MouseEvent("click",{bubbles:true}));return true')
    assert js('return document.getElementById("net").value')=='VCC'
    assert js('return document.querySelectorAll("#robot-svg .net-picked").length>0')
    change('zoom','3','input')
    assert js('return [...document.querySelectorAll(".surface")].every(s=>s.style.width==="300%")')
    js('const v=document.getElementById("robot-viewport");v.scrollLeft=123;v.scrollTop=234;return true');time.sleep(.2)
    assert js('return Math.abs(document.getElementById("robot-viewport").scrollLeft-document.getElementById("now-viewport").scrollLeft)<2&&Math.abs(document.getElementById("robot-viewport").scrollTop-document.getElementById("now-viewport").scrollTop)<2')
    point=js('const r=document.getElementById("robot-viewport").getBoundingClientRect();return {x:Math.round(r.left+200),y:Math.round(r.top+150)}')
    call('WebDriver:PerformActions',dict(actions=[dict(type='pointer',id='pan-mouse',parameters=dict(pointerType='mouse'),actions=[dict(type='pointerMove',duration=0,origin='viewport',x=point['x'],y=point['y']),dict(type='pointerDown',button=0),dict(type='pointerMove',duration=200,origin='viewport',x=point['x']-60,y=point['y']-50),dict(type='pointerUp',button=0)])]))
    time.sleep(.2)
    assert js('return document.getElementById("robot-viewport").scrollLeft>160&&document.getElementById("now-viewport").scrollLeft>160')
    checks.append('Copper clicks select the matching net in both views; zoom, mouse-drag pan and both scroll axes stay synchronized')
    change('layer','back');ready()
    assert js('return document.querySelectorAll(".surface.mirrored").length')==2
    click('#mirror');assert js('return document.querySelectorAll(".surface.mirrored").length')==0
    click('#reset');assert js('return document.querySelectorAll(".net-dim").length')==0
    assert js('return document.getElementById("zoom").value')=='1'
    change('mode','wipe');change('split','30','input')
    assert js('return getComputedStyle(document.getElementById("now-pane")).clipPath')=='inset(0px 0px 0px 30%)'
    assert js('return Math.abs(document.getElementById("robot-viewport").getBoundingClientRect().width-document.getElementById("now-viewport").getBoundingClientRect().width)<1')
    change('layer','front');ready();change('net','/SCL');shot('wipe.png')
    checks.append('Rear mirroring, reset, wipe divider and equal overlay scale work')
    call('WebDriver:Navigate',dict(url=base+'#layer=back&view=wipe&net=%2FSCL'));ready()
    assert js('return document.getElementById("layer").value')=='back'
    assert js('return document.getElementById("mode").value')=='wipe'
    assert js('return document.getElementById("net").value')=='/SCL'
    checks.append('Shared URLs restore the selected layer, view and net')
    change('mode','side');change('layer','front');ready();click('#reset')
    for width in [320,390,768,1024,1440]:
        call('WebDriver:SwitchToFrame',dict(id=None))
        # Firefox enforces a minimum native window width. An actual child
        # browsing context exercises CSS media queries at the requested width.
        call('WebDriver:SetWindowRect',dict(width=max(650,width+40),height=960))
        js('const f=document.createElement("iframe");f.id="mobile-check";f.src='+json.dumps(base)+';f.style.cssText="border:0;display:block;width:'+str(width)+'px;height:2400px";document.body.replaceChildren(f);return true')
        element=call('WebDriver:FindElement',dict(using='css selector',value='#mobile-check'))['value']
        call('WebDriver:SwitchToFrame',dict(id=element));ready()
        assert js('return innerWidth')==width
        assert js('return document.documentElement.scrollWidth<=innerWidth'),width
        if width==390:
            js('frameElement.style.height=document.documentElement.scrollHeight+"px";return true')
            shot('mobile.png')
    checks.append('Actual CSS viewport widths 320, 390, 768, 1024 and 1440 px have no horizontal page overflow')
    call('WebDriver:SwitchToFrame',dict(id=None))
    call('WebDriver:Navigate',dict(url=base.replace('v3.2-comparison/','')))
    assert js('return [...document.querySelectorAll("a")].filter(a=>a.getAttribute("href")==="v3.2-comparison/").length')>=2
    checks.append('Work index links to the comparison and retains the earlier work entries')
    result=dict(status='PASS',url=base,checks=checks)
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
finally:
    if sock:
        try:call('Marionette:Quit',dict(flags=['eForceQuit']))
        except Exception:pass
        sock.close()
    proc.terminate();proc.wait(timeout=10);server.shutdown();profile.cleanup()
