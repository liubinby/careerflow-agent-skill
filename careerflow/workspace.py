"""First-run setup and diagnostics, without candidate-specific defaults."""
import importlib.util
from pathlib import Path
import shutil
import sys

from . import core


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get('schema_version') != 1:
        raise ValueError('Profile requires schema_version=1')
    if type(profile.get('revision')) is not int or profile['revision'] < 1:
        raise ValueError('Profile revision must be a positive integer')
    for key in ('candidate', 'employment', 'claims', 'preferences'):
        if not isinstance(profile.get(key), dict):
            raise ValueError('Profile ' + key + ' must be an object')
    if not isinstance(profile.get('education'), list) or not all(isinstance(x,str) for x in profile['education']):
        raise ValueError('Education must be a list of text entries')
    for key in ('name', 'email', 'phone', 'linkedin'):
        if not isinstance(profile['candidate'].get(key, ''), str):
            raise ValueError('Candidate ' + key + ' must be text')
    for eid, employment in profile['employment'].items():
        if eid != core.slug(eid) or not isinstance(employment, dict) or not all(
                isinstance(employment.get(k),str) and employment[k].strip() for k in ('employer','title','dates')):
            raise ValueError('Employment requires stable ID, employer, title and dates')
    for cid, claim in profile['claims'].items():
        if not isinstance(claim,dict) or claim.get('id') != cid or claim.get('employment_id') not in profile['employment']:
            raise ValueError('Claim needs matching ID and existing employment: ' + cid)
        if (not isinstance(claim.get('text'),str) or not claim['text'].strip()
                or type(claim.get('revision')) is not int or claim['revision'] < 1
                or claim.get('status') not in {'active','inactive'}
                or not isinstance(claim.get('sources'),list) or not claim['sources']
                or not all(isinstance(s,dict) and s.get('kind') for s in claim['sources'])
                or not isinstance(claim.get('verification'),str)):
            raise ValueError('Claim needs text, revision, status, provenance and verification: ' + cid)


def initialize(root, profile_file=None, template_file=None):
    # Validate both inputs and every destination before the first content write.
    profile = core.read(profile_file) if profile_file else {
        'schema_version':1, 'revision':1,
        'candidate':{'name':'','email':'','phone':'','linkedin':''},
        'employment':{}, 'education':[], 'claims':{}, 'preferences':{}}
    validate_profile(profile)
    for claim in profile['claims'].values():
        for source in claim['sources']:
            if source.get('path'):core.local(root,source['path'])
    template = core.read(template_file or Path(__file__).parent/'assets/resume.json')
    if not isinstance(template,dict) or template.get('version') != 1:
        raise ValueError('Resume template requires version=1')
    destinations = [root/'data/profile.json', root/'templates/resume.json']
    if any(p.exists() for p in destinations):
        raise ValueError('Workspace profile or template exists; refusing to overwrite')
    # Ignore private material by default even when a workspace is inside a code checkout.
    ignore = root/'.gitignore'
    addition = '\n# Private Careerflow workspace\n/data/\n/applications/\n/interviews/\n/training/\n/evidence/\n/profile/\n/employment/\n/.careerflow/\n/APPLICATIONS.html\n/APPLICATIONS.md\n'
    previous = ignore.read_text() if ignore.exists() else ''
    core.write(destinations[1], template)
    core.write(destinations[0], profile)
    ignore.write_text(previous + addition)
    core.checkpoint(root)
    return {'result':'initialized', 'root':str(root), 'next':'Add candidate-confirmed profile facts; run doctor before PDF builds.'}


def doctor():
    tools = {name:shutil.which(name) is not None for name in ('pdftotext','pdfinfo','pdftoppm')}
    reportlab = importlib.util.find_spec('reportlab') is not None
    return {'python':sys.version.split()[0], 'metadata_ready':sys.version_info >= (3,10),
            'reportlab':reportlab, 'tools':tools,
            'pdf_build_ready':reportlab and tools['pdftotext'] and tools['pdfinfo'],
            'pdf_visual_review_ready':tools['pdftoppm'],
            'note':'Metadata has no third-party dependencies. Install the pdf extra and Poppler for PDFs. Use Linux, macOS or WSL; native Windows is not supported.'}
