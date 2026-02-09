#!/usr/bin/env python3
"""
Normalize thought stream JSONs into a richer schema.

Usage:
  python scripts/normalize_thought_stream.py input_path.json [output_path.json]

The script will produce a normalized JSON alongside the input if no output is given.
"""
import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict

STOPWORDS = set([
    "the","and","is","in","to","of","a","an","that","this","it","for",
    "on","with","as","are","was","were","be","by","or","from","at","which",
    "i","you","he","she","they","we","us","them","his","her","their"
])


def load_stream(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_stream(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def tokenize(text):
    tokens = re.findall(r"\w+", text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def sentence_split(text):
    # naive sentence split
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def top_keywords(text, k=8):
    tokens = tokenize(text)
    return [w for w, _ in Counter(tokens).most_common(k)]


def summarize_to_fraction(text, fraction=1/8):
    if not text:
        return ""
    sentences = sentence_split(text)
    if not sentences:
        return text[:200]
    words = re.findall(r"\w+", text)
    target_words = max(1, math.ceil(len(words) * fraction))

    freq = Counter(tokenize(text))

    # score sentences by sum of keyword frequencies
    sent_scores = []
    for s in sentences:
        score = sum(freq.get(w, 0) for w in tokenize(s))
        sent_scores.append((score, s))

    sent_scores.sort(reverse=True)

    chosen = []
    chosen_words = 0
    for score, s in sent_scores:
        s_word_count = len(re.findall(r"\w+", s))
        if chosen_words + s_word_count <= target_words or not chosen:
            chosen.append(s)
            chosen_words += s_word_count
        if chosen_words >= target_words:
            break

    # preserve original order
    chosen_set = set(chosen)
    ordered = [s for s in sentences if s in chosen_set]
    return ' '.join(ordered)


def build_knowledge_tree(text, top_k=6):
    keywords = top_keywords(text, k=top_k)
    sentences = sentence_split(text)
    tree = {}
    for kw in keywords:
        occurrences = [s for s in sentences if re.search(r"\b" + re.escape(kw) + r"\b", s, re.I)]
        tree[kw] = {
            'count': len(occurrences),
            'sentences': occurrences[:5]
        }

    # simple relations: co-occurrence counts
    relations = []
    for i, a in enumerate(keywords):
        for b in keywords[i+1:]:
            co = sum(1 for s in sentences if re.search(r"\b"+re.escape(a)+r"\b", s, re.I) and re.search(r"\b"+re.escape(b)+r"\b", s, re.I))
            if co:
                relations.append({'a': a, 'b': b, 'cooccurrence': co})

    return {'keywords': keywords, 'nodes': tree, 'relations': relations}


def normalize_thoughts(stream):
    thoughts = stream.get('thoughts', [])
    combined_text = ' '.join([t.get('content','') or '' for t in thoughts])

    normalized = []
    freq = Counter(tokenize(combined_text))
    top_kw = [k for k,_ in freq.most_common(12)]

    for i, t in enumerate(thoughts):
        entry = {
            'id': i,
            'timestamp': t.get('timestamp'),
            'type': t.get('type'),
            'content': t.get('content'),
            'context': t.get('context', {}),
        }

        # enrich questions with topic and relevance
        if entry['type'] == 'question' or (isinstance(entry['content'], str) and entry['content'].strip().endswith('?')):
            tokens = tokenize(entry['content'] or '')
            # topic: best matching top keyword or first 4 words
            topic = next((kw for kw in top_kw if kw in tokens), None)
            if not topic:
                topic = ' '.join((entry['content'] or '').split()[:4])
            # relevance: overlap with top_kw
            overlap = sum(1 for w in tokens if w in top_kw)
            relevance = round(min(1.0, overlap / max(1, len(tokens))) if tokens else 0.0, 2)
            entry['topic'] = topic
            entry['relevance'] = relevance

        normalized.append(entry)

    summary = summarize_to_fraction(combined_text, fraction=1/8)
    knowledge = build_knowledge_tree(combined_text, top_k=8)

    # generate clarifying questions about top keywords and loose ends
    clarifying = []
    kws = knowledge.get('keywords', [])
    for i, kw in enumerate(kws):
        # general clarifier
        clarifying.append(f"What are the main causes or drivers of {kw}?")
        # relational clarifier
        if i+1 < len(kws):
            clarifying.append(f"How does {kw} relate to {kws[i+1]}?")

    # deduplicate and keep to a reasonable size
    clarifying = list(dict.fromkeys(clarifying))[:20]

    return {
        'timestamp': stream.get('timestamp'),
        'original_file_thought_count': stream.get('thought_count'),
        'normalized_thoughts': normalized,
        'summary': summary,
        'knowledge_tree': knowledge,
        'clarifying_questions': clarifying,
        'cumulative_stats': stream.get('cumulative_stats', {})
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('input', help='input thought stream json path')
    p.add_argument('output', nargs='?', help='output normalized json path')
    args = p.parse_args()

    inp = args.input
    out = args.output
    if not out:
        base, ext = os.path.splitext(inp)
        out = base + '.normalized.json'

    stream = load_stream(inp)
    norm = normalize_thoughts(stream)
    save_stream(norm, out)
    print(f"Wrote normalized output to {out}")


if __name__ == '__main__':
    main()
