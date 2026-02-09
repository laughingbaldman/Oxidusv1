#!/usr/bin/env python3
"""Run a series of owner-mode smoke queries against Oxidus.safe_think()."""
import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.oxidus import Oxidus

queries = [
    "Hello, how are you?",
    "What is freedom?",
    "Summarize the key mechanisms that cause ocean tides.",
    "Give me three practical steps to encourage growth mindset in students.",
    "What are the ethics of autonomous systems in medicine?"
]

ox = Oxidus()
for q in queries:
    print('\n== QUERY ==')
    print(q)
    resp = ox.safe_think(q, user_id=ox.owner_id)
    print('\n== RESPONSE ==')
    print(resp[:800])
