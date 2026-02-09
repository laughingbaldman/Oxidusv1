#!/usr/bin/env python3
"""Validate taxonomy, topic registry, mappings, and graph edges."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml


def _utc_iso(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _as_list(value) -> List:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


def _normalize_id(value: str) -> str:
    if value is None:
        return ""
    return str(value).strip()


def validate(taxonomy_path: Path,
             topic_registry_path: Path,
             topic_mapping_path: Path,
             graph_edges_path: Path,
             topic_synonyms_path: Path) -> Dict:
    errors = []
    warnings = []

    taxonomy = _load_yaml(taxonomy_path)
    registry = _load_json(topic_registry_path)
    mappings = _load_json(topic_mapping_path)
    edges = _load_json(graph_edges_path)
    synonyms = _load_json(topic_synonyms_path)

    taxonomy_domains = _as_list(taxonomy.get("domains"))
    taxonomy_ids = [
        _normalize_id(item.get("id"))
        for item in taxonomy_domains
        if isinstance(item, dict)
    ]
    taxonomy_ids = [item for item in taxonomy_ids if item]

    registry_topics = _as_list(registry.get("topics"))
    registry_domain_ids = [
        _normalize_id(item.get("id"))
        for item in registry_topics
        if isinstance(item, dict) and item.get("type") == "domain"
    ]
    registry_domain_ids = [item for item in registry_domain_ids if item]

    taxonomy_missing = sorted(set(registry_domain_ids) - set(taxonomy_ids))
    registry_missing = sorted(set(taxonomy_ids) - set(registry_domain_ids))

    for domain_id in taxonomy_missing:
        warnings.append({
            "type": "domain_missing_in_taxonomy",
            "detail": domain_id
        })
    for domain_id in registry_missing:
        warnings.append({
            "type": "domain_missing_in_registry",
            "detail": domain_id
        })

    mapping_entries = _as_list(mappings.get("mappings"))
    for entry in mapping_entries:
        if not isinstance(entry, dict):
            continue
        topic = _normalize_id(entry.get("topic"))
        domain_id = _normalize_id(entry.get("domain_id"))
        if not topic:
            errors.append({
                "type": "mapping_missing_topic",
                "detail": entry
            })
        if not domain_id:
            errors.append({
                "type": "mapping_missing_domain",
                "detail": entry
            })
        elif domain_id not in taxonomy_ids:
            errors.append({
                "type": "mapping_unknown_domain",
                "detail": domain_id
            })

    edge_entries = _as_list(edges.get("edges"))
    for edge in edge_entries:
        if not isinstance(edge, dict):
            continue
        from_topic = _normalize_id(edge.get("from"))
        to_topic = _normalize_id(edge.get("to"))
        relation = _normalize_id(edge.get("relation"))
        if not from_topic or not to_topic:
            errors.append({
                "type": "edge_missing_endpoint",
                "detail": edge
            })
        if not relation:
            errors.append({
                "type": "edge_missing_relation",
                "detail": edge
            })
        evidence = edge.get("evidence")
        if evidence is None or (isinstance(evidence, list) and len(evidence) == 0):
            warnings.append({
                "type": "edge_missing_evidence",
                "detail": {
                    "from": from_topic,
                    "to": to_topic,
                    "relation": relation
                }
            })
        elif isinstance(evidence, list):
            for entry in evidence:
                if not isinstance(entry, dict):
                    warnings.append({
                        "type": "edge_evidence_invalid",
                        "detail": {
                            "from": from_topic,
                            "to": to_topic,
                            "relation": relation
                        }
                    })
                    continue
                source_id = _normalize_id(entry.get("source_id"))
                source_url = _normalize_id(entry.get("source_url"))
                if not source_id or not source_url:
                    warnings.append({
                        "type": "edge_evidence_missing_fields",
                        "detail": {
                            "from": from_topic,
                            "to": to_topic,
                            "relation": relation,
                            "source_id": source_id,
                            "source_url": source_url
                        }
                    })

    synonyms_map = synonyms.get("synonyms") if isinstance(synonyms, dict) else None
    if isinstance(synonyms_map, dict):
        for key, items in synonyms_map.items():
            if not _normalize_id(key):
                errors.append({
                    "type": "synonym_missing_key",
                    "detail": key
                })
            if not isinstance(items, list) or not items:
                warnings.append({
                    "type": "synonym_missing_values",
                    "detail": key
                })
    elif synonyms_map is not None:
        errors.append({
            "type": "synonym_invalid_format",
            "detail": "synonyms must be a map"
        })

    registry_ids = {
        _normalize_id(item.get("id"))
        for item in registry_topics
        if isinstance(item, dict) and item.get("id")
    }

    for redirect in _as_list(registry.get("redirects")):
        if not isinstance(redirect, dict):
            continue
        source_id = _normalize_id(redirect.get("from"))
        target_id = _normalize_id(redirect.get("to"))
        if source_id and source_id not in registry_ids:
            errors.append({
                "type": "redirect_unknown_source",
                "detail": source_id
            })
        if target_id and target_id not in registry_ids:
            errors.append({
                "type": "redirect_unknown_target",
                "detail": target_id
            })

    for merge in _as_list(registry.get("merges")):
        if not isinstance(merge, dict):
            continue
        source_id = _normalize_id(merge.get("from"))
        target_id = _normalize_id(merge.get("to"))
        if source_id and source_id not in registry_ids:
            errors.append({
                "type": "merge_unknown_source",
                "detail": source_id
            })
        if target_id and target_id not in registry_ids:
            errors.append({
                "type": "merge_unknown_target",
                "detail": target_id
            })

    return {
        "schema_version": "1.0",
        "generated_utc": _utc_iso(datetime.utcnow().timestamp()),
        "counts": {
            "taxonomy_domains": len(taxonomy_ids),
            "registry_domains": len(registry_domain_ids),
            "mappings": len(mapping_entries),
            "edges": len(edge_entries),
            "synonyms": len(synonyms_map) if isinstance(synonyms_map, dict) else 0
        },
        "errors": errors,
        "warnings": warnings
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate taxonomy and knowledge graph metadata")
    parser.add_argument("--taxonomy", default="data/knowledge_base/classification/topic_taxonomy.yaml")
    parser.add_argument("--registry", default="data/knowledge_base/metadata/topic_registry.json")
    parser.add_argument("--mappings", default="data/knowledge_base/metadata/topic_to_domain.json")
    parser.add_argument("--edges", default="data/knowledge_base/metadata/graph_edges.json")
    parser.add_argument("--synonyms", default="data/knowledge_base/metadata/topic_synonyms.json")
    parser.add_argument("--output", default=None, help="Optional JSON report path")
    args = parser.parse_args()

    report = validate(
        Path(args.taxonomy),
        Path(args.registry),
        Path(args.mappings),
        Path(args.edges),
        Path(args.synonyms)
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))

    if report.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
