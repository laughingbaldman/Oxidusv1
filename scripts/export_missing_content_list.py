#!/usr/bin/env python3
"""Export full list of knowledge_base JSON files missing a usable 'content' field to a text file."""
import sys
from pathlib import Path
import json

repo_root = Path(__file__).resolve().parent.parent
kb_root = repo_root / 'data' / 'knowledge_base'
scan_roots = [
    kb_root / 'wiki_corpus',
    kb_root / 'notes'
]

out = repo_root / 'data' / 'knowledge_base' / 'skipped_missing_content.txt'

missing = []
count = 0
skipped = 0
skip_dirs = {'cache', 'wiki_cache'}

for root in scan_roots:
    if not root.exists():
        continue
    for p in root.glob('**/*.json'):
        if any(part in skip_dirs for part in p.parts):
            skipped += 1
            continue
        count += 1
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            missing.append(f'{p}    INVALID_JSON')
            continue
        content = None
        if isinstance(data, dict):
            content = data.get('content')
        if not content or not isinstance(content, str) or len(content.strip()) < 50:
            missing.append(str(p))

with open(out, 'w', encoding='utf-8') as f:
    f.write(f'Total scanned: {count}\n')
    f.write(f'Skipped (cache): {skipped}\n')
    f.write(f'Missing or invalid content: {len(missing)}\n')
    f.write('Scan roots:\n')
    for root in scan_roots:
        f.write(f'- {root}\n')
    f.write('\n')
    for m in missing:
        f.write(m + '\n')

print('Wrote', out)
