#!/usr/bin/env python3
"""
Simple heuristic sorter for knowledge JSON files.
Usage:
  python scripts/sort_knowledge.py --source <backup_dir> --out <out_dir>

It scans JSON files recursively, inspects filename and common keys (title/text/content),
then places files into category folders under the output directory.
"""
import argparse
import json
import os
import shutil
from collections import defaultdict

CATEGORY_KEYWORDS = {
    'science': ['science','astronomy','physics','chemistry','biology','planet','star','galaxy','astronom','cosmo','space','nasa'],
    'history': ['history','histor','ancient','medieval','timeline','war','empire','revolution'],
    'philosophy': ['philosophy','philosoph','critica','critical thinking','logic','metaphys','epistem'],
    'ethics': ['ethic','ethical','golden rule','moral','morals','ethics'],
    'psychology': ['psychology','psycholog','mind','behavior','behaviour','cognitive','human nature'],
    'wiki': ['wiki','wikipedia','encyclopedia']
}

def text_for_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        try:
            return open(path, 'r', encoding='utf-8', errors='ignore').read()
        except Exception:
            return ''
    # flatten common fields
    parts = []
    if isinstance(data, dict):
        for k in ('title','name','headline'):
            if k in data and isinstance(data[k], str):
                parts.append(data[k])
        for k in ('text','content','body','summary','excerpt'):
            if k in data:
                v = data[k]
                if isinstance(v, str):
                    parts.append(v[:1000])
                elif isinstance(v, list):
                    parts.extend([str(x) for x in v[:3]])
    else:
        parts.append(str(data)[:1000])
    return ' '.join(parts)


def categorize_text(text):
    if not text:
        return 'uncategorized'
    t = text.lower()
    # check exact keyword groups
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                return cat
    # fallback heuristics
    if 'ngc' in t or 'messier' in t or 'galaxy' in t or 'planet' in t:
        return 'science'
    return 'uncategorized'


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source','-s', required=True)
    p.add_argument('--out','-o', required=True)
    args = p.parse_args()

    src = os.path.abspath(args.source)
    out = os.path.abspath(args.out)
    ensure_dir(out)

    counts = defaultdict(int)
    total = 0

    for root, dirs, files in os.walk(src):
        for fn in files:
            if not fn.lower().endswith('.json'):
                continue
            total += 1
            src_path = os.path.join(root, fn)
            # try to build a text blob from filename + content
            blob = fn.replace('_',' ').replace('-', ' ')
            blob += ' ' + text_for_file(src_path)
            cat = categorize_text(blob)
            dest_dir = os.path.join(out, cat)
            ensure_dir(dest_dir)
            # avoid name collisions by preserving directory structure under out
            rel = os.path.relpath(src_path, src)
            dest_path = os.path.join(dest_dir, rel)
            dest_parent = os.path.dirname(dest_path)
            ensure_dir(dest_parent)
            try:
                shutil.move(src_path, dest_path)
            except Exception:
                # fallback to copy then remove
                shutil.copy2(src_path, dest_path)
                try:
                    os.remove(src_path)
                except Exception:
                    pass
            counts[cat] += 1

    print(f"Processed {total} JSON files.")
    for c, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{c}: {n}")

if __name__ == '__main__':
    main()
