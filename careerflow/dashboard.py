"""Generate local navigation without hosting, dependencies, or parallel status edits."""
from html import escape
import json
from pathlib import Path
from . import core


def make(root):
    rows=[]
    for r in core.records(root):
        freshness=core.current_build(root,r)
        detail=root/'applications'/r['id']/'README.md'
        md=['# '+r['employer']+' — '+r['title'],'',
            f"Requisition: {r['requisition']} · Stage: {r['stage']} · Pursuit: {r['pursuit']} · Priority: {r['priority']}",
            '',f"Location: {r['location']}",'',f"[Employer posting]({r['url']})",'',
            '## Screening','']
        md.extend('- **'+c['key']+' — '+c['status']+'**: '+c['detail'] for c in r['checks'])
        if r.get('shortlist_override'):
            md+=['','Review override: '+r['shortlist_override']]
        md+=['','## Documents','', 'Build freshness: **'+freshness+'**. Legacy files are retained for reference.']
        documents=[]
        if r.get('latest_build') and (detail.parent/'builds'/r['latest_build']/'manifest.json').is_file():
            base='builds/'+r['latest_build']
            m=core.read(detail.parent/base/'manifest.json')
            md+=['','QA: '+json.dumps(m['qa'])]
            md.extend('- ['+name+']('+base+'/'+name+')' for name in m['outputs'])
            documents=[{'name':name,'path':'applications/'+r['id']+'/'+base+'/'+name} for name in m['outputs']]
        md+=['','## Sources and preparation','']
        md.extend('- ['+name.replace('_',' ')+'](../../'+path+')' for name,path in r.get('links',{}).items())
        md+=['','[Edit record](application.json) · [Content selection](content.json) · [All applications](../../APPLICATIONS.html)','']
        if detail.parent.exists():
            md = [line.replace('[Edit record](application.json)', 'Record: `python -m careerflow show '+r['id']+'`') for line in md]
            detail.write_text('\n'.join(md))
        rows.append({k:r[k] for k in ['id','employer','requisition','title','stage','pursuit','priority','location']})
        rows[-1].update(outcome=r.get('outcome',''),freshness=freshness,path=('applications/'+r['id']+'/README.md') if detail.parent.exists() else 'APPLICATIONS.html#'+r['id'],url=r['url'],checks=r['checks'],documents=documents)
    title='Job Application Dashboard'
    md=['# '+title,'','Generated from the local SQLite job store; use `python -m careerflow` to update records. `data/jobs.jsonl` is the portable checkpoint.',
        '',f"{len(rows)} jobs tracked. [Search/filter all jobs](APPLICATIONS.html)",'',
        '| Job | Stage | Pursuit | Priority | Build |','|---|---|---|---|---|']
    for r in rows[:50]:
        md.append('| ['+r['employer']+' '+r['requisition']+' — '+r['title']+']('+r['path']+') | '+r['stage']+(' / '+r['outcome'] if r.get('outcome') else '')+' | '+r['pursuit']+' | '+r['priority']+' | '+r['freshness']+' |')
    if len(rows)>50:md+=['', 'Showing the first 50 records; use the searchable index or CLI for all jobs.']
    # Preserve existing dashboard fragment links without reproducing a giant status document.
    for r in rows[:50]:
        md+=['', '<a id="'+r['id']+'"></a>', '', '## '+r['employer']+' '+r['requisition'], '', '[Open package and status]('+r['path']+')']
    (root/'APPLICATIONS.md').write_text('\n'.join(md)+'\n')
    data=json.dumps(rows,ensure_ascii=False).replace('<','\\u003c')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Job Application Dashboard</title>
