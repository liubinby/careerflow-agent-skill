#!/usr/bin/env python3
"""Use the bundled runtime, or the source checkout; never infer a private root."""
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
runtime = here/'runtime'
repository = here.parents[2]
if (runtime/'careerflow/__main__.py').is_file():
    sys.path.insert(0,str(runtime))
elif (repository/'careerflow/__main__.py').is_file():
    sys.path.insert(0,str(repository))
else:
    raise SystemExit('Runtime missing. Install the generated skill bundle, not the bare skill source folder.')

from careerflow.__main__ import main
if __name__ == '__main__':
    main()
