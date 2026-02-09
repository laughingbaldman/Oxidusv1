import argparse
import json
import os
import re
import time
from datetime import datetime

DEFAULT_ALLOWED_EXTENSIONS = {".md", ".json", ".yaml", ".txt"}
FILENAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}__[^_]+__[^_]+__v\d+$")
SKIP_FILES = {
    "skipped_missing_content.txt"
}


def _utc_iso(ts):
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_allowed_extensions(rules_path):
    if not rules_path or not os.path.exists(rules_path):
        return DEFAULT_ALLOWED_EXTENSIONS

    allowed = []
    in_block = False
    with open(rules_path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith("allowed_extensions:"):
                in_block = True
                continue
            if in_block:
                if stripped.startswith("-"):
                    allowed.append(stripped.lstrip("-").strip())
                elif stripped and not stripped.startswith("#"):
                    break
    return set(allowed) if allowed else DEFAULT_ALLOWED_EXTENSIONS


def _should_skip(path, exclude_dirs):
    parts = path.replace("\\", "/").split("/")
    return any(part in exclude_dirs for part in parts)


def validate(root, rules_path, output_path=None):
    exclude_dirs = {
        "archives",
        "cache",
        "classification",
        "domains",
        "metadata",
        "normalized_deeper",
        "notes",
        "retired",
        "wiki_corpus",
        "__pycache__",
        ".git",
    }
    allowed_exts = _load_allowed_extensions(rules_path)
    violations = []
    checked = 0

    for base, _, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            rel_path = os.path.relpath(path, start=root).replace("\\", "/")
            if _should_skip(rel_path, exclude_dirs):
                continue
            if name.lower().startswith("readme."):
                continue
            if name.lower() == "seed_topics.md":
                continue
            if rel_path in SKIP_FILES:
                continue

            checked += 1
            ext = os.path.splitext(name)[1].lower()
            if ext not in allowed_exts:
                violations.append(
                    {
                        "type": "extension",
                        "path": rel_path,
                        "detail": f"Extension {ext} not allowed",
                    }
                )

            stem = os.path.splitext(name)[0]
            if not FILENAME_PATTERN.match(stem):
                violations.append(
                    {
                        "type": "filename",
                        "path": rel_path,
                        "detail": "Does not match YYYY-MM-DD__source__topic__vNN",
                    }
                )

            if stem.lower() != stem:
                violations.append(
                    {
                        "type": "lowercase",
                        "path": rel_path,
                        "detail": "Filename should be lowercase",
                    }
                )

    report = {
        "schema_version": "1.0",
        "checked_files": checked,
        "violation_count": len(violations),
        "generated_utc": _utc_iso(time.time()),
        "violations": violations,
    }

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="Validate knowledge base naming and extensions")
    parser.add_argument("--root", default=os.path.join("data", "knowledge_base"))
    parser.add_argument("--rules", default=os.path.join("data", "knowledge_base", "metadata", "ingest_rules.yaml"))
    parser.add_argument("--output", default=None, help="Optional JSON report path")
    args = parser.parse_args()

    report = validate(args.root, args.rules, args.output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
