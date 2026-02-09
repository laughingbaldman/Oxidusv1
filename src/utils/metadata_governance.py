"""
Governance utilities for metadata validation and provenance logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import hashlib
import json
import os


DEFAULT_TIERS = ["primary", "secondary", "tertiary", "unknown"]
DEFAULT_MIN_TIER = "secondary"
LIFECYCLE_ORDER = ["raw", "draft", "curated", "archived"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _normalize_tier(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    return str(value).strip().lower()


def _normalize_lifecycle_state(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return str(value).strip().lower()


def _parse_front_matter_value(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    try:
        return json.loads(value)
    except Exception:
        return value.strip('"')


def _read_front_matter(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    data = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            continue
        data[key] = _parse_front_matter_value(value)
    return data


def _get_existing_lifecycle_state(path: Optional[Path]) -> Optional[str]:
    if not path:
        return None
    front_matter = _read_front_matter(path)
    return _normalize_lifecycle_state(front_matter.get("lifecycle_state"))


def _load_tier_order(metadata_dir: Path) -> Dict[str, int]:
    tiers_path = metadata_dir / "source_trust_tiers.json"
    data = _safe_read_json(tiers_path)
    tiers = []
    for item in data.get("tiers", []):
        name = _normalize_tier(item.get("name"))
        if name and name not in tiers:
            tiers.append(name)
    if not tiers:
        tiers = list(DEFAULT_TIERS)
    return {name: idx for idx, name in enumerate(tiers)}


def _find_source_entry(registry: Dict[str, Any], source_url: str, source_id: Optional[str]) -> Optional[Dict[str, Any]]:
    sources = registry.get("sources", [])
    if not sources:
        return None
    for entry in sources:
        if source_id and entry.get("id") == source_id:
            return entry
    for entry in sources:
        if source_url and entry.get("source_url") == source_url:
            return entry
    return None


def _metadata_dir_from_env() -> Optional[Path]:
    env_path = os.environ.get("OXIDUS_METADATA_DIR")
    if not env_path:
        return None
    return Path(env_path)


def _resolve_metadata_dir(metadata_dir: Optional[Path]) -> Path:
    if metadata_dir:
        return metadata_dir
    env_dir = _metadata_dir_from_env()
    if env_dir:
        return env_dir
    return Path("data") / "knowledge_base" / "metadata"


def _get_min_trust_tier() -> str:
    return _normalize_tier(os.environ.get("OXIDUS_MIN_TRUST_TIER", DEFAULT_MIN_TIER))


def _metadata_hash(metadata: Dict[str, Any]) -> str:
    payload = json.dumps(metadata, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def enforce_front_matter(
    front_matter: Dict[str, Any],
    metadata_dir: Optional[Path] = None,
    min_trust_tier: Optional[str] = None,
    path: Optional[Path] = None
) -> Tuple[Dict[str, Any], str]:
    metadata_dir = _resolve_metadata_dir(metadata_dir)
    schema = _safe_read_json(metadata_dir / "metadata_schema.json")

    required = schema.get("required", [])
    types = schema.get("types", {})

    normalized = dict(front_matter)
    if not normalized.get("created_utc"):
        normalized["created_utc"] = _utc_now_iso()
    normalized["updated_utc"] = _utc_now_iso()

    for key in required:
        value = normalized.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"Missing required metadata field: {key}")

    lifecycle_state = _normalize_lifecycle_state(normalized.get("lifecycle_state"))
    if lifecycle_state and lifecycle_state not in LIFECYCLE_ORDER:
        raise ValueError(f"Invalid lifecycle_state: {lifecycle_state}")

    previous_state = _get_existing_lifecycle_state(path)
    if previous_state and lifecycle_state:
        if previous_state in LIFECYCLE_ORDER:
            prev_index = LIFECYCLE_ORDER.index(previous_state)
            next_index = LIFECYCLE_ORDER.index(lifecycle_state)
            if next_index < prev_index or next_index > prev_index + 1:
                raise ValueError(
                    "Lifecycle transition out of order: "
                    f"{previous_state} -> {lifecycle_state}"
                )

    for key, expected in types.items():
        if key not in normalized:
            continue
        value = normalized.get(key)
        if expected == "number" and not isinstance(value, (int, float)):
            raise ValueError(f"Metadata field '{key}' must be a number")
        if expected == "array" and not isinstance(value, (list, tuple)):
            raise ValueError(f"Metadata field '{key}' must be an array")

    registry = _safe_read_json(metadata_dir / "source_registry.json")
    entry = _find_source_entry(registry, normalized.get("source_url", ""), normalized.get("source_id"))
    trust_tier = _normalize_tier((entry or {}).get("trust_tier"))

    tier_order = _load_tier_order(metadata_dir)
    min_tier = _normalize_tier(min_trust_tier or _get_min_trust_tier())
    min_rank = tier_order.get(min_tier, tier_order.get(DEFAULT_MIN_TIER, 1))
    current_rank = tier_order.get(trust_tier, tier_order.get("unknown", max(tier_order.values(), default=3)))

    if current_rank > min_rank:
        raise ValueError(
            "Source trust tier below minimum: "
            f"{trust_tier} < {min_tier} for {normalized.get('source_url', '')}"
        )

    normalized["trust_tier"] = trust_tier
    return normalized, trust_tier


def append_provenance(
    metadata_dir: Optional[Path],
    event: Dict[str, Any]
) -> str:
    metadata_dir = _resolve_metadata_dir(metadata_dir)
    log_path = metadata_dir / "provenance_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    prev_hash = None
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            if lines:
                prev_hash = json.loads(lines[-1]).get("hash")
        except Exception:
            prev_hash = None

    payload = dict(event)
    payload["prev_hash"] = prev_hash
    payload["ts_utc"] = payload.get("ts_utc") or _utc_now_iso()

    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    payload_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    payload["hash"] = payload_hash

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    return payload_hash


def verify_provenance_log(log_path: Path) -> Dict[str, Any]:
    if not log_path.exists():
        return {
            "ok": False,
            "error": "provenance log not found",
            "path": str(log_path.as_posix())
        }

    issues = []
    previous_hash = None
    total = 0

    for line_no, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        total += 1
        try:
            entry = json.loads(line)
        except Exception:
            issues.append({"line": line_no, "error": "invalid json"})
            continue

        expected_prev = entry.get("prev_hash")
        if previous_hash != expected_prev:
            issues.append({
                "line": line_no,
                "error": "hash chain mismatch",
                "expected_prev": previous_hash,
                "found_prev": expected_prev
            })

        recorded_hash = entry.get("hash")
        if recorded_hash:
            payload = dict(entry)
            payload.pop("hash", None)
            encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
            computed = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            if computed != recorded_hash:
                issues.append({
                    "line": line_no,
                    "error": "hash mismatch",
                    "expected_hash": computed,
                    "found_hash": recorded_hash
                })

        previous_hash = recorded_hash

    return {
        "ok": not issues,
        "path": str(log_path.as_posix()),
        "entries": total,
        "issues": issues
    }


def govern_write(
    front_matter: Dict[str, Any],
    content: str,
    path: Path,
    metadata_dir: Optional[Path] = None,
    action: str = "write_markdown"
) -> Dict[str, Any]:
    updated, trust_tier = enforce_front_matter(front_matter, metadata_dir=metadata_dir, path=path)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    event = {
        "action": action,
        "path": str(path.as_posix()),
        "source_url": updated.get("source_url"),
        "source_title": updated.get("source_title"),
        "source_type": updated.get("source_type"),
        "topic_type": updated.get("topic_type"),
        "license": updated.get("license"),
        "curator": updated.get("curator"),
        "lifecycle_state": updated.get("lifecycle_state"),
        "created_utc": updated.get("created_utc"),
        "updated_utc": updated.get("updated_utc"),
        "trust_tier": trust_tier,
        "metadata_hash": _metadata_hash(updated),
        "content_hash": content_hash
    }
    append_provenance(metadata_dir, event)
    return updated
