#!/usr/bin/env python3
"""Build a self-contained skill from an explicit public-file allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
NAME = 'job-application-workflow'
FILES = [
    'SKILL.md', 'agents/openai.yaml', 'scripts/manage_applications.py',
    'references/workspace.md', 'references/applications.md', 'references/interviews-training.md', 'references/training-sessions.md',
]
MODULES = ['__init__.py','__main__.py','core.py','dashboard.py','render.py','workspace.py','learning.py','training.py','training_web.py']


def members(root=ROOT):
    result = {NAME+'/'+name:root/'skills'/NAME/name for name in FILES}
    result.update({NAME+'/scripts/runtime/careerflow/'+name:root/'careerflow'/name for name in MODULES})
    result[NAME+'/scripts/runtime/careerflow/assets/resume.json'] = root/'careerflow/assets/resume.json'
    result[NAME+'/scripts/runtime/careerflow/assets/training.html'] = root/'careerflow/assets/training.html'
    result[NAME+'/LICENSE'] = root/'LICENSE'
    for path in result.values():
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Missing or unsafe release input: '+str(path))
    return result


def build(output, root=ROOT):
    inputs=members(root)
    if output.resolve() in {p.resolve() for p in inputs.values()}:
        raise ValueError('Output would overwrite a release input')
    output.parent.mkdir(parents=True,exist_ok=True)
    hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in inputs.items()}
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for name,path in sorted(inputs.items()):archive.writestr(name,path.read_bytes())
        archive.writestr(NAME+'/bundle-manifest.json',json.dumps({'schema_version':1,'files':hashes},indent=2)+'\n')
    return output


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist'/f'{NAME}.zip')
    print(build(parser.parse_args().output))
