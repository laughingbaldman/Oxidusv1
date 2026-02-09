#!/usr/bin/env python3
"""Run targeted QA checks on a handful of loaded KnowledgeText entries to verify recall and summarization."""
import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.oxidus import Oxidus

ox = Oxidus()
kb = ox.knowledge_base

# Pick a few representative texts (if available)
candidates = []
for cat in ['ethics', 'psychology', 'science', 'history', 'wiki']:
    texts = kb.get_texts_by_category(cat)[:2]
    for t in texts:
        candidates.append((cat, t.title, t.id))

if not candidates:
    print('No texts found for QA')
    sys.exit(0)

for cat, title, tid in candidates:
    print('\n== TEXT ==')
    print(f'Category: {cat} | Title: {title} | ID: {tid}')
    # Ask Oxidus to summarize the text by ID
    prompt = f"Summarize the key points of '{title}' in 3 bullet points." 
    resp = ox.safe_think(prompt, user_id=ox.owner_id)
    print('\nResponse:')
    print(resp[:1000])
    # Ask memory index for topics related to this title
    if ox.memory_index:
        topics = ox.memory_index.extract_topics(title)
        print('\nExtracted topics:', topics)
        recalled = ox.memory_index.recall_by_topics(topics, max_results=3) if topics else []
        print('\nRecalled memories count:', len(recalled))
        for r in recalled:
            print('-', r.content[:200])

print('\nQA complete')
