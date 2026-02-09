#!/usr/bin/env python3
"""Audit domain folder coverage against taxonomy."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

import yaml


def _utc_iso(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _folder_file_count(folder: Path) -> int:
    if not folder.exists():
        return 0
    count = 0
    for path in folder.rglob("*"):
        if path.is_file() and path.name.lower() != "readme.md":
            count += 1
    return count


def audit(taxonomy_path: Path, kb_root: Path) -> Dict:
    taxonomy = _load_yaml(taxonomy_path)
    domains = taxonomy.get("domains") or []

    expected = []
    for domain in domains:
        if not isinstance(domain, dict):
            continue
        for folder in domain.get("folders") or []:
            expected.append(folder)

    expected_paths = [kb_root / Path(path).relative_to("data/knowledge_base") for path in expected]
    expected_set = {str(path.resolve()) for path in expected_paths}

    actual_root = kb_root / "domains"
    actual_paths = []
    if actual_root.exists():
        for entry in actual_root.iterdir():
            if entry.is_dir():
                actual_paths.append(entry)

    actual_set = {str(path.resolve()) for path in actual_paths}

    missing = [str(path) for path in expected_paths if not path.exists()]
    extra = [str(path) for path in actual_paths if str(path.resolve()) not in expected_set]

    coverage = []
    for path in expected_paths:
        coverage.append({
            "path": str(path),
            "exists": path.exists(),
            "file_count": _folder_file_count(path)
        })

    empty = [item for item in coverage if item.get("exists") and item.get("file_count") == 0]

    return {
        "schema_version": "1.0",
        "generated_utc": _utc_iso(datetime.utcnow().timestamp()),
        "missing_folders": missing,
        "extra_folders": extra,
        "coverage": coverage,
        "empty_folders": empty
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit domain folder coverage")
    parser.add_argument("--taxonomy", default="data/knowledge_base/classification/topic_taxonomy.yaml")
    parser.add_argument("--kb-root", default="data/knowledge_base")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = audit(Path(args.taxonomy), Path(args.kb_root))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))

    if report.get("missing_folders"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
