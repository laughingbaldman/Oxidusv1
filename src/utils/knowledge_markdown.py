"""
Helpers for readable knowledge exports.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from metadata_governance import govern_write
    GOVERNANCE_AVAILABLE = True
except Exception:
    GOVERNANCE_AVAILABLE = False


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_list(values: Iterable[Any]) -> List[str]:
    items = list(values)
    if not items:
        return ["[]"]
    lines = []
    for item in items:
        lines.append(f"- {_yaml_scalar(item)}")
    return lines


def dump_front_matter(data: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            lines.append(f"{key}:")
            lines.extend([f"  {line}" for line in _yaml_list(value)])
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def epoch_to_iso(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value)).isoformat()
    except Exception:
        return None


def write_markdown(
    path: Path,
    front_matter: Dict[str, Any],
    body: str,
    sections: Optional[List[Tuple[str, List[str]]]] = None,
    *,
    enforce_governance: bool = False,
    metadata_dir: Optional[Path] = None,
    action: str = "write_markdown"
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body_text = (body or "").rstrip() + "\n"
    sections_text = ""
    if sections:
        for title, lines in sections:
            if not lines:
                continue
            sections_text += f"\n## {title}\n"
            for line in lines:
                sections_text += f"- {line}\n"
    if enforce_governance and GOVERNANCE_AVAILABLE:
        front_matter = govern_write(
            front_matter,
            body_text + sections_text,
            path,
            metadata_dir=metadata_dir,
            action=action
        )
    content = dump_front_matter(front_matter) + body_text + sections_text
    path.write_text(content, encoding="utf-8")
