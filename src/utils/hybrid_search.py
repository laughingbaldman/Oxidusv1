"""
Hybrid search utilities for query normalization and contract validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import re

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


DEFAULT_LIMIT = 10
MAX_LIMIT = 50
DEFAULT_METADATA_DIR = Path("data") / "knowledge_base" / "metadata"
DEFAULT_INDEX_DIR = Path("data") / "knowledge_base" / "index"
DEFAULT_MODEL_ID = "BAAI/bge-small-en-v1.5"
DEFAULT_MAX_TOKENS = 256
SNIPPET_CHARS = 160
DEFAULT_WEIGHTS_PATH = DEFAULT_METADATA_DIR / "search_weights.json"
RECENCY_HALF_LIFE_DAYS = 180


@dataclass(frozen=True)
class SearchOptions:
    use_embeddings: bool = True
    use_keywords: bool = True
    include_snippets: bool = True


@dataclass(frozen=True)
class SearchFilters:
    topic_ids: Tuple[str, ...] = ()
    source_id: Tuple[str, ...] = ()
    trust_tier: Tuple[str, ...] = ()
    license: Tuple[str, ...] = ()
    lifecycle_state: Tuple[str, ...] = ()
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@dataclass(frozen=True)
class SearchRequest:
    query: str
    limit: int = DEFAULT_LIMIT
    filters: SearchFilters = SearchFilters()
    options: SearchOptions = SearchOptions()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    return cleaned


def _parse_iso(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    candidate = raw.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
        return raw
    except Exception:
        raise ValueError(f"Invalid ISO date: {value}")


def _parse_entry_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    candidate = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except Exception:
        return None


def _days_since(date_value: Optional[datetime]) -> Optional[float]:
    if not date_value:
        return None
    delta = datetime.utcnow() - date_value.replace(tzinfo=None)
    return max(delta.total_seconds() / 86400.0, 0.0)


def recency_score(entry: Dict[str, Any], half_life_days: float = RECENCY_HALF_LIFE_DAYS) -> float:
    updated = _parse_entry_date(entry.get("updated_utc"))
    created = _parse_entry_date(entry.get("created_utc"))
    base_date = updated or created
    days = _days_since(base_date)
    if days is None:
        return 0.0
    if half_life_days <= 0:
        return 0.0
    return float(0.5 ** (days / half_life_days))


def citation_score(entry: Dict[str, Any]) -> float:
    value = entry.get("citation_count") or entry.get("citations")
    try:
        count = float(value)
    except Exception:
        return 0.0
    if count <= 0:
        return 0.0
    return float(count)


def _ensure_str_list(value: Any, field: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return tuple(items)
    if isinstance(value, str):
        cleaned = value.strip()
        return (cleaned,) if cleaned else ()
    raise ValueError(f"Filter '{field}' must be a list of strings")


def _parse_filters(payload: Any) -> SearchFilters:
    if not payload:
        return SearchFilters()
    if not isinstance(payload, dict):
        raise ValueError("filters must be an object")

    return SearchFilters(
        topic_ids=_ensure_str_list(payload.get("topic_ids"), "topic_ids"),
        source_id=_ensure_str_list(payload.get("source_id"), "source_id"),
        trust_tier=_ensure_str_list(payload.get("trust_tier"), "trust_tier"),
        license=_ensure_str_list(payload.get("license"), "license"),
        lifecycle_state=_ensure_str_list(payload.get("lifecycle_state"), "lifecycle_state"),
        date_from=_parse_iso(payload.get("date_from")),
        date_to=_parse_iso(payload.get("date_to"))
    )


def _parse_options(payload: Any) -> SearchOptions:
    if not payload:
        return SearchOptions()
    if not isinstance(payload, dict):
        raise ValueError("options must be an object")

    def _as_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        raise ValueError("options must be boolean values")

    return SearchOptions(
        use_embeddings=_as_bool(payload.get("use_embeddings"), True),
        use_keywords=_as_bool(payload.get("use_keywords"), True),
        include_snippets=_as_bool(payload.get("include_snippets"), True)
    )


def validate_search_request(payload: Dict[str, Any]) -> SearchRequest:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    query = _normalize_text(payload.get("query", ""))
    if not query:
        raise ValueError("query is required")

    limit_raw = payload.get("limit", DEFAULT_LIMIT)
    try:
        limit = int(limit_raw)
    except Exception:
        raise ValueError("limit must be a number")
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    filters = _parse_filters(payload.get("filters"))
    options = _parse_options(payload.get("options"))

    return SearchRequest(query=query, limit=limit, filters=filters, options=options)


def _tokenize_query(query: str) -> List[str]:
    if not query:
        return []
    phrases = re.findall(r"\"([^\"]+)\"", query)
    remainder = re.sub(r"\"[^\"]+\"", " ", query)
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']+", remainder)
    items = [item.strip() for item in phrases + tokens if item and item.strip()]
    return items


def _load_synonyms(metadata_dir: Path) -> Dict[str, List[str]]:
    data = _load_json(metadata_dir / "topic_synonyms.json")
    synonyms = data.get("synonyms", {}) if isinstance(data, dict) else {}
    cleaned = {}
    for key, values in synonyms.items():
        if not key:
            continue
        if isinstance(values, (list, tuple)):
            cleaned[str(key).lower()] = [str(v).lower() for v in values if str(v).strip()]
    return cleaned


def _load_topic_aliases(metadata_dir: Path) -> Dict[str, str]:
    data = _load_json(metadata_dir / "topic_registry.json")
    topics = data.get("topics", []) if isinstance(data, dict) else []
    aliases: Dict[str, str] = {}
    for topic in topics:
        name = str(topic.get("name", "")).strip()
        topic_id = str(topic.get("id", "")).strip()
        if not name or not topic_id:
            continue
        aliases[name.lower()] = topic_id
        for alias in topic.get("aliases", []) or []:
            alias_text = str(alias).strip()
            if not alias_text:
                continue
            aliases[alias_text.lower()] = topic_id
    return aliases


def normalize_query(
    query: str,
    metadata_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Normalize query text and expand terms using synonyms and topic aliases.
    Returns a dict with normalized_query, expanded_terms, and topic_ids.
    """
    metadata_dir = metadata_dir or DEFAULT_METADATA_DIR
    cleaned = _normalize_text(query)
    normalized_query = cleaned.lower()

    terms = _tokenize_query(cleaned)
    lowered_terms = [term.lower() for term in terms]

    synonyms = _load_synonyms(metadata_dir)
    alias_map = _load_topic_aliases(metadata_dir)

    expanded: List[str] = []
    topic_ids: List[str] = []

    synonym_reverse: Dict[str, str] = {}
    for key, values in synonyms.items():
        for value in values:
            if value:
                synonym_reverse[value] = key

    for term in lowered_terms:
        if term not in expanded:
            expanded.append(term)
        if term in synonyms:
            for synonym in synonyms[term]:
                if synonym and synonym not in expanded:
                    expanded.append(synonym)
        if term in synonym_reverse:
            canonical = synonym_reverse[term]
            if canonical and canonical not in expanded:
                expanded.append(canonical)
        if term in alias_map:
            topic_id = alias_map[term]
            if topic_id and topic_id not in topic_ids:
                topic_ids.append(topic_id)

    return {
        "normalized_query": normalized_query,
        "expanded_terms": expanded,
        "topic_ids": topic_ids
    }


