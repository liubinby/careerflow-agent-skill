#!/usr/bin/env python3
"""Install a built skill into a chosen directory; never overwrite an installation."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from zipfile import ZipFile

NAME='job-application-workflow'


def install(bundle, destination):
    destination=destination.expanduser().absolute()
    if destination.name != NAME:
        raise ValueError('Destination directory must be named '+NAME)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination exists; refusing to overwrite: '+str(destination))
    with ZipFile(bundle) as archive:
        infos=archive.infolist()
        paths=[i.filename for i in infos]
        if len(paths)!=len(set(paths)) or sum(i.file_size for i in infos)>10_000_000:
            raise ValueError('Duplicate entries or oversized skill bundle')
        for info in infos:
            path=PurePosixPath(info.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in info.filename
                    or not path.parts or path.parts[0]!=NAME
                    or (info.external_attr>>16)&0o170000 == 0o120000):
                raise ValueError('Unsafe bundle path: '+info.filename)
        manifest_name=NAME+'/bundle-manifest.json'
        manifest=json.loads(archive.read(manifest_name))
        files=manifest['files']
        if set(paths)!=(set(files)|{manifest_name}):
            raise ValueError('Bundle contents do not match manifest')
        if NAME+'/SKILL.md' not in files or NAME+'/scripts/runtime/careerflow/__main__.py' not in files:
            raise ValueError('Bundle is missing skill or runtime')
        # Check every hash before creating anything at the installation path.
        for name,digest in files.items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:
                raise ValueError('Bundle hash mismatch: '+name)
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=Path(tempfile.mkdtemp(prefix='.careerflow-install-',dir=destination.parent))
        try:
            archive.extractall(temporary)
            (temporary/NAME).rename(destination)
        finally:
            shutil.rmtree(temporary)
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True,help='Full target path ending in job-application-workflow')
    args=parser.parse_args()
    try:print(install(args.bundle,args.destination))
    except (ValueError,KeyError) as exc:parser.exit(2,'Error: '+str(exc)+'\n')
