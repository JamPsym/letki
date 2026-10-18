'use strict';
const $=id=>document.getElementById(id),versions=['robot','now'],cache=new Map();
const layerNames={front:'F.Cu',back:'B.Cu',inner1:'In1.Cu',inner2:'In2.Cu'};
let manifest,request=0,picked='',syncing=false;
function highlight(){
  const counts={};
  for(const key of versions){let n=0;for(const el of $(key+'-svg').querySelectorAll('[data-net]')){const match=el.dataset.net===picked;el.classList.toggle('net-dim',!!picked&&!match);el.classList.toggle('net-picked',!!picked&&match);if(match)n++;}counts[key]=n;}
  $('net').value=picked;
  $('status').textContent=picked?(picked+(counts.robot&&counts.now?' highlighted in both versions':counts.robot?' · no copper on this layer in the current board':counts.now?' · no copper on this layer in the first version':' · no copper on this layer')):'All nets · click a track or pad to highlight the same connection in both versions.';
}
function transform(){
  const zoom=Number($('zoom').value);$('zoom-value').textContent=zoom+'×';
  for(const key of versions){const el=$(key+'-svg');el.style.width=zoom*100+'%';el.classList.toggle('mirrored',$('layer').value==='back'&&$('mirror').checked);}
}
function setMode(){
  $('comparison').dataset.mode=$('mode').value;$('wipe-controls').hidden=$('mode').value!=='wipe';
  $('comparison').style.setProperty('--split',$('split').value+'%');transform();
  for(const key of versions){$(key+'-viewport').scrollLeft=0;$(key+'-viewport').scrollTop=0;}
}
function writeHash(){const p=new URLSearchParams({layer:$('layer').value,view:$('mode').value});if(picked)p.set('net',picked);history.replaceState(null,'','#'+p);}
async function showLayer(){
  const id=++request,layer=$('layer').value,wrap=$('comparison');wrap.dataset.ready='false';wrap.setAttribute('aria-busy','true');
  $('status').textContent='Loading '+layerNames[layer]+'…';$('mirror-label').hidden=layer!=='back';
  try{
    const results=await Promise.all(versions.map(async key=>{const url=key+'/'+layer+'-inline.svg';if(!cache.has(url))cache.set(url,fetch(url).then(r=>{if(!r.ok)throw new Error('SVG request failed');return r.text();}).catch(e=>{cache.delete(url);throw e;}));return [key,await cache.get(url)];}));
    if(id!==request)return;
    let viewBox;
    for(const [key,text] of results){
      const doc=new DOMParser().parseFromString(text,'image/svg+xml');if(doc.querySelector('parsererror')||doc.documentElement.localName!=='svg')throw new Error('Invalid SVG');
      const svg=document.importNode(doc.documentElement,true);svg.setAttribute('role','img');svg.setAttribute('aria-label',(key==='robot'?'First robot version':'Current board')+' '+layerNames[layer]);
      if(viewBox&&viewBox!==svg.getAttribute('viewBox'))throw new Error('Board coordinate frames differ');viewBox=svg.getAttribute('viewBox');
      $(key+'-svg').replaceChildren(svg);$(key+'-stat').textContent=manifest[key].layers[layerNames[layer]].segments.toLocaleString()+' track objects';
      $(key+'-download').href=key+'/'+layer+'.svg';
    }
    const names=[...new Set(versions.flatMap(key=>[...$(key+'-svg').querySelectorAll('[data-net]')].map(n=>n.dataset.net)).concat(picked||[]))].filter(Boolean).sort();
    $('net').replaceChildren(new Option('All nets',''),...names.map(n=>new Option(n,n)));
    transform();highlight();for(const key of versions){$(key+'-viewport').scrollLeft=0;$(key+'-viewport').scrollTop=0;}
    wrap.dataset.ready='true';wrap.setAttribute('aria-busy','false');writeHash();
  }catch(e){if(id!==request)return;wrap.dataset.ready='error';wrap.setAttribute('aria-busy','false');$('status').textContent='Could not load the comparison. The full SVG downloads remain available.';console.error(e);}
}
for(const key of versions){
  const viewport=$(key+'-viewport'),other=$(versions.find(k=>k!==key)+'-viewport');
  viewport.addEventListener('scroll',()=>{if(syncing)return;syncing=true;other.scrollLeft=viewport.scrollLeft;other.scrollTop=viewport.scrollTop;requestAnimationFrame(()=>{syncing=false;});},{passive:true});
  let drag=null,suppress=false;
  viewport.addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse'||e.button!==0)return;drag={x:e.clientX,y:e.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};suppress=false;});
  viewport.addEventListener('pointermove',e=>{if(!drag)return;if(!(e.buttons&1)){drag=null;viewport.classList.remove('dragging');return;}const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4){suppress=true;viewport.setPointerCapture(e.pointerId);viewport.classList.add('dragging');viewport.scrollLeft=drag.left-dx;viewport.scrollTop=drag.top-dy;e.preventDefault();}});
  const end=()=>{drag=null;viewport.classList.remove('dragging');};viewport.addEventListener('pointerup',end);viewport.addEventListener('pointercancel',end);
  viewport.addEventListener('click',e=>{if(suppress){suppress=false;return;}const node=e.target.closest('[data-net]');if(node){picked=node.dataset.net;highlight();writeHash();}});
}
$('layer').addEventListener('change',showLayer);$('net').addEventListener('change',()=>{picked=$('net').value;highlight();writeHash();});
$('zoom').addEventListener('input',transform);$('mirror').addEventListener('change',transform);
$('mode').addEventListener('change',()=>{setMode();writeHash();});$('split').addEventListener('input',()=>$('comparison').style.setProperty('--split',$('split').value+'%'));
$('reset').addEventListener('click',()=>{picked='';$('zoom').value='1';$('mirror').checked=true;$('split').value='50';setMode();highlight();writeHash();});
function restoreHash(){
  const p=new URLSearchParams(location.hash.slice(1));
  $('layer').value=p.get('layer') in layerNames?p.get('layer'):'front';
  $('mode').value=['side','wipe'].includes(p.get('view'))?p.get('view'):'side';
  picked=p.get('net')||'';setMode();return showLayer();
}
addEventListener('hashchange',()=>{if(manifest)restoreHash();});
async function init(){
  try{
    const response=await fetch('manifest.json');if(!response.ok)throw new Error('Manifest request failed');manifest=await response.json();
    const old=manifest.robot,current=manifest.now,delta=old.segments-current.segments;
    $('summary').replaceChildren(...['<strong>'+old.segments.toLocaleString()+' → '+current.segments.toLocaleString()+'</strong> track objects','<strong>'+delta+' fewer</strong> · '+(delta/old.segments*100).toFixed(1)+'%','<strong>'+old.footprints+'</strong> fixed component placements','<strong>'+current.vias+'</strong> vias · <strong>'+current.nets+'</strong> connected nets'].map(text=>{const span=document.createElement('span');span.innerHTML=text;return span;}));
    $('change-note').textContent=manifest.change_note;
    await restoreHash();
  }catch(e){$('status').textContent='Could not load snapshot details. Use the standalone SVG links below.';$('comparison').dataset.ready='error';console.error(e);}
}
init();
