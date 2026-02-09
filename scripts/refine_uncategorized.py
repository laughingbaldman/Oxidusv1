#!/usr/bin/env python3
"""
Refine classification for previously `uncategorized` JSON files.
Usage:
  python scripts/refine_uncategorized.py --src <uncat_dir> --root <sorted_root>
This script applies extra heuristics (filename patterns, wiki markers, philosopher/psychology names,
history date patterns, astronomy identifiers) and moves files into better categories under the
existing sorted root.
"""
import argparse
import os
import re
import shutil
from collections import defaultdict

PHILOSOPHERS = ['plato','aristotle','kant','nietzsche','socrates','descartes','hume','locke','spinoza']
PSYCH_NAMES = ['freud','jung','behavior','behaviour','cognitive','piaget','skinner','maslow']
HISTORY_MARKERS = ['bc','ad','century','king','queen','empire','battle','war','revolution','treaty']
ASTRO_MARKERS = ['ngc','messier','star','galaxy','nebula','exoplanet','planet','astronom','constellation']
WIKI_MARKERS = ['references','external links','==','[[','wikipedia','infobox']
CHEM_PHYS = ['chemistry','physics','atom','molecule','element','electron','proton','neutron','quantum','thermo']

KW_GROUPS = {
    'philosophy': PHILOSOPHERS,
    'psychology': PSYCH_NAMES,
    'history': HISTORY_MARKERS,
    'science': CHEM_PHYS + ASTRO_MARKERS,
    'wiki': WIKI_MARKERS,
    'astronomy': ASTRO_MARKERS,
}

YEAR_RE = re.compile(r"\b(\d{3,4})\b")


def read_text(path):
    try:
        import json
        with open(path, 'r', encoding='utf-8') as f:
            j = json.load(f)
        if isinstance(j, dict):
            parts = []
            for k in ('title','name','headline'):
                if k in j and isinstance(j[k], str):
                    parts.append(j[k])
            for k in ('text','content','body','summary','excerpt'):
                if k in j:
                    v = j[k]
                    if isinstance(v, str):
                        parts.append(v[:2000])
                    elif isinstance(v, list):
                        parts.extend([str(x)[:200] for x in v[:3]])
            return ' '.join(parts)
        else:
            return str(j)[:2000]
    except Exception:
        try:
            return open(path, 'r', encoding='utf-8', errors='ignore').read()[:2000]
        except Exception:
            return ''


def ensure(p):
    os.makedirs(p, exist_ok=True)


def classify_blob(fn, text):
    name = os.path.basename(fn).lower()
    # filename heuristics
    if name.startswith('wiki_') or name.endswith('.wiki.json') or 'wikipedia' in name:
        return 'wiki'
    # wiki content markers
    low = text.lower()
    for m in WIKI_MARKERS:
        if m in low:
            return 'wiki'
    # philosopher names
    for p in PHILOSOPHERS:
        if p in low or p in name:
            return 'philosophy'
    for p in PSYCH_NAMES:
        if p in low or p in name:
            return 'psychology'
    for p in ASTRO_MARKERS:
        if p in low or p in name:
            return 'science'
    for p in HISTORY_MARKERS:
        if p in low or p in name:
            return 'history'
    for p in CHEM_PHYS:
        if p in low:
            return 'science'
    # year-heavy documents -> history
    years = YEAR_RE.findall(low)
    if years and any( (1000 <= int(y) <= 2100) for y in years ):
        return 'history'
    # fallback: if text is long treat as wiki/science
    if len(low) > 1000:
        # if many technical words -> science else wiki
        tech = sum(1 for w in ['figure','table','data','observ','spectrum','galaxy','experiment'] if w in low)
        if tech >= 2:
            return 'science'
        return 'wiki'
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--src','-s', required=True)
    p.add_argument('--root','-r', required=True)
    args = p.parse_args()

    src = os.path.abspath(args.src)
    root = os.path.abspath(args.root)
    counts = defaultdict(int)
    moved = 0

    for fn in os.listdir(src):
        if not fn.lower().endswith('.json'):
            continue
        src_path = os.path.join(src, fn)
        text = read_text(src_path)
        cat = classify_blob(fn, text)
        if not cat:
            # try reading a bit more (full file) for stronger heuristics
            try:
                text_full = open(src_path, 'r', encoding='utf-8', errors='ignore').read()
            except Exception:
                text_full = text
            cat = classify_blob(fn, text_full) or 'uncategorized'
        dest_dir = os.path.join(root, cat)
        ensure(dest_dir)
        try:
            shutil.move(src_path, os.path.join(dest_dir, fn))
            counts[cat] += 1
            moved += 1
        except Exception:
            # fallback to copy
            try:
                shutil.copy2(src_path, os.path.join(dest_dir, fn))
                counts[cat] += 1
                moved += 1
            except Exception:
                print('failed:', src_path)

    print(f'Refined and moved {moved} files:')
    for c,n in sorted(counts.items(), key=lambda x:-x[1]):
        print(f'{c}: {n}')

if __name__ == '__main__':
    main()
