"""Generate a reusable interactive swimlane roadmap from JSON.

Usage:
    python roadmap_generator.py
    python roadmap_generator.py my_data.json my_roadmap.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light dark;--bg:#f7f8fa;--fg:#172033;--muted:#667085;--line:#d0d5dd;--panel:#fff;--sub:#eef2f6;--program:#2563eb;--contract:#7c3aed;--recovery:#0f766e;--migration:#c2410c;--customer:#475467;--decision:#dc2626;--bar-text:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#101318;--fg:#f2f4f7;--muted:#98a2b3;--line:#344054;--panel:#1b2028;--sub:#202631;--program:#2563eb;--contract:#7c3aed;--recovery:#0f766e;--migration:#c2410c;--customer:#475467;--decision:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}.page{max-width:1400px;margin:auto;padding:24px}h1{font-size:24px;margin:0 0 3px}p{margin:0;color:var(--muted)}.controls{display:flex;flex-wrap:wrap;gap:14px 22px;margin:20px 0 12px}.field{display:grid;gap:5px;min-width:230px}.field label{font-weight:600}select{padding:8px;background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:6px;font:inherit}.legend{display:flex;flex-wrap:wrap;gap:14px;color:var(--muted);margin-bottom:10px}.legend span{display:flex;align-items:center;gap:6px}.swatch{width:18px;height:8px;border-radius:2px}.program{background:var(--program)}.contract{background:var(--contract)}.recovery{background:var(--recovery)}.migration{background:var(--migration)}.customer{background:var(--customer)}.chart{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px}svg{display:block;width:100%;height:auto}.year-line,.lane-line{stroke:var(--line);stroke-width:1}.sub-bg{fill:var(--sub)}.axis-text,.lane-text{fill:var(--fg);font-family:inherit}.axis-text{fill:var(--muted)}.bar,.decision-hit{cursor:pointer}.bar.program{fill:var(--program)}.bar.contract{fill:var(--contract)}.bar.recovery{fill:var(--recovery)}.bar.migration{fill:var(--migration)}.bar.customer{fill:var(--customer)}.decision{fill:var(--decision)}.decision-hit{fill:transparent}.bar-text{fill:var(--bar-text);font-family:inherit;font-size:11px;font-weight:600;pointer-events:none}.decision-text{fill:var(--fg);pointer-events:auto;cursor:pointer}.detail{min-height:24px;margin-top:10px;color:var(--muted)}.mobile{display:none}.mobile div{padding:9px 0;border-top:1px solid var(--line)}.mobile strong{display:block}@media(max-width:600px){.page{padding:14px}.chart{display:none}.mobile{display:block}.field{width:100%;min-width:0}}
</style>
</head>
<body><main class="page">
<h1 id="heading"></h1><p id="subtitle"></p>
<div class="controls" id="controls"></div>
<div class="legend"><span><i class="swatch program"></i>Program</span><span><i class="swatch contract"></i>Contract</span><span><i class="swatch recovery"></i>Recovery</span><span><i class="swatch migration"></i>Migration</span><span><i class="swatch customer"></i>Customer work</span></div>
<div class="chart"><svg role="img" aria-labelledby="svg-title svg-desc"></svg></div>
<div class="mobile" aria-live="polite"></div><div class="detail" aria-live="polite"></div>
</main>
<script type="application/json" id="roadmap-data">__DATA__</script>
<script>
(()=>{const data=JSON.parse(document.getElementById('roadmap-data').textContent),svg=document.querySelector('svg'),controls=document.getElementById('controls'),detail=document.querySelector('.detail'),mobile=document.querySelector('.mobile'),NS='http://www.w3.org/2000/svg',state={};
document.title=data.title;document.getElementById('heading').textContent=data.title;document.getElementById('subtitle').textContent=`${data.start_year}–${data.end_year} · ${data.subtitle}`;
data.scenario_groups.forEach(g=>{state[g.id]=g.default;const box=document.createElement('div');box.className='field';const label=document.createElement('label');label.htmlFor='scenario-'+g.id;label.textContent=g.label;const select=document.createElement('select');select.id='scenario-'+g.id;g.options.forEach(o=>{const opt=document.createElement('option');opt.value=o.value;opt.textContent=o.label;opt.selected=o.value===g.default;select.append(opt)});select.addEventListener('change',()=>{state[g.id]=select.value;draw()});box.append(label,select);controls.append(box)});
function node(name,attrs={},text=''){const n=document.createElementNS(NS,name);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text)n.textContent=text;return n}function visible(e){return !e.when||Object.entries(e.when).every(([k,v])=>state[k]===v)}
function wrappedLines(label,width){const maxChars=Math.max(4,Math.floor((width-12)/6.2)),words=label.split(/\s+/),lines=[''];for(const word of words){const candidate=(lines[lines.length-1]+' '+word).trim();if(candidate.length<=maxChars)lines[lines.length-1]=candidate;else if(lines.length<2)lines.push(word);else{let last=lines[1];lines[1]=(last.length+word.length+1<=maxChars?last+' '+word:last).slice(0,Math.max(1,maxChars-1))+'…';break}}return lines}
function draw(){svg.replaceChildren();const W=1200,left=180,right=12,top=38,laneH=106,bottom=20,H=top+data.lanes.length*laneH+bottom,span=data.end_year-data.start_year+1,plotW=W-left-right,x=y=>left+(y-data.start_year)/span*plotW;
svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.append(node('title',{id:'svg-title'},data.title));svg.append(node('desc',{id:'svg-desc'},'Interactive swimlane roadmap. Use the scenario selectors to compare paths.'));
for(let yr=data.start_year;yr<=data.end_year;yr++){const xx=x(yr);svg.append(node('line',{x1:xx,y1:top-5,x2:xx,y2:H-bottom,class:'year-line'}));svg.append(node('text',{x:xx+4,y:20,class:'axis-text','font-size':13},String(yr)))}svg.append(node('line',{x1:x(data.end_year+1),y1:top-5,x2:x(data.end_year+1),y2:H-bottom,class:'year-line'}));
data.lanes.forEach((lane,i)=>{const yy=top+i*laneH;if(lane.sub_lane)svg.append(node('rect',{x:0,y:yy,width:W,height:laneH,class:'sub-bg'}));svg.append(node('line',{x1:0,y1:yy+laneH,x2:W,y2:yy+laneH,class:'lane-line'}));svg.append(node('text',{x:lane.sub_lane?20:5,y:yy+18,class:'lane-text','font-size':13,'font-weight':600},lane.label))});
data.entries.forEach((e,index)=>{const li=data.lanes.findIndex(l=>l.id===e.lane),yy=top+li*laneH+28+(e.row||0)*25,on=visible(e);if(e.point!==undefined){const xx=x(e.point),s=7,d=`M ${xx} ${yy} l ${s} ${s} l ${-s} ${s} l ${-s} ${-s} Z`,showDetail=()=>detail.textContent=`${e.label} — ${e.detail||''}`,mark=node('path',{d,class:'decision',opacity:on?1:.14}),hit=node('rect',{x:xx-10,y:yy-8,width:Math.max(44,e.label.length*7+32),height:36,class:'decision-hit',role:'button',tabindex:0,'aria-label':`${e.label}. ${e.detail||''}`});hit.addEventListener('click',showDetail);hit.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();showDetail()}});svg.append(mark);if(on){const label=node('text',{x:xx+12,y:yy+11,class:'bar-text decision-text'},e.label);label.addEventListener('click',showDetail);svg.append(label)}svg.append(hit);return}const sx=x(e.start),ex=x(Math.min(e.end,data.end_year+1)),width=Math.max(7,ex-sx-3),barH=23,clipId=`bar-clip-${index}`,defs=svg.querySelector('defs')||svg.insertBefore(node('defs'),svg.firstChild),clip=node('clipPath',{id:clipId});clip.append(node('rect',{x:sx+3,y:yy,width:Math.max(1,width-6),height:barH}));defs.append(clip);const rect=node('rect',{x:sx,y:yy,width,height:barH,rx:3,class:`bar ${e.category||'program'}`,opacity:on?1:.13,'aria-label':`${e.label}. ${e.detail||''}`});rect.addEventListener('click',()=>detail.textContent=`${e.label} — ${e.detail||''}`);svg.append(rect);if(on&&width>34){const text=node('text',{x:sx+6,y:yy+9,class:'bar-text','clip-path':`url(#${clipId})`});wrappedLines(e.label,width).forEach((line,i)=>text.append(node('tspan',{x:sx+6,dy:i===0?0:11},line)));svg.append(text)}});
const active=data.entries.filter(visible);mobile.innerHTML=active.map(e=>{const lane=data.lanes.find(l=>l.id===e.lane);const timing=e.point!==undefined?`Decision: ${Math.floor(e.point)}`:`${e.start}–${Math.min(e.end,data.end_year+1)}`;return `<div><strong>${lane.label}: ${e.label}</strong><span>${timing}</span></div>`}).join('');detail.textContent='Select a bar for its description. Faded bars belong to another scenario.'}draw()})();
</script></body></html>'''


def validate(data: dict) -> None:
    required = {"title", "start_year", "end_year", "lanes", "entries"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Missing required JSON keys: {', '.join(sorted(missing))}")
    if data["end_year"] < data["start_year"]:
        raise ValueError("end_year must be greater than or equal to start_year")
    lane_ids = {lane["id"] for lane in data["lanes"]}
    for index, entry in enumerate(data["entries"], start=1):
        if entry.get("lane") not in lane_ids:
            raise ValueError(f"Entry {index} references unknown lane: {entry.get('lane')}")
        if "point" not in entry and not {"start", "end"} <= entry.keys():
            raise ValueError(f"Entry {index} needs either point or both start and end")


def generate(source: Path, destination: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    validate(data)
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__TITLE__", str(data["title"])).replace("__DATA__", embedded)
    destination.write_text(html, encoding="utf-8")
    print(f"Created {destination.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an interactive swimlane roadmap from JSON.")
    parser.add_argument("source", nargs="?", type=Path, default=Path("roadmap_data.json"))
    parser.add_argument("destination", nargs="?", type=Path, default=Path("roadmap.html"))
    args = parser.parse_args()
    generate(args.source, args.destination)


if __name__ == "__main__":
    main()
