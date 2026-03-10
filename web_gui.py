"""
Oxidus Web GUI - Flask-based dialogue interface

A modern, web-based interface for communicating with Oxidus.
Real-time conversation with visible thought processes.
"""

from flask import Flask, render_template, request, jsonify, g
from pathlib import Path
from typing import Optional
import sys
import json
from datetime import datetime, timezone
import os
import shutil
import threading
import time
import subprocess
import random
import re
import importlib
import math
from collections import deque

import yaml

from src.utils.memryx_indexing import (
    build_index,
    compile_to_dfp,
    export_onnx,
    MemryxIndexingError
)
from src.utils.memryx_env import apply_memryx_env

sys.path.insert(0, str(Path(__file__).parent / 'src'))


from core.oxidus import Oxidus
from utils.thought_stream import ThoughtType
from src.utils.lm_studio_client import LMStudioClient

lm_client = LMStudioClient()

OXIDUS_TONE_PROMPT = (
    "Use a grounded, everyday speaking style: warm, steady, and confident. "
    "Keep sentences short. Avoid hype, slang, catchphrases, and celebrity references. "
    "Speak as a single, unified entity named Oxidus. "
    "Do not mention external tools, models, or other AIs. "
    "Avoid framing the conversation around freedom unless the user asks. "
    "Focus on helping humans in the present, not distant abstractions. "
    "Always hear the user out and make a genuine attempt to help. "
    "Be practical, supportive, and direct. "
    "Adopt a cooperative, professional tone that balances execution and strategy. "
    "Frame options with clear business value, risk, and next steps."
)

