#!/usr/bin/env python3
"""Package the submission source, final PDF, and raw evidence for handoff."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/DOKS_Submission.zip'
files=[]
for folder in ['app','k8s','scripts','docs','evidence']:
    for path in (ROOT/folder).rglob('*'):
        if path.is_file() and path.name!='.DS_Store' and '__pycache__' not in path.parts and path.suffix!='.pyc':
            files.append(path)
files.extend([ROOT/'README.md',ROOT/'.gitignore',ROOT/'output/pdf/DOKS_TAM_Case_Study.pdf',ROOT/'output/pdf/build-info.json'])
assert all(path.exists() for path in files)
manifest={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}
with ZipFile(OUT,'w',ZIP_DEFLATED) as bundle:
    for path in sorted(files): bundle.write(path,path.relative_to(ROOT))
    bundle.writestr('SHA256SUMS.json',json.dumps(manifest,indent=2)+'\n')
with ZipFile(OUT) as bundle:
    assert bundle.testzip() is None
print(f'{OUT}: {len(files)} files, {OUT.stat().st_size:,} bytes; integrity check passed')