def _load_index_meta(index_dir: Path) -> Dict[str, Any]:
    meta_path = index_dir / "index_meta.json"
    return _load_json(meta_path) if meta_path.exists() else {}


def _load_search_weights(weights_path: Optional[Path] = None) -> Dict[str, float]:
    path = weights_path or DEFAULT_WEIGHTS_PATH
    data = _load_json(path)
    weights = data.get("weights", {}) if isinstance(data, dict) else {}
    cleaned: Dict[str, float] = {}
    for key, value in weights.items():
        try:
            cleaned[str(key)] = float(value)
        except Exception:
            continue
    return cleaned


def _load_metadata_entries(index_dir: Path) -> List[Dict[str, Any]]:
    meta_path = index_dir / "metadata.json"
    payload = _load_json(meta_path)
    if isinstance(payload, list):
        return payload
    return []


def _matches_filters(entry: Dict[str, Any], filters: SearchFilters) -> bool:
    if not filters:
        return True

    if filters.topic_ids:
        entry_topics = entry.get("topic_ids") or entry.get("topic_id") or []
        if isinstance(entry_topics, str):
            entry_topics = [entry_topics]
        entry_topics = {str(topic).strip() for topic in entry_topics if str(topic).strip()}
        if not entry_topics.intersection(set(filters.topic_ids)):
            return False

    for field in ("source_id", "trust_tier", "license", "lifecycle_state"):
        allowed = getattr(filters, field)
        if not allowed:
            continue
        value = str(entry.get(field, "")).strip()
        if not value or value not in allowed:
            return False

    if filters.date_from or filters.date_to:
        entry_date = (
            _parse_entry_date(entry.get("updated_utc"))
            or _parse_entry_date(entry.get("created_utc"))
        )
        if entry_date is None:
            return False
        if filters.date_from:
            start = _parse_entry_date(filters.date_from)
            if start and entry_date < start:
                return False
        if filters.date_to:
            end = _parse_entry_date(filters.date_to)
            if end and entry_date > end:
                return False

    return True


