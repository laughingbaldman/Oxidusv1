"""
Cleanup external scraped sources from the knowledge base.

Defaults to dry-run. Use --apply to delete files.
"""

from pathlib import Path
import argparse

BASE_DIR = Path(__file__).resolve().parents[1]

EXTERNAL_DIRS = [
    BASE_DIR / 'data' / 'knowledge_base' / 'wiki',
    BASE_DIR / 'data' / 'knowledge_base' / 'wiki_corpus',
    BASE_DIR / 'data' / 'knowledge_base' / 'normalized_deeper',
    BASE_DIR / 'data' / 'knowledge_base' / 'cache'
]

EXTERNAL_DIRS_RETIRED = [
    BASE_DIR / 'retired' / 'data' / 'knowledge_base' / 'wiki',
    BASE_DIR / 'retired' / 'data' / 'knowledge_base' / 'wiki_corpus',
    BASE_DIR / 'retired' / 'data' / 'knowledge_base' / 'normalized_deeper',
    BASE_DIR / 'retired' / 'data' / 'knowledge_base' / 'cache'
]


def cleanup(include_retired: bool, apply: bool) -> dict:
    targets = list(EXTERNAL_DIRS)
    if include_retired:
        targets.extend(EXTERNAL_DIRS_RETIRED)

    removed_files = 0
    missing_dirs = 0

    for base_dir in targets:
        if not base_dir.exists():
            missing_dirs += 1
            continue

        for entry in base_dir.rglob('*'):
            if entry.is_file():
                removed_files += 1
                if apply:
                    try:
                        entry.unlink()
                    except Exception:
                        pass

        if apply:
            for child in base_dir.iterdir():
                if child.is_dir():
                    try:
                        for nested in child.rglob('*'):
                            if nested.is_file():
                                nested.unlink()
                        child.rmdir()
                    except Exception:
                        pass

    return {
        'apply': apply,
        'include_retired': include_retired,
        'removed_files': removed_files,
        'missing_dirs': missing_dirs,
        'targets': [str(p) for p in targets]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup external scraped sources")
    parser.add_argument('--apply', action='store_true', help='Delete files (default is dry-run)')
    parser.add_argument('--include-retired', action='store_true', help='Include retired data directories')
    args = parser.parse_args()

    result = cleanup(include_retired=args.include_retired, apply=args.apply)
    print(result)


if __name__ == '__main__':
    main()
