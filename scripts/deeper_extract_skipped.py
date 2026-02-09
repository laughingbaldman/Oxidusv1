#!/usr/bin/env python3
"""Attempt deeper extraction from skipped knowledge JSON files.
Reads `data/knowledge_base/skipped_missing_content.txt` if present, otherwise scans the knowledge_base
for JSON files missing a non-empty `content` field. Recovers string values recursively and writes
normalized JSON to `data/knowledge_base/normalized_deeper/` when extraction yields sufficient text.
"""
import json
import sys
from pathlib import Path
from collections import deque

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src' / 'utils'))

from knowledge_markdown import write_markdown

KB_DIR = ROOT / 'data' / 'knowledge_base'
SKIPPED_LIST = KB_DIR / 'skipped_missing_content.txt'
OUT_DIR = KB_DIR / 'normalized_deeper'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def collect_strings(obj):
    out = []
    stack = deque([obj])
    while stack:
        v = stack.pop()
        if v is None:
            continue
        if isinstance(v, str):
            out.append(v.strip())
        elif isinstance(v, dict):
            for val in v.values():
                stack.append(val)
        elif isinstance(v, (list, tuple)):
            for item in v:
                stack.append(item)
        else:
            # non-string leaf; stringify small primitives
            if isinstance(v, (int, float, bool)):
                out.append(str(v))
    return ' '.join([s for s in out if s])


def candidates_from_skipfile():
    if SKIPPED_LIST.exists():
        with SKIPPED_LIST.open('r', encoding='utf-8') as f:
            for line in f:
                path = line.strip()
                if not path:
                    continue
                p = ROOT / path if not Path(path).is_absolute() else Path(path)
                if p.exists():
                    yield p
    else:
        # fallback: scan KB for JSONs missing `content`
        for p in KB_DIR.rglob('*.json'):
            try:
                j = json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            content = j.get('content')
            if not content or not isinstance(content, str) or len(content.strip()) < 50:
                yield p


def main():
    processed = 0
    recovered = 0
    for p in candidates_from_skipfile():
        processed += 1
        try:
            raw = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"Skipping {p} (invalid JSON): {e}")
            continue
        text = collect_strings(raw)
        # heuristic: require at least 300 characters of recovered text
        if len(text) < 300:
            print(f"Insufficient extraction from {p} (len={len(text)})")
            continue
        # build normalized object
        norm = {
            'id': p.stem,
            'title': raw.get('title') or p.stem,
            'author': raw.get('author', 'unknown'),
            'category': raw.get('category', 'wiki'),
            'content': text,
            'source_file': str(p.relative_to(ROOT))
        }
        out_path = OUT_DIR / p.name
        try:
            out_path.write_text(json.dumps(norm, ensure_ascii=False, indent=2), encoding='utf-8')
            md_path = out_path.with_suffix('.md')
            front_matter = {
                'id': norm.get('id'),
                'title': norm.get('title'),
                'author': norm.get('author'),
                'category': norm.get('category'),
                'source_file': norm.get('source_file')
            }
            write_markdown(md_path, front_matter, norm.get('content', ''))
            recovered += 1
            print(f"Recovered -> {out_path}")
        except Exception as e:
            print(f"Failed to write {out_path}: {e}")
    print(f"Processed: {processed}, Recovered: {recovered}")


if __name__ == '__main__':
    main()