<style>body{font:16px system-ui;max-width:1400px;margin:36px auto;padding:0 20px;color:#222;background:#fafafa}h1{margin-bottom:8px}input,select{font:inherit;padding:9px;margin:12px 8px 12px 0}table{width:100%;border-collapse:collapse;background:white}td,th{text-align:left;padding:12px;border-bottom:1px solid #ddd}th{background:#eee}a{color:#185ea8}#count{margin:12px 0}small{color:#555}</style>
<h1>Job Application Dashboard</h1><p>Local generated index. Edit canonical records through the CLI. <a href="APPLICATIONS.md">Markdown view</a></p>
<label>Search <input id="query" placeholder="Company, role, requisition, location"></label>
<label>Pursuit <select id="pursuit"><option value="">All</option><option>pursue</option><option>review</option><option>defer</option><option>decline</option></select></label>
<label>Stage <select id="stage"><option value="">All</option><option>intake</option><option>screened</option><option>shortlisted</option><option>prepared</option><option>applied</option><option>interviewing</option><option>closed</option></select></label>
<noscript>This dashboard needs JavaScript. Open it in your browser rather than a file preview.</noscript><section id="detail" tabindex="-1" aria-label="Selected application"></section><div id="count" aria-live="polite"></div><table><thead><tr><th>Application</th><th>Location</th><th>Stage</th><th>Pursuit</th><th>Priority</th><th>Build</th></tr></thead><tbody id="rows"></tbody></table><script>
const data=DATA;
function draw(){const q=document.getElementById('query').value.toLowerCase(),p=document.getElementById('pursuit').value,s=document.getElementById('stage').value;const selected=data.filter(r=>(!p||r.pursuit===p)&&(!s||r.stage===s)&&[r.employer,r.title,r.requisition,r.location].join(' ').toLowerCase().includes(q));const body=document.getElementById('rows');body.replaceChildren();for(const r of selected.slice(0,100)){const tr=document.createElement('tr');const first=document.createElement('td'),a=document.createElement('a');a.href='#'+r.id;a.addEventListener('click',event=>{event.preventDefault();history.replaceState(null,'','#'+r.id);show(r.id);});a.textContent=r.employer+' '+r.requisition+' — '+r.title;first.append(a);tr.append(first);for(const key of ['location','stage','pursuit','priority','freshness']){const td=document.createElement('td');td.textContent=r[key]+(key==='stage'&&r.outcome?' / '+r.outcome:'');tr.append(td);}body.append(tr);}document.getElementById('count').textContent=selected.length+' matching jobs; showing '+Math.min(selected.length,100)+' (narrow the search for more).';}
function show(id){const r=data.find(x=>x.id===id);if(!r)return;const box=document.getElementById('detail');box.replaceChildren();const h=document.createElement('h2');h.textContent=r.employer+' '+r.requisition+' — '+r.title;box.append(h);const status=document.createElement('p');status.textContent='Stage: '+r.stage+(r.outcome?' / '+r.outcome:'')+' · Pursuit: '+r.pursuit+' · Build: '+r.freshness;box.append(status);for(const d of r.documents){const p=document.createElement('p'),link=document.createElement('a');link.href=d.path;link.textContent='Open '+d.name;link.target='_blank';link.rel='noopener';p.append(link);box.append(p);}for(const c of r.checks){const p=document.createElement('p');p.textContent=c.key+' ['+c.status+']: '+c.detail;box.append(p);}const a=document.createElement('a');a.href=r.url;a.target='_blank';a.rel='noopener';a.textContent='Employer posting';box.append(a);if(!r.path.startsWith('APPLICATIONS.html#')){const p=document.createElement('p'),link=document.createElement('a');link.href=r.path;link.textContent='Open documents and notes';p.append(link);box.append(p);}box.focus({preventScroll:true});box.scrollIntoView({block:'start'});}
window.addEventListener('hashchange',()=>show(decodeURIComponent(location.hash.slice(1))));
if(location.hash)show(decodeURIComponent(location.hash.slice(1)));
for(const id of ['query','pursuit','stage'])document.getElementById(id).addEventListener('input',draw);draw();</script></html>'''.replace('DATA',data)
    (root/'APPLICATIONS.html').write_text(html)
    return {'jobs':len(rows),'dashboard':'APPLICATIONS.html'}
