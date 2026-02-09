#!/usr/bin/env python3
"""Tests for metadata governance and provenance utilities."""

from pathlib import Path
import json
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.metadata_governance import enforce_front_matter, append_provenance, verify_provenance_log


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_enforce_front_matter_and_provenance():
    with tempfile.TemporaryDirectory() as tmp:
        metadata_dir = Path(tmp)
        _write_json(metadata_dir / "metadata_schema.json", {
            "schema_version": "1.0",
            "required": [
                "source_url",
                "source_title",
                "source_type",
                "topic_type",
                "license",
                "curator",
                "created_utc",
                "updated_utc",
                "lifecycle_state"
            ],
            "optional": ["source_id", "trust_tier"],
            "types": {"tags": "array"}
        })
        _write_json(metadata_dir / "source_trust_tiers.json", {
            "schema_version": "1.0",
            "tiers": [
                {"name": "primary"},
                {"name": "secondary"},
                {"name": "unknown"}
            ]
        })
        _write_json(metadata_dir / "source_registry.json", {
            "schema_version": "1.0",
            "sources": [
                {
                    "id": "example",
                    "source_url": "https://example.com",
                    "trust_tier": "secondary"
                }
            ]
        })

        front_matter = {
            "source_id": "example",
            "source_url": "https://example.com",
            "source_title": "Example",
            "source_type": "web",
            "topic_type": "reference",
            "license": "CC BY-SA 4.0",
            "curator": "tester",
            "created_utc": "2026-02-08T00:00:00Z",
            "lifecycle_state": "raw"
        }

        updated, tier = enforce_front_matter(front_matter, metadata_dir=metadata_dir, min_trust_tier="secondary")
        assert tier == "secondary"
        assert updated.get("updated_utc")
        assert updated.get("trust_tier") == "secondary"

        log_hash = append_provenance(metadata_dir, {"action": "test", "path": "example.md"})
        assert log_hash

        report = verify_provenance_log(metadata_dir / "provenance_log.jsonl")
        assert report.get("ok") is True
        assert report.get("entries") == 1
