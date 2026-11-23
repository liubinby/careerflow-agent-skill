#!/usr/bin/env python3
"""Initialize or resume a private workspace and launch its local training app."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from careerflow import core, workspace, training_web

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path(os.environ.get('CAREERFLOW_WORKSPACE',str(Path.home()/'careerflow-workspace'))))
parser.add_argument('--port',type=int,default=8872)
parser.add_argument('--no-browser',action='store_true')
parser.add_argument('--foreground',action='store_true')
args=parser.parse_args()
try:
    root=args.root.expanduser().resolve()
    with core.locked(root):
        if not (root/'data/profile.json').exists():workspace.initialize(root)
    result=training_web.run(root,args.port,args.foreground,not args.no_browser)
    print('Careerflow training: '+result['url'])
    print('Private workspace: '+str(root))
    print('Use your AI agent with job-application-workflow to generate lessons and review submitted attempts.')
except (ValueError,OSError) as exc:parser.exit(2,'Error: '+str(exc)+'\n')