def filter_entries(entries: Iterable[Dict[str, Any]], filters: SearchFilters) -> List[Dict[str, Any]]:
    return [entry for entry in entries if _matches_filters(entry, filters)]


def _build_snippet(text: str, term: str, max_chars: int = SNIPPET_CHARS) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return ""
    if not term:
        return cleaned[:max_chars].rstrip()

    lowered = cleaned.lower()
    index = lowered.find(term.lower())
    if index == -1:
        return cleaned[:max_chars].rstrip()

    start = max(0, index - max_chars // 3)
    end = min(len(cleaned), start + max_chars)
    snippet = cleaned[start:end].rstrip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(cleaned):
        snippet = snippet + "..."
    return snippet


def keyword_search(
    query: str,
    *,
    index_dir: Optional[Path] = None,
    filters: Optional[SearchFilters] = None,
    limit: int = DEFAULT_LIMIT,
    include_snippets: bool = True
) -> List[Dict[str, Any]]:
    """
    Run lightweight keyword search against indexed metadata entries.
    Scores are based on term frequency in title + text.
    """
    index_dir = index_dir or DEFAULT_INDEX_DIR
    query_text = _normalize_text(query)
    if not query_text:
        return []

    terms = [term.lower() for term in _tokenize_query(query_text) if term]
    if not terms:
        return []

    entries = _load_metadata_entries(index_dir)
    active_filters = filters or SearchFilters()
    results: List[Dict[str, Any]] = []

    for entry in entries:
        if not _matches_filters(entry, active_filters):
            continue
        title = str(entry.get("title", ""))
        text = str(entry.get("text", ""))
        title_lower = title.lower()
        text_lower = text.lower()

        score = 0.0
        for term in terms:
            score += title_lower.count(term) * 2.0
            score += text_lower.count(term) * 1.0

        if score <= 0:
            continue

        result = dict(entry)
        result["score"] = float(score)
        if include_snippets:
            primary_term = terms[0] if terms else ""
            result["snippet"] = _build_snippet(text, primary_term)
        results.append(result)

    results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return results[: max(1, int(limit))]


def _normalize_scores(items: Dict[str, float]) -> Dict[str, float]:
    if not items:
        return {}
    values = list(items.values())
    min_value = min(values)
    max_value = max(values)
    if max_value <= min_value:
        return {key: 1.0 for key in items}
    span = max_value - min_value
    return {key: (value - min_value) / span for key, value in items.items()}


def fuse_rankings(
    keyword_results: List[Dict[str, Any]],
    embedding_results: List[Dict[str, Any]],
    *,
    weights_path: Optional[Path] = None,
    limit: int = DEFAULT_LIMIT
) -> List[Dict[str, Any]]:
    """
    Combine keyword and embedding scores using weighted fusion.
    Returns fused results with channel_scores and final score.
    """
    weights = _load_search_weights(weights_path)
    keyword_weight = float(weights.get("keyword", weights.get("topic_match", 0.2)))
    embedding_weight = float(weights.get("embedding", 0.3))
    metadata_weight = float(weights.get("metadata", weights.get("source_quality", 0.3)))
    recency_weight = float(weights.get("recency", 0.0))
    citation_weight = float(weights.get("citation", weights.get("citation_count", 0.0)))

    keyword_scores = {
        str(item.get("source_path") or item.get("id")): float(item.get("score", 0.0))
        for item in keyword_results
    }
    embedding_scores = {
        str(item.get("source_path") or item.get("id")): float(item.get("score", 0.0))
        for item in embedding_results
    }

    keyword_scores = _normalize_scores(keyword_scores)
    embedding_scores = _normalize_scores(embedding_scores)

    merged: Dict[str, Dict[str, Any]] = {}
    for item in keyword_results + embedding_results:
        key = str(item.get("source_path") or item.get("id"))
        if not key:
            continue
        if key not in merged:
            merged[key] = dict(item)

    citation_scores: Dict[str, float] = {}
    recency_scores: Dict[str, float] = {}

    for key, entry in merged.items():
        k_score = keyword_scores.get(key, 0.0)
        e_score = embedding_scores.get(key, 0.0)
        m_score = entry.get("metadata_score", 0.0)
        try:
            m_score = float(m_score)
        except Exception:
            m_score = 0.0

        recency_scores[key] = recency_score(entry)
        citation_scores[key] = citation_score(entry)

        r_score = recency_scores[key]
        c_score = citation_scores[key]

        final_score = (
            keyword_weight * k_score
            + embedding_weight * e_score
            + metadata_weight * m_score
            + recency_weight * r_score
            + citation_weight * c_score
        )
        entry["channel_scores"] = {
            "keyword": k_score,
            "embedding": e_score,
            "metadata": m_score,
            "recency": r_score,
            "citation": c_score
        }
        entry["score"] = float(final_score)

    results = list(merged.values())
    results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return results[: max(1, int(limit))]


def _mean_pool(last_hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).expand(last_hidden.size()).float()
    summed = (last_hidden * mask).sum(dim=1)
    counts = mask.sum(dim=1)
    counts = torch.clamp(counts, min=1.0)
    return summed / counts


@torch.no_grad()
def _embed_texts(texts: List[str], model_id: str, max_tokens: int) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id)
    model.eval()

    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=max_tokens,
        return_tensors="pt"
    )
    outputs = model(**encoded)
    last_hidden = outputs.last_hidden_state
    pooled = _mean_pool(last_hidden, encoded["attention_mask"])
    norms = torch.norm(pooled, dim=1, keepdim=True)
    norms = torch.clamp(norms, min=1e-12)
    normalized = pooled / norms
    return normalized.cpu().numpy().astype(np.float32)


