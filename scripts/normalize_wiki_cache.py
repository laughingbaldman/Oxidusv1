#!/usr/bin/env python3
"""Normalize wiki/cache JSONs into KnowledgeText-like JSON files with 'content' field.
"""
import json
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parent.parent
kb_root = repo_root / 'data' / 'knowledge_base'

candidates = list(kb_root.glob('**/cache/**/*.json')) + list(kb_root.glob('**/wiki/**/*.json'))
processed = 0
fixed = 0
skipped = 0

def find_text_in_obj(obj):
    # Search for the first reasonably long string in nested structures
    if isinstance(obj, str):
        if len(obj.strip()) > 50:
            return obj.strip()
        return None
    if isinstance(obj, dict):
        # common keys
        for key in ('content','text','extract','summary','body','article','page','content_text'):
            if key in obj and isinstance(obj[key], str) and len(obj[key].strip())>50:
                return obj[key].strip()
        for v in obj.values():
            t = find_text_in_obj(v)
            if t:
                return t
    if isinstance(obj, list):
        for item in obj:
            t = find_text_in_obj(item)
            if t:
                return t
    return None

for p in candidates:
    processed += 1
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        skipped += 1
        continue
    # If already has content, skip
    if isinstance(data, dict) and data.get('content') and isinstance(data.get('content'), str) and len(data.get('content').strip())>50:
        continue
    # Try to find text
    text = find_text_in_obj(data)
    if not text:
        skipped += 1
        continue
    # Build normalized structure
    title = data.get('title') if isinstance(data, dict) and data.get('title') else p.stem
    normalized = {
        'title': title,
        'author': data.get('author') if isinstance(data, dict) and data.get('author') else 'Unknown',
        'category': 'wiki',
        'content': text,
        'source_url': data.get('source_url') if isinstance(data, dict) and data.get('source_url') else '',
        'publication_year': None
    }
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)
        fixed += 1
    except Exception:
        skipped += 1

print('Processed:', processed)
print('Fixed:', fixed)
print('Skipped:', skipped)
