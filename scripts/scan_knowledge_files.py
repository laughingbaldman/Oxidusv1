#!/usr/bin/env python3
"""Scan data/knowledge_base JSON files for invalid JSON or missing/invalid 'content' field."""
import sys
from pathlib import Path
import json

repo_root = Path(__file__).resolve().parent.parent
kb_root = repo_root / 'data' / 'knowledge_base'

problems = {
    'invalid_json': [],
    'missing_content': [],
}

count = 0
for cat in kb_root.glob('**/*.json'):
    count += 1
    try:
        with open(cat, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        problems['invalid_json'].append((str(cat), str(e)))
        continue
    content = data.get('content') if isinstance(data, dict) else None
    if not content or not isinstance(content, str):
        problems['missing_content'].append(str(cat))

print('Total JSON files scanned:', count)
print('Invalid JSON files:', len(problems['invalid_json']))
for p, err in problems['invalid_json'][:20]:
    print('  INVALID:', p, '->', err)
print('\nFiles missing content:', len(problems['missing_content']))
for p in problems['missing_content'][:20]:
    print('  MISSING:', p)
