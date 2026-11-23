"""SQLite job records, versioned profile claims, and portable checkpoints."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import hashlib
import json
import os
import re
import sqlite3
import tempfile

STAGES = ['intake', 'screened', 'shortlisted', 'prepared', 'applied', 'interviewing', 'closed']
PURSUITS = {'review', 'pursue', 'defer', 'decline'}
PRIORITIES = {'high', 'normal', 'low'}
REQUIRED_CHECKS = {'interest','location','eligibility','level_compensation','technical_fit','source_freshness'}

def needs_review(record):
    return bool(REQUIRED_CHECKS - {c['key'] for c in record['checks']}) or any(c['status']=='review' for c in record['checks'])


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def slug(value):
    result = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    if not result:
        raise ValueError('Empty identity')
    return result


def local(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path leaves repository: ' + str(relative))
    return path


@contextmanager
def locked(root):
    import fcntl
    directory = root / '.careerflow'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'write.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def database(root):
    path = root / 'data/careerflow.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS applications (id TEXT PRIMARY KEY, employer TEXT, requisition TEXT, title TEXT, stage TEXT, pursuit TEXT, priority TEXT, location TEXT, payload TEXT NOT NULL)')
    db.execute('CREATE INDEX IF NOT EXISTS application_state ON applications(stage,pursuit,priority)')
    db.execute('CREATE TABLE IF NOT EXISTS posting_snapshots (sha256 TEXT PRIMARY KEY, body TEXT NOT NULL, created_at TEXT NOT NULL)')
    db.commit()
    return db


def records(root):
    with database(root) as db:
        result = [json.loads(r['payload']) for r in db.execute('SELECT payload FROM applications ORDER BY id')]
    db.close()
    return result


def get(root, app_id):
    if app_id != slug(app_id):
        raise ValueError('Invalid application ID')
    with database(root) as db:
        row = db.execute('SELECT payload FROM applications WHERE id=?', (app_id,)).fetchone()
    db.close()
    if not row:
        raise ValueError('Unknown application: ' + app_id)
    return json.loads(row['payload'])


def save_many(root, batch):
    db = database(root)
    try:
        with db:
            db.executemany('INSERT INTO applications VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET employer=excluded.employer,requisition=excluded.requisition,title=excluded.title,stage=excluded.stage,pursuit=excluded.pursuit,priority=excluded.priority,location=excluded.location,payload=excluded.payload',
                [tuple(r[k] for k in ['id','employer','requisition','title','stage','pursuit','priority','location']) + (json.dumps(r,ensure_ascii=False),) for r in batch])
    finally:
        db.close()


def save(root, record):
    save_many(root, [record])


def checkpoint(root):
    destination = root / 'data/jobs.jsonl'
    rows = records(root)
    text = ''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in rows)
    fd, name = tempfile.mkstemp(dir=destination.parent,prefix='.jobs-')
    try:
        with os.fdopen(fd,'w') as f: f.write(text)
        os.replace(name,destination)
    finally:
        if os.path.exists(name):os.unlink(name)
    db=database(root)
    sources=[dict(r) for r in db.execute('SELECT * FROM posting_snapshots ORDER BY sha256')]
    db.close()
    write(root/'data/posting-snapshots.json',sources)
    return {'jobs':len(rows),'snapshot':str(destination.relative_to(root)),'source_snapshots':len(sources)}


def restore(root, path):
    if records(root):
        raise ValueError('Restore requires an empty database; back up the existing database first')
    batch=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids=[r['id'] for r in batch]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate IDs in snapshot')
    for r in batch:
        if r['id']!=slug(r['id']) or r['stage'] not in STAGES or r['pursuit'] not in PURSUITS:
            raise ValueError('Invalid snapshot record')
    source_file=path.parent/'posting-snapshots.json'
    sources=read(source_file) if source_file.exists() else []
    for source in sources:
        if hashlib.sha256(source['body'].encode()).hexdigest()!=source['sha256']:raise ValueError('Invalid source snapshot hash')
    save_many(root,batch)
    db=database(root)
    with db:db.executemany('INSERT OR IGNORE INTO posting_snapshots VALUES (?,?,?)',[(s['sha256'],s['body'],s['created_at']) for s in sources])
    db.close()
    return {'restored':len(batch)}


def event(record, action, detail):
    record.setdefault('history', []).append({'at': now(), 'action': action, 'detail': detail})
    record['updated_at'] = now()


def canonical_url(url):
    p = urlsplit(url)
    if p.scheme not in {'https', 'http'} or not p.hostname or p.username or p.password:
        raise ValueError('A public http(s) job URL is required')
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k not in {'q', 'source', 'ref'}]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), urlencode(query), ''))


def identity(job):
    employer = slug(job['employer'])
    url = canonical_url(job['url'])
    req = job.get('requisition')
    if not req:
        match = re.search(r'_(R\d+)(?:-\d+)?(?:/|$)', urlsplit(url).path, re.I)
        req = match.group(1) if match else None
    return employer + '-' + (slug(req) if req else digest(url)[:12]), url


def import_jobs(root, jobs):
    existing = {r['id']: r for r in records(root)}
    # Validate the entire batch before mutation, including conflicts in the same batch.
    pending, results = {}, []
    for job in jobs:
        app_id, url = identity(job)
        if not job.get('title'):
            raise ValueError('Job title is required')
        if app_id in existing or app_id in pending:
            results.append({'id': app_id, 'result': 'duplicate'})
            continue
        record = {'schema_version': 1, 'id': app_id, 'employer': job['employer'],
                  'requisition': job.get('requisition') or app_id.rsplit('-', 1)[-1].upper(),
                  'title': job['title'], 'url': url, 'location': job.get('location', 'Unverified'),
                  'family': job.get('family', 'unclassified'), 'created_at': now(), 'updated_at': now(),
                  'stage': 'intake', 'pursuit': 'review', 'priority': 'normal',
                  'checks': [], 'requirements': job.get('requirements', []), 'history': [],
                  'sources': job.get('sources', []), 'links': {}, 'latest_build': None,
                  'submissions': []}
        event(record, 'import', 'Imported job metadata; no description retrieval or factual matching assumed.')
        pending[app_id] = record
        results.append({'id': app_id, 'result': 'created'})
    save_many(root, list(pending.values()))
    return results


def screened(record, pursuit, priority, checks, reason):
    if pursuit not in PURSUITS or priority not in PRIORITIES or not reason.strip():
        raise ValueError('Valid pursuit, priority, and reason are required')
    if len({c.get('key') for c in checks}) != len(checks):
        raise ValueError('Duplicate check keys')
    for c in checks:
        if c.get('status') not in {'pass','review','fail'} or not c.get('key') or not c.get('detail'):
            raise ValueError('Each check needs key, status pass/review/fail, and detail')
    record.update(pursuit=pursuit,priority=priority,checks=checks)
    if record['stage']=='intake':record['stage']='screened'
    event(record,'screen',reason)
    return record


def screen(root, app_id, pursuit, priority, checks, reason):
    r=screened(get(root,app_id),pursuit,priority,checks,reason)
    save(root,r)
    return r


def screen_batch(root, decisions):
    batch=[];seen=set()
    for d in decisions:
        if d['id'] in seen:raise ValueError('Duplicate decision in batch')
        seen.add(d['id'])
        batch.append(screened(get(root,d['id']),d['pursuit'],d.get('priority','normal'),d['checks'],d['reason']))
    save_many(root,batch)
    return {'updated':len(batch),'ids':[r['id'] for r in batch[:10]]}


def source_snapshot(root, app_id, body, url, kind):
    r=get(root,app_id);url=canonical_url(url);sha=hashlib.sha256(body.encode()).hexdigest()
    item={'kind':kind,'url':url,'retrieved_at':now(),'snapshot_id':sha}
    if any(s.get('snapshot_id')==sha and s.get('url')==url for s in r['sources']):
        return {'snapshot_id':sha,'result':'already_saved'}
    r['sources'].append(item);event(r,'source_snapshot',item)
    db=database(root)
    try:
        with db:
            db.execute('INSERT OR IGNORE INTO posting_snapshots VALUES (?,?,?)',(sha,body,now()))
            db.execute('UPDATE applications SET payload=? WHERE id=?',(json.dumps(r,ensure_ascii=False),app_id))
    finally:db.close()
    return item


def shortlist(root, app_id, override=None):
    r = get(root, app_id)
    if r['stage'] not in {'screened', 'shortlisted', 'prepared'} or r['pursuit'] != 'pursue':
        raise ValueError('Shortlisting requires a screened job with pursuit=pursue')
    if any(c['status'] == 'fail' for c in r['checks']):
        raise ValueError('Resolve failed conditions before shortlisting')
    if needs_review(r) and not override:
        raise ValueError('Unresolved conditions require an explicit --override reason')
    r['shortlist_override'] = override
    if r['stage'] != 'prepared':
        r['stage'] = 'shortlisted'
    event(r, 'shortlist', override or 'Screening conditions resolved')
    save(root, r)
    return r


def snapshot(root, app_id):
    r = get(root, app_id)
    content = read(root / 'applications' / app_id / 'content.json')
    if content.get('letter_source'):
        path = local(root, 'applications/' + app_id + '/' + content['letter_source'])
        content['letter'] = [block.strip() for block in path.read_text().split('\n\n') if block.strip()]
    profile = read(root / 'data/profile.json')
    for key in ('name','email'):
        if not isinstance(profile['candidate'].get(key),str) or not profile['candidate'][key].strip():
            raise ValueError('Complete candidate '+key+' before building')
    for key in ('headline','summary'):
        if not isinstance(content['resume'].get(key),str) or not content['resume'][key].strip():
            raise ValueError('Tailor resume '+key+' before building')
    claim_ids = {cid for job in content['resume']['experience'] for cid in job['claim_ids']}
    # Letters may cite claims not selected in the resume; they are dependencies too.
    claim_ids.update(content.get('letter_claim_ids', []))
    claims = {}
    for cid in sorted(claim_ids):
        claim = profile['claims'].get(cid)
        if not claim or claim['status'] != 'active':
            raise ValueError('Missing or inactive claim: ' + cid)
        if claim.get('kind','experience')!='experience':raise ValueError('An experience boundary cannot be rendered as an accomplishment: '+cid)
        claims[cid] = claim
    employers = {job['employment_id'] for job in content['resume']['experience']}
    for job in content['resume']['experience']:
        for cid in job['claim_ids']:
            if claims[cid]['employment_id'] != job['employment_id']:
                raise ValueError('Claim assigned to wrong employer: ' + cid)
    # Only explicitly public contact data enters artifacts; no eligibility/preferences.
    public = {k: profile['candidate'].get(k, '') for k in ['name', 'email', 'phone', 'linkedin']}
    # A portal may require an application-specific verified contact address.
    # Keep the master contact and historical submission snapshots unchanged.
    if 'contact_email' in content:
        email = content['contact_email']
        if (not isinstance(email, str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)
                or not isinstance(content.get('contact_email_source'), str)
                or not content['contact_email_source'].strip()):
            raise ValueError('Application contact email requires a valid address and provenance')
        public['email'] = email
    employment = {k: dict(profile['employment'][k]) for k in sorted(employers)}
    # Candidate-confirmed display titles may differ by application audience.
    # Resolve them here so Markdown, PDF and build fingerprints stay consistent.
    overrides = content.get('employment_title_overrides', {})
    if not isinstance(overrides, dict):
        raise ValueError('Employment title overrides must be an object')
    for employment_id, override in overrides.items():
        if (employment_id not in employment or not isinstance(override, dict)
                or not isinstance(override.get('title'), str) or not override['title'].strip()
                or not isinstance(override.get('source'), str) or not override['source'].strip()):
            raise ValueError('Employment title override requires selected employer, title and provenance')
        employment[employment_id]['title'] = override['title']
    template = read(root / 'templates/resume.json')
    code = (Path(__file__).parent / 'render.py').read_text()
    return {'application': {k: r[k] for k in ['id', 'employer', 'requisition', 'title']},
            'candidate': public, 'employment': employment,
            'education': profile['education'], 'claims': claims, 'content': content,
            'template': template, 'renderer_sha256': hashlib.sha256(code.encode()).hexdigest()}


def current_build(root, record):
    build_id = record.get('latest_build')
    if not build_id:
        return 'legacy' if record.get('links') else 'not_built'
    try:
        base=root/'applications'/record['id']/'builds'/build_id
        if not (base/'manifest.json').exists():return 'missing'
        manifest=read(base/'manifest.json')
        if any(not (base/name).exists() for name in manifest['outputs']):return 'missing'
        return 'current' if digest(snapshot(root, record['id']))[:20] == build_id else 'stale'
    except (ValueError, FileNotFoundError, KeyError):
        return 'invalid'


def add_note(root, text, employer, source, project=None, kind="experience"):
    if kind not in {'experience','boundary'}:raise ValueError('Invalid claim kind')
    if not text.strip() or not source.strip():
        raise ValueError('Text and provenance source are required')
    profile = read(root / 'data/profile.json')
    if employer not in profile['employment']:
        raise ValueError('Unknown employment ID')
    note_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    note = {'id': note_id, 'created_at': now(), 'text': text, 'employment_id': employer,
            'source': source, 'project': project, 'kind': kind, 'status': 'pending'}
    write(root / 'data/intake' / (note_id + '.json'), note)
    return note


def accept_note(root, note_id, text, supersedes=None, tags=None):
    if not re.fullmatch(r'\d{8}T\d{12}', note_id):
        raise ValueError('Invalid intake ID')
    path = root / 'data/intake' / (note_id + '.json')
    note, profile = read(path), read(root / 'data/profile.json')
    if note_id in profile.get('accepted_intake', {}):
        note.update(status='accepted',claim_id=profile['accepted_intake'][note_id])
        write(path,note)
        return {'claim_id':note['claim_id'],'result':'already_accepted'}
    if note['status'] == 'accepted':
        return {'claim_id': note['claim_id'], 'result': 'already_accepted'}
    claim_id = supersedes or 'claim-' + digest({'note': note_id})[:12]
    old = profile['claims'].get(claim_id)
    if supersedes and (not old or old['employment_id'] != note['employment_id']):
        raise ValueError('Superseded claim must exist under the same employer')
    history = list(old.get('history', [])) if old else []
    if old:
        history.append({k: v for k, v in old.items() if k != 'history'})
    profile['claims'][claim_id] = {
        'id': claim_id, 'employment_id': note['employment_id'], 'text': text or note['text'],
        'revision': old['revision'] + 1 if old else 1, 'status': 'active',
        'verification': 'user_recorded', 'kind': note.get('kind','experience'), 'project': note.get('project') or (old.get('project') if old else None), 'tags': tags or (old.get('tags', []) if old else []),
        'sources': [{'kind': 'intake', 'path': str(path.relative_to(root)), 'source': note['source']}],
        'history': history, 'updated_at': now()}
    profile['revision'] += 1
    profile.setdefault('accepted_intake', {})[note_id] = claim_id
    write(root / 'data/profile.json', profile)
    note.update(status='accepted', claim_id=claim_id, accepted_at=now())
    write(path, note)
    return {'claim_id': claim_id, 'revision': profile['claims'][claim_id]['revision']}


def impact(root, claim_id):
    result = []
    for r in records(root):
        p = root / 'applications' / r['id'] / 'content.json'
        if not p.exists():
            continue
        c = read(p)
        selected = {cid for job in c['resume']['experience'] for cid in job['claim_ids']}
        selected.update(c.get('letter_claim_ids', []))
        if claim_id in selected:
            result.append({'id': r['id'], 'stage': r['stage'], 'pursuit': r['pursuit'],
                           'build': current_build(root, r), 'historical_submissions': len(r['submissions'])})
    return result


def profile_set(root, key, value, source):
    if key not in {'name', 'email', 'phone', 'linkedin'} or not source.strip():
        raise ValueError('Supported public metadata: name,email,phone,linkedin; provenance required')
    p = root / 'data/profile.json'
    profile = read(p)
    profile.setdefault('metadata_history', []).append({'at': now(), 'key': key,
        'previous': profile['candidate'].get(key), 'value': value, 'source': source})
    profile['candidate'][key] = value
    profile['revision'] += 1
    write(p, profile)


def search(root, query='', stage=None, pursuit=None, limit=25):
    db = database(root)
    where, params = ['(id LIKE ? OR employer LIKE ? OR title LIKE ? OR location LIKE ?)'], ['%'+query+'%']*4
    for key, value in [('stage',stage),('pursuit',pursuit)]:
        if value:
            where.append(key+'=?'); params.append(value)
    params.append(limit)
    try:
        return [dict(r) for r in db.execute('SELECT id,employer,requisition,title,stage,pursuit,priority,location FROM applications WHERE '+ ' AND '.join(where)+' ORDER BY id LIMIT ?',params)]
    finally:
        db.close()


def validate(root):
    errors = []
    profile = read(root / 'data/profile.json')
    for cid, claim in profile['claims'].items():
        if cid != claim['id'] or not claim.get('text') or not claim.get('sources') or claim['revision'] < 1:
            errors.append('Invalid claim ' + cid)
        if claim['employment_id'] not in profile['employment']:
            errors.append('Unknown claim employer ' + cid)
        for source in claim.get('sources', []):
            if source.get('path') and not local(root, source['path']).exists():
                errors.append('Missing source ' + source['path'])
    db=database(root)
    source_ids={row['sha256'] for row in db.execute('SELECT sha256 FROM posting_snapshots')}
    db.close()
    seen = set()
    for r in records(root):
        if r['id'] in seen or r['stage'] not in STAGES or r['pursuit'] not in PURSUITS or r['priority'] not in PRIORITIES:
            errors.append('Invalid job/state ' + r['id'])
        seen.add(r['id'])
        for source in r.get('sources',[]):
            if source.get('snapshot_id') and source['snapshot_id'] not in source_ids:errors.append(r['id']+': missing posting snapshot')
        for submission in r.get('submissions',[]):
            if not local(root,submission['path']).exists():errors.append(r['id']+': missing submitted package')
        for path in r.get('links', {}).values():
            if not local(root, path).exists():
                errors.append(r['id'] + ': missing ' + path)
        content = root / 'applications' / r['id'] / 'content.json'
        if content.exists():
            try:
                snapshot(root, r['id'])
            except (ValueError, KeyError, FileNotFoundError) as e:
                errors.append(r['id'] + ': ' + str(e))
    return errors


def employment_set(root, employment_id, value, source):
    if employment_id != slug(employment_id) or not source.strip() or not all(value.get(k) for k in ['employer','title','dates']):
        raise ValueError('Employment needs stable ID, employer, title, dates, and provenance')
    path=root/'data/profile.json';profile=read(path)
    previous=profile['employment'].get(employment_id)
    profile.setdefault('employment_history',[]).append({'at':now(),'id':employment_id,'previous':previous,'source':source})
    profile['employment'][employment_id]=value;profile['revision']+=1;write(path,profile)
    return {'employment_id':employment_id,'result':'updated' if previous else 'created'}


def preference_set(root, key, value, source):
    if not key or not source.strip():raise ValueError('Preference key and provenance required')
    path=root/'data/profile.json';profile=read(path)
    profile.setdefault('preference_history',[]).append({'at':now(),'key':key,'previous':profile['preferences'].get(key),'source':source})
    profile['preferences'][key]=value;profile['revision']+=1;write(path,profile)
    return {'preference':key,'result':'updated; rerun affected screening decisions explicitly'}
