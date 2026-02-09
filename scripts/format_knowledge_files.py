#!/usr/bin/env python3
"""Backfill readable markdown for knowledge base JSON files."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src' / 'utils'))

from knowledge_markdown import epoch_to_iso, write_markdown

KB_DIR = ROOT / 'data' / 'knowledge_base'
WIKI_DIR = KB_DIR / 'wiki_corpus'
NORMALIZED_DIR = KB_DIR / 'normalized_deeper'
NOTES_DIR = KB_DIR / 'notes'


def write_wiki_markdown(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False

    content = payload.get('content') or ''
    links = payload.get('links') or []
    front_matter = {
        'title': payload.get('title'),
        'domain': payload.get('domain'),
        'url': payload.get('url'),
        'source': 'wikipedia',
        'timestamp': epoch_to_iso(payload.get('timestamp')),
        'content_length': payload.get('content_length'),
        'links_count': len(links)
    }

    md_path = path.with_suffix('.md')
    sections = [("Links", [str(link) for link in links])] if links else None
    write_markdown(md_path, front_matter, content, sections=sections)
    return True


def write_normalized_markdown(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False

    front_matter = {
        'id': payload.get('id'),
        'title': payload.get('title'),
        'author': payload.get('author'),
        'category': payload.get('category'),
        'source_file': payload.get('source_file')
    }

    md_path = path.with_suffix('.md')
    write_markdown(md_path, front_matter, payload.get('content', ''))
    return True


def write_notes_markdown(path: Path) -> int:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return 0

    notes = []
    if isinstance(payload, dict):
        notes = payload.get('notes', [])
    elif isinstance(payload, list):
        notes = payload

    if not isinstance(notes, list):
        return 0

    entries_dir = NOTES_DIR / 'entries'
    entries_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for note in notes:
        if not isinstance(note, dict):
            continue
        note_id = note.get('id') or 'note'
        md_path = entries_dir / f"{note_id}.md"
        front_matter = {
            'id': note.get('id'),
            'topic': note.get('topic'),
            'status': note.get('status'),
            'created_at': note.get('created_at'),
            'updated_at': note.get('updated_at'),
            'next_review_at': note.get('next_review_at'),
            'review_count': note.get('review_count', 0)
        }

        sections = []
        summary = (note.get('summary') or '').strip()
        if summary:
            sections.append(("Summary", [summary]))
        questions = note.get('questions') or []
        if questions:
            sections.append(("Questions", [str(q) for q in questions]))
        actions = note.get('action_items') or []
        if actions:
            sections.append(("Action Items", [str(a) for a in actions]))
        sources = note.get('sources') or []
        if sources:
            sections.append(("Sources", [str(s) for s in sources]))

        write_markdown(md_path, front_matter, "", sections=sections)
        count += 1

    return count


def main() -> None:
    wiki_total = 0
    norm_total = 0
    notes_total = 0

    if WIKI_DIR.exists():
        for path in WIKI_DIR.rglob('*.json'):
            if write_wiki_markdown(path):
                wiki_total += 1

    if NORMALIZED_DIR.exists():
        for path in NORMALIZED_DIR.rglob('*.json'):
            if write_normalized_markdown(path):
                norm_total += 1

    notes_index = NOTES_DIR / 'notes_index.json'
    if notes_index.exists():
        notes_total = write_notes_markdown(notes_index)

    print(f"Wiki markdown: {wiki_total}")
    print(f"Normalized markdown: {norm_total}")
    print(f"Notes markdown: {notes_total}")


if __name__ == '__main__':
    main()