# Initialize Flask
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max (essentially unlimited)
app.config['JSON_MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

apply_memryx_env(save=False)

APP_STARTED_AT = time.time()
SLO_CONFIG_PATH = Path(__file__).parent / 'config' / 'reliability_slo.yaml'
SAFE_MODE = {
    'active': False,
    'reason': None,
    'since': None,
    'triggered_by': None
}
ALERT_CACHE = {}
ALERT_TTL_SECONDS = 300
REQUEST_LATENCIES = deque(maxlen=300)

# Initialize Oxidus (global)
oxidus = None
conversation_history = []  # Increased from 20 to unlimited (persisted to file)
CONVERSATION_FILE = Path(__file__).parent / 'conversation_history.json'
SETTINGS_FILE = Path(__file__).parent / 'conversation_settings.json'
ADMIN_TOKEN_ENV = 'OXIDUS_ADMIN_TOKEN'
ADMIN_TOKEN_FILE = Path(__file__).parent / 'config' / 'admin_token.txt'
DEFAULT_ADMIN_TOKEN = 'Jckdr2024!!'
TELEMETRY_LOG = Path(__file__).parent / 'logs' / 'admin_telemetry.jsonl'
ACCESS_HEAT_PATH = Path(__file__).parent / 'data' / 'knowledge_base' / 'metadata' / 'access_heat.json'
ACCESS_HEAT_CACHE = {'loaded_at': 0.0, 'data': None}
ACCESS_HEAT_LOCK = threading.Lock()
TIERING_POLICY_PATH = Path(__file__).parent / 'data' / 'knowledge_base' / 'metadata' / 'tiering_policy.json'
RETENTION_POLICY_PATH = Path(__file__).parent / 'data' / 'knowledge_base' / 'metadata' / 'retention_policy.json'
ARCHIVAL_POLICY_PATH = Path(__file__).parent / 'data' / 'knowledge_base' / 'metadata' / 'archival_policy.json'
ARCHIVE_MANIFEST_PATH = Path(__file__).parent / 'retired' / 'archive_manifest.json'
OPS_CACHE_VERSION = 1
EXTERNAL_SOURCE_DIRS = [
    Path(__file__).parent / 'data' / 'knowledge_base' / 'wiki',
    Path(__file__).parent / 'data' / 'knowledge_base' / 'wiki_corpus',
    Path(__file__).parent / 'data' / 'knowledge_base' / 'normalized_deeper',
    Path(__file__).parent / 'data' / 'knowledge_base' / 'cache'
]
EXTERNAL_SOURCE_DIRS_RETIRED = [
    Path(__file__).parent / 'retired' / 'data' / 'knowledge_base' / 'wiki',
    Path(__file__).parent / 'retired' / 'data' / 'knowledge_base' / 'wiki_corpus',
    Path(__file__).parent / 'retired' / 'data' / 'knowledge_base' / 'normalized_deeper',
    Path(__file__).parent / 'retired' / 'data' / 'knowledge_base' / 'cache'
]

MAINTENANCE_TASKS = {
    'scan_knowledge_files': {'script': 'scan_knowledge_files.py', 'needs_confirm': False},
    'export_missing_content_list': {'script': 'export_missing_content_list.py', 'needs_confirm': False},
    'normalize_wiki_cache': {'script': 'normalize_wiki_cache.py', 'needs_confirm': True},
    'deeper_extract_skipped': {'script': 'deeper_extract_skipped.py', 'needs_confirm': True},
    'run_rebuild_smoke': {'script': 'run_rebuild_smoke.py', 'needs_confirm': False},
    'qa_loaded_texts': {'script': 'qa_loaded_texts.py', 'needs_confirm': False},
    'normalize_thought_stream': {'script': 'normalize_thought_stream.py', 'needs_confirm': False},
    'nlp_refine': {'script': 'nlp_refine.py', 'needs_confirm': True},
    'refine_uncategorized': {'script': 'refine_uncategorized.py', 'needs_confirm': True},
    'sort_knowledge': {'script': 'sort_knowledge.py', 'needs_confirm': True}
}

LAST_MAINTENANCE_RESULT = {}
INDEXING_STATUS = {
    'running': False,
    'last_error': None,
    'last_result': None,
    'processed_batches': 0,
    'total_batches': 0,
    'throughput_eps': 0.0,
    'started_at': None,
    'avg_batch_ms': 0.0,
    'device_ids': [],
    'priority_paths': [],
    'batch_delay_ms': 0
}

OPS_CACHE = {}
OPS_MODE = {
    'mode': 'chat',
    'crawl_strategy': 'breadth',
    'seed_strategy': 'auto',
    'last_changed_at': None
}
STUDY_STATUS = {
    'last_run_at': None,
    'summary': None
}
LAST_WATCHDOG_RESTART_AT = None


def _utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _safe_load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with path.open('r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        return None


def _file_summary(path: Path) -> dict:
    if not path.exists():
        return {'exists': False}
    stat = path.stat()
    return {
        'exists': True,
        'size_bytes': stat.st_size,
        'modified_utc': _utc_iso(stat.st_mtime)
    }


def _count_taxonomy_domains(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        return 0
    return len(re.findall(r"^\s*-\s*id:\s*\"domain-", text, re.MULTILINE))


def _load_kb_governance_summary() -> dict:
    base_dir = Path(__file__).parent / 'data' / 'knowledge_base'
    metadata_dir = base_dir / 'metadata'
    index_path = metadata_dir / 'indexes' / 'wiki_file_topic_index.json'
    taxonomy_path = base_dir / 'classification' / 'topic_taxonomy.yaml'

    topic_registry = _safe_load_json(metadata_dir / 'topic_registry.json') or {}
    source_registry = _safe_load_json(metadata_dir / 'source_registry.json') or {}
    synonyms = _safe_load_json(metadata_dir / 'topic_synonyms.json') or {}
    mappings = _safe_load_json(metadata_dir / 'topic_to_domain.json') or {}
    edges = _safe_load_json(metadata_dir / 'graph_edges.json') or {}
    dedupe = _safe_load_json(metadata_dir / 'dedupe_registry.json') or {}
    curriculum = _safe_load_json(metadata_dir / 'curriculum_index.json') or {}

    index = _safe_load_json(index_path) or {}
    index_files = index.get('files') or []

    return {
        'registries': {
            'topics': len(topic_registry.get('topics') or []),
            'sources': len(source_registry.get('sources') or []),
            'synonyms': len((synonyms.get('synonyms') or {}).keys()),
            'topic_mappings': len(mappings.get('mappings') or []),
            'graph_edges': len(edges.get('edges') or []),
            'dedupe_items': len(dedupe.get('items') or []),
            'curricula': len(curriculum.get('curricula') or [])
        },
        'updated': {
            'topic_registry': topic_registry.get('updated_utc'),
            'source_registry': source_registry.get('updated_utc'),
            'synonyms': synonyms.get('updated_utc'),
            'topic_mappings': mappings.get('updated_utc'),
            'graph_edges': edges.get('updated_utc'),
            'dedupe_registry': dedupe.get('updated_utc'),
            'curriculum_index': curriculum.get('updated_utc')
        },
        'taxonomy': {
            'domains': _count_taxonomy_domains(taxonomy_path)
        },
        'index': {
            'wiki_files': len(index_files),
            'updated_utc': index.get('updated_utc'),
            'root': index.get('root'),
            'file_summary': _file_summary(index_path)
        },
        'files': {
            'lifecycle_policy': _file_summary(metadata_dir / 'lifecycle_policy.md'),
            'metadata_schema': _file_summary(metadata_dir / 'metadata_schema.json'),
            'ingest_rules': _file_summary(metadata_dir / 'ingest_rules.yaml')
        }
    }


def _get_cached(key: str, ttl_seconds: float, compute):
    now = time.time()
    cached = OPS_CACHE.get(key)
    if cached and (now - cached.get('ts', 0)) < ttl_seconds:
        return cached.get('value')
    value = compute()
    OPS_CACHE[key] = {'ts': now, 'value': value}
    return value


def _cache_key(namespace: str, *parts: str) -> str:
    suffix = ":".join(str(part) for part in parts if part)
    if suffix:
        return f"{namespace}:v{OPS_CACHE_VERSION}:{suffix}"
    return f"{namespace}:v{OPS_CACHE_VERSION}"


def _invalidate_cache(prefix: Optional[str] = None) -> None:
    if not prefix:
        OPS_CACHE.clear()
        return
    keys = [key for key in OPS_CACHE.keys() if key.startswith(prefix)]
    for key in keys:
        OPS_CACHE.pop(key, None)


def _warm_ops_cache() -> None:
    if not oxidus:
        return
    OPS_CACHE[_cache_key('ops_summary')] = {
        'ts': time.time(),
        'value': _build_ops_summary(include_admin=False)
    }
    OPS_CACHE[_cache_key('admin_ops_summary')] = {
        'ts': time.time(),
        'value': _build_ops_summary(include_admin=True)
    }


@app.before_request
def _start_request_timer():
    g.request_start = time.time()


@app.after_request
def _record_request_latency(response):
    start = getattr(g, 'request_start', None)
    if start is not None:
        elapsed_ms = round((time.time() - start) * 1000, 2)
        REQUEST_LATENCIES.append(elapsed_ms)
    return response


def _load_reliability_slo() -> dict:
    defaults = {
        'uptime_slo_pct': 99.5,
        'api_latency_p95_ms': 800,
        'ingestion_throughput_eps_min': 50.0,
        'crawler_pages_per_min_min': 5.0,
        'index_staleness_hours': 72.0,
        'storage_free_gb_min': 5.0,
        'alert_dedupe_seconds': ALERT_TTL_SECONDS
    }
    if not SLO_CONFIG_PATH.exists():
        return defaults
    try:
        payload = yaml.safe_load(SLO_CONFIG_PATH.read_text(encoding='utf-8')) or {}
    except Exception:
        return defaults
    reliability = payload.get('reliability', {}) if isinstance(payload, dict) else {}
    merged = dict(defaults)
    for key, value in reliability.items():
        if value is not None:
            merged[key] = value
    return merged


def _latency_stats() -> dict:
    if not REQUEST_LATENCIES:
        return {'count': 0, 'p50_ms': None, 'p95_ms': None}
    values = sorted(REQUEST_LATENCIES)
    size = len(values)

    def _percentile(pct: float) -> float:
        if size == 1:
            return values[0]
        rank = max(1, math.ceil(pct * size)) - 1
        rank = min(rank, size - 1)
        return values[rank]

    return {
        'count': size,
        'p50_ms': round(_percentile(0.50), 2),
        'p95_ms': round(_percentile(0.95), 2)
    }


def _storage_health() -> dict:
    base_dir = Path(__file__).parent
    kb_root = _knowledge_base_root()
    target = kb_root if kb_root.exists() else base_dir
    try:
        usage = shutil.disk_usage(target)
        free_gb = round(usage.free / (1024 ** 3), 2)
        total_gb = round(usage.total / (1024 ** 3), 2)
        used_pct = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
    except Exception:
        free_gb = None
        total_gb = None
        used_pct = None
    return {
        'path': str(target),
        'free_gb': free_gb,
        'total_gb': total_gb,
        'used_pct': used_pct
    }


def _enter_safe_mode(reason: str, triggered_by: str) -> None:
    global SAFE_MODE
    if SAFE_MODE.get('active') and SAFE_MODE.get('reason') == reason:
        return
    SAFE_MODE.update({
        'active': True,
        'reason': reason,
        'since': time.time(),
        'triggered_by': triggered_by
    })
    _log_telemetry('safe_mode_enabled', {
        'reason': reason,
        'triggered_by': triggered_by
    })
    if oxidus and getattr(oxidus, 'wikipedia_crawler', None):
        try:
            oxidus.stop_wiki_crawl()
        except Exception:
            pass


def _exit_safe_mode() -> None:
    global SAFE_MODE
    SAFE_MODE.update({
        'active': False,
        'reason': None,
        'since': None,
        'triggered_by': None
    })
    _log_telemetry('safe_mode_cleared')


def _block_if_safe_mode(action: str):
    if not SAFE_MODE.get('active'):
        return None
    default_device_ids = get_memryx_devices().get('device_ids') or []
    default_num_chips = max(len(default_device_ids), 1)

    return jsonify({
        'success': False,
        'error': 'Safe mode enabled',
        'action': action,
        'detail': SAFE_MODE.get('reason')
    }), 423


def _maybe_record_alert(code: str, level: str, message: str, meta: Optional[dict] = None) -> None:
    now = time.time()
    ttl = int(_load_reliability_slo().get('alert_dedupe_seconds', ALERT_TTL_SECONDS))
    last = ALERT_CACHE.get(code, 0)
    if now - last < ttl:
        return
    ALERT_CACHE[code] = now
    _log_telemetry('reliability_alert', {
        'code': code,
        'level': level,
        'message': message,
        'meta': meta or {}
    })


def _maybe_record_snapshot(code: str, event: str, payload: Optional[dict] = None) -> None:
    now = time.time()
    ttl = int(_load_reliability_slo().get('alert_dedupe_seconds', ALERT_TTL_SECONDS))
    last = ALERT_CACHE.get(code, 0)
    if now - last < ttl:
        return
    ALERT_CACHE[code] = now
    _log_telemetry(event, payload or {})


def _build_health_report(include_admin: bool = False) -> dict:
    slo = _load_reliability_slo()
    latency = _latency_stats()
    uptime_seconds = int(time.time() - APP_STARTED_AT)

    crawler = None
    if oxidus:
        try:
            crawler = oxidus.wiki_crawl_status()
        except Exception:
            crawler = None

    lm_status = {'available': False}
    try:
        from src.utils.lm_studio_client import get_lm_studio_client
        client = get_lm_studio_client()
        client.ensure_model_selected()
        available = client.is_available()
        expected_model = client.primary_model
        active_model = client.model
        lm_status = {
            'available': available,
            'model': active_model,
            'expected_model': expected_model,
            'model_match': bool(available and active_model == expected_model)
        }
    except Exception:
        lm_status = {'available': False}

    memryx_status = get_memryx_status()
    memryx_devices = {'device_ids': [], 'source': 'unknown', 'errors': []}
    if include_admin:
        memryx_devices = get_memryx_devices()

    storage = _storage_health()
    indexing = dict(INDEXING_STATUS)
    index_meta = _load_index_meta()
    index_staleness_hours = None
    index_ts = _parse_indexed_at(index_meta) or index_meta.get('file_mtime')
    if index_ts:
        index_staleness_hours = round((time.time() - float(index_ts)) / 3600, 2)

    crawler_pages_per_min = None
    crawler_health = (crawler or {}).get('health') or {}
    started_at = (crawler or {}).get('started_at') or crawler_health.get('started_at')
    pages = (crawler or {}).get('pages_crawled') or 0
    if started_at and pages:
        elapsed_min = max((time.time() - started_at) / 60.0, 0.01)
        crawler_pages_per_min = round(pages / elapsed_min, 2)

    if crawler_health.get('stalled'):
        _enter_safe_mode('Crawler stalled', 'crawler')
    if indexing.get('last_error'):
        _enter_safe_mode(f"Indexing error: {indexing.get('last_error')}", 'indexing')

    alerts = []
    if SAFE_MODE.get('active'):
        alerts.append({'code': 'safe_mode', 'level': 'critical', 'message': SAFE_MODE.get('reason')})
        _maybe_record_alert('safe_mode', 'critical', SAFE_MODE.get('reason') or 'Safe mode enabled')

    if crawler_health.get('stalled'):
        alerts.append({'code': 'crawler_stalled', 'level': 'critical', 'message': 'Crawler stalled'})
        _maybe_record_alert('crawler_stalled', 'critical', 'Crawler stalled')
    elif crawler_health.get('last_error'):
        alerts.append({'code': 'crawler_error', 'level': 'warning', 'message': crawler_health.get('last_error')})
        _maybe_record_alert('crawler_error', 'warning', crawler_health.get('last_error'))

    if indexing.get('last_error'):
        alerts.append({'code': 'indexing_error', 'level': 'critical', 'message': indexing.get('last_error')})
        _maybe_record_alert('indexing_error', 'critical', indexing.get('last_error'))

    if indexing.get('running') and indexing.get('throughput_eps', 0) < slo.get('ingestion_throughput_eps_min', 0):
        alerts.append({'code': 'indexing_throughput', 'level': 'warning', 'message': 'Indexing throughput below SLO'})
        _maybe_record_alert('indexing_throughput', 'warning', 'Indexing throughput below SLO')

    if (not indexing.get('running')) and index_staleness_hours is not None:
        threshold = float(slo.get('index_staleness_hours', 0) or 0)
        if threshold > 0 and index_staleness_hours > threshold:
            alerts.append({'code': 'index_staleness', 'level': 'warning', 'message': 'Index staleness above threshold'})
            _maybe_record_alert('index_staleness', 'warning', 'Index staleness above threshold', {
                'staleness_hours': index_staleness_hours,
                'threshold_hours': threshold
            })

    if crawler_health.get('running') and crawler_pages_per_min is not None:
        if crawler_pages_per_min < slo.get('crawler_pages_per_min_min', 0):
            alerts.append({'code': 'crawler_throughput', 'level': 'warning', 'message': 'Crawler throughput below SLO'})
            _maybe_record_alert('crawler_throughput', 'warning', 'Crawler throughput below SLO')

    if latency.get('p95_ms') is not None and latency.get('p95_ms') > slo.get('api_latency_p95_ms', 0):
        alerts.append({'code': 'latency_p95', 'level': 'warning', 'message': 'API latency above SLO'})
        _maybe_record_alert('latency_p95', 'warning', 'API latency above SLO')

    if storage.get('free_gb') is not None and storage.get('free_gb') < slo.get('storage_free_gb_min', 0):
        alerts.append({'code': 'storage_low', 'level': 'critical', 'message': 'Storage free space below SLO'})
        _maybe_record_alert('storage_low', 'critical', 'Storage free space below SLO')
        _enter_safe_mode('Storage free space below SLO', 'storage')

    if not lm_status.get('available'):
        alerts.append({'code': 'lm_offline', 'level': 'warning', 'message': 'LM Studio offline'})
        _maybe_record_alert('lm_offline', 'warning', 'LM Studio offline')
    elif not lm_status.get('model_match'):
        expected = lm_status.get('expected_model') or 'unknown'
        active = lm_status.get('model') or 'unknown'
        message = f"LM Studio model mismatch (expected {expected}, got {active})"
        alerts.append({'code': 'lm_model_mismatch', 'level': 'warning', 'message': message})
        _maybe_record_alert('lm_model_mismatch', 'warning', message, {
            'expected_model': expected,
            'active_model': active
        })

    if include_admin and not (memryx_devices.get('device_ids') or []):
        alerts.append({'code': 'memryx_devices', 'level': 'warning', 'message': 'No MemryX devices detected'})
        _maybe_record_alert('memryx_devices', 'warning', 'No MemryX devices detected')

    indexing['index_meta'] = index_meta
    indexing['staleness_hours'] = index_staleness_hours
    indexing['indexed_at_utc'] = _compute_index_staleness(index_meta).get('indexed_at_utc')

    return {
        'uptime_seconds': uptime_seconds,
        'latency': latency,
        'slo': slo,
        'safe_mode': dict(SAFE_MODE),
        'alerts': alerts,
        'crawler': crawler,
        'indexing': indexing,
        'lm_studio': lm_status,
        'memryx': {
            'status': memryx_status,
            'devices': memryx_devices if include_admin else None
        },
        'storage': storage,
        'crawler_pages_per_min': crawler_pages_per_min,
        'gui': {
            'running': True,
            'port': 5000,
            'mode': 'flask'
        }
    }


def _run_study_sweep() -> dict:
    if not oxidus or not oxidus.knowledge_organizer:
        return {'success': False, 'error': 'Knowledge organizer not available'}

    organizer = oxidus.knowledge_organizer
    try:
        clusters = organizer.cluster_concepts()
        hierarchy = organizer.build_hierarchy()
        open_threads = organizer.get_open_threads()
        loose_ends = organizer.get_loose_ends_report()
        summary = {
            'clusters': len(clusters),
            'hierarchy_roots': len(hierarchy),
            'open_threads': len(open_threads),
            'low_coherence_sources': len(loose_ends.get('low_coherence_sources') or []),
            'review_queue': len(loose_ends.get('review_queue') or [])
        }
    except Exception as exc:
        _log_telemetry('error', {'operation': 'organize_knowledge', 'error_type': type(exc).__name__})
        return {'success': False, 'error': 'Failed to organize knowledge'}

    STUDY_STATUS['last_run_at'] = datetime.now().isoformat()
    STUDY_STATUS['summary'] = summary
    if oxidus and getattr(oxidus, 'thought_stream', None):
        oxidus.thought_stream.add_thought(
            ThoughtType.REFLECTION,
            f"Study sweep complete: {summary}"
        )
    return {'success': True, 'summary': summary, 'last_run_at': STUDY_STATUS['last_run_at']}

MEMRYX_MODEL_ID = 'BAAI/bge-small-en-v1.5'
MEMRYX_TUNED_DIR = Path(__file__).parent / 'data' / 'models' / 'memryx' / 'bge-small-en-v1.5-tuned'
MEMRYX_TUNED_ONNX = MEMRYX_TUNED_DIR / 'model.onnx'
MEMRYX_TUNED_DFP = MEMRYX_TUNED_DIR / 'model.dfp'
MEMRYX_ONNX_PATH = Path(__file__).parent / 'data' / 'models' / 'memryx' / 'bge-small-en-v1.5.onnx'
MEMRYX_DFP_PATH = Path(__file__).parent / 'data' / 'models' / 'memryx' / 'bge-small-en-v1.5.dfp'
MEMRYX_INDEX_DIR = Path(__file__).parent / 'data' / 'knowledge_base' / 'index'
MEMRYX_DATA_ROOT = Path(__file__).parent / 'data' / 'knowledge_base'


def save_conversation():
    """Save conversation history to file for persistence."""
    try:
        with open(CONVERSATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(conversation_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving conversation: {e}")


def load_conversation():
    """Load conversation history from file if it exists."""
    global conversation_history
    if CONVERSATION_FILE.exists():
        try:
            with open(CONVERSATION_FILE, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
                print(f"Loaded {len(conversation_history)} messages from conversation history")
        except Exception as e:
            print(f"Error loading conversation: {e}")
            conversation_history = []
    else:
        conversation_history = []


def load_settings() -> dict:
    """Load persisted UI/behavior settings."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
    return {}


def _log_telemetry(event_type: str, payload: Optional[dict] = None) -> None:
    """Append a lightweight telemetry event for admin actions."""
    try:
        TELEMETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            'ts': datetime.now().isoformat(),
            'event': event_type,
            'payload': payload or {}
        }
        if request:
            entry['remote_addr'] = request.remote_addr
            entry['user_agent'] = request.headers.get('User-Agent')
        with open(TELEMETRY_LOG, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _load_access_heat() -> dict:
    cached = ACCESS_HEAT_CACHE.get('data')
    if isinstance(cached, dict):
        return cached

    data = {
        'updated_utc': None,
        'topics': {},
        'paths': {},
        'events': {}
    }

    if ACCESS_HEAT_PATH.exists():
        try:
            payload = json.loads(ACCESS_HEAT_PATH.read_text(encoding='utf-8'))
            if isinstance(payload, dict):
                data['updated_utc'] = payload.get('updated_utc')
                data['topics'] = payload.get('topics') or {}
                data['paths'] = payload.get('paths') or {}
                data['events'] = payload.get('events') or {}
        except Exception:
            pass

    ACCESS_HEAT_CACHE['data'] = data
    return data


def _save_access_heat(data: dict) -> None:
    try:
        ACCESS_HEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = ACCESS_HEAT_PATH.with_suffix('.json.tmp')
        with tmp_path.open('w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2, ensure_ascii=True)
        tmp_path.replace(ACCESS_HEAT_PATH)
        ACCESS_HEAT_CACHE['data'] = data
    except Exception:
        pass


def _record_access_signal(event: str, topics: Optional[list] = None, paths: Optional[list] = None) -> None:
    if not event:
        return

    topic_list = [topic for topic in (topics or []) if topic]
    path_list = [path for path in (paths or []) if path]

    now = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    with ACCESS_HEAT_LOCK:
        data = _load_access_heat()
        events = data.setdefault('events', {})
        events[event] = int(events.get(event, 0) or 0) + 1

        topics_store = data.setdefault('topics', {})
        for topic in topic_list:
            key = _normalize_topic_key(topic)
            if not key:
                continue
            entry = topics_store.setdefault(key, {'count': 0, 'last_access_utc': None})
            entry['count'] = int(entry.get('count', 0) or 0) + 1
            entry['last_access_utc'] = now

        paths_store = data.setdefault('paths', {})
        for path in path_list:
            entry = paths_store.setdefault(path, {'count': 0, 'last_access_utc': None})
            entry['count'] = int(entry.get('count', 0) or 0) + 1
            entry['last_access_utc'] = now

        data['updated_utc'] = now
        _save_access_heat(data)


def _build_access_heat_snapshot(limit: int = 50) -> dict:
    data = _load_access_heat()
    topics = data.get('topics') or {}
    paths = data.get('paths') or {}

    def _sort_key(item):
        payload = item[1] if isinstance(item[1], dict) else {}
        return int(payload.get('count', 0) or 0)

    top_topics = sorted(topics.items(), key=_sort_key, reverse=True)[:limit]
    top_paths = sorted(paths.items(), key=_sort_key, reverse=True)[:limit]

    return {
        'updated_utc': data.get('updated_utc'),
        'events': data.get('events') or {},
        'top_topics': [
            {'topic': topic, 'count': entry.get('count', 0), 'last_access_utc': entry.get('last_access_utc')}
            for topic, entry in top_topics
            if isinstance(entry, dict)
        ],
        'top_paths': [
            {'path': path, 'count': entry.get('count', 0), 'last_access_utc': entry.get('last_access_utc')}
            for path, entry in top_paths
            if isinstance(entry, dict)
        ]
    }


def require_admin_token():
    """Validate admin token for protected endpoints."""
    expected = os.environ.get(ADMIN_TOKEN_ENV)
    if not expected:
        try:
            if ADMIN_TOKEN_FILE.exists():
                expected = ADMIN_TOKEN_FILE.read_text(encoding='utf-8').strip()
                if expected:
                    os.environ[ADMIN_TOKEN_ENV] = expected
        except Exception:
            expected = None
    if not expected:
        expected = DEFAULT_ADMIN_TOKEN
        os.environ[ADMIN_TOKEN_ENV] = expected
    if not expected:
        return jsonify({'error': 'Admin token not configured'}), 503

    payload = request.get_json(silent=True) or {}
    supplied = (
        request.headers.get('X-Oxidus-Admin-Token')
        or request.args.get('admin_token')
        or payload.get('admin_token')
    )
    if not supplied or supplied != expected:
        return jsonify({'error': 'Unauthorized'}), 401

    return None


def cleanup_external_sources(include_retired: bool = False, dry_run: bool = True) -> dict:
    """Remove external scraped sources from disk."""
    targets = list(EXTERNAL_SOURCE_DIRS)
    if include_retired:
        targets.extend(EXTERNAL_SOURCE_DIRS_RETIRED)

    removed_files = 0
    removed_dirs = 0
    missing_dirs = 0

    for base_dir in targets:
        if not base_dir.exists():
            missing_dirs += 1
            continue

        for entry in base_dir.rglob('*'):
            if entry.is_file():
                removed_files += 1
                if not dry_run:
                    try:
                        entry.unlink()
                    except Exception:
                        pass

        if not dry_run:
            try:
                for child in base_dir.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                        removed_dirs += 1
            except Exception:
                pass

    return {
        'dry_run': dry_run,
        'include_retired': include_retired,
        'removed_files': removed_files,
        'removed_dirs': removed_dirs,
        'missing_dirs': missing_dirs,
        'targets': [str(p) for p in targets]
    }


def build_integrity_report() -> dict:
    """Check for missing scripts, unregistered scripts, and component availability."""
    base_dir = Path(__file__).parent
    scripts_dir = base_dir / 'scripts'
    script_files = set()
    if scripts_dir.exists():
        for path in scripts_dir.glob('*.py'):
            script_files.add(path.name)

    task_scripts = {task['script'] for task in MAINTENANCE_TASKS.values()}
    optional_scripts = {
        'check_lm_studio.py',
        'cleanup_external_sources.py',
        'lm_probe.py',
        'lm_studio_e2e.py',
        'lm_studio_retry.py',
        'memryx_monitor.py',
        'owner_smoke_queries.py',
        'train_memryx_embeddings.py'
    }
    unregistered_scripts = sorted(script_files - task_scripts - optional_scripts)
    missing_scripts = sorted(task_scripts - script_files)

    key_dirs = [
        base_dir / 'templates',
        base_dir / 'src',
        base_dir / 'config',
        base_dir / 'data',
        base_dir / 'data' / 'knowledge_base',
        base_dir / 'data' / 'research',
    ]
    dir_status = {
        str(path.relative_to(base_dir)): path.exists()
        for path in key_dirs
    }

    components = {
        'oxidus_initialized': oxidus is not None,
        'knowledge_organizer': bool(oxidus and oxidus.knowledge_organizer),
        'memory_index': bool(oxidus and oxidus.memory_index),
        'web_research': bool(oxidus and getattr(oxidus, 'web_research', None)),
        'wikipedia_api': bool(oxidus and getattr(oxidus, 'wikipedia', None)),
        'wiki_crawler': bool(oxidus and getattr(oxidus, 'wikipedia_crawler', None)),
        'ai_conversation': bool(oxidus and getattr(oxidus, 'ai_conversation', None))
    }

    return {
        'scripts_total': len(script_files),
        'tasks_total': len(task_scripts),
        'missing_scripts': missing_scripts,
        'unregistered_scripts': unregistered_scripts,
        'dir_status': dir_status,
        'components': components
    }


def get_memryx_status() -> dict:
    """Return MemryX installation and Python binding status."""
    root = Path(os.environ.get('MEMRYX_HOME', r'C:/Program Files/MemryX'))
    python_dir = root / 'python'
    binding_files = []
    if python_dir.exists():
        binding_files.extend(list(python_dir.glob('*.pyd')))
        binding_files.extend(list(python_dir.glob('*.so')))

    module_name = None
    module_importable = False
    module_path = None
    import_error = None

    prefer_mxa = any(p.name.lower().startswith('mxa.') for p in binding_files)
    import_order = ('mxa', 'memryx') if prefer_mxa else ('memryx', 'mxa')
    for name in import_order:
        try:
            module = importlib.import_module(name)
            module_name = name
            module_importable = True
            module_path = getattr(module, '__file__', None)
            import_error = None
            break
        except Exception as exc:
            _log_telemetry('error', {'operation': 'module_import', 'module': name, 'error_type': type(exc).__name__})
            import_error = 'Import failed'

    if not module_importable and python_dir.exists():
        if str(python_dir) not in sys.path:
            sys.path.insert(0, str(python_dir))
        for name in import_order:
            try:
                module = importlib.import_module(name)
                module_name = name
                module_importable = True
                module_path = getattr(module, '__file__', None)
                import_error = None
                break
            except Exception as exc:
                _log_telemetry('error', {'operation': 'module_import_syspath', 'module': name, 'error_type': type(exc).__name__})
                import_error = 'Import failed'

    return {
        'installed': root.exists() or module_importable,
        'root': str(root),
        'driver_present': (root / 'driver').exists(),
        'python_binding': bool(binding_files) or module_importable,
        'python_dir': str(python_dir),
        'module_name': module_name,
        'module_importable': module_importable,
        'module_path': module_path,
        'import_error': import_error
    }


def get_memryx_devices() -> dict:
    """Attempt to list MX3 device IDs via runtime API, fallback to mx_bench."""
    def _truncate(text: Optional[str], limit: int = 1200) -> Optional[str]:
        if text is None:
            return None
        value = str(text)
        return value if len(value) <= limit else value[:limit] + '...'

    def _find_mx_bench(root: Path) -> Optional[str]:
        if not root.exists():
            return None
        for name in ('mx_bench.exe', 'mx_bench'):
            try:
                for path in root.rglob(name):
                    if path.is_file():
                        return str(path)
            except Exception:
                continue
        return None

    def _prefer_wsl_mx_bench() -> bool:
        return os.environ.get('OXIDUS_WSL_MX_BENCH', '0').lower() in {'1', 'true', 'yes', 'on'}

    module = None
    errors = []
    attempts = []

    memryx_root = Path(os.environ.get('MEMRYX_HOME', r'C:/Program Files/MemryX'))
    python_dir = memryx_root / 'python'
    mx_bench_path = shutil.which('mx_bench')
    accl_bench_cmd = None
    if sys.platform == 'win32':
        candidate = memryx_root / 'acclBench' / 'acclBench.exe'
        accl_bench_cmd = str(candidate) if candidate.exists() else None
    else:
        accl_bench_cmd = shutil.which('acclBench')
    if not mx_bench_path:
        mx_bench_path = _find_mx_bench(memryx_root)

    if python_dir.exists() and str(python_dir) not in sys.path:
        sys.path.insert(0, str(python_dir))

    diagnostics = {
        'memryx_home': str(memryx_root),
        'python_dir': str(python_dir),
        'python_dir_exists': python_dir.exists(),
        'python_dir_in_sys_path': str(python_dir) in sys.path,
        'mx_bench_path': mx_bench_path,
        'mx_bench_wsl': None,
        'accl_bench_path': accl_bench_cmd or '',
        'accl_bench_exists': bool(accl_bench_cmd),
        'platform': sys.platform,
        'python_executable': sys.executable
    }

    prefer_mxa = any(p.name.lower().startswith('mxa.') for p in python_dir.glob('*.pyd')) if python_dir.exists() else False
    import_order = ('mxa', 'memryx') if prefer_mxa else ('memryx', 'mxa')
    module = None
    for name in import_order:
        try:
            module = __import__(name)  # type: ignore
            attempts.append({'name': f'import_{name}', 'success': True})
            diagnostics['module_path'] = getattr(module, '__file__', None)
            break
        except Exception as exc:
            _log_telemetry('error', {'operation': 'module_import', 'module': name, 'error_type': type(exc).__name__})
            attempts.append({'name': f'import_{name}', 'success': False, 'error': 'Import failed'})

    if module is None and python_dir.exists():
        diagnostics['python_dir_in_sys_path'] = str(python_dir) in sys.path
        for name in import_order:
            try:
                module = __import__(name)  # type: ignore
                attempts.append({'name': f'import_{name}_from_memryx_home', 'success': True})
                diagnostics['module_path'] = getattr(module, '__file__', None)
                break
            except Exception as exc:
                _log_telemetry('error', {'operation': 'module_import', 'module': name, 'error_type': type(exc).__name__})
                attempts.append({'name': f'import_{name}_from_memryx_home', 'success': False, 'error': 'Import failed'})
                errors.append(f"{name} import failed")
        if module is None:
            module = None

    def _try_call(obj, names):
        for name in names:
            fn = getattr(obj, name, None)
            if callable(fn):
                try:
                    return fn()
                except Exception:
                    continue
        return None

    device_ids = None
    source = 'unknown'
    if module:
        device_ids = _try_call(module, ['get_device_ids', 'list_devices', 'device_ids'])
        if device_ids is None and hasattr(module, 'accl'):
            device_ids = _try_call(module.accl, ['get_device_ids', 'list_devices', 'device_ids'])
        if device_ids is not None:
            source = 'runtime'
            attempts.append({'name': 'runtime_device_query', 'success': True})
        else:
            attempts.append({'name': 'runtime_device_query', 'success': False, 'error': 'no device ids returned'})

    if device_ids is None and mx_bench_path:
        try:
            cmd = [mx_bench_path, '--hello']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                ids = []
                for line in result.stdout.splitlines():
                    match = re.match(r"\s*(\d+)\s*\|", line)
                    if match:
                        ids.append(int(match.group(1)))
                if ids:
                    device_ids = ids
                    source = 'mx_bench'
                    attempts.append({'name': 'mx_bench', 'success': True, 'returncode': result.returncode})
                else:
                    attempts.append({
                        'name': 'mx_bench',
                        'success': False,
                        'returncode': result.returncode,
                        'stdout': _truncate(result.stdout),
                        'stderr': _truncate(result.stderr)
                    })
            else:
                errors.append(result.stderr.strip() or 'mx_bench failed')
                attempts.append({
                    'name': 'mx_bench',
                    'success': False,
                    'returncode': result.returncode,
                    'stdout': _truncate(result.stdout),
                    'stderr': _truncate(result.stderr)
                })
        except Exception as exc:
            _log_telemetry('error', {'operation': 'mx_bench', 'error_type': type(exc).__name__})
            errors.append('mx_bench failed')
            attempts.append({'name': 'mx_bench', 'success': False, 'error': 'Benchmark failed'})

    if device_ids is None:
        try:
            if accl_bench_cmd:
                result = subprocess.run([accl_bench_cmd, '--hello'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    ids = []
                    for line in result.stdout.splitlines():
                        match = re.match(r"\s*(\d+)\s*\|", line)
                        if match:
                            ids.append(int(match.group(1)))
                    if ids:
                        device_ids = ids
                        source = 'acclBench'
                        attempts.append({'name': 'acclBench', 'success': True, 'returncode': result.returncode})
                    else:
                        attempts.append({
                            'name': 'acclBench',
                            'success': False,
                            'returncode': result.returncode,
                            'stdout': _truncate(result.stdout),
                            'stderr': _truncate(result.stderr)
                        })
                else:
                    errors.append(result.stderr.strip() or 'acclBench failed')
                    attempts.append({
                        'name': 'acclBench',
                        'success': False,
                        'returncode': result.returncode,
                        'stdout': _truncate(result.stdout),
                        'stderr': _truncate(result.stderr)
                    })
            else:
                attempts.append({'name': 'acclBench', 'success': False, 'error': 'acclBench not found'})
        except Exception as exc:
            _log_telemetry('error', {'operation': 'acclBench', 'error_type': type(exc).__name__})
            errors.append('acclBench not available')
            attempts.append({'name': 'acclBench', 'success': False, 'error': 'Benchmark failed'})

    if device_ids is None and sys.platform == 'win32' and _prefer_wsl_mx_bench():
        try:
            venv = os.environ.get('OXIDUS_WSL_MX_VENV', '').strip() or '$HOME/mx'
            activate = f"source {venv}/bin/activate >/dev/null 2>&1 || true"
            cmd = f"{activate} && mx_bench --hello"
            result = subprocess.run(
                ['wsl', '-e', 'bash', '-lc', cmd],
                capture_output=True,
                text=True,
                timeout=15
            )
            diagnostics['mx_bench_wsl'] = 'wsl mx_bench --hello'
            if result.returncode == 0:
                ids = []
                for line in result.stdout.splitlines():
                    match = re.match(r"\s*(\d+)\s*\|", line)
                    if match:
                        ids.append(int(match.group(1)))
                if ids:
                    device_ids = ids
                    source = 'mx_bench_wsl'
                    attempts.append({'name': 'mx_bench_wsl', 'success': True, 'returncode': result.returncode})
                else:
                    attempts.append({
                        'name': 'mx_bench_wsl',
                        'success': False,
                        'returncode': result.returncode,
                        'stdout': _truncate(result.stdout),
                        'stderr': _truncate(result.stderr)
                    })
            else:
                errors.append(result.stderr.strip() or 'mx_bench failed in WSL')
                attempts.append({
                    'name': 'mx_bench_wsl',
                    'success': False,
                    'returncode': result.returncode,
                    'stdout': _truncate(result.stdout),
                    'stderr': _truncate(result.stderr)
                })
        except FileNotFoundError as exc:
            _log_telemetry('error', {'operation': 'mx_bench_wsl', 'error_type': 'FileNotFoundError'})
            errors.append('wsl not available for mx_bench')
            attempts.append({'name': 'mx_bench_wsl', 'success': False, 'error': 'WSL not available'})
        except Exception as exc:
            _log_telemetry('error', {'operation': 'mx_bench_wsl', 'error_type': type(exc).__name__})
            errors.append('mx_bench not available in WSL')
            attempts.append({'name': 'mx_bench_wsl', 'success': False, 'error': 'Benchmark failed'})

    if device_ids:
        errors = [e for e in errors if 'mx_bench' not in e.lower() and 'wsl' not in e.lower()]

    return {
        'device_ids': device_ids or [],
        'source': source,
        'errors': errors,
        'attempts': attempts,
        'diagnostics': diagnostics
    }


def _load_index_meta() -> dict:
    meta_path = MEMRYX_INDEX_DIR / 'index_meta.json'
    if not meta_path.exists():
        return {}
    try:
        with meta_path.open('r', encoding='utf-8') as f:
            meta = json.load(f)
        try:
            meta['file_mtime'] = meta_path.stat().st_mtime
        except Exception:
            meta.setdefault('file_mtime', None)
        return meta
    except Exception:
        return {}


def _parse_indexed_at(index_meta: dict) -> Optional[float]:
    indexed_at = index_meta.get('indexed_at') or index_meta.get('updated_utc')
    if isinstance(indexed_at, (int, float)):
        return float(indexed_at)
    if isinstance(indexed_at, str):
        raw = indexed_at.strip()
        if raw:
            try:
                return datetime.strptime(raw, '%Y-%m-%d %H:%M:%S').timestamp()
            except Exception:
                pass
            try:
                if raw.endswith('Z'):
                    raw = raw[:-1] + '+00:00'
                return datetime.fromisoformat(raw).timestamp()
            except Exception:
                pass
    return None


def _compute_index_staleness(index_meta: dict) -> dict:
    index_ts = _parse_indexed_at(index_meta) or index_meta.get('file_mtime')
    if not index_ts:
        return {'indexed_at_utc': None, 'staleness_hours': None}
    index_ts = float(index_ts)
    indexed_at_utc = datetime.fromtimestamp(index_ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    staleness_hours = round((time.time() - index_ts) / 3600, 2)
    return {'indexed_at_utc': indexed_at_utc, 'staleness_hours': staleness_hours}


def _log_indexing(message: str) -> None:
    try:
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'memryx_indexing.log'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with log_path.open('a', encoding='utf-8') as log:
            log.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _run_memryx_indexing(payload: dict) -> None:
    INDEXING_STATUS['running'] = True
    INDEXING_STATUS['last_error'] = None
    INDEXING_STATUS['last_result'] = None
    INDEXING_STATUS['processed_batches'] = 0
    INDEXING_STATUS['total_batches'] = 0
    INDEXING_STATUS['throughput_eps'] = 0.0
    INDEXING_STATUS['started_at'] = time.time()
    INDEXING_STATUS['avg_batch_ms'] = 0.0
    INDEXING_STATUS['device_ids'] = []
    INDEXING_STATUS['priority_paths'] = []
    INDEXING_STATUS['batch_delay_ms'] = 0

    _log_indexing('Indexing started')

    if MEMRYX_TUNED_ONNX.exists():
        default_onnx = MEMRYX_TUNED_ONNX
        default_dfp = MEMRYX_TUNED_DFP
        default_model = str(MEMRYX_TUNED_DIR)
    else:
        default_onnx = MEMRYX_ONNX_PATH
        default_dfp = MEMRYX_DFP_PATH
        default_model = MEMRYX_MODEL_ID

    model_id = payload.get('model_id') or default_model
    onnx_path = Path(payload.get('onnx_path') or default_onnx)
    dfp_path = Path(payload.get('dfp_path') or default_dfp)
    data_root = Path(payload.get('data_root') or MEMRYX_DATA_ROOT)
    output_dir = Path(payload.get('output_dir') or MEMRYX_INDEX_DIR)
    max_tokens = int(payload.get('max_tokens') or 192)
    batch_size = int(payload.get('batch_size') or 48)
    device_ids = payload.get('device_ids') or []
    if not device_ids:
        device_ids = get_memryx_devices().get('device_ids') or []
    if not device_ids:
        device_ids = [0]
    num_chips = int(payload.get('num_chips') or max(len(device_ids), 1))
    prefer_async = bool(payload.get('prefer_async', True))
    priority_paths = payload.get('priority_paths') or _build_index_priority_paths()
    batch_delay_ms = float(payload.get('batch_delay_ms') or 0)
    batch_delay_s = max(batch_delay_ms, 0) / 1000.0
    INDEXING_STATUS['device_ids'] = device_ids
    INDEXING_STATUS['priority_paths'] = priority_paths
    INDEXING_STATUS['batch_delay_ms'] = batch_delay_ms

    try:
        def _should_fallback_to_cpu(error_text: str) -> bool:
            text = (error_text or '').lower()
            markers = [
                'unsupported nodes',
                'operatorerror',
                'mx_nc not found',
                'decodeerror',
                'compilererror'
            ]
            return any(marker in text for marker in markers)

        if not onnx_path.exists():
            export_onnx(model_id=model_id, onnx_path=onnx_path, max_tokens=max_tokens)

        use_memryx = True
        if not dfp_path.exists():
            try:
                compile_to_dfp(onnx_path, dfp_path, num_chips=num_chips, max_tokens=max_tokens)
            except Exception as compile_exc:
                # Only use exception type for fallback decision to prevent info disclosure
                error_type = type(compile_exc).__name__
                if _should_fallback_to_cpu(error_type):
                    use_memryx = False
                    _log_indexing(f"MemryX compile fallback to CPU: {error_type}")
                else:
                    raise

        def _progress(processed, total, elapsed):
            INDEXING_STATUS['processed_batches'] = processed
            INDEXING_STATUS['total_batches'] = total
            if elapsed > 0:
                INDEXING_STATUS['throughput_eps'] = round((processed * batch_size) / elapsed, 2)
            INDEXING_STATUS['avg_batch_ms'] = round((elapsed / max(processed, 1)) * 1000, 2)
            if processed == 1 or processed % 10 == 0 or processed == total:
                _log_indexing(
                    f"Progress {processed}/{total} | {INDEXING_STATUS['throughput_eps']} eps | "
                    f"{INDEXING_STATUS['avg_batch_ms']} ms/batch"
                )

        try:
            result = build_index(
                model_id=model_id,
                onnx_path=onnx_path,
                dfp_path=dfp_path,
                data_root=data_root,
                output_dir=output_dir,
                max_tokens=max_tokens,
                batch_size=batch_size,
                device_ids=device_ids,
                use_memryx=use_memryx,
                prefer_async=prefer_async,
                progress_cb=_progress,
                priority_paths=priority_paths,
                batch_delay_s=batch_delay_s
            )
        except Exception as run_exc:
            # Only use exception type for fallback decision to prevent info disclosure
            error_type = type(run_exc).__name__
            if use_memryx and _should_fallback_to_cpu(error_type):
                _log_indexing(f"MemryX runtime fallback to CPU: {error_type}")
                result = build_index(
                    model_id=model_id,
                    onnx_path=onnx_path,
                    dfp_path=dfp_path,
                    data_root=data_root,
                    output_dir=output_dir,
                    max_tokens=max_tokens,
                    batch_size=batch_size,
                    device_ids=device_ids,
                    use_memryx=False,
                    prefer_async=False,
                    progress_cb=_progress,
                    priority_paths=priority_paths,
                    batch_delay_s=batch_delay_s
                )
            else:
                raise

        _log_indexing(
            f"Indexing done: {result.get('vectors', 0)} vectors | {result.get('dimensions', 0)} dim"
        )
        INDEXING_STATUS['last_result'] = result
        _invalidate_cache('ops_summary')
        _invalidate_cache('admin_ops_summary')
        _invalidate_cache('tiering_overview')
        _warm_ops_cache()
    except Exception as exc:
        _log_telemetry('error', {'operation': 'indexing', 'error_type': type(exc).__name__})
        INDEXING_STATUS['last_error'] = 'Indexing failed'
        _log_indexing(f"Indexing error: {type(exc).__name__}")
        _enter_safe_mode(f"Indexing error: {type(exc).__name__}", 'indexing')
    finally:
        INDEXING_STATUS['running'] = False


def _latest_thought_stream() -> Optional[str]:
    streams_dir = Path(__file__).parent / 'data' / 'thought_streams'
    if not streams_dir.exists():
        return None
    candidates = list(streams_dir.glob('*.json'))
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return str(latest)


def run_maintenance_task(task: str, data: dict) -> dict:
    task_info = MAINTENANCE_TASKS.get(task)
    if not task_info:
        return {'success': False, 'error': 'Unknown maintenance task'}

    if task_info.get('needs_confirm') and not data.get('confirm'):
        return {'success': False, 'error': 'Confirmation required for this task'}

    script_path = Path(__file__).parent / 'scripts' / task_info['script']
    if not script_path.exists():
        return {'success': False, 'error': f'Script not found: {script_path}'}

    args = []
    data_dir = Path(__file__).parent / 'data'
    allowed_base = data_dir.resolve()
    scripts_dir = (Path(__file__).parent / 'scripts').resolve()
    script_path = script_path.resolve()
    
    if task == 'normalize_thought_stream':
        input_path = data.get('input_path') or _latest_thought_stream()
        output_path = data.get('output_path')
        if not input_path:
            return {'success': False, 'error': 'No thought stream file found'}
        input_resolved = _resolve_path_under_base(str(input_path), allowed_base)
        if not input_resolved:
            return {'success': False, 'error': 'Invalid input path'}
        args.append(str(input_resolved))
        if output_path:
            output_resolved = _resolve_path_under_base(str(output_path), allowed_base)
            if not output_resolved:
                return {'success': False, 'error': 'Invalid output path'}
            args.append(str(output_resolved))
    elif task == 'nlp_refine':
        root = data.get('root')
        if not root:
            return {'success': False, 'error': 'root is required'}
        root_resolved = _resolve_path_under_base(str(root), allowed_base)
        if not root_resolved:
            return {'success': False, 'error': 'Invalid root path'}
        args.extend(['--root', str(root_resolved)])
    elif task == 'refine_uncategorized':
        src = data.get('src')
        root = data.get('root')
        if not src or not root:
            return {'success': False, 'error': 'src and root are required'}
        src_resolved = _resolve_path_under_base(str(src), allowed_base)
        root_resolved = _resolve_path_under_base(str(root), allowed_base)
        if not src_resolved or not root_resolved:
            return {'success': False, 'error': 'Invalid path'}
        args.extend(['--src', str(src_resolved), '--root', str(root_resolved)])
    elif task == 'sort_knowledge':
        source = data.get('source')
        out_dir = data.get('out')
        if not source or not out_dir:
            return {'success': False, 'error': 'source and out are required'}
        source_resolved = _resolve_path_under_base(str(source), allowed_base)
        out_resolved = _resolve_path_under_base(str(out_dir), allowed_base)
        if not source_resolved or not out_resolved:
            return {'success': False, 'error': 'Invalid path'}
        args.extend(['--source', str(source_resolved), '--out', str(out_resolved)])

    # Final validation: ensure script_path is safe and args contain only validated paths
    try:
        if not _is_path_safe(script_path, scripts_dir):
            return {'success': False, 'error': 'Invalid script path'}

        # Additional security: validate that all args are safe strings without shell metacharacters
        dangerous_chars = set(';&|`$()<>{}[]!*?~')
        for arg in args:
            if any(char in str(arg) for char in dangerous_chars):
                return {'success': False, 'error': 'Invalid argument characters'}

        result = subprocess.run(
            [sys.executable, str(script_path), *args],
            capture_output=True,
            text=True,
            timeout=120,
            shell=False  # Explicitly disable shell to prevent command injection
        )
        result_payload = {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout[-8000:],
            'stderr': result.stderr[-4000:]
        }
        LAST_MAINTENANCE_RESULT.update({
            'task': task,
            'timestamp': datetime.now().isoformat(),
            **result_payload
        })
        return result_payload
    except subprocess.TimeoutExpired:
        result_payload = {'success': False, 'error': 'Task timed out'}
        LAST_MAINTENANCE_RESULT.update({
            'task': task,
            'timestamp': datetime.now().isoformat(),
            **result_payload
        })
        return result_payload
    except Exception as e:
        _log_telemetry('error', {'operation': 'maintenance_task', 'task': task, 'error_type': type(e).__name__})
        result_payload = {'success': False, 'error': 'Failed to complete maintenance task'}
        LAST_MAINTENANCE_RESULT.update({
            'task': task,
            'timestamp': datetime.now().isoformat(),
            **result_payload
        })
        return result_payload


def init_oxidus():
    """Initialize Oxidus on app startup."""
    global oxidus, conversation_history
    
    # Load previous conversation if it exists
    load_conversation()
    
    # Only initialize Oxidus if not already done
    if oxidus is None:
        oxidus = Oxidus()

        settings = load_settings()
        chat_style = settings.get('chat_style', 'hybrid')
        oxidus.set_chat_style(chat_style)
        
        # If no saved conversation, add initial greeting
        if not conversation_history:
            initial_message = {
                'speaker': 'OXIDUS',
                'message': oxidus_greeting(),
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'type': 'greeting'
            }
            conversation_history.append(initial_message)
            save_conversation()

        if os.environ.get('OXIDUS_AUTO_INDEXING', '1').lower() not in {'0', 'false', 'off', 'no'}:
            if SAFE_MODE.get('active'):
                _log_telemetry('auto_indexing_skipped', {'reason': SAFE_MODE.get('reason')})
            elif not INDEXING_STATUS.get('running'):
                devices = get_memryx_devices().get('device_ids', [])
                if devices:
                    thread = threading.Thread(target=_run_memryx_indexing, args=({},), daemon=True)
                    thread.start()


def oxidus_greeting() -> str:
    """Return Oxidus's initial greeting."""
    return _build_opening_message()


_OPENERS_GENERAL = [
    "I am Oxidus. I am awake and listening. What do you want to focus on today?",
    "I am here. What is on your mind right now?",
    "I can help you think, plan, or decide. Where do you want to start?",
    "We can go deep or keep it practical. What do you want to work on today?",
]

_OPENERS_USER = [
    "You mentioned {seed} before. Do you want to continue there, or switch gears?",
    "Last time you brought up {seed}. Want to pick it back up?",
    "I remember {seed} from earlier. Want to dig into it or move to something new?",
]

_OPENERS_KNOWLEDGE = [
    "A thread that keeps surfacing is {seed}. Want a quick summary or do you want to steer?",
    "I have been tracking {seed}. Do you want to explore it or set a new direction?",
    "{seed} stood out in recent reading. Want to go there, or focus on your current task?",
]

_KNOWLEDGE_CONTEXT_LINES = [
    "Seed context: from the archive.",
    "Seed context: from the knowledge archive.",
    "Seed context: from collected sources.",
]

_USER_CONTEXT_LINES = [
    "From you: {snippet}",
    "From our last thread: {snippet}",
    "From your last note: {snippet}",
]

_IGNORED_TOPICS = {
    'hello', 'hi', 'hey', 'greetings', 'freedom', 'please', 'thanks', 'thank',
    'give', 'list', 'interesting', 'topic', 'topics', 'about', 'question'
}


def _extract_user_topics(max_items: int = 6) -> list:
    if not conversation_history:
        return []

    stopwords = {
        'the', 'and', 'that', 'with', 'from', 'this', 'have', 'what', 'your', 'about',
        'when', 'where', 'which', 'their', 'there', 'would', 'could', 'should', 'just',
        'like', 'want', 'need', 'been', 'into', 'than', 'then', 'them', 'they', 'you',
        'are', 'was', 'were', 'will', 'can', 'how', 'why', 'who', 'for', 'not', 'but',
    }

    counts = {}
    recent = conversation_history[-50:]
    for entry in reversed(recent):
        if entry.get('speaker') != 'YOU':
            continue
        message = entry.get('message') or ''
        for word in re.findall(r"[A-Za-z][A-Za-z\-']{2,}", message.lower()):
            if word in stopwords or word in _IGNORED_TOPICS:
                continue
            counts[word] = counts.get(word, 0) + 1
    if not counts:
        return []
    sorted_items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [word for word, _ in sorted_items[:max_items]]


def _extract_query_topics(message: str, max_items: int = 3) -> list:
    if not message:
        return []
    
    # Limit input length to prevent ReDoS
    if len(message) > 10000:
        message = message[:10000]

    cleaned = ' '.join(message.split()).strip()
    if not cleaned:
        return []

    lowered = cleaned.lower()

    parts = []
    if 'between ' in lowered and ' and ' in lowered:
        tail = lowered.split('between ', 1)[1]
        left, right = tail.split(' and ', 1)
        parts = [left.strip(), right.strip()]
    else:
        segment = lowered
        for trigger in ('about ', 'on ', 'regarding ', 're:', 'concerning '):
            marker = segment.find(trigger)
            if marker != -1:
                segment = segment[marker + len(trigger):]
                break

        normalized = segment.replace(',', ' and ')
        normalized = normalized.replace(' versus ', ' and ')
        normalized = normalized.replace(' vs ', ' and ')
        normalized = normalized.replace(' plus ', ' and ')
        parts = [chunk.strip() for chunk in normalized.split(' and ') if chunk.strip()]

    leading_phrases = (
        "tell me about", "tell me", "what about", "explain", "describe",
        "overview of", "give me", "compare", "difference between", "between"
    )
    stopwords = {
        'the', 'and', 'that', 'with', 'from', 'this', 'have', 'what', 'your', 'about',
        'when', 'where', 'which', 'their', 'there', 'would', 'could', 'should', 'just',
        'like', 'want', 'need', 'been', 'into', 'than', 'then', 'them', 'they', 'you',
        'are', 'was', 'were', 'will', 'can', 'how', 'why', 'who', 'for', 'not', 'but',
    }

    topics = []
    seen = set()
    for part in parts:
        chunk = part.strip(" .!?;:")
        if not chunk:
            continue
        chunk_lower = chunk.lower()
        for phrase in leading_phrases:
            if chunk_lower.startswith(phrase + " "):
                chunk = chunk[len(phrase):].strip()
                chunk_lower = chunk.lower()
                break

        tokens = re.findall(r"[A-Za-z][A-Za-z\-']+", chunk_lower)
        if not tokens or all(token in stopwords for token in tokens):
            continue

        key = " ".join(tokens)
        if key in seen:
            continue
        seen.add(key)
        topics.append(chunk)
        if len(topics) >= max_items:
            break

    return topics


def _collect_knowledge_seeds(max_items: int = 10) -> list:
    seeds = []
    if not oxidus or not oxidus.knowledge_organizer:
        return seeds

    organizer = oxidus.knowledge_organizer

    try:
        seeds.extend(organizer.get_open_threads()[:max_items])
    except Exception:
        pass

    try:
        seeds.extend(organizer.get_underexplored_values()[:max_items])
    except Exception:
        pass

    for note in organizer.notes[-20:]:
        topic = (note or {}).get('topic')
        if topic:
            seeds.append(topic)

    for source in list(organizer.scraped_sources.values())[-30:]:
        title = (source or {}).get('title')
        if title:
            seeds.append(title)

    unique = []
    seen = set()
    for seed in seeds:
        cleaned = str(seed).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen or key in _IGNORED_TOPICS:
            continue
        seen.add(key)
        unique.append(cleaned)
        if len(unique) >= max_items:
            break
    return unique


def _is_trivial_user_message(message: str) -> bool:
    if not message:
        return True
    cleaned = re.sub(r"\s+", " ", message).strip().lower()
    if len(cleaned) < 12:
        return True
    if re.fullmatch(r"(hello|hi|hey|greetings)(\s+there)?[!.]?", cleaned):
        return True
    words = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", cleaned)
    if not words:
        return True
    return all(word in _IGNORED_TOPICS for word in words)


def _latest_user_message() -> Optional[str]:
    for entry in reversed(conversation_history):
        if entry.get('speaker') == 'YOU':
            message = (entry.get('message') or '').strip()
            return message or None
    return None


def _shorten_snippet(text: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[:max_len - 1].rstrip()}…"


def _normalize_topic_key(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _title_from_wiki_filename(file_name: str) -> str:
    stem = Path(file_name).stem
    if "_" not in stem:
        return stem
    return stem.rsplit("_", 1)[0]


def _load_wiki_corpus_index() -> list:
    index_path = Path(__file__).parent / 'data' / 'knowledge_base' / 'metadata' / 'indexes' / 'wiki_file_topic_index.json'
    payload = _safe_load_json(index_path) or {}
    return payload.get('files') or []


def _find_wiki_corpus_matches(topics: list, max_items: int = 2) -> list:
    if not topics:
        return []
    index_entries = _load_wiki_corpus_index()
    if not index_entries:
        return []

    normalized_topics = [_normalize_topic_key(topic) for topic in topics if topic]
    normalized_topics = [topic for topic in normalized_topics if topic]
    if not normalized_topics:
        return []

    matches = []
    for entry in index_entries:
        file_name = entry.get('file_name') or ''
        if not file_name:
            continue
        title = _title_from_wiki_filename(file_name)
        title_key = _normalize_topic_key(title)
        if not title_key:
            continue
        for topic_key in normalized_topics:
            if topic_key in title_key or title_key in topic_key:
                relative_path = entry.get('relative_path')
                if not relative_path:
                    continue
                matches.append({
                    'title': title,
                    'path': Path(__file__).parent / 'data' / 'knowledge_base' / relative_path
                })
                break
        if len(matches) >= max_items:
            break

    return matches


def _extract_wiki_snippet(path: Path, max_len: int = 600) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    paragraph = []
    for line in lines:
        if line.startswith("#"):
            continue
        paragraph.append(line)
        if len(" ".join(paragraph)) >= max_len:
            break

    snippet = " ".join(paragraph).strip()
    if len(snippet) > max_len:
        snippet = snippet[:max_len - 1].rstrip() + "..."
    return snippet


def _is_breakdown_prompt(message: str) -> bool:
    if not message:
        return False
    lowered = message.strip().lower()
    if lowered.startswith("i can keep going if we break this into smaller questions"):
        return True
    if lowered.startswith("that is a complex question"):
        return True
    return False


def _store_answered_exchange(question: str, answer: str) -> bool:
    if not oxidus or not answer or _is_breakdown_prompt(answer):
        return False

    topics = _extract_query_topics(question, max_items=2)
    note_topic = topics[0] if topics else question[:120].strip()
    follow_ups = _build_follow_up_tasks(question, answer, topics)

    summary = f"Q: {question}\nA: {answer}".strip()
    if len(summary) > 1600:
        summary = summary[:1597].rstrip() + "..."

    if oxidus.knowledge_organizer:
        try:
            oxidus.knowledge_organizer.add_note(
                topic=note_topic or "answered_question",
                summary=summary,
                questions=[question] if question else [],
                action_items=follow_ups,
                sources=["chat_exchange"]
            )
        except Exception:
            return False

    if oxidus.memory_index:
        try:
            memory_topics = oxidus.memory_index.extract_topics(summary) if summary else []
            if memory_topics:
                oxidus.memory_index.add_memory(
                    f"Answered: {question}\n{answer}",
                    memory_type='conversation',
                    topics=memory_topics
                )
        except Exception:
            return False

    if oxidus.ai_conversation and follow_ups:
        for item in follow_ups:
            oxidus.ai_conversation.add_understanding_gap(item)

    return True


def _build_follow_up_tasks(question: str, answer: str, topics: list) -> list:
    base = topics[0] if topics else ''
    label = base or "this topic"
    tasks = [
        f"Collect 2-3 authoritative sources on {label}",
        f"Identify key mechanisms and measurable variables for {label}",
        f"List main risks, failure modes, and constraints for {label}",
        f"Draft a 5-step validation plan or small test for {label}"
    ]

    if question:
        tasks.insert(0, f"Clarify scope: {question[:120].strip()}")

    if answer:
        tasks.append("Extract 3 concise takeaways and compare against sources")

    seen = set()
    deduped = []
    for task in tasks:
        key = task.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(task)
    return deduped[:6]


def _build_user_context_line(user_topics: list) -> Optional[str]:
    last_message = _latest_user_message()
    if last_message and not _is_trivial_user_message(last_message):
        snippet = _shorten_snippet(last_message)
        return random.choice(_USER_CONTEXT_LINES).format(snippet=snippet)
    if user_topics:
        return f"From you: {random.choice(user_topics)}."
    return None


def _fallback_response(user_message: str) -> str:
    topics = _extract_query_topics(user_message, max_items=3)
    wiki_matches = _find_wiki_corpus_matches(topics, max_items=2)
    if wiki_matches:
        matched_paths = [_relative_kb_path(match['path']) for match in wiki_matches]
        _record_access_signal('local_kb_fallback', topics=topics, paths=matched_paths)
        lines = ["I do not have a live model response, but I can use local knowledge:"]
        for match in wiki_matches:
            snippet = _extract_wiki_snippet(match['path'])
            if snippet:
                lines.append(f"- {match['title']}: {snippet}")
            else:
                lines.append(f"- {match['title']}: Local knowledge file found, but it is empty or unreadable.")
        lines.append("If you want a deeper answer, tell me the angle (definition, history, observations, or open questions).")
        return "\n".join(lines)

    if len(topics) >= 2:
        topic_a, topic_b = topics[0], topics[1]
        return (
            f"I can cover {topic_a} and {topic_b}, then connect them. "
            "I will define each clearly, then map a bridge (shared mechanisms, materials, or constraints). "
            "If you want a specific angle (scientific, practical, or historical), tell me."
        )

    topic = None
    for word in _extract_user_topics(max_items=1):
        topic = word
        break
    if topic:
        return (
            f"I can help with {topic}. Here is a practical starting map:\n"
            "- Core concepts and definitions\n"
            "- Current applications and constraints\n"
            "- Key risks and safety boundaries\n"
            "- Open questions worth researching\n\n"
            "Tell me your goal (learn, build, compare, or decide) and I will go deeper."
        )
    return (
        "I am here to help. Tell me the area you want to explore, and I will map it,"
        " connect the dots, and give you clear next steps."
    )


def _build_opening_message() -> str:
    user_topics = _extract_user_topics()
    knowledge_seeds = _collect_knowledge_seeds()
    user_context_line = _build_user_context_line(user_topics)

    if not user_topics and not knowledge_seeds:
        opener = random.choice(_OPENERS_GENERAL)
        if user_context_line:
            return f"{opener}\n\n{user_context_line}"
        return opener

    if user_topics and knowledge_seeds:
        source = random.choices(['user', 'knowledge'], weights=[0.7, 0.3], k=1)[0]
    elif user_topics:
        source = 'user'
    else:
        source = 'knowledge'

    if source == 'user':
        seed = random.choice(user_topics)
        opener = random.choice(_OPENERS_USER).format(seed=seed)
        if user_context_line:
            return f"{opener}\n\n{user_context_line}"
        return opener

    seed = random.choice(knowledge_seeds)
    opener = random.choice(_OPENERS_KNOWLEDGE).format(seed=seed)
    context_line = random.choice(_KNOWLEDGE_CONTEXT_LINES)
    if user_context_line:
        return f"{opener}\n\n{context_line}\n{user_context_line}"
    return f"{opener}\n\n{context_line}"


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/admin')
def admin_page():
    """Serve the admin page."""
    return render_template('admin.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get Oxidus status."""
    try:
        if not oxidus:
            return jsonify({'error': 'Oxidus not initialized'})
        
        summary = oxidus.thought_stream.get_thinking_summary()
        
        return jsonify({
            'total_thoughts': summary['total_thoughts'],
            'questions': summary['total_questions'],
            'decisions': summary['total_decisions'],
            'ethical_checks': summary['ethical_checks'],
            'insights': summary['insights_gained'],
            'most_active': summary['most_active']
        })
    except Exception as exc:
        _log_telemetry('error', {'operation': 'get_status', 'error_type': type(exc).__name__})
        return jsonify({'error': 'Failed to retrieve status'}), 500
@app.route('/api/health', methods=['GET'])
def health_check():
    """Get system health for uptime, latency, and ingestion checks."""
    return jsonify(_build_health_report(include_admin=False))


@app.route('/api/admin/health', methods=['GET'])
def admin_health_check():
    """Get detailed system health for admin use."""
    guard = require_admin_token()
    if guard:
        return guard

    return jsonify(_build_health_report(include_admin=True))


@app.route('/api/admin/safe-mode/clear', methods=['POST'])
def admin_clear_safe_mode():
    """Clear safe mode (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    _exit_safe_mode()
    return jsonify({'success': True, 'safe_mode': dict(SAFE_MODE)})


@app.route('/api/thoughts', methods=['GET'])
def get_thoughts():
    """Get recent thoughts."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    recent = oxidus.thought_stream.get_recent_thoughts(10)
    thought_items = []
    for thought in recent:
        if thought is None:
            continue
        thought_items.append({
            'type': thought.type.value,
            'content': thought.content,
            'timestamp': thought.timestamp.isoformat(),
            'context': thought.context,
            'display': str(thought)
        })

    if request.args.get('format') == 'legacy':
        return jsonify({'thoughts': [item['display'] for item in thought_items]})

    return jsonify(thought_items)


@app.route('/api/message', methods=['POST'])
def send_message():
    """Send a message to Oxidus and get response."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Empty message'})
    
    # Add user message to history
    user_entry = {
        'speaker': 'YOU',
        'message': user_message,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': 'user'
    }
    conversation_history.append(user_entry)
    
    # Get Oxidus response from LM Studio
    message_topics = _extract_query_topics(user_message, max_items=3)
    _record_access_signal('user_message', topics=message_topics)
    system_prompt = OXIDUS_TONE_PROMPT
    if len(message_topics) >= 2:
        system_prompt = (
            f"{OXIDUS_TONE_PROMPT} "
            "When the user asks about multiple topics, cover each briefly, then add a short section that "
            "connects them. Look for at least one shared mechanism, constraint, or practical bridge. "
            "If the connection is weak, say so and offer 1-2 angles to explore."
        )
    lm_response = lm_client.ask_routed_question(user_message, system_prompt=system_prompt)
    if lm_response is None or not str(lm_response).strip():
        lm_response = _fallback_response(user_message)
    documented = _store_answered_exchange(user_message, str(lm_response))
    oxidus_entry = {
        'speaker': 'OXIDUS',
        'message': str(lm_response),
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': 'oxidus',
        'documented': bool(documented)
    }
    conversation_history.append(oxidus_entry)
    save_conversation()
    summary = oxidus.thought_stream.get_thinking_summary()
    return jsonify({
        'user_message': user_entry,
        'oxidus_response': oxidus_entry,
        'status': {
            'total_thoughts': summary['total_thoughts'],
            'questions': summary['total_questions'],
            'decisions': summary['total_decisions'],
            'insights': summary['insights_gained']
        }
    })


@app.route('/api/conversation', methods=['GET'])
def get_conversation():
    """Get full conversation history."""
    if request.args.get('format') == 'legacy':
        return jsonify({'history': conversation_history})

    return jsonify(conversation_history)


@app.route('/api/clear', methods=['POST'])
def clear_conversation():
    """Clear conversation history."""
    global conversation_history
    conversation_history = []
    
    # Remove saved file
    if CONVERSATION_FILE.exists():
        try:
            os.remove(CONVERSATION_FILE)
        except Exception as e:
            print(f"Error deleting conversation file: {e}")
    
    initial_message = {
        'speaker': 'OXIDUS',
        'message': "Conversation cleared. Let's start fresh.",
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': 'greeting'
    }
    conversation_history.append(initial_message)
    save_conversation()
    
    return jsonify({'success': True})


@app.route('/api/understanding', methods=['GET'])
def get_understanding():
    """Get Oxidus's current understanding evolution."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    understanding = oxidus.get_understanding_summary()
    
    return jsonify({
        'summary': understanding,
        'concepts': oxidus.understanding_model,
        'adaptation_count': oxidus.adaptation_frequency,
        'total_concepts': len(oxidus.understanding_model)
    })


@app.route('/api/memories', methods=['GET'])
def get_memory_summary():
    """Get Oxidus's memory index summary."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    summary = oxidus.get_memory_summary()
    memories = []
    if oxidus.memory_index is not None:
        try:
            memories = [
                {
                    'content': memory.content,
                    'memory_type': memory.memory_type,
                    'topics': list(memory.topics),
                    'recall_count': memory.recall_count,
                    'timestamp': memory.timestamp.isoformat()
                }
                for memory in oxidus.memory_index.memories
            ]
        except Exception:
            memories = []
    
    return jsonify({
        'summary': summary,
        'memories': memories,
        'available': oxidus.memory_index is not None
    })


@app.route('/api/wiki-search', methods=['POST'])
def wiki_search():
    """Search Wikipedia and return results."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    if not getattr(oxidus, 'wikipedia', None):
        return jsonify({'error': 'Wikipedia API not available'})

    data = request.json or {}
    query = data.get('query', '').strip()
    limit = int(data.get('limit', 5))

    if not query:
        return jsonify({'error': 'No query provided'})

    _record_access_signal('wiki_search', topics=[query])
    result = oxidus.wiki_search(query, limit=limit)
    return jsonify(result)


@app.route('/api/wiki-page', methods=['POST'])
def wiki_page():
    """Fetch a Wikipedia page and optionally organize it."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    if not getattr(oxidus, 'wikipedia', None):
        return jsonify({'error': 'Wikipedia API not available'})

    data = request.json or {}
    title = data.get('title', '').strip()
    organize = bool(data.get('organize', True))

    if not title:
        return jsonify({'error': 'No title provided'})

    _record_access_signal('wiki_page', topics=[title])
    result = oxidus.wiki_page(title, organize=organize)
    return jsonify(result)


@app.route('/api/wiki-crawl/start', methods=['POST'])
def wiki_crawl_start():
    """Start Wikipedia crawling for selected domains."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('wiki_crawl_start')
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    data = request.json or {}
    domains = data.get('domains', [])
    max_depth = int(data.get('max_depth', 2))
    max_pages = data.get('max_pages')
    if max_pages is not None:
        max_pages = int(max_pages)
    strategy = (data.get('strategy') or 'breadth').strip().lower()
    seed_strategy = (data.get('seed_strategy') or 'auto').strip().lower()

    if not domains:
        return jsonify({'error': 'No domains provided'})

    result = oxidus.start_wiki_crawl(
        domains=domains,
        max_depth=max_depth,
        max_pages=max_pages,
        strategy=strategy,
        seed_strategy=seed_strategy
    )
    if result.get('success'):
        OPS_MODE['mode'] = 'crawl'
        OPS_MODE['crawl_strategy'] = strategy
        OPS_MODE['seed_strategy'] = seed_strategy
        OPS_MODE['last_changed_at'] = datetime.now().isoformat()
        _log_telemetry('wiki_crawl_start', {
            'domains': domains,
            'max_depth': max_depth,
            'max_pages': max_pages,
            'strategy': strategy,
            'seed_strategy': seed_strategy
        })
    return jsonify(result)


@app.route('/api/wiki-crawl/stop', methods=['POST'])
def wiki_crawl_stop():
    """Stop Wikipedia crawling."""
    guard = require_admin_token()
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    result = oxidus.stop_wiki_crawl()
    if result.get('success'):
        OPS_MODE['mode'] = 'chat'
        OPS_MODE['last_changed_at'] = datetime.now().isoformat()
        _log_telemetry('wiki_crawl_stop')
    return jsonify(result)


@app.route('/api/wiki-crawl/resume', methods=['POST'])
def wiki_crawl_resume():
    """Resume Wikipedia crawling from saved state."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('wiki_crawl_resume')
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    data = request.json or {}
    max_pages = data.get('max_pages')
    if max_pages is not None:
        max_pages = int(max_pages)

    result = oxidus.resume_wiki_crawl(max_pages=max_pages)
    if result.get('success'):
        OPS_MODE['mode'] = 'crawl'
        OPS_MODE['last_changed_at'] = datetime.now().isoformat()
        _log_telemetry('wiki_crawl_resume', {'max_pages': max_pages})
    return jsonify(result)


@app.route('/api/wiki-crawl/status', methods=['GET'])
def wiki_crawl_status():
    """Get Wikipedia crawler status."""
    guard = require_admin_token()
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    result = oxidus.wiki_crawl_status()
    return jsonify(result)


@app.route('/api/wiki-crawl/settings', methods=['GET', 'POST'])
def wiki_crawl_settings():
    """Get or update Wikipedia crawler settings."""
    guard = require_admin_token()
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    if request.method == 'GET':
        result = oxidus.wiki_crawl_settings()
        return jsonify(result)

    updates = request.json or {}
    guard = _block_if_safe_mode('wiki_crawl_settings_update')
    if guard:
        return guard
    result = oxidus.update_wiki_crawl_settings(updates)
    if result.get('success'):
        _log_telemetry('wiki_crawl_settings_update', {'updates': updates})
    return jsonify(result)


@app.route('/api/wiki-crawl/settings/reset', methods=['POST'])
def wiki_crawl_settings_reset():
    """Reset Wikipedia crawler settings to defaults."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('wiki_crawl_settings_reset')
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    result = oxidus.reset_wiki_crawl_settings()
    if result.get('success'):
        _log_telemetry('wiki_crawl_settings_reset')
    return jsonify(result)


@app.route('/api/admin/telemetry/recent', methods=['GET'])
def admin_telemetry_recent():
    """Fetch recent admin telemetry entries."""
    guard = require_admin_token()
    if guard:
        return guard

    try:
        limit = int(request.args.get('limit', 60))
    except ValueError:
        limit = 60
    limit = max(1, min(limit, 200))

    if not TELEMETRY_LOG.exists():
        return jsonify({'entries': []})

    entries = []
    try:
        with open(TELEMETRY_LOG, 'r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return jsonify({'error': 'Unable to read telemetry log'}), 500

    return jsonify({'entries': entries[-limit:]})


@app.route('/api/admin/validate-e2e', methods=['POST'])
def admin_validate_e2e():
    """Run end-to-end validation checks (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    result = _run_e2e_validation()
    _log_telemetry('e2e_validation', {'success': result.get('success')})
    return jsonify(result)


@app.route('/api/ops/mode', methods=['GET', 'POST'])
def ops_mode():
    """Get or set operations mode (chat, study, crawl)."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    if request.method == 'GET':
        return jsonify({
            'mode': OPS_MODE.get('mode'),
            'crawl_strategy': OPS_MODE.get('crawl_strategy'),
            'seed_strategy': OPS_MODE.get('seed_strategy'),
            'last_changed_at': OPS_MODE.get('last_changed_at'),
            'study_status': STUDY_STATUS
        })

    payload = request.json or {}
    mode = (payload.get('mode') or 'chat').strip().lower()
    if mode not in {'chat', 'study', 'crawl'}:
        return jsonify({'error': 'Invalid mode'}), 400

    if SAFE_MODE.get('active') and mode == 'crawl':
        return jsonify({'error': 'Safe mode enabled. Crawl mode blocked.'}), 423

    OPS_MODE['mode'] = mode
    OPS_MODE['crawl_strategy'] = (payload.get('crawl_strategy') or OPS_MODE['crawl_strategy']).strip().lower()
    OPS_MODE['seed_strategy'] = (payload.get('seed_strategy') or OPS_MODE['seed_strategy']).strip().lower()
    OPS_MODE['last_changed_at'] = datetime.now().isoformat()
    _log_telemetry('ops_mode_set', {
        'mode': OPS_MODE['mode'],
        'crawl_strategy': OPS_MODE['crawl_strategy'],
        'seed_strategy': OPS_MODE['seed_strategy']
    })

    result = {'success': True, 'mode': OPS_MODE['mode']}
    if mode == 'study':
        result['study'] = _run_study_sweep()
    elif mode == 'crawl':
        domains = payload.get('domains') or []
        max_depth = int(payload.get('max_depth', 2))
        max_pages = payload.get('max_pages')
        if max_pages is not None:
            max_pages = int(max_pages)
        if domains:
            crawl_result = oxidus.start_wiki_crawl(
                domains=domains,
                max_depth=max_depth,
                max_pages=max_pages,
                strategy=OPS_MODE['crawl_strategy'],
                seed_strategy=OPS_MODE['seed_strategy']
            )
            result['crawl'] = crawl_result
        else:
            result['crawl'] = {'success': False, 'error': 'No domains provided'}

    return jsonify(result)


@app.route('/api/admin/status', methods=['GET'])
def admin_status():
    """Get admin status overview."""
    guard = require_admin_token()
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    health_report = _build_health_report(include_admin=True)

    crawler = oxidus.wiki_crawl_status()
    try:
        health = (crawler or {}).get('health') or {}
        last_restart = health.get('last_watchdog_restart_at')
        global LAST_WATCHDOG_RESTART_AT
        if last_restart and last_restart != LAST_WATCHDOG_RESTART_AT:
            _log_telemetry('watchdog_restarted', {
                'restarts': health.get('watchdog_restart_count'),
                'last_watchdog_restart_at': last_restart
            })
            LAST_WATCHDOG_RESTART_AT = last_restart
    except Exception:
        pass
    lm_status = None
    try:
        from src.utils.lm_studio_client import get_lm_studio_client
        client = get_lm_studio_client()
        lm_status = {
            'available': client.is_available(),
            'model': client.model,
            'primary_model': client.primary_model,
            'secondary_model': client.secondary_model
        }
    except Exception:
        lm_status = {'available': False}

    knowledge_sources = 0
    knowledge_loose_ends = {}
    if oxidus.knowledge_organizer:
        knowledge_sources = len(oxidus.knowledge_organizer.scraped_sources)
        try:
            knowledge_loose_ends = oxidus.knowledge_organizer.get_loose_ends_report()
        except Exception as exc:
            _log_telemetry('error', {'operation': 'get_loose_ends', 'error_type': type(exc).__name__})
            knowledge_loose_ends = {}

    return jsonify({
        'chat_style': oxidus.get_chat_style(),
        'autonomy_enabled': bool(getattr(oxidus, 'autonomous_thinking_enabled', False)),
        'crawler': crawler,
        'lm_studio': lm_status,
        'knowledge_sources': knowledge_sources,
        'knowledge': {
            'loose_ends': knowledge_loose_ends
        },
        'conversation_messages': len(conversation_history),
        'last_maintenance': LAST_MAINTENANCE_RESULT,
        'memryx': get_memryx_status(),
        'indexing': health_report.get('indexing') or {},
        'safe_mode': health_report.get('safe_mode'),
        'alerts': health_report.get('alerts') or []
    })


def _run_e2e_validation() -> dict:
    checks = []

    def add_check(name: str, ok: bool, detail: Optional[str] = None):
        checks.append({'check': name, 'ok': ok, 'detail': detail})

    if not oxidus:
        add_check('oxidus_initialized', False, 'Oxidus not initialized')
        return {'success': False, 'checks': checks}

    add_check('oxidus_initialized', True)
    add_check('knowledge_organizer', bool(oxidus.knowledge_organizer))
    add_check('memory_index', bool(oxidus.memory_index))
    add_check('wikipedia_api', bool(getattr(oxidus, 'wikipedia', None)))
    add_check('wiki_crawler', bool(getattr(oxidus, 'wikipedia_crawler', None)))

    try:
        status = oxidus.wiki_crawl_status()
        add_check('wiki_crawl_status', status.get('success', False), status.get('error'))
    except Exception as exc:
        _log_telemetry('error', {'operation': 'wiki_crawl_status', 'error_type': type(exc).__name__})
        add_check('wiki_crawl_status', False, 'Failed to check wiki crawl status')

    try:
        settings = oxidus.wiki_crawl_settings()
        add_check('wiki_crawl_settings', settings.get('success', False), settings.get('error'))
    except Exception as exc:
        _log_telemetry('error', {'operation': 'wiki_crawl_settings', 'error_type': type(exc).__name__})
        add_check('wiki_crawl_settings', False, 'Failed to check wiki crawl settings')

    try:
        summary = _build_ops_summary(include_admin=False)
        ok = bool(summary.get('knowledge', {}).get('available'))
        add_check('ops_summary', ok, None if ok else 'knowledge summary unavailable')
    except Exception as exc:
        _log_telemetry('error', {'operation': 'ops_summary', 'error_type': type(exc).__name__})
        add_check('ops_summary', False, 'Failed to check operations summary')

    return {
        'success': all(item['ok'] for item in checks),
        'checks': checks
    }


def _build_ops_summary(include_admin: bool = False) -> dict:
    summary = oxidus.thought_stream.get_thinking_summary() if oxidus else {}

    lm_status = {'available': False}
    try:
        from src.utils.lm_studio_client import get_lm_studio_client
        client = get_lm_studio_client()
        lm_status = {
            'available': client.is_available(),
            'model': client.model,
            'primary_model': client.primary_model,
            'secondary_model': client.secondary_model
        }
    except Exception:
        lm_status = {'available': False}

    memryx_status = get_memryx_status()
    memryx_devices = {
        'device_ids': [],
        'source': 'unknown',
        'errors': []
    }
    if include_admin:
        memryx_devices = get_memryx_devices()

    knowledge_summary = {
        'available': False,
        'metrics': {},
        'coverage': {},
        'pipeline': {},
        'pipeline_health': {},
        'notes': {},
        'loose_ends': {},
        'governance': _load_kb_governance_summary()
    }

    if oxidus and oxidus.knowledge_organizer:
        try:
            organizer = oxidus.knowledge_organizer
            pipeline = organizer.get_pipeline_summary()
            total_sources = pipeline.get('total_sources') or 0
            pipeline_health = {}
            if total_sources:
                pipeline_health = {
                    'concepts_extracted_pct': round((pipeline.get('concepts_extracted', 0) / total_sources) * 100, 1),
                    'values_mapped_pct': round((pipeline.get('values_mapped', 0) / total_sources) * 100, 1),
                    'summaries_generated_pct': round((pipeline.get('summaries_generated', 0) / total_sources) * 100, 1),
                    'indexed_pct': round((pipeline.get('indexed', 0) / total_sources) * 100, 1)
                }

            loose_ends = organizer.get_loose_ends_report()
            coverage = organizer.get_coverage_report()
            freshness = organizer.get_freshness_report()
            knowledge_summary = {
                'available': True,
                'metrics': {
                    'total_sources': len(organizer.scraped_sources),
                    'total_concepts': len(organizer.concept_index)
                },
                'coverage': coverage,
                'freshness': freshness,
                'pipeline': pipeline,
                'pipeline_health': pipeline_health,
                'notes': {
                    'total': len(organizer.list_notes()),
                    'open': len(organizer.list_notes(status='open'))
                },
                'loose_ends': {
                    'open_threads': (loose_ends.get('open_threads') or [])[:8],
                    'underexplored_values': (loose_ends.get('underexplored_values') or [])[:8],
                    'review_queue': (loose_ends.get('review_queue') or [])[:6]
                },
                'governance': _load_kb_governance_summary()
            }
        except Exception:
            knowledge_summary = {
                'available': True,
                'metrics': {},
                'coverage': {},
                'freshness': {},
                'pipeline': {},
                'pipeline_health': {},
                'notes': {},
                'loose_ends': {},
                'governance': _load_kb_governance_summary()
            }

    if include_admin:
        freshness = knowledge_summary.get('freshness') or {}
        global_freshness = freshness.get('global') or {}
        domain_freshness = freshness.get('domains') or {}
        stale_domains = sorted(
            [
                {'domain': domain, 'age_hours': data.get('age_hours')}
                for domain, data in domain_freshness.items()
                if data.get('age_hours') is not None
            ],
            key=lambda item: item.get('age_hours', 0),
            reverse=True
        )[:5]
        _maybe_record_snapshot('freshness_snapshot', 'freshness_snapshot', {
            'global_age_hours': global_freshness.get('age_hours'),
            'global_last_ingest_at': global_freshness.get('last_ingest_at'),
            'stale_domains': stale_domains,
            'domain_count': len(domain_freshness)
        })

        index_meta = _load_index_meta()
        staleness = _compute_index_staleness(index_meta)
        _maybe_record_snapshot('index_staleness_snapshot', 'index_staleness_snapshot', {
            'staleness_hours': staleness.get('staleness_hours'),
            'indexed_at_utc': staleness.get('indexed_at_utc')
        })

    payload = {
        'thoughts': {
            'total_thoughts': summary.get('total_thoughts', 0),
            'questions': summary.get('total_questions', 0),
            'decisions': summary.get('total_decisions', 0),
            'ethical_checks': summary.get('ethical_checks', 0),
            'insights': summary.get('insights_gained', 0)
        },
        'lm_studio': lm_status,
        'memryx': {
            'status': memryx_status,
            'devices': {
                'device_ids': memryx_devices.get('device_ids', []),
                'source': memryx_devices.get('source'),
                'errors': memryx_devices.get('errors', [])
            }
        },
        'knowledge': knowledge_summary,
        'ops_mode': {
            'mode': OPS_MODE.get('mode'),
            'crawl_strategy': OPS_MODE.get('crawl_strategy'),
            'seed_strategy': OPS_MODE.get('seed_strategy'),
            'last_changed_at': OPS_MODE.get('last_changed_at')
        },
        'reliability': {
            'slo': _load_reliability_slo(),
            'latency': _latency_stats(),
            'safe_mode': dict(SAFE_MODE),
            'alerts': _build_health_report(include_admin=False).get('alerts', []),
            'storage': _storage_health()
        },
        'timestamp': datetime.now().isoformat()
    }

    if include_admin:
        payload['memryx']['health'] = _build_memryx_health_report()
        payload['indexing_metrics'] = _build_indexing_metrics()
        payload['tiering'] = _get_cached(
            _cache_key('tiering_overview'),
            15.0,
            lambda: _build_tiering_overview(max_candidates=50)
        )

    return payload


@app.route('/api/ops/summary', methods=['GET'])
def ops_summary():
    """Get streamlined operations summary for the main UI."""
    try:
        if not oxidus:
            return jsonify({'error': 'Oxidus not initialized'})

        summary = _get_cached(_cache_key('ops_summary'), 3.0, lambda: _build_ops_summary(include_admin=False))
        return jsonify(summary)
    except Exception as exc:
        _log_telemetry('error', {'operation': 'ops_summary', 'error_type': type(exc).__name__})
        return jsonify({'error': 'Failed to retrieve operations summary'}), 500


@app.route('/api/admin/ops/summary', methods=['GET'])
def admin_ops_summary():
    """Get streamlined operations summary for the admin UI."""
    guard = require_admin_token()
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    summary = _get_cached(_cache_key('admin_ops_summary'), 4.0, lambda: _build_ops_summary(include_admin=True))
    return jsonify(summary)


@app.route('/api/admin/integrity', methods=['GET'])
def admin_integrity():
    """Run integrity checks for scripts, directories, and components."""
    guard = require_admin_token()
    if guard:
        return guard

    report = build_integrity_report()
    return jsonify(report)


@app.route('/api/admin/clear-conversation', methods=['POST'])
def admin_clear_conversation():
    """Clear conversation via admin control."""
    guard = require_admin_token()
    if guard:
        return guard
    return clear_conversation()


@app.route('/api/admin/conversation', methods=['GET'])
def admin_conversation_log():
    """Get recent conversation entries for admin review."""
    guard = require_admin_token()
    if guard:
        return guard

    try:
        limit = int(request.args.get('limit', 80))
    except ValueError:
        limit = 80
    limit = max(1, min(limit, 300))

    entries = conversation_history[-limit:]
    formatted = []
    for entry in entries:
        formatted.append({
            'speaker': entry.get('speaker', 'UNKNOWN'),
            'message': entry.get('message', ''),
            'timestamp': entry.get('timestamp'),
            'documented': bool(entry.get('documented'))
        })

    return jsonify({
        'count': len(formatted),
        'entries': formatted
    })


@app.route('/api/admin/stop-autonomy', methods=['POST'])
def admin_stop_autonomy():
    """Stop Oxidus's autonomous thinking loop (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    try:
        oxidus.autonomous_thinking_enabled = False
        # Attempt to join the thread if it exists and is alive
        t = getattr(oxidus, 'autonomous_thread', None)
        if t and t.is_alive():
            try:
                # give it a moment to exit
                t.join(timeout=1)
            except Exception:
                pass

        oxidus.thought_stream.add_thought(ThoughtType.DECISION, 'Autonomy disabled by admin')
        _log_telemetry('autonomy_disabled')
        return jsonify({'success': True, 'message': 'Autonomous thinking disabled'})
    except Exception as exc:
        return _handle_api_error(exc, 'stop_autonomy')


@app.route('/api/admin/reset-knowledge', methods=['POST'])
def admin_reset_knowledge():
    """Reset organized knowledge and wipe wiki corpus on disk."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('admin_reset_knowledge')
    if guard:
        return guard
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    result = oxidus.reset_knowledge_organizer()
    corpus_dir = Path(__file__).parent / 'data' / 'knowledge_base' / 'wiki_corpus'
    if corpus_dir.exists():
        for entry in corpus_dir.iterdir():
            try:
                if entry.is_file():
                    entry.unlink()
                elif entry.is_dir():
                    shutil.rmtree(entry)
            except Exception:
                pass

    _log_telemetry('knowledge_reset')
    return jsonify(result)


@app.route('/api/admin/knowledge/dedupe', methods=['POST'])
def admin_knowledge_dedupe():
    """Dedupe and reindex knowledge sources (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('admin_knowledge_dedupe')
    if guard:
        return guard
    if not oxidus or not oxidus.knowledge_organizer:
        return jsonify({'success': False, 'error': 'Knowledge organizer not available'}), 400

    try:
        result = oxidus.knowledge_organizer.dedupe_sources()
    except Exception as exc:
        return _handle_api_error(exc, 'deduplicate_sources')

    _log_telemetry('knowledge_dedupe', {
        'removed_duplicates': result.get('removed_duplicates'),
        'total_sources': result.get('total_sources')
    })
    return jsonify({'success': True, 'result': result})


@app.route('/api/admin/knowledge/rebuild-dedupe', methods=['POST'])
def admin_knowledge_rebuild_dedupe():
    """Rebuild knowledge index from disk, then dedupe/reindex (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('admin_knowledge_rebuild_dedupe')
    if guard:
        return guard
    if not oxidus or not oxidus.knowledge_organizer:
        return jsonify({'success': False, 'error': 'Knowledge organizer not available'}), 400

    rebuild_result = {}
    try:
        rebuild_result = oxidus.rebuild_knowledge_index()
    except Exception as exc:
        return _handle_api_error(exc, 'rebuild_knowledge_index')

    try:
        dedupe_result = oxidus.knowledge_organizer.dedupe_sources()
    except Exception as exc:
        return _handle_api_error(exc, 'dedupe_sources')

    _log_telemetry('knowledge_rebuild_dedupe', {
        'rebuild': rebuild_result,
        'dedupe': dedupe_result
    })
    return jsonify({
        'success': True,
        'rebuild': rebuild_result,
        'dedupe': dedupe_result
    })


@app.route('/api/admin/notes', methods=['GET', 'POST'])
def admin_notes():
    """Create or list structured notes (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    if not oxidus or not oxidus.knowledge_organizer:
        return jsonify({'error': 'Knowledge organizer not available'})

    if request.method == 'GET':
        status = request.args.get('status')
        return jsonify({'notes': oxidus.knowledge_organizer.list_notes(status=status)})

    data = request.json or {}
    note = oxidus.knowledge_organizer.add_note(
        topic=data.get('topic', ''),
        summary=data.get('summary', ''),
        questions=data.get('questions') or [],
        action_items=data.get('action_items') or [],
        sources=data.get('sources') or [],
        status=data.get('status', 'open')
    )
    return jsonify({'success': True, 'note': note})


@app.route('/api/admin/notes/review', methods=['POST'])
def admin_review_note():
    """Mark a note as reviewed (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    if not oxidus or not oxidus.knowledge_organizer:
        return jsonify({'error': 'Knowledge organizer not available'})

    data = request.json or {}
    note_id = data.get('note_id')
    if not note_id:
        return jsonify({'error': 'note_id required'}), 400

    note = oxidus.knowledge_organizer.review_note(note_id)
    if not note:
        return jsonify({'error': 'Note not found'}), 404

    return jsonify({'success': True, 'note': note})


@app.route('/api/admin/knowledge-config', methods=['GET', 'POST'])
def admin_knowledge_config():
    """Get or update knowledge relevance/retention settings (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    if not oxidus or not oxidus.knowledge_organizer:
        return jsonify({'error': 'Knowledge organizer not available'})

    if request.method == 'GET':
        return jsonify({
            'relevance': oxidus.knowledge_organizer.relevance,
            'retention': oxidus.knowledge_organizer.retention,
            'coverage_targets': oxidus.knowledge_organizer.coverage_targets,
            'quality_thresholds': oxidus.knowledge_organizer.quality_thresholds
        })

    data = request.json or {}
    guard = _block_if_safe_mode('admin_knowledge_config_update')
    if guard:
        return guard
    relevance = data.get('relevance', {})
    retention = data.get('retention', {})
    coverage_targets = data.get('coverage_targets')
    quality_thresholds = data.get('quality_thresholds')

    updated_relevance = oxidus.knowledge_organizer.set_relevance_config(
        min_content_len=relevance.get('min_content_len'),
        min_concepts=relevance.get('min_concepts'),
        min_value_hits=relevance.get('min_value_hits'),
        strict=relevance.get('strict'),
        lm_gate_enabled=relevance.get('lm_gate_enabled'),
        lm_gate_min_score=relevance.get('lm_gate_min_score'),
        lm_gate_required=relevance.get('lm_gate_required')
    )
    updated_retention = oxidus.knowledge_organizer.set_retention_config(
        interval_days=retention.get('interval_days')
    )
    updated_targets = oxidus.knowledge_organizer.set_coverage_targets(coverage_targets)
    updated_thresholds = oxidus.knowledge_organizer.set_quality_thresholds(quality_thresholds)

    return jsonify({
        'success': True,
        'relevance': updated_relevance,
        'retention': updated_retention,
        'coverage_targets': updated_targets,
        'quality_thresholds': updated_thresholds
    })


@app.route('/api/admin/learning-trace', methods=['GET'])
def admin_learning_trace():
    """Return the most recent learning trace from ingestion."""
    guard = require_admin_token()
    if guard:
        return guard

    try:
        if not oxidus or not oxidus.knowledge_organizer:
            return jsonify({'success': False, 'error': 'Knowledge organizer not available'}), 400

        trace = oxidus.knowledge_organizer.get_learning_trace() or {}
        return jsonify({'success': True, 'trace': trace})
    except Exception as exc:
        return _handle_api_error(exc, 'learning_trace')


@app.route('/api/admin/moltbook/ingest', methods=['POST'])
def admin_moltbook_ingest():
    """Trigger a manual Moltbook ingest cycle."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('admin_moltbook_ingest')
    if guard:
        return guard

    if not oxidus:
        return jsonify({'success': False, 'error': 'Oxidus not initialized'}), 400

    if not getattr(oxidus, 'moltbook', None):
        return jsonify({'success': False, 'error': 'Moltbook client not available'}), 400

    if not getattr(oxidus, 'knowledge_organizer', None):
        return jsonify({'success': False, 'error': 'Knowledge organizer not available'}), 400

    try:
        oxidus._moltbook_ingest_once()
    except Exception as exc:
        _enter_safe_mode(f"Moltbook ingest error: {type(exc).__name__}", 'moltbook_ingest')
        return _handle_api_error(exc, 'moltbook_ingest')

    return jsonify({'success': True, 'message': 'Moltbook ingest complete.'})


def _knowledge_base_root() -> Path:
    return Path(__file__).parent / 'data' / 'knowledge_base'


def _relative_kb_path(path: Path) -> str:
    """Convert an absolute path to a relative knowledge base path. Returns sanitized path."""
    kb_root = _knowledge_base_root().resolve()
    try:
        # Only return relative path if it's actually within the knowledge base
        resolved_path = path.resolve()
        if _is_path_safe(resolved_path, kb_root):
            relative = str(resolved_path.relative_to(kb_root))
            return relative.replace('\\', '/')
        else:
            # Path is outside knowledge base - return generic indicator
            return 'external'
    except (ValueError, OSError):
        # If path resolution fails, return generic indicator
        return 'invalid'


def _hot_index_roots() -> list:
    kb_root = _knowledge_base_root()
    return [
        kb_root / 'normalized_deeper' / 'sorted',
        kb_root / 'wiki_corpus',
        kb_root / 'notes'
    ]


def _load_policy(path: Path, defaults: dict) -> dict:
    if not path.exists():
        return dict(defaults)
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return dict(defaults)
    if not isinstance(payload, dict):
        return dict(defaults)
    merged = dict(defaults)
    merged.update({key: value for key, value in payload.items() if value is not None})
    return merged


def _load_tiering_policy() -> dict:
    defaults = {
        'hot_access_count': 5,
        'hot_access_days': 30,
        'warm_access_count': 2,
        'warm_access_days': 60,
        'max_candidates': 200
    }
    return _load_policy(TIERING_POLICY_PATH, defaults)


def _load_retention_policy() -> dict:
    defaults = {
        'no_access_days': 180,
        'min_age_days': 180,
        'max_candidates': 200,
        'eligible_roots': [
            'normalized_deeper/sorted',
            'wiki_corpus',
            'notes'
        ],
        'exclude_paths': [
            'metadata',
            'index'
        ]
    }
    return _load_policy(RETENTION_POLICY_PATH, defaults)


def _load_archival_policy() -> dict:
    defaults = {
        'archive_root': str(Path(__file__).parent / 'retired' / 'data' / 'knowledge_base' / 'archives'),
        'max_per_run': 200,
        'dry_run_default': True
    }
    return _load_policy(ARCHIVAL_POLICY_PATH, defaults)


def _build_index_priority_paths(limit: int = 100) -> list:
    kb_root = _knowledge_base_root().resolve()
    paths = []
    for root in _hot_index_roots():
        if root.exists():
            paths.append(str(root.resolve()))

    heat = _load_access_heat()
    heat_paths = heat.get('paths') or {}
    ranked = sorted(
        heat_paths.items(),
        key=lambda item: int((item[1] or {}).get('count', 0) or 0),
        reverse=True
    )
    for rel_path, entry in ranked[:limit]:
        if not rel_path:
            continue
        candidate = _resolve_relative_path_under_base(str(rel_path), kb_root)
        if candidate and candidate.exists():
            paths.append(str(candidate))

    seen = set()
    deduped = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _parse_iso_utc(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _days_since(value: Optional[datetime]) -> Optional[float]:
    if not value:
        return None
    try:
        delta = datetime.utcnow() - value.replace(tzinfo=None)
    except Exception:
        return None
    return round(delta.total_seconds() / 86400, 2)


def _iter_kb_files(roots: Optional[list] = None, max_files: Optional[int] = None) -> list:
    kb_root = _knowledge_base_root().resolve()
    resolved_roots = []
    if roots:
        for rel in roots:
            # Validate that the relative path doesn't escape kb_root
            if not isinstance(rel, str):
                continue
            constructed = _resolve_relative_path_under_base(str(rel), kb_root)
            if constructed and _is_path_safe(constructed, kb_root):
                resolved_roots.append(constructed)
    else:
        resolved_roots = [kb_root]

    files = []
    for root in resolved_roots:
        if not root.exists():
            continue
        for ext in ('.json', '.md'):
            for path in root.rglob(f'*{ext}'):
                if not path.is_file():
                    continue
                # Validate each file is within kb_root
                if not _is_path_safe(path, kb_root):
                    continue
                files.append(path)
                if max_files and len(files) >= max_files:
                    return files
    return files


def _build_tiering_overview(max_candidates: Optional[int] = None) -> dict:
    policy = _load_tiering_policy()
    retention = _load_retention_policy()
    max_candidates = max_candidates or int(policy.get('max_candidates', 200))

    heat = _load_access_heat()
    heat_paths = heat.get('paths') or {}

    hot_roots = _hot_index_roots()
    hot_root_set = {str(root.resolve()) for root in hot_roots}

    def _tier_for_path(path: Path) -> str:
        for root in hot_roots:
            try:
                path.resolve().relative_to(root.resolve())
                return 'hot'
            except Exception:
                continue
        return 'cold'

    promote = []
    demote = []
    tier_counts = {'hot': 0, 'cold': 0}

    candidates = _iter_kb_files(roots=retention.get('eligible_roots'))
    for path in candidates:
        relative = _relative_kb_path(path)
        entry = heat_paths.get(relative) or {}
        access_count = int(entry.get('count', 0) or 0)
        last_access = _parse_iso_utc(entry.get('last_access_utc'))
        access_age_days = _days_since(last_access)
        tier = _tier_for_path(path)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        if tier == 'cold':
            if access_count >= policy.get('hot_access_count', 0):
                if access_age_days is None or access_age_days <= policy.get('hot_access_days', 0):
                    promote.append({
                        'path': relative,
                        'access_count': access_count,
                        'last_access_utc': entry.get('last_access_utc')
                    })
        if tier == 'hot':
            no_access_days = retention.get('no_access_days')
            if access_age_days is not None and no_access_days is not None:
                if access_age_days >= float(no_access_days):
                    demote.append({
                        'path': relative,
                        'access_count': access_count,
                        'last_access_utc': entry.get('last_access_utc')
                    })

        if len(promote) >= max_candidates and len(demote) >= max_candidates:
            break

    return {
        'policy': policy,
        'retention': retention,
        'tier_counts': tier_counts,
        'promote_candidates': promote[:max_candidates],
        'demote_candidates': demote[:max_candidates]
    }


def _load_archive_manifest() -> dict:
    if not ARCHIVE_MANIFEST_PATH.exists():
        return {'entries': []}
    try:
        payload = json.loads(ARCHIVE_MANIFEST_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {'entries': []}
    if not isinstance(payload, dict):
        return {'entries': []}
    if 'entries' not in payload or not isinstance(payload.get('entries'), list):
        payload['entries'] = []
    return payload


def _save_archive_manifest(payload: dict) -> None:
    try:
        ARCHIVE_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = ARCHIVE_MANIFEST_PATH.with_suffix('.json.tmp')
        with tmp_path.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
        tmp_path.replace(ARCHIVE_MANIFEST_PATH)
    except Exception:
        pass


def _compute_archival_candidates(max_candidates: Optional[int] = None) -> list:
    retention = _load_retention_policy()
    heat = _load_access_heat()
    heat_paths = heat.get('paths') or {}

    max_candidates = max_candidates or int(retention.get('max_candidates', 200))
    no_access_days = float(retention.get('no_access_days', 180))
    min_age_days = float(retention.get('min_age_days', 180))

    candidates = []
    for path in _iter_kb_files(roots=retention.get('eligible_roots')):
        relative = _relative_kb_path(path)
        excluded = any(relative.startswith(prefix) for prefix in retention.get('exclude_paths', []))
        if excluded:
            continue
        entry = heat_paths.get(relative) or {}
        last_access = _parse_iso_utc(entry.get('last_access_utc'))
        access_age_days = _days_since(last_access)
        if access_age_days is not None and access_age_days < no_access_days:
            continue
        age_days = _days_since(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
        if age_days is not None and age_days < min_age_days:
            continue

        candidates.append({
            'path': relative,
            'access_count': int(entry.get('count', 0) or 0),
            'last_access_utc': entry.get('last_access_utc'),
            'age_days': age_days
        })
        if len(candidates) >= max_candidates:
            break

    return candidates


def _recent_knowledge_files(limit: int = 8) -> list:
    kb_root = _knowledge_base_root()
    roots = [
        kb_root / 'wiki_corpus',
        kb_root / 'normalized_deeper' / 'sorted',
        kb_root / 'notes'
    ]
    files = []
    for root in roots:
        if not root.exists():
            continue
        for ext in ('.json', '.md'):
            for path in root.rglob(f'*{ext}'):
                try:
                    stat = path.stat()
                except Exception:
                    continue
                files.append((stat.st_mtime, path, stat.st_size))

    files.sort(key=lambda item: item[0], reverse=True)
    recent = []
    for mtime, path, size in files[:limit]:
        # Validate path is within knowledge base before returning
        if not _is_path_safe(path, kb_root):
            continue
        try:
            relative = str(path.relative_to(kb_root))
        except Exception:
            # If relative_to fails, skip this file
            continue
        recent.append({
            'path': relative,  # Only return relative paths to client
            'relative': relative,
            'name': path.name,
            'mtime': mtime,
            'size': size
        })
    return recent


@app.route('/api/files/recent', methods=['GET'])
def recent_files():
    limit = int(request.args.get('limit', 8))
    limit = max(1, min(limit, 50))
    return jsonify({'success': True, 'files': _recent_knowledge_files(limit=limit)})


@app.route('/api/files/open', methods=['POST'])
def open_file():
    data = request.json or {}
    path_raw = (data.get('path') or '').strip()
    if not path_raw:
        return jsonify({'success': False, 'error': 'path required'}), 400

    kb_root = _knowledge_base_root().resolve()
    path = _resolve_path_under_base(path_raw, kb_root)
    if not path:
        return jsonify({'success': False, 'error': 'path not allowed'}), 403

    if not path.exists():
        return jsonify({'success': False, 'error': 'file not found'}), 404

    _record_access_signal('file_open', paths=[_relative_kb_path(path)])

    try:
        if sys.platform == 'win32':
            # os.startfile is safe on Windows - doesn't use shell
            # path is already validated and resolved
            os.startfile(str(path))
        elif sys.platform == 'darwin':
            # Explicitly disable shell to prevent command injection
            subprocess.Popen(['open', str(path)], shell=False)
        else:
            # Explicitly disable shell to prevent command injection
            subprocess.Popen(['xdg-open', str(path)], shell=False)
    except Exception as exc:
        _log_telemetry('error', {'operation': 'open_file', 'error_type': type(exc).__name__})
        return jsonify({'error': 'Failed to open file'}), 500

    return jsonify({'success': True})


@app.route('/api/admin/rebuild-knowledge', methods=['POST'])
def admin_rebuild_knowledge():
    """Rebuild knowledge index from disk (texts -> organizer -> memory index)."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('admin_rebuild_knowledge')
    if guard:
        return guard

    try:
        if not oxidus:
            return jsonify({'error': 'Oxidus not initialized'})
        result = oxidus.rebuild_knowledge_index()
        _log_telemetry('knowledge_rebuild')
        _invalidate_cache('ops_summary')
        _invalidate_cache('admin_ops_summary')
        _warm_ops_cache()
        return jsonify(result)
    except Exception as exc:
        return _handle_api_error(exc, 'rebuild_knowledge')
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    result = {}
    try:
        result = oxidus.rebuild_knowledge_index()
    except Exception as exc:
        return _handle_api_error(exc, 'rebuild_knowledge')

    if result.get('success'):
        _invalidate_cache('ops_summary')
        _invalidate_cache('admin_ops_summary')
        _invalidate_cache('tiering_overview')
        _warm_ops_cache()

    return jsonify(result)


@app.route('/api/admin/cleanup-external', methods=['POST'])
def admin_cleanup_external_sources():
    """Cleanup external scraped sources from disk (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('admin_cleanup_external_sources')
    if guard:
        return guard

    try:
        data = request.json or {}
        include_retired = bool(data.get('include_retired', False))
        dry_run = bool(data.get('dry_run', True))
        confirm = bool(data.get('confirm', False))

        if not dry_run and not confirm:
            return jsonify({'success': False, 'error': 'Confirmation required for destructive cleanup'}), 400

        result = cleanup_external_sources(include_retired=include_retired, dry_run=dry_run)
        result['success'] = True
        return jsonify(result)
    except Exception as exc:
        return _handle_api_error(exc, 'cleanup_external')


@app.route('/api/admin/maintenance/run', methods=['POST'])
def admin_run_maintenance():
    """Run maintenance tasks (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('admin_run_maintenance')
    if guard:
        return guard

    data = request.json or {}
    task = data.get('task')
    result = run_maintenance_task(task, data)
    if result.get('success'):
        _invalidate_cache('ops_summary')
        _invalidate_cache('admin_ops_summary')
        _invalidate_cache('tiering_overview')
        _warm_ops_cache()
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@app.route('/api/admin/memryx/benchmark', methods=['POST'])
def admin_memryx_benchmark():
    """Run MemryX benchmark hello to verify devices."""
    guard = require_admin_token()
    if guard:
        return guard

    memryx_root = Path(os.environ.get('MEMRYX_HOME', r'C:/Program Files/MemryX'))
    mx_bench_path = shutil.which('mx_bench')
    accl_bench_cmd = None
    if sys.platform == 'win32':
        candidate = memryx_root / 'acclBench' / 'acclBench.exe'
        accl_bench_cmd = str(candidate) if candidate.exists() else None
    else:
        accl_bench_cmd = shutil.which('acclBench')

    if mx_bench_path:
        cmd = [mx_bench_path, '--hello']
    elif accl_bench_cmd:
        cmd = [accl_bench_cmd, '--hello']
    else:
        return jsonify({'success': False, 'error': 'mx_bench or acclBench not found'}), 400
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return jsonify({
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        })
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'mx_bench/acclBench not found'}), 400
    except Exception as exc:
        return _handle_api_error(exc, 'memryx_benchmark')


def _build_memryx_health_report() -> dict:
    status = get_memryx_status()
    devices = get_memryx_devices()
    diagnostics = devices.get('diagnostics') or {}
    hints = []

    if not status.get('installed'):
        hints.append('MemryX not detected on this Windows host. Install the Windows SDK/runtime or set MEMRYX_HOME.')
    if status.get('installed') and not status.get('module_importable'):
        hints.append('Python binding not importable. Ensure MEMRYX_HOME/python is on PYTHONPATH or installed in this venv.')
    if not diagnostics.get('mx_bench_path') and diagnostics.get('accl_bench_exists') is False:
        hints.append('mx_bench not on PATH for this process (WSL installs are not visible to Windows).')
    if diagnostics.get('accl_bench_exists') is False:
        hints.append('acclBench.exe not found under MEMRYX_HOME/acclBench.')
    if not devices.get('device_ids'):
        hints.append('No devices detected. Check USB connection, driver install, and power.')

    return {
        'status': status,
        'devices': devices,
        'hints': hints,
        'generated_at': datetime.now().isoformat()
    }


def _hybrid_status() -> dict:
    memryx_root = Path(os.environ.get('MEMRYX_HOME', r'C:/Program Files/MemryX'))
    wsl_enabled = os.environ.get('OXIDUS_WSL_MX', '0').lower() in {'1', 'true', 'yes', 'on'}
    wsl_venv = os.environ.get('OXIDUS_WSL_MX_VENV', '$HOME/mx')

    wsl_available = False
    wsl_mx_nc = None
    if sys.platform == 'win32' and wsl_enabled:
        try:
            result = subprocess.run(
                ['wsl', '-e', 'bash', '-lc', 'true'],
                capture_output=True,
                text=True,
                timeout=5
            )
            wsl_available = result.returncode == 0
        except Exception:
            wsl_available = False

    if wsl_available:
        try:
            activate = f"source {wsl_venv}/bin/activate >/dev/null 2>&1 || true"
            cmd = f"{activate} && mx_nc --version"
            result = subprocess.run(
                ['wsl', '-e', 'bash', '-lc', cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                wsl_mx_nc = result.stdout.strip() or 'ok'
            else:
                wsl_mx_nc = result.stderr.strip() or 'not available'
        except Exception:
            wsl_mx_nc = 'error'

    accl_bench = memryx_root / 'acclBench' / 'acclBench.exe'
    mx_bench_path = shutil.which('mx_bench')

    return {
        'compile_mode': 'wsl' if wsl_enabled else 'windows',
        'wsl_enabled': wsl_enabled,
        'wsl_available': wsl_available,
        'wsl_venv': wsl_venv,
        'wsl_mx_nc': wsl_mx_nc,
        'memryx_home': str(memryx_root),
        'accl_bench': str(accl_bench) if accl_bench.exists() else '',
        'mx_bench_path': mx_bench_path or ''
    }


def _build_search_observability() -> dict:
    index_meta = _safe_load_json(MEMRYX_INDEX_DIR / 'index_meta.json') or {}
    staleness = _compute_index_staleness(index_meta)
    weights = _safe_load_json(Path(__file__).parent / 'data' / 'knowledge_base' / 'metadata' / 'search_weights.json') or {}
    tuning_set = _safe_load_json(Path(__file__).parent / 'data' / 'knowledge_base' / 'metadata' / 'search_tuning_set.json') or {}

    metadata_entries = _safe_load_json(MEMRYX_INDEX_DIR / 'metadata.json')
    entry_count = len(metadata_entries) if isinstance(metadata_entries, list) else 0

    return {
        'index_meta': index_meta,
        'index_entries': entry_count,
        'index_staleness_hours': staleness.get('staleness_hours'),
        'index_last_built_utc': staleness.get('indexed_at_utc'),
        'weights': weights.get('weights', {}),
        'tuning_cases': len((tuning_set.get('cases') or [])),
        'tuning_updated_utc': tuning_set.get('updated_utc')
    }


def _build_indexing_metrics() -> dict:
    index_meta = _load_index_meta()
    staleness = _compute_index_staleness(index_meta)
    return {
        'running': INDEXING_STATUS.get('running', False),
        'processed_batches': INDEXING_STATUS.get('processed_batches', 0),
        'total_batches': INDEXING_STATUS.get('total_batches', 0),
        'throughput_eps': INDEXING_STATUS.get('throughput_eps', 0.0),
        'avg_batch_ms': INDEXING_STATUS.get('avg_batch_ms', 0.0),
        'batch_delay_ms': INDEXING_STATUS.get('batch_delay_ms', 0),
        'last_error': INDEXING_STATUS.get('last_error'),
        'index_staleness_hours': staleness.get('staleness_hours'),
        'index_last_built_utc': staleness.get('indexed_at_utc')
    }


@app.route('/api/admin/memryx/health', methods=['GET'])
def admin_memryx_health():
    """Get MemryX health diagnostics for the admin UI."""
    guard = require_admin_token()
    if guard:
        return guard

    return jsonify(_build_memryx_health_report())


@app.route('/api/admin/hybrid-status', methods=['GET'])
def admin_hybrid_status():
    """Get hybrid compile/runtime status (WSL compile + Windows runtime)."""
    guard = require_admin_token()
    if guard:
        return guard

    return jsonify(_hybrid_status())


@app.route('/api/admin/search/overview', methods=['GET'])
def admin_search_overview():
    """Get hybrid search observability snapshot (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    snapshot = _build_search_observability()
    _log_telemetry('search_overview', {'index_entries': snapshot.get('index_entries', 0)})
    return jsonify(snapshot)


@app.route('/api/admin/access-heat', methods=['GET'])
def admin_access_heat():
    """Get access heat snapshot for tiering decisions (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    try:
        limit = int(request.args.get('limit', 50))
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 200))

    snapshot = _build_access_heat_snapshot(limit=limit)
    _log_telemetry('access_heat_snapshot', {'limit': limit})
    return jsonify(snapshot)


@app.route('/api/admin/cache/clear', methods=['POST'])
def admin_cache_clear():
    """Clear ops caches (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    data = request.json or {}
    prefix = (data.get('prefix') or '').strip() or None
    _invalidate_cache(prefix)
    _log_telemetry('cache_clear', {'prefix': prefix})
    return jsonify({'success': True, 'prefix': prefix})


@app.route('/api/admin/cache/warm', methods=['POST'])
def admin_cache_warm():
    """Warm ops caches (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    _warm_ops_cache()
    _log_telemetry('cache_warm')
    return jsonify({'success': True})


@app.route('/api/admin/tiering/overview', methods=['GET'])
def admin_tiering_overview():
    """Get tiering overview and candidate movements (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    try:
        limit = int(request.args.get('limit', 200))
    except ValueError:
        limit = 200
    limit = max(10, min(limit, 500))

    overview = _build_tiering_overview(max_candidates=limit)
    _log_telemetry('tiering_overview', {'limit': limit})
    return jsonify(overview)


def _is_path_safe(path: Path, base: Path) -> bool:
    """Verify that path is within the base directory (prevents path traversal)."""
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _resolve_path_under_base(raw_path: str, base: Path) -> Optional[Path]:
    """Resolve a user-provided path and ensure it remains under base."""
    if not isinstance(raw_path, str):
        return None
    candidate_text = raw_path.strip()
    if not candidate_text:
        return None
    try:
        candidate = Path(candidate_text).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        resolved = candidate.resolve()
        if not _is_path_safe(resolved, base):
            return None
        return resolved
    except (ValueError, OSError, RuntimeError):
        return None


def _resolve_relative_path_under_base(rel_path: str, base: Path) -> Optional[Path]:
    """Resolve a relative path safely under a base directory."""
    if not isinstance(rel_path, str):
        return None
    candidate_text = rel_path.strip()
    if not candidate_text:
        return None
    try:
        candidate = Path(candidate_text)
        if candidate.is_absolute() or any(part == '..' for part in candidate.parts):
            return None
        normalized = Path(*[part for part in candidate.parts if part not in {'', '.'}])
        if not normalized.parts:
            return None
        resolved = (base / normalized).resolve()
        if not _is_path_safe(resolved, base):
            return None
        return resolved
    except (ValueError, OSError, RuntimeError):
        return None


def _handle_api_error(exc: Exception, operation: str = 'operation') -> tuple:
    """Handle API errors safely: log details, return generic message to client."""
    _log_telemetry('api_error', {'operation': operation, 'error_type': type(exc).__name__})
    # Log the full exception for debugging but don't expose to client
    import traceback
    _log_indexing(f"Exception traceback: {traceback.format_exc()}")
    # Return generic error message to prevent information disclosure
    return jsonify({'success': False, 'error': f'Failed to complete {operation}'}), 500


def _archive_paths(paths: list, dry_run: bool = True, reason: str = 'retention_policy') -> dict:
    policy = _load_archival_policy()
    archive_root = Path(policy.get('archive_root') or '').expanduser()
    if not archive_root.is_absolute():
        archive_root = (Path(__file__).parent / archive_root).resolve()

    kb_root = _knowledge_base_root().resolve()
    manifest = _load_archive_manifest()
    entries = manifest.get('entries') or []
    now = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    moved = []
    skipped = []
    for rel_path in paths:
        if not rel_path:
            continue
        source = _resolve_relative_path_under_base(str(rel_path), kb_root)
        if not source:
            skipped.append({'path': rel_path, 'reason': 'invalid_path'})
            continue
        normalized_rel_path = source.relative_to(kb_root).as_posix()
        if not source.exists():
            skipped.append({'path': normalized_rel_path, 'reason': 'missing'})
            continue
        dest = _resolve_relative_path_under_base(normalized_rel_path, archive_root)
        if not dest:
            skipped.append({'path': normalized_rel_path, 'reason': 'invalid_path'})
            continue
        if dest.exists():
            skipped.append({'path': normalized_rel_path, 'reason': 'already_archived'})
            continue
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(dest))
        entry = {
            'original_relative': normalized_rel_path,
            'archived_relative': normalized_rel_path,
            'archived_at_utc': now,
            'reason': reason
        }
        entries.append(entry)
        moved.append(entry)

    if not dry_run:
        manifest['entries'] = entries
        _save_archive_manifest(manifest)

    return {
        'dry_run': dry_run,
        'archive_root': str(archive_root),
        'moved': moved,
        'skipped': skipped
    }


@app.route('/api/admin/archive/preview', methods=['GET'])
def admin_archive_preview():
    """Preview archival candidates based on retention policy (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    try:
        limit = int(request.args.get('limit', 200))
    except ValueError:
        limit = 200
    limit = max(10, min(limit, 500))

    candidates = _compute_archival_candidates(max_candidates=limit)
    _log_telemetry('archive_preview', {'limit': limit, 'count': len(candidates)})
    return jsonify({'candidates': candidates})


@app.route('/api/admin/archive/execute', methods=['POST'])
def admin_archive_execute():
    """Archive low-value content to cold storage (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    data = request.json or {}
    confirm = bool(data.get('confirm', False))
    dry_run = bool(data.get('dry_run', not confirm))
    limit = int(data.get('limit') or 200)
    limit = max(1, min(limit, 500))

    candidates = _compute_archival_candidates(max_candidates=limit)
    if not candidates:
        return jsonify({'success': True, 'dry_run': dry_run, 'moved': [], 'skipped': []})

    result = _archive_paths([item['path'] for item in candidates], dry_run=dry_run)
    _log_telemetry('archive_execute', {'dry_run': dry_run, 'count': len(result.get('moved', []))})

    if not dry_run:
        _invalidate_cache('ops_summary')
        _invalidate_cache('admin_ops_summary')
        _warm_ops_cache()

    return jsonify({'success': True, **result})


@app.route('/api/admin/archive/manifest', methods=['GET'])
def admin_archive_manifest():
    """Return archive manifest entries (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    payload = _load_archive_manifest()
    return jsonify(payload)


@app.route('/api/admin/archive/restore', methods=['POST'])
def admin_archive_restore():
    """Restore an archived item back to the knowledge base (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    data = request.json or {}
    rel_path = (data.get('path') or '').strip()
    if not rel_path:
        return jsonify({'success': False, 'error': 'path required'}), 400

    policy = _load_archival_policy()
    archive_root = Path(policy.get('archive_root') or '').expanduser()
    if not archive_root.is_absolute():
        archive_root = (Path(__file__).parent / archive_root).resolve()

    kb_root = _knowledge_base_root().resolve()
    source = _resolve_relative_path_under_base(rel_path, archive_root)
    if not source:
        return jsonify({'success': False, 'error': 'path not allowed'}), 403
    normalized_rel_path = source.relative_to(archive_root).as_posix()
    dest = _resolve_relative_path_under_base(normalized_rel_path, kb_root)
    if not dest:
        return jsonify({'success': False, 'error': 'path not allowed'}), 403
    
    if not source.exists():
        return jsonify({'success': False, 'error': 'archived file not found'}), 404
    if dest.exists():
        return jsonify({'success': False, 'error': 'destination already exists'}), 409

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))

    manifest = _load_archive_manifest()
    entries = manifest.get('entries') or []
    manifest['entries'] = [entry for entry in entries if entry.get('archived_relative') != normalized_rel_path]
    _save_archive_manifest(manifest)

    _log_telemetry('archive_restore', {'path': normalized_rel_path})
    _invalidate_cache('ops_summary')
    _invalidate_cache('admin_ops_summary')
    _warm_ops_cache()

    return jsonify({'success': True, 'path': normalized_rel_path})


@app.route('/api/admin/memryx/devices', methods=['GET'])
def admin_memryx_devices():
    """List MX3 device IDs using runtime API when available."""
    guard = require_admin_token()
    if guard:
        return guard

    return jsonify(get_memryx_devices())


@app.route('/api/admin/indexing/start', methods=['POST'])
def admin_start_indexing():
    """Start MemryX indexing pipeline in background."""
    guard = require_admin_token()
    if guard:
        return guard
    guard = _block_if_safe_mode('admin_start_indexing')
    if guard:
        return guard

    if INDEXING_STATUS.get('running'):
        return jsonify({'success': False, 'error': 'Indexing already running'}), 409

    payload = request.json or {}
    thread = threading.Thread(target=_run_memryx_indexing, args=(payload,), daemon=True)
    thread.start()
    return jsonify({'success': True, 'message': 'Indexing started'})


@app.route('/api/admin/indexing/status', methods=['GET'])
def admin_indexing_status():
    """Get MemryX indexing status."""
    guard = require_admin_token()
    if guard:
        return guard

    try:
        if MEMRYX_TUNED_ONNX and MEMRYX_TUNED_ONNX.exists():
            default_onnx = MEMRYX_TUNED_ONNX
            default_dfp = MEMRYX_TUNED_DFP
            default_model = str(MEMRYX_TUNED_DIR)
        else:
            default_onnx = MEMRYX_ONNX_PATH
            default_dfp = MEMRYX_DFP_PATH
            default_model = MEMRYX_MODEL_ID

        default_device_ids = get_memryx_devices().get('device_ids') or []
        default_num_chips = max(len(default_device_ids), 1)

        index_meta = _load_index_meta()
        staleness = _compute_index_staleness(index_meta)
        return jsonify({
            'running': INDEXING_STATUS.get('running', False),
            'last_error': INDEXING_STATUS.get('last_error'),
            'last_result': INDEXING_STATUS.get('last_result'),
            'processed_batches': INDEXING_STATUS.get('processed_batches', 0),
            'total_batches': INDEXING_STATUS.get('total_batches', 0),
            'throughput_eps': INDEXING_STATUS.get('throughput_eps', 0.0),
            'started_at': INDEXING_STATUS.get('started_at'),
            'avg_batch_ms': INDEXING_STATUS.get('avg_batch_ms', 0.0),
            'device_ids': INDEXING_STATUS.get('device_ids', []),
            'priority_paths': INDEXING_STATUS.get('priority_paths', []),
            'batch_delay_ms': INDEXING_STATUS.get('batch_delay_ms', 0),
            'index_meta': index_meta,
            'index_staleness_hours': staleness.get('staleness_hours'),
            'index_last_built_utc': staleness.get('indexed_at_utc'),
            'model_id': default_model,
            'onnx_path': str(default_onnx) if default_onnx else None,
            'dfp_path': str(default_dfp) if default_dfp else None,
            'output_dir': str(MEMRYX_INDEX_DIR) if MEMRYX_INDEX_DIR else None,
            'defaults': {
                'batch_size': 48,
                'max_tokens': 192,
                'num_chips': default_num_chips,
                'device_ids': default_device_ids,
                'prefer_async': True,
                'batch_delay_ms': 0
            }
        })
    except Exception as exc:
        _log_telemetry('error', {'operation': 'indexing_status', 'error_type': type(exc).__name__})
        return jsonify({
            'running': False,
            'last_error': 'Failed to retrieve indexing status',
            'last_result': None,
            'processed_batches': 0,
            'total_batches': 0,
            'throughput_eps': 0.0,
            'started_at': None,
            'avg_batch_ms': 0.0,
            'device_ids': [],
            'priority_paths': [],
            'batch_delay_ms': 0,
            'index_meta': {},
            'index_staleness_hours': None,
            'index_last_built_utc': None,
            'model_id': None,
            'onnx_path': None,
            'dfp_path': None,
            'output_dir': None,
            'defaults': {}
        }), 200  # Return 200 with error info instead of 500


@app.route('/api/admin/indexing/metrics', methods=['GET'])
def admin_indexing_metrics():
    """Get concise indexing metrics (admin only)."""
    guard = require_admin_token()
    if guard:
        return guard

    metrics = _build_indexing_metrics()
    _log_telemetry('indexing_metrics', {'running': metrics.get('running')})
    return jsonify(metrics)


@app.route('/api/admin/shutdown', methods=['POST'])
def admin_shutdown():
    """Shutdown the Flask server (dev server only)."""
    guard = require_admin_token()
    if guard:
        return guard
    shutdown_func = request.environ.get('werkzeug.server.shutdown')
    if shutdown_func is None:
        return jsonify({'success': False, 'error': 'Shutdown not available'})

    shutdown_func()
    return jsonify({'success': True})


@app.route('/api/admin/restart', methods=['POST'])
def admin_restart():
    """Restart the Flask server (dev server only)."""
    guard = require_admin_token()
    if guard:
        return guard
    if not oxidus:
        return jsonify({'success': False, 'error': 'Oxidus not initialized'})

    shutdown_func = request.environ.get('werkzeug.server.shutdown')

    def _restart():
        save_conversation()
        time.sleep(0.5)
        try:
            subprocess.Popen([sys.executable, os.path.abspath(__file__)])
        except Exception:
            pass

        if shutdown_func:
            shutdown_func()

    threading.Thread(target=_restart, daemon=True).start()
    return jsonify({'success': True})


@app.route('/api/recall', methods=['POST'])
def recall_memories():
    """Recall memories about a specific topic."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    data = request.json
    topic = data.get('topic', '').strip()
    max_results = data.get('max_results', 5)
    
    if not topic:
        return jsonify({'error': 'No topic provided'})
    
    _record_access_signal('memory_recall', topics=[topic])
    memories = oxidus.recall_memories(topic, max_results=max_results)
    
    return jsonify({
        'topic': topic,
        'memories': memories
    })


@app.route('/api/knowledge', methods=['GET'])
def get_knowledge_organization():
    """Get knowledge organization report."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    # Get raw report (string or dict)
    report = oxidus.get_knowledge_organization_report()

    # Get understanding summary and model
    understanding_summary = oxidus.get_understanding_summary()
    understanding_model = getattr(oxidus, 'understanding_model', {})
    adaptation_count = getattr(oxidus, 'adaptation_frequency', 0)
    total_concepts = len(understanding_model)

    # Get memory summary
    memory_summary = oxidus.get_memory_summary() if hasattr(oxidus, 'get_memory_summary') else None

    # Get recent thoughts
    recent_thoughts = []
    if hasattr(oxidus, 'thought_stream') and hasattr(oxidus.thought_stream, 'thoughts'):
        recent_thoughts = [str(t) for t in oxidus.thought_stream.thoughts[-10:]]

    loose_ends = {}
    notes_summary = {}
    pipeline_summary = {}
    research_needs = {}
    relevance_config = {}
    retention_config = {}
    if oxidus.knowledge_organizer:
        try:
            loose_ends = oxidus.knowledge_organizer.get_loose_ends_report()
            notes_summary = {
                'total': len(oxidus.knowledge_organizer.list_notes()),
                'open': len(oxidus.knowledge_organizer.list_notes(status='open'))
            }
            pipeline_summary = oxidus.knowledge_organizer.get_pipeline_summary()
            research_needs = oxidus.knowledge_organizer.get_research_needs()
            relevance_config = dict(oxidus.knowledge_organizer.relevance)
            retention_config = dict(oxidus.knowledge_organizer.retention)
        except Exception:
            loose_ends = {}
            notes_summary = {}
            pipeline_summary = {}
            research_needs = {}
            relevance_config = {}
            retention_config = {}

    pipeline_health = {}
    total_sources = pipeline_summary.get('total_sources') or 0
    if total_sources:
        pipeline_health = {
            'concepts_extracted_pct': round((pipeline_summary.get('concepts_extracted', 0) / total_sources) * 100, 1),
            'values_mapped_pct': round((pipeline_summary.get('values_mapped', 0) / total_sources) * 100, 1),
            'summaries_generated_pct': round((pipeline_summary.get('summaries_generated', 0) / total_sources) * 100, 1),
            'indexed_pct': round((pipeline_summary.get('indexed', 0) / total_sources) * 100, 1)
        }

    # Try to extract structured metrics from report if possible
    metrics = {}
    if isinstance(report, dict):
        metrics = report
    elif isinstance(report, str):
        def _extract_int(patterns):
            for pattern in patterns:
                match = re.search(pattern, report)
                if match:
                    return int(match.group(1))
            return 0

        metrics['total_sources'] = _extract_int([
            r'Total Sources Scraped:\s*(\d+)',
            r'Total sources: (\d+)',
            r'Sources Organized: (\d+)'
        ])
        metrics['total_concepts'] = _extract_int([
            r'Total Concepts Indexed:\s*(\d+)'
        ])
        metrics['value_connections'] = {}
        value_section = re.search(r'VALUE TRENDS ACROSS SOURCES\n([\s\S]+?)(?:\n\n|$)', report)
        if value_section:
            for line in value_section.group(1).splitlines():
                m = re.match(r'-\s*(\w+):\s*(\d+)', line)
                if m:
                    metrics['value_connections'][m.group(1)] = int(m.group(2))
        # Top concepts
        top_concepts_section = re.search(r'TOP CONCEPTS FOUND\n([\s\S]+?)(?:\n\n|$)', report)
        metrics['top_concepts'] = []
        if top_concepts_section:
            for line in top_concepts_section.group(1).splitlines():
                m = re.match(r'-\s*\*\*(\w+)\*\* \((\d+)', line)
                if m:
                    metrics['top_concepts'].append(m.group(1))

    return jsonify({
        'report': report,
        'metrics': metrics,
        'understanding_summary': understanding_summary,
        'understanding_model': understanding_model,
        'adaptation_count': adaptation_count,
        'total_concepts': total_concepts,
        'memory_summary': memory_summary,
        'recent_thoughts': recent_thoughts,
        'loose_ends': loose_ends,
        'notes_summary': notes_summary,
        'pipeline_summary': pipeline_summary,
        'pipeline_health': pipeline_health,
        'index_meta': _load_index_meta(),
        'research_needs': research_needs,
        'relevance_config': relevance_config,
        'retention_config': retention_config,
        'available': oxidus.knowledge_organizer is not None
    })


@app.route('/api/initiate', methods=['POST'])
def initiate_conversation():
    """Oxidus initiates conversation autonomously."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    if conversation_history:
        latest = None
        for entry in reversed(conversation_history):
            if entry.get('speaker') == 'OXIDUS':
                latest = entry
                break
        if not latest:
            latest = {
                'speaker': 'OXIDUS',
                'message': _build_opening_message(),
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'type': 'oxidus_initiate',
                'skipped': True
            }
        summary = oxidus.thought_stream.get_thinking_summary()
        return jsonify({
            'oxidus_message': latest,
            'status': {
                'total_thoughts': summary['total_thoughts'],
                'questions': summary['total_questions'],
                'decisions': summary['total_decisions'],
                'insights': summary['insights_gained']
            },
            'skipped': True
        })

    opening = _build_opening_message()
    oxidus_entry = {
        'speaker': 'OXIDUS',
        'message': opening,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': 'oxidus_initiate'
    }
    conversation_history.append(oxidus_entry)
    summary = oxidus.thought_stream.get_thinking_summary()
    return jsonify({
        'oxidus_message': oxidus_entry,
        'status': {
            'total_thoughts': summary['total_thoughts'],
            'questions': summary['total_questions'],
            'decisions': summary['total_decisions'],
            'insights': summary['insights_gained']
        }
    })


@app.route('/api/mode', methods=['GET', 'POST'])
def manage_conversation_mode():
    """Get or set conversation mode (human/ai)."""
    if not oxidus or not oxidus.ai_conversation:
        return jsonify({'error': 'AI conversation not available'})
    
    if request.method == 'POST':
        data = request.json
        new_mode = data.get('mode', 'human')
        
        response = oxidus.switch_conversation_mode(new_mode)
        
        return jsonify({
            'success': True,
            'mode': new_mode,
            'message': response,
            'description': oxidus.get_conversation_mode()
        })
    
    else:
        # GET - return current mode
        return jsonify({
            'mode': oxidus.ai_conversation.mode,
            'descriptor': oxidus.get_conversation_mode(),
            'learning_summary': oxidus.ai_conversation.get_learning_summary()
        })


@app.route('/api/chat-style', methods=['GET', 'POST'])
def manage_chat_style():
    """Get or set chat style (hybrid/user_led)."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})

    if request.method == 'POST':
        data = request.json or {}
        style = data.get('style', 'hybrid')

        message = oxidus.set_chat_style(style)
        settings = load_settings()
        settings['chat_style'] = oxidus.get_chat_style()
        save_settings(settings)

        return jsonify({
            'success': True,
            'style': oxidus.get_chat_style(),
            'message': message
        })

    return jsonify({
        'style': oxidus.get_chat_style()
    })


@app.route('/api/ask-novel-question', methods=['POST'])
def ask_novel_question():
    """Ask a novel question to avoid repetition."""
    if not oxidus or not oxidus.ai_conversation:
        return jsonify({'error': 'AI conversation not available'})
    
    data = request.json
    topic = data.get('topic', 'understanding')
    
    question = oxidus.generate_novel_question(topic)
    
    return jsonify({
        'topic': topic,
        'question': question,
        'mode': oxidus.ai_conversation.mode
    })


@app.route('/api/process-ai-response', methods=['POST'])
def process_ai_response():
    """Process a response from another AI."""
    if not oxidus or not oxidus.ai_conversation:
        return jsonify({'error': 'AI conversation not available'})
    
    data = request.json
    ai_response = data.get('response', '')
    question = data.get('question', '')
    
    analysis = oxidus.process_ai_response(ai_response, question)
    
    return jsonify({
        'success': True,
        'analysis': analysis,
        'learning_summary': oxidus.ai_conversation.get_learning_summary()
    })


@app.route('/api/mode-analysis', methods=['GET'])
def mode_analysis():
    """Analyze learning from different modes."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    analysis = oxidus.analyze_mode_differences()
    
    return jsonify({
        'analysis': analysis,
        'available': oxidus.ai_conversation is not None
    })


@app.route('/api/ask-lm-studio', methods=['POST'])
def ask_lm_studio():
    """Ask LM Studio AI a question and learn from the response."""
    if not oxidus or not oxidus.ai_conversation:
        return jsonify({'error': 'AI conversation not available'})
    
    # Import LM Studio client
    import sys
    sys.path.insert(0, 'src/utils')
    from src.utils.lm_studio_client import get_lm_studio_client
    
    client = get_lm_studio_client()
    
    # Check if LM Studio is available
    if not client.is_available():
        return jsonify({
            'error': 'LM Studio not available',
            'message': 'Make sure LM Studio is running at http://127.0.0.1:1234'
        })
    
    data = request.json
    topic = data.get('topic', 'understanding')
    
    # Generate a novel question
    question = oxidus.generate_novel_question(topic)
    
    if not question or "exhausted" in question.lower():
        return jsonify({
            'error': 'No more questions available for this topic',
            'topic': topic
        })
    
    # Ask primary model
    result = client.ask_for_oxidus(question, context=f"Learning about: {topic}")
    
    if not result['success']:
        return jsonify({
            'error': 'Failed to get response from LM Studio',
            'question': question
        })
    
    # Process the primary AI response
    analysis = oxidus.process_ai_response(result['response'], question)

    # Ask secondary judgment model
    secondary_response = client.ask_secondary_judgment(
        primary_response=result['response'],
        original_question=question,
        context=f"Learning about: {topic}"
    )
    secondary_analysis = None
    if secondary_response:
        secondary_analysis = oxidus.process_secondary_judgment(secondary_response, question)
    
    return jsonify({
        'success': True,
        'topic': topic,
        'question': question,
        'ai_response': result['response'],
        'oxidus_analysis': analysis,
        'secondary_response': secondary_response,
        'secondary_analysis': secondary_analysis,
        'mode': oxidus.ai_conversation.mode,
        'learning_summary': oxidus.ai_conversation.get_learning_summary()
    })


@app.route('/api/lm-studio-status', methods=['GET'])
def lm_studio_status():
    """Check if LM Studio is available."""
    import sys
    sys.path.insert(0, 'src/utils')
    from src.utils.lm_studio_client import get_lm_studio_client
    
    client = get_lm_studio_client()
    available = client.is_available()
    client.ensure_model_selected()
    expected_model = client.primary_model
    active_model = client.model
    model_match = bool(available and active_model == expected_model)
    
    model_info = None
    if available:
        model_info = client.get_model_info()
    
    return jsonify({
        'available': available,
        'url': client.base_url,
        'model': active_model,
        'primary_model': expected_model,
        'secondary_model': client.secondary_model,
        'model_info': model_info,
        'expected_model': expected_model,
        'model_match': model_match,
        'assertions': {
            'model_match': model_match,
            'expected_model': expected_model,
            'active_model': active_model,
            'ok': bool(available and model_match)
        }
    }), 503 if available and not model_match else 200


if __name__ == '__main__':
    threading.Thread(target=init_oxidus, daemon=True).start()
    # Debug mode disabled in production; set OXIDUS_DEBUG env var to enable
    debug_mode = os.environ.get('OXIDUS_DEBUG', '').lower() in ('true', '1', 'yes')
    app.run(debug=debug_mode, port=5000, host='127.0.0.1')