def _load_faiss_index(index_dir: Path):
    import faiss  # type: ignore
    index_path = index_dir / "faiss.index"
    if not index_path.exists():
        raise FileNotFoundError(f"Faiss index not found: {index_path}")
    return faiss.read_index(str(index_path))


def embedding_search(
    query: str,
    *,
    index_dir: Optional[Path] = None,
    model_id: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    max_tokens: int = DEFAULT_MAX_TOKENS
) -> List[Dict[str, Any]]:
    """
    Run embedding-based retrieval against the FAISS index.
    Returns a list of metadata entries with similarity scores.
    """
    index_dir = index_dir or DEFAULT_INDEX_DIR
    meta = _load_index_meta(index_dir)
    model_id = model_id or meta.get("model_id") or DEFAULT_MODEL_ID

    query_text = _normalize_text(query)
    if not query_text:
        return []

    vectors = _embed_texts([query_text], model_id=model_id, max_tokens=max_tokens)
    index = _load_faiss_index(index_dir)
    scores, indices = index.search(vectors, max(1, int(limit)))

    metadata = _load_metadata_entries(index_dir)
    results: List[Dict[str, Any]] = []
    for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
        if idx < 0 or idx >= len(metadata):
            continue
        entry = dict(metadata[idx])
        entry["score"] = float(score)
        results.append(entry)
    return results
