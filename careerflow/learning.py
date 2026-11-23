"""Interview and learning records, deliberately separate from professional claims."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from . import core

STATES = {'interview':{'scheduled','completed','cancelled'},
          'training':{'planned','in_progress','completed','paused'}}
DIRECTORIES = {'interview':'interviews','training':'training'}


def _text(value, label):
    if not isinstance(value,str) or not value.strip():
        raise ValueError(label + ' is required')
    return value.strip()


def _reference(root, path):
    if path is None:
        return None
    # Paths are relative to --root, including when the CLI runs elsewhere.
    resolved = core.local(root, path)
    if not resolved.is_file():
        raise ValueError('Evidence/notes file not found: ' + str(path))
    return str(resolved.relative_to(root.resolve()))


def _create(root, kind, fields):
    record = {'schema_version':1, 'id':kind+'-'+uuid4().hex[:12], 'kind':kind,
              'created_at':core.now(), 'updated_at':core.now(), 'history':[], **fields}
    core.event(record, 'created', record['source'])
    core.write(root/DIRECTORIES[kind]/(record['id']+'.json'), record)
    return record


def add_interview(root, job, date, source, notes=None):
    core.get(root,job)
    timestamp = datetime.fromisoformat(date)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError('Interview timestamp requires a UTC offset')
    return _create(root,'interview',{'job_id':job, 'scheduled_at':timestamp.isoformat(),
        'source':_text(source,'Source'), 'notes_path':_reference(root,notes), 'status':'scheduled'})


def add_training(root, topic, goal, source, job=None):
    if job:
        core.get(root,job)
    return _create(root,'training',{'topic':_text(topic,'Topic'), 'goal':_text(goal,'Goal'),
        'source':_text(source,'Source'), 'job_id':job, 'status':'planned', 'evidence_path':None})


def update(root, record_id, kind, status, note, evidence=None, notes=None):
    if status not in STATES[kind] or not record_id.startswith(kind+'-') or record_id != core.slug(record_id):
        raise ValueError('Invalid learning record identity or status')
    path = root/DIRECTORIES[kind]/(record_id+'.json')
    record = core.read(path)
    if record.get('id') != record_id or record.get('kind') != kind:
        raise ValueError('Learning record identity mismatch')
    note = _text(note,'Result/change note')
    evidence_path = _reference(root,evidence) if evidence is not None else record.get('evidence_path')
    notes_path = _reference(root,notes) if notes is not None else record.get('notes_path')
    if kind == 'training' and status == 'completed':
        if not evidence_path:
            raise ValueError('Completed training requires an evidence artifact')
        _reference(root,Path(evidence_path))
    record.update(status=status)
    if kind == 'training':record['evidence_path'] = evidence_path
    else:record['notes_path'] = notes_path
    core.event(record,'status_changed',{'status':status,'note':note})
    core.write(path,record)
    return record


def list_records(root, kind=None, job=None, limit=20):
    if limit < 1 or limit > 1000:
        raise ValueError('Limit must be between 1 and 1000')
    records=[]
    for k in ([kind] if kind else STATES):
        for path in sorted((root/DIRECTORIES[k]).glob('*.json')):
            record=core.read(path)
            if not job or record.get('job_id') == job:records.append(record)
    return sorted(records,key=lambda r:(r['updated_at'],r['id']),reverse=True)[:limit]


def validate(root):
    errors=[]
    jobs={r['id'] for r in core.records(root)}
    for kind in STATES:
        for path in (root/DIRECTORIES[kind]).glob('*.json'):
            try:
                record=core.read(path)
                if record['id'] != path.stem or record['kind'] != kind or record['status'] not in STATES[kind]:
                    raise ValueError('Invalid record identity or status')
                if record.get('job_id') and record['job_id'] not in jobs:
                    raise ValueError('Unknown linked job')
                for key in ('notes_path','evidence_path'):
                    if record.get(key):_reference(root,Path(record[key]))
                if kind=='training' and record['status']=='completed' and not record.get('evidence_path'):
                    raise ValueError('Completed training has no evidence')
            except (ValueError,KeyError,OSError) as exc:
                errors.append(str(path.relative_to(root))+': '+str(exc))
    return errors
