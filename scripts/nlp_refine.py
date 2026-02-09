#!/usr/bin/env python3
"""
NLP-based refiner: trains a TF-IDF + MultinomialNB classifier on already-sorted categories
and classifies files from the `uncategorized` folder. Moves files to predicted category.
Usage:
  python scripts/nlp_refine.py --root <sorted_root>
"""
import argparse
import json
import os
import shutil
from collections import defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

CATS_EXCLUDE = ('uncategorized',)


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            j = json.load(f)
    except Exception:
        try:
            return open(path, 'r', encoding='utf-8', errors='ignore').read()
        except Exception:
            return ''
    parts = []
    if isinstance(j, dict):
        for k in ('title','name','headline'):
            if k in j and isinstance(j[k], str):
                parts.append(j[k])
        for k in ('text','content','body','summary','excerpt'):
            if k in j:
                v = j[k]
                if isinstance(v, str):
                    parts.append(v[:2000])
                elif isinstance(v, list):
                    parts.extend([str(x) for x in v[:3]])
    else:
        parts.append(str(j)[:2000])
    return ' '.join(parts)


def collect_training(root):
    X = []
    y = []
    for name in os.listdir(root):
        cat_dir = os.path.join(root, name)
        if not os.path.isdir(cat_dir):
            continue
        if name.lower() in CATS_EXCLUDE:
            continue
        for dirpath, _, files in os.walk(cat_dir):
            for fn in files:
                if not fn.lower().endswith('.json'):
                    continue
                fp = os.path.join(dirpath, fn)
                txt = read_text(fp)
                if not txt.strip():
                    continue
                X.append(txt)
                y.append(name)
    return X, y


def classify_uncat(root):
    uncat_dir = os.path.join(root, 'uncategorized')
    if not os.path.isdir(uncat_dir):
        print('No uncategorized folder, nothing to do.')
        return
    # collect training
    X_train, y_train = collect_training(root)
    if len(X_train) < 20:
        print('Not enough training samples (need >=20). Skipping NLP pass.')
        return
    vec = TfidfVectorizer(max_features=20000, ngram_range=(1,2))
    Xv = vec.fit_transform(X_train)
    clf = MultinomialNB()
    clf.fit(Xv, y_train)

    moved = defaultdict(int)
    total = 0
    for dirpath, _, files in os.walk(uncat_dir):
        for fn in files:
            if not fn.lower().endswith('.json'):
                continue
            fp = os.path.join(dirpath, fn)
            txt = read_text(fp)
            if not txt.strip():
                target = 'uncategorized'
            else:
                xv = vec.transform([txt])
                pred = clf.predict(xv)[0]
                target = pred
            dest_dir = os.path.join(root, target)
            os.makedirs(dest_dir, exist_ok=True)
            try:
                shutil.move(fp, os.path.join(dest_dir, fn))
            except Exception:
                try:
                    shutil.copy2(fp, os.path.join(dest_dir, fn))
                    os.remove(fp)
                except Exception:
                    print('failed to move:', fp)
                    continue
            moved[target] += 1
            total += 1
    print(f'NLP refined {total} files:')
    for k,v in sorted(moved.items(), key=lambda x:-x[1]):
        print(f'{k}: {v}')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root','-r', required=True)
    args = p.parse_args()
    classify_uncat(os.path.abspath(args.root))
