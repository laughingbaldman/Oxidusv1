#!/usr/bin/env python3
"""Run KB validation checks and emit a consolidated report."""
import argparse
import importlib.util
import json
from datetime import datetime
from pathlib import Path
import sys


def _utc_iso(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scan_json_content(root: Path) -> dict:
    problems = {
        "invalid_json": [],
        "missing_content": []
    }
    count = 0
    for path in root.rglob("*.json"):
        parts = {part.lower() for part in path.parts}
        if parts & {
            "cache",
            "classification",
            "indexes",
            "metadata",
            "normalized_deeper",
            "notes",
            "wiki_corpus"
        }:
            continue
        count += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            problems["invalid_json"].append({"path": str(path), "error": str(exc)})
            continue
        content = data.get("content") if isinstance(data, dict) else None
        if not content or not isinstance(content, str):
            problems["missing_content"].append(str(path))
    return {
        "total_json_files": count,
        "invalid_json": problems["invalid_json"],
        "missing_content": problems["missing_content"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Oxidus knowledge base validations")
    parser.add_argument("--output", default=None, help="Optional JSON report path")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    scripts_dir = repo_root / "scripts"
    kb_root = repo_root / "data" / "knowledge_base"

    sys.path.insert(0, str(repo_root / "src"))

    validate_kb = _load_module("validate_kb", scripts_dir / "validate_kb.py")
    validate_taxonomy_graph = _load_module("validate_taxonomy_graph", scripts_dir / "validate_taxonomy_graph.py")
    audit_domain_coverage = _load_module("audit_domain_coverage", scripts_dir / "audit_domain_coverage.py")

    report = {
        "schema_version": "1.0",
        "generated_utc": _utc_iso(datetime.utcnow().timestamp()),
        "checks": {}
    }

    report["checks"]["kb_naming"] = validate_kb.validate(
        str(kb_root),
        str(kb_root / "metadata" / "ingest_rules.yaml"),
        output_path=None
    )

    report["checks"]["json_content"] = _scan_json_content(kb_root)

    report["checks"]["taxonomy_graph"] = validate_taxonomy_graph.validate(
        kb_root / "classification" / "topic_taxonomy.yaml",
        kb_root / "metadata" / "topic_registry.json",
        kb_root / "metadata" / "topic_to_domain.json",
        kb_root / "metadata" / "graph_edges.json",
        kb_root / "metadata" / "topic_synonyms.json"
    )

    report["checks"]["domain_coverage"] = audit_domain_coverage.audit(
        kb_root / "classification" / "topic_taxonomy.yaml",
        kb_root
    )

    try:
        from utils.metadata_governance import verify_provenance_log
        log_path = kb_root / "metadata" / "provenance_log.jsonl"
        report["checks"]["provenance"] = verify_provenance_log(log_path)
    except Exception as exc:
        report["checks"]["provenance"] = {
            "ok": False,
            "error": str(exc)
        }

    has_errors = bool(report["checks"].get("taxonomy_graph", {}).get("errors"))
    has_errors = has_errors or bool(report["checks"].get("kb_naming", {}).get("violation_count"))
    has_errors = has_errors or bool(report["checks"].get("domain_coverage", {}).get("missing_folders"))

    report["ok"] = not has_errors

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))

    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
