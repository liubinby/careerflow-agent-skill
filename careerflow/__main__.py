"""Run from the repository: python -m careerflow --help."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys
from . import core, dashboard, workspace, learning, training


def parser():
    p=argparse.ArgumentParser(description='Local evidence-based application pipeline')
    p.add_argument('--root',type=Path,default=Path.cwd(),help='Private workspace (default: current directory)')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('validate');sub.add_parser('dashboard');sub.add_parser('checkpoint');sub.add_parser('doctor')
    x=sub.add_parser('restore');x.add_argument('file',type=Path)
    x=sub.add_parser('init');x.add_argument('--profile',type=Path);x.add_argument('--template',type=Path)
    x=sub.add_parser('screen-batch');x.add_argument('file',type=Path)
    x=sub.add_parser('import');x.add_argument('file',type=Path,help='JSONL employer/title/url/requisition records')
    x=sub.add_parser('list');x.add_argument('--query',default='');x.add_argument('--stage');x.add_argument('--pursuit');x.add_argument('--limit',type=int,default=25)
    x=sub.add_parser('show');x.add_argument('id')
    x=sub.add_parser('context');x.add_argument('id');x.add_argument('--query',default='');x.add_argument('--limit',type=int,default=8)
    x=sub.add_parser('screen');x.add_argument('id');x.add_argument('--pursuit',choices=sorted(core.PURSUITS),required=True);x.add_argument('--priority',choices=sorted(core.PRIORITIES),default='normal');x.add_argument('--checks',type=Path,required=True);x.add_argument('--reason',required=True)
    x=sub.add_parser('shortlist');x.add_argument('id');x.add_argument('--override')
    x=sub.add_parser('source');x.add_argument('id');x.add_argument('--file',type=Path,required=True);x.add_argument('--url',required=True);x.add_argument('--kind',choices=['employer','mirror','provided'],required=True)
    x=sub.add_parser('build');x.add_argument('id');x.add_argument('--layout',choices=['styled','plain','both'],default='styled');x.add_argument('--letter',action='store_true')
    x=sub.add_parser('review');x.add_argument('id');x.add_argument('--visual',action='store_true');x.add_argument('--candidate',action='store_true');x.add_argument('--note',required=True)
    x=sub.add_parser('record-submission');x.add_argument('id');x.add_argument('--date',required=True);x.add_argument('--confirmation',required=True)
    x=sub.add_parser('advance');x.add_argument('id');x.add_argument('--stage',choices=['interviewing','closed'],required=True);x.add_argument('--outcome',choices=['offer','rejected','withdrawn','accepted']);x.add_argument('--note',required=True)
    x=sub.add_parser('profile-intake');g=x.add_mutually_exclusive_group(required=True);g.add_argument('--text');g.add_argument('--file',type=Path);x.add_argument('--employer',required=True);x.add_argument('--source',required=True);x.add_argument('--project');x.add_argument('--kind',choices=['experience','boundary'],default='experience')
    x=sub.add_parser('profile-accept');x.add_argument('note_id');x.add_argument('--text');x.add_argument('--supersedes');x.add_argument('--tags',default='')
    x=sub.add_parser('profile-set');x.add_argument('--key',required=True);x.add_argument('--value',required=True);x.add_argument('--source',required=True)
    x=sub.add_parser('employment-set');x.add_argument('employment_id');x.add_argument('--file',type=Path,required=True);x.add_argument('--source',required=True)
    x=sub.add_parser('preference-set');x.add_argument('--key',required=True);x.add_argument('--value',required=True,help='JSON value');x.add_argument('--source',required=True)
    x=sub.add_parser('draft');x.add_argument('id');x.add_argument('--from-application')
    x=sub.add_parser('claims');x.add_argument('--query',default='');x.add_argument('--employer');x.add_argument('--limit',type=int,default=20)
    x=sub.add_parser('impact');x.add_argument('claim_id')
    x=sub.add_parser('interview-add');x.add_argument('--job',required=True);x.add_argument('--date',required=True,help='ISO 8601 timestamp including UTC offset');x.add_argument('--source',required=True);x.add_argument('--notes',type=Path)
    x=sub.add_parser('interview-update');x.add_argument('id');x.add_argument('--status',choices=['scheduled','completed','cancelled'],required=True);x.add_argument('--note',required=True);x.add_argument('--notes',type=Path)
    x=sub.add_parser('training-add');x.add_argument('--topic',required=True);x.add_argument('--goal',required=True);x.add_argument('--source',required=True);x.add_argument('--job')
    x=sub.add_parser('training-update');x.add_argument('id');x.add_argument('--status',choices=['planned','in_progress','completed','paused'],required=True);x.add_argument('--note',required=True);x.add_argument('--evidence',type=Path)
    x=sub.add_parser('learning-list');x.add_argument('--kind',choices=['interview','training']);x.add_argument('--job');x.add_argument('--limit',type=int,default=20)
    x=sub.add_parser('training-request');x.add_argument('--topic',default='');x.add_argument('--minutes',type=int,default=30);x.add_argument('--focus',default='');x.add_argument('--job');x.add_argument('--source',default='Candidate training request')
    sub.add_parser('training-pending')
    for command in ('training-show','training-context','training-start'):
        x=sub.add_parser(command);x.add_argument('id')
    for command in ('training-plan','training-feedback','training-attempt','training-draft'):
        x=sub.add_parser(command);x.add_argument('id');x.add_argument('--file',type=Path,required=True,help='Workspace-relative input file')
        if command=='training-attempt':x.add_argument('--note',required=True)
    x=sub.add_parser('training-complete');x.add_argument('id');x.add_argument('--note',required=True)
    x=sub.add_parser('training-web');x.add_argument('--port',type=int,default=8872);x.add_argument('--foreground',action='store_true');x.add_argument('--no-browser',action='store_true')
    return p


def execute(a):
    root=a.root.resolve()
    if a.command=='checkpoint':return core.checkpoint(root)
    if a.command=='restore':return core.restore(root,a.file)
    if a.command=='doctor':return workspace.doctor()
    if a.command=='init':
        return workspace.initialize(root,a.profile,a.template)
    if a.command=='screen-batch':return core.screen_batch(root,[json.loads(l) for l in a.file.read_text().splitlines() if l.strip()])
    if a.command=='import':
        result=core.import_jobs(root,[json.loads(l) for l in a.file.read_text().splitlines() if l.strip()])
        return {'created':sum(r['result']=='created' for r in result),'duplicates':sum(r['result']=='duplicate' for r in result),'examples':result[:10]}
    if a.command=='list':return core.search(root,a.query,a.stage,a.pursuit,a.limit)
    if a.command=='show':return core.get(root,a.id)
    if a.command in {'claims','context'}:
        profile=core.read(root/'data/profile.json');words=set(a.query.lower().split())
        candidates=[]
        for cid,c in profile['claims'].items():
            if a.command=='claims' and a.employer and c['employment_id']!=a.employer:continue
            text=(c['text']+' '+' '.join(c.get('tags',[]))).lower()
            score=sum(word in text for word in words)
            if words and not score:continue
            candidates.append((score,cid,c))
        candidates.sort(key=lambda x:(-x[0],x[1]))
        selected=[{'id':cid,'revision':c['revision'],'employment_id':c['employment_id'],
                   'text':c['text'],'verification':c['verification'],'sources':c['sources']} for _,cid,c in candidates[:a.limit]]
        if a.command=='claims':return selected
        record=core.get(root,a.id)
        return {'job':{k:record[k] for k in ['id','title','family','checks','requirements','pursuit','priority']},
                'candidate_preferences':profile['preferences'],'claims':selected,
                'note':'Lexical retrieval only; not an evidence-based fit score. Verify scope before use.'}
    if a.command in {'screen','shortlist'}:
        r=(core.screen(root,a.id,a.pursuit,a.priority,core.read(a.checks),a.reason)
           if a.command=='screen' else core.shortlist(root,a.id,a.override))
        return {k:r[k] for k in ['id','stage','pursuit','priority']}
    if a.command=='source':return core.source_snapshot(root,a.id,a.file.read_text(),a.url,a.kind)
    if a.command=='employment-set':return core.employment_set(root,a.employment_id,core.read(a.file),a.source)
    if a.command=='preference-set':return core.preference_set(root,a.key,json.loads(a.value),a.source)
    if a.command=='draft':
        r=core.get(root,a.id)
        if r['stage']!='shortlisted' or r['pursuit']!='pursue':raise ValueError('Draft requires shortlisting first')
        destination=root/'applications'/a.id/'content.json'
        if destination.exists():raise ValueError('Draft already exists; refusing to overwrite')
        content=(core.read(core.local(root,'applications/'+a.from_application+'/content.json')) if a.from_application else
                 {'schema_version':1,'resume':{'headline':'','summary':'','skills':[],'experience':[]}})
        content['letter_source']='letter.md';content['letter_claim_ids']=[]
        content['notes']='Seeded selection only. Tailor headline/summary/skills and review evidence for this job before building. Letter intentionally empty.'
        content['build_options']={'layouts':['styled'],'include_letter':False}
        core.write(destination,content);(destination.parent/'letter.md').write_text('')
        return {'id':a.id,'content':str(destination.relative_to(root)),'result':'seeded; tailoring required'}
    if a.command=='profile-intake':return core.add_note(root,a.text if a.text is not None else a.file.read_text(),a.employer,a.source,a.project,a.kind)
    if a.command=='profile-accept':return core.accept_note(root,a.note_id,a.text,a.supersedes,[s.strip() for s in a.tags.split(',') if s.strip()])
    if a.command=='profile-set':
        core.profile_set(root,a.key,a.value,a.source);return {'result':'updated','key':a.key}
    if a.command=='impact':return core.impact(root,a.claim_id)
    if a.command=='interview-add':return learning.add_interview(root,a.job,a.date,a.source,a.notes)
    if a.command=='interview-update':return learning.update(root,a.id,'interview',a.status,a.note,notes=a.notes)
    if a.command=='training-add':return learning.add_training(root,a.topic,a.goal,a.source,a.job)
    if a.command=='training-update':return learning.update(root,a.id,'training',a.status,a.note,evidence=a.evidence)
    if a.command=='learning-list':return learning.list_records(root,a.kind,a.job,a.limit)
    if a.command=='training-request':return training.request(root,a.topic,a.minutes,a.focus,a.job,a.source)
    if a.command=='training-pending':return training.pending(root)
    if a.command=='training-show':return training.get(root,a.id)
    if a.command=='training-context':return training.context(root,a.id)
    if a.command=='training-start':return training.start(root,a.id)
    if a.command in {'training-plan','training-feedback','training-attempt','training-draft'}:
        path=core.local(root,a.file)
        if a.command=='training-plan':return training.plan(root,a.id,core.read(path))
        if a.command=='training-feedback':return training.feedback(root,a.id,core.read(path))
        if a.command=='training-draft':return training.save_draft(root,a.id,path.read_text())
        return training.attempt(root,a.id,path.read_text(),a.note)
    if a.command=='training-complete':return training.complete(root,a.id,a.note)
    if a.command=='training-web':
        from . import training_web
        return training_web.run(root,a.port,a.foreground,not a.no_browser)
    if a.command=='dashboard':return dashboard.make(root)
    if a.command=='validate':
        errors=core.validate(root)+learning.validate(root)
        if errors:raise ValueError('\n'.join(errors))
        return {'result':'valid','applications':len(core.records(root))}
    if a.command in {'build','review','record-submission'}:
        from . import render
        if a.command=='build':
            if not workspace.doctor()['pdf_build_ready']:
                raise ValueError('PDF dependencies missing; run doctor and install ReportLab plus Poppler')
            return render.build(root,a.id,('styled','plain') if a.layout=='both' else (a.layout,),a.letter)
        if a.command=='review':return render.review(root,a.id,a.visual,a.candidate,a.note)
        return render.record_submission(root,a.id,a.date,a.confirmation)
    if a.command=='advance':
        r=core.get(root,a.id)
        if not r['submissions'] or r['stage'] not in {'applied','interviewing'}:
            raise ValueError('Interview/outcome tracking requires a recorded application')
        if a.stage=='closed' and not a.outcome:raise ValueError('Closing requires an outcome')
        r['stage']=a.stage;r['outcome']=a.outcome;core.event(r,'user_reported_stage',a.note);core.save(root,r)
        return r
    raise ValueError('Unknown command')


def main():
    args=parser().parse_args()
    try:
        with (nullcontext() if args.command in {'doctor','training-web'} else core.locked(args.root.resolve())):
            result=execute(args)
            if args.command in {'import','screen','screen-batch','shortlist','source','build','review','record-submission','advance','restore'}:
                core.checkpoint(args.root.resolve())
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as exc:
        print('Error: '+str(exc),file=sys.stderr)
        sys.exit(2)


if __name__=='__main__':main()
