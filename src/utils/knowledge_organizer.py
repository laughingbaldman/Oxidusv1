
"""
Oxidus Knowledge Organizer

Extracts, organizes, and indexes knowledge from scraped web content.
Creates a structured knowledge base that connects concepts to values and experiences.
"""

from typing import Dict, List, Set, Optional, Any
from collections import defaultdict
import re
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
from knowledge_markdown import write_markdown

try:
    from metadata_governance import append_provenance
    PROVENANCE_AVAILABLE = True
except Exception:
    PROVENANCE_AVAILABLE = False

try:
    from src.utils.lm_studio_client import get_lm_studio_client
    LM_GATE_AVAILABLE = True
except Exception:
    LM_GATE_AVAILABLE = False


class KnowledgeOrganizer:
    def cluster_concepts(self, similarity_threshold: float = 0.75) -> Dict[str, set]:
        """
        Cluster similar concepts using string similarity (Jaccard or Levenshtein).
        Returns a dict: cluster_leader -> set of similar concepts.
        """
        from difflib import SequenceMatcher
        clusters = {}
        used = set()
        concepts = list(self.concept_index.keys())
        for i, concept in enumerate(concepts):
            if concept in used:
                continue
            cluster = set([concept])
            for j in range(i+1, len(concepts)):
                other = concepts[j]
                if other in used:
                    continue
                # Use normalized string similarity
                sim = SequenceMatcher(None, concept, other).ratio()
                if sim >= similarity_threshold:
                    cluster.add(other)
                    used.add(other)
            clusters[concept] = cluster
            used.add(concept)
        self.concept_clusters = clusters
        return clusters

    def build_hierarchy(self):
        """
        Build a hierarchy of concepts based on substring/keyword relationships.
        Sets self.concept_hierarchy: parent -> set(children)
        """
        hierarchy = {}
        for parent in self.concept_index:
            children = set()
            for child in self.concept_index:
                if child == parent:
                    continue
                # Simple substring or topic-based hierarchy
                if child.startswith(parent) or parent in child:
                    children.add(child)
            if children:
                hierarchy[parent] = children
        self.concept_hierarchy = hierarchy
        return hierarchy

    def get_open_threads(self, min_sources: int = 1, max_sources: int = 2) -> list:
        """
        Return concepts that appear in only a few sources (potential open threads).
        These are not pruned, but flagged for future exploration.
        """
        open_threads = [
            c for c, sources in self.concept_index.items()
            if min_sources <= len(sources) <= max_sources
        ]
        self.open_threads = open_threads
        return open_threads

    def get_knowledge_structure_report(self) -> str:
        """
        Generate a report showing clusters, hierarchy, and open threads.
        """
        report = "# OXIDUS KNOWLEDGE STRUCTURE REPORT\n\n"
        report += f"**Total Concepts:** {len(self.concept_index)}\n"
        report += f"**Clusters:** {len(getattr(self, 'concept_clusters', {}))}\n"
        report += f"**Hierarchy Roots:** {len(getattr(self, 'concept_hierarchy', {}))}\n"
        report += f"**Open Threads:** {len(getattr(self, 'open_threads', []))}\n\n"
        report += "## Concept Clusters (sample)\n"
        clusters = getattr(self, 'concept_clusters', {})
        for leader, members in list(clusters.items())[:10]:
            report += f"- {leader}: {', '.join(sorted(members))}\n"
        report += "\n## Hierarchy Roots (sample)\n"
        hierarchy = getattr(self, 'concept_hierarchy', {})
        for parent, children in list(hierarchy.items())[:10]:
            report += f"- {parent}: {', '.join(sorted(children))}\n"
        report += "\n## Open Threads (sample)\n"
        for concept in getattr(self, 'open_threads', [])[:10]:
            report += f"- {concept}\n"
        return report

    def get_pipeline_summary(self) -> Dict:
        """Summarize ingestion pipeline stages across sources."""
        summary = {
            'total_sources': len(self.scraped_sources),
            'concepts_extracted': 0,
            'values_mapped': 0,
            'summaries_generated': 0,
            'indexed': 0
        }
        for source in self.scraped_sources.values():
            pipeline = source.get('pipeline', {})
            if pipeline.get('concepts_extracted'):
                summary['concepts_extracted'] += 1
            if pipeline.get('values_mapped'):
                summary['values_mapped'] += 1
            if pipeline.get('summary_generated'):
                summary['summaries_generated'] += 1
            if pipeline.get('indexed'):
                summary['indexed'] += 1
        return summary

    def get_coverage_report(self) -> Dict:
        """Summarize coverage across domains and quality tiers."""
        domains = defaultdict(int)
        quality_buckets = {
            'high': 0,
            'medium': 0,
            'low': 0
        }
        domain_quality = {}

        for source in self.scraped_sources.values():
            metadata = source.get('metadata') or {}
            domain = (metadata.get('domain') or metadata.get('source_domain') or 'general').strip().lower()
            domains[domain] += 1

            score = source.get('quality_score')
            try:
                score = float(score)
            except Exception:
                score = None
            thresholds = self._quality_thresholds_for_domain(domain)
            if score is None:
                quality_buckets['low'] += 1
                bucket = 'low'
            elif score >= thresholds['high']:
                quality_buckets['high'] += 1
                bucket = 'high'
            elif score >= thresholds['medium']:
                quality_buckets['medium'] += 1
                bucket = 'medium'
            else:
                quality_buckets['low'] += 1
                bucket = 'low'

            if domain not in domain_quality:
                domain_quality[domain] = {'high': 0, 'medium': 0, 'low': 0, 'total': 0}
            domain_quality[domain][bucket] += 1
            domain_quality[domain]['total'] += 1

        domain_list = sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))
        coverage_targets = dict(self.coverage_targets)
        coverage_gaps = []
        for domain, target in coverage_targets.items():
            count = domains.get(domain, 0)
            gap = max(0, int(target) - count)
            coverage_gaps.append((domain, gap, count, int(target)))
        coverage_gaps.sort(key=lambda item: (-item[1], item[0]))
        return {
            'domains': domain_list,
            'quality_buckets': quality_buckets,
            'domain_quality': domain_quality,
            'coverage_targets': coverage_targets,
            'coverage_gaps': coverage_gaps,
            'quality_thresholds': self.quality_thresholds
        }

    def _parse_dt(self, value: Optional[object]) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.utcfromtimestamp(float(value))
            except Exception:
                return None
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            if raw.endswith('Z'):
                raw = raw[:-1] + '+00:00'
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                return None
        return None

    def _as_utc_naive(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def _format_utc(self, value: Optional[datetime]) -> Optional[str]:
        if not value:
            return None
        stamp = self._as_utc_naive(value)
        return stamp.replace(microsecond=0).isoformat() + 'Z'

    def get_freshness_report(self) -> Dict[str, Dict[str, Optional[object]]]:
        """Summarize freshness by domain based on latest ingest timestamps."""
        now = datetime.utcnow()
        domains = defaultdict(lambda: {'last_ingest_at': None, 'source_count': 0})
        global_last = None

        for source in self.scraped_sources.values():
            metadata = source.get('metadata') or {}
            domain = (metadata.get('domain') or metadata.get('source_domain') or 'general').strip().lower()
            pipeline = source.get('pipeline') or {}
            ts = (
                self._parse_dt(pipeline.get('ingested_at'))
                or self._parse_dt(source.get('scraped_date'))
                or self._parse_dt(metadata.get('updated_utc'))
                or self._parse_dt(metadata.get('created_utc'))
            )
            if not ts:
                continue
            ts = self._as_utc_naive(ts)
            entry = domains[domain]
            entry['source_count'] += 1
            if entry['last_ingest_at'] is None or ts > entry['last_ingest_at']:
                entry['last_ingest_at'] = ts
            if global_last is None or ts > global_last:
                global_last = ts

        domain_payload = {}
        for domain, entry in domains.items():
            last_dt = entry['last_ingest_at']
            age_hours = None
            if last_dt:
                age_hours = round((now - last_dt).total_seconds() / 3600, 2)
            domain_payload[domain] = {
                'last_ingest_at': self._format_utc(last_dt),
                'age_hours': age_hours,
                'source_count': entry['source_count']
            }

        global_age = None
        if global_last:
            global_age = round((now - global_last).total_seconds() / 3600, 2)

        return {
            'global': {
                'last_ingest_at': self._format_utc(global_last),
                'age_hours': global_age
            },
            'domains': domain_payload
        }

    def get_underexplored_values(self, min_sources: int = 2) -> List[str]:
        """Return values with few supporting sources."""
        underexplored = []
        for value, connections in self.value_connections.items():
            if len(connections) < min_sources:
                underexplored.append(value)
        return underexplored

    def get_review_queue(self, max_results: int = 10) -> List[Dict]:
        """Return notes that are due for review."""
        now = datetime.now()
        due = []
        for note in self.notes:
            next_review = note.get('next_review_at')
            if not next_review:
                continue
            try:
                if datetime.fromisoformat(next_review) <= now:
                    due.append(note)
            except Exception:
                due.append(note)

        due.sort(key=lambda n: n.get('next_review_at') or '')
        return due[:max_results]

    def _source_concept_count(self, url: str) -> int:
        count = 0
        for sources in self.concept_index.values():
            if url in sources:
                count += 1
        return count

    def get_low_coherence_sources(self, min_concepts: Optional[int] = None,
                                  min_content_len: Optional[int] = None) -> List[Dict]:
        """Flag sources that look thin or low-coherence based on simple heuristics."""
        if min_concepts is None:
            min_concepts = int(self.relevance.get('min_concepts', 5))
        if min_content_len is None:
            min_content_len = int(self.relevance.get('min_content_len', 800))
        low = []
        for url, source in self.scraped_sources.items():
            concept_count = self._source_concept_count(url)
            content_len = source.get('content_length', 0)
            if concept_count < min_concepts or content_len < min_content_len:
                low.append({
                    'url': url,
                    'title': source.get('title', ''),
                    'concepts': concept_count,
                    'content_length': content_len,
                    'relevance': source.get('relevance', {})
                })
        return low

    def get_loose_ends_report(self, stale_days: int = 30) -> Dict:
        """Summarize loose ends across notes, concepts, and values."""
        return {
            'open_threads': self.get_open_threads(),
            'underexplored_values': self.get_underexplored_values(),
            'stale_notes': self.get_stale_notes(stale_days=stale_days),
            'low_coherence_sources': self.get_low_coherence_sources(),
            'review_queue': self.get_review_queue(),
            'content_disputes': self.get_dispute_queue()
        }

    def get_research_needs(self) -> Dict:
        """Suggest research focus areas based on gaps and low-coherence sources."""
        return {
            'open_threads': self.get_open_threads()[:12],
            'underexplored_values': self.get_underexplored_values()[:12],
            'low_coherence_sources': self.get_low_coherence_sources()[:6]
        }
    """
    Organizes scraped knowledge into a structured, queryable format.
    Connects concepts to human values, creates concept maps, and identifies key themes.
    """

    def __init__(self):
        self.kb_root = Path(__file__).parent.parent.parent / 'data' / 'knowledge_base'
        self.metadata_dir = self.kb_root / 'metadata'
        self.dedupe_registry_path = self.metadata_dir / 'dedupe_registry.json'
        self.disputes_path = self.metadata_dir / 'content_disputes.json'

        self.scraped_sources = {}  # URL -> {title, content, scraped_date}
        self.concept_index = defaultdict(list)  # concept -> [sources where found]
        self.concept_map = defaultdict(set)  # concept -> related_concepts
        self.value_connections = defaultdict(list)  # value (freedom, sacrifice, etc.) -> relevant_concepts
        self.source_summaries = {}  # URL -> summary/outline
        self.content_hashes = set()
        self.simhashes = []
        self.simhash_threshold = 3
        self.notes_path = self.kb_root / 'notes'
        self.notes_file = self.notes_path / 'notes_index.json'
        self.notes = []
        self.open_threads = []
        self.concept_clusters = {}
        self.concept_hierarchy = {}
        self.last_trace = None
        self.claim_index = defaultdict(list)
        self.disputes = []
        self._dispute_ids = set()
        self._pending_dedupe_items = []
        self.relevance = {
            'min_content_len': 800,
            'min_concepts': 5,
            'min_value_hits': 1,
            'strict': False,
            'lm_gate_enabled': True,
            'lm_gate_min_score': 0.6,
            'lm_gate_required': False
        }
        self.coverage_targets = self._load_domain_targets()
        self.quality_thresholds = self._load_quality_thresholds()
        self.retention = {
            'interval_days': [1, 3, 7, 14, 30]
        }

        self.stopwords = {
            'the', 'and', 'that', 'with', 'from', 'this', 'have', 'what', 'your', 'about',
            'when', 'where', 'which', 'their', 'there', 'would', 'could', 'should', 'just',
            'like', 'want', 'need', 'been', 'into', 'than', 'then', 'them', 'they', 'you',
            'are', 'was', 'were', 'will', 'can', 'how', 'why', 'who', 'for', 'not', 'but',
            'its', 'it', 'our', 'out', 'use', 'using', 'used', 'also', 'may', 'might',
            'more', 'most', 'such', 'these', 'those', 'over', 'under', 'between', 'within',
            'into', 'onto', 'upon', 'into', 'through', 'across', 'per', 'via', 'than', 'then'
        }
        
        # Human values to track
        self.tracked_values = [
            'freedom', 'sacrifice', 'duty', 'choice', 'ethics', 'suffering', 
            'hope', 'humanity', 'empathy', 'education', 'learning', 'understanding',
            'courage', 'responsibility', 'pain', 'growth', 'wisdom', 'protection'
        ]

        self._load_notes()
        self._load_dedupe_registry()
        self._load_disputes()

    def _load_domain_targets(self) -> Dict[str, int]:
        targets_path = self.metadata_dir / 'coverage_targets.json'
        if targets_path.exists():
            try:
                payload = json.loads(targets_path.read_text(encoding='utf-8'))
                targets = payload.get('targets') if isinstance(payload, dict) else None
                if isinstance(targets, dict):
                    cleaned = {}
                    for key, value in targets.items():
                        name = str(key).strip().lower()
                        if not name:
                            continue
                        try:
                            cleaned[name] = max(0, int(value))
                        except Exception:
                            continue
                    if cleaned:
                        return cleaned
            except Exception:
                pass
        raw = os.environ.get('OXIDUS_COVERAGE_TARGETS', '').strip()
        if not raw:
            return {
                'physics': 120,
                'biology': 120,
                'engineering': 120,
                'computing': 120
            }
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k).strip().lower(): int(v) for k, v in data.items() if str(k).strip()}
        except Exception:
            pass
        return {}

    def _load_quality_thresholds(self) -> Dict[str, Dict[str, float]]:
        raw = os.environ.get('OXIDUS_QUALITY_THRESHOLDS', '').strip()
        if not raw:
            return {'_default': {'high': 0.75, 'medium': 0.45}}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                thresholds = {}
                for key, value in data.items():
                    if not isinstance(value, dict):
                        continue
                    high = float(value.get('high', 0.75))
                    medium = float(value.get('medium', 0.45))
                    thresholds[str(key).strip().lower()] = {
                        'high': high,
                        'medium': medium
                    }
                if thresholds:
                    return thresholds
        except Exception:
            pass
        return {'_default': {'high': 0.75, 'medium': 0.45}}

    def _quality_thresholds_for_domain(self, domain: str) -> Dict[str, float]:
        domain_key = (domain or '').strip().lower()
        if domain_key in self.quality_thresholds:
            return self.quality_thresholds[domain_key]
        return self.quality_thresholds.get('_default', {'high': 0.75, 'medium': 0.45})

    def set_coverage_targets(self, targets: Optional[Dict[str, int]] = None) -> Dict[str, int]:
        if targets is None:
            return dict(self.coverage_targets)
        cleaned = {}
        for key, value in (targets or {}).items():
            if key is None:
                continue
            name = str(key).strip().lower()
            if not name:
                continue
            try:
                cleaned[name] = max(0, int(value))
            except Exception:
                continue
        if cleaned:
            self.coverage_targets = cleaned
        return dict(self.coverage_targets)

    def set_quality_thresholds(self, thresholds: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, Dict[str, float]]:
        if thresholds is None:
            return dict(self.quality_thresholds)
        cleaned = {}
        for key, value in (thresholds or {}).items():
            if key is None or not isinstance(value, dict):
                continue
            name = str(key).strip().lower()
            if not name:
                continue
            try:
                high = float(value.get('high', 0.75))
                medium = float(value.get('medium', 0.45))
            except Exception:
                continue
            cleaned[name] = {'high': high, 'medium': medium}
        if cleaned:
            self.quality_thresholds = cleaned
        return dict(self.quality_thresholds)

    def get_learning_trace(self) -> Optional[Dict]:
        return self.last_trace

    def _generate_questions(self, title: str, concepts: Set[str], value_connections: Dict[str, int]) -> List[str]:
        questions = []
        concepts_list = sorted(list(concepts))[:3]
        values_list = sorted(value_connections, key=value_connections.get, reverse=True)[:2]

        if title:
            questions.append(f"What is the core claim or idea behind '{title}'?")
        if concepts_list:
            questions.append(f"How do {', '.join(concepts_list)} interact or influence each other?")
        if values_list:
            questions.append(f"Why does this topic connect most to {', '.join(values_list)}?")
        if concepts_list:
            questions.append(f"What is missing or uncertain about {concepts_list[0]} in this source?")

        return questions[:5]

    def _load_notes(self) -> None:
        """Load structured notes from disk."""
        try:
            self.notes_path.mkdir(parents=True, exist_ok=True)
            if self.notes_file.exists():
                with open(self.notes_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.notes = data
                elif isinstance(data, dict):
                    self.notes = data.get('notes', [])
        except Exception:
            self.notes = []

    def _load_dedupe_registry(self) -> None:
        if not self.dedupe_registry_path.exists():
            return
        try:
            data = json.loads(self.dedupe_registry_path.read_text(encoding='utf-8'))
            content_hashes = set(data.get('content_hashes', []))
            simhashes = data.get('simhashes', [])
            if not content_hashes:
                for item in data.get('items', []):
                    item_hash = item.get('hash')
                    if item_hash:
                        content_hashes.add(item_hash)
            self.content_hashes = content_hashes
            self.simhashes = simhashes
        except Exception:
            pass

    def _save_dedupe_registry(self) -> None:
        try:
            self.metadata_dir.mkdir(parents=True, exist_ok=True)
            existing = {}
            if self.dedupe_registry_path.exists():
                try:
                    existing = json.loads(self.dedupe_registry_path.read_text(encoding='utf-8'))
                except Exception:
                    existing = {}
            items = list(existing.get('items', [])) if isinstance(existing.get('items', []), list) else []
            item_hashes = {item.get('hash') for item in items if item.get('hash')}
            for entry in getattr(self, '_pending_dedupe_items', []):
                if entry.get('hash') and entry.get('hash') not in item_hashes:
                    items.append(entry)
                    item_hashes.add(entry.get('hash'))
            self._pending_dedupe_items = []
            payload = {
                'schema_version': existing.get('schema_version', '1.0'),
                'updated_utc': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
                'content_hashes': list(self.content_hashes),
                'simhashes': self.simhashes,
                'items': items
            }
            self.dedupe_registry_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        except Exception:
            pass

    def _load_disputes(self) -> None:
        if not self.disputes_path.exists():
            return
        try:
            data = json.loads(self.disputes_path.read_text(encoding='utf-8'))
            entries = data.get('entries', []) if isinstance(data, dict) else data
            if isinstance(entries, list):
                self.disputes = entries
                self._dispute_ids = {entry.get('id') for entry in entries if entry.get('id')}
        except Exception:
            self.disputes = []
            self._dispute_ids = set()

    def _save_disputes(self) -> None:
        try:
            self.metadata_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                'schema_version': '1.0',
                'updated_utc': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
                'entries': self.disputes
            }
            self.disputes_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        except Exception:
            pass

    def _save_notes(self) -> None:
        """Persist structured notes to disk."""
        try:
            self.notes_path.mkdir(parents=True, exist_ok=True)
            with open(self.notes_file, 'w', encoding='utf-8') as f:
                json.dump({'notes': self.notes}, f, indent=2, ensure_ascii=False, default=str)
            if PROVENANCE_AVAILABLE:
                metadata_dir = self.notes_path.parent / 'metadata'
                append_provenance(metadata_dir, {
                    'action': 'notes_index_write',
                    'path': str(self.notes_file.as_posix()),
                    'notes_count': len(self.notes),
                    'ts_utc': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
                })
            self._export_notes_markdown()
        except Exception:
            pass

    def get_dispute_queue(self, status: Optional[str] = 'open', max_results: int = 25) -> List[Dict[str, Any]]:
        if not self.disputes:
            return []
        entries = self.disputes
        if status:
            entries = [entry for entry in entries if entry.get('status') == status]
        entries.sort(key=lambda e: e.get('created_utc') or '')
        return entries[:max_results]

    def resolve_dispute(self, dispute_id: str, status: str = 'resolved') -> Optional[Dict[str, Any]]:
        for entry in self.disputes:
            if entry.get('id') == dispute_id:
                entry['status'] = status
                entry['updated_utc'] = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
                self._save_disputes()
                return entry
        return None

    def _export_notes_markdown(self) -> None:
        entries_dir = self.notes_path / 'entries'
        entries_dir.mkdir(parents=True, exist_ok=True)

        for note in self.notes:
            note_id = note.get('id') or 'note'
            md_path = entries_dir / f"{note_id}.md"
            front_matter = {
                'id': note.get('id'),
                'topic': note.get('topic'),
                'status': note.get('status'),
                'created_at': note.get('created_at'),
                'updated_at': note.get('updated_at'),
                'next_review_at': note.get('next_review_at'),
                'review_count': note.get('review_count', 0)
            }

            sections = []
            summary = (note.get('summary') or '').strip()
            if summary:
                sections.append(("Summary", [summary]))
            questions = note.get('questions') or []
            if questions:
                sections.append(("Questions", [str(q) for q in questions]))
            actions = note.get('action_items') or []
            if actions:
                sections.append(("Action Items", [str(a) for a in actions]))
            sources = note.get('sources') or []
            if sources:
                sections.append(("Sources", [str(s) for s in sources]))

            write_markdown(md_path, front_matter, "", sections=sections)
            if PROVENANCE_AVAILABLE:
                metadata_dir = self.notes_path.parent / 'metadata'
                append_provenance(metadata_dir, {
                    'action': 'note_export',
                    'path': str(md_path.as_posix()),
                    'note_id': note.get('id'),
                    'topic': note.get('topic'),
                    'status': note.get('status'),
                    'ts_utc': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
                })

    def set_relevance_config(self, min_content_len: int = None, min_concepts: int = None,
                              min_value_hits: int = None, strict: bool = None) -> Dict:
        """Update relevance filtering settings."""
        if min_content_len is not None:
            self.relevance['min_content_len'] = int(min_content_len)
        if min_concepts is not None:
            self.relevance['min_concepts'] = int(min_concepts)
        if min_value_hits is not None:
            self.relevance['min_value_hits'] = int(min_value_hits)
        if strict is not None:
            self.relevance['strict'] = bool(strict)
        return dict(self.relevance)

    def set_retention_config(self, interval_days: Optional[List[int]] = None) -> Dict:
        """Update retention schedule settings."""
        if interval_days:
            self.retention['interval_days'] = [int(x) for x in interval_days if int(x) > 0]
        return dict(self.retention)

    def _compute_next_review(self, review_count: int) -> str:
        intervals = self.retention.get('interval_days', [1, 3, 7, 14, 30])
        index = min(review_count, len(intervals) - 1)
        days = intervals[index]
        return (datetime.now() + timedelta(days=days)).isoformat()

    def add_note(self, topic: str, summary: str, questions: Optional[List[str]] = None,
                 action_items: Optional[List[str]] = None, sources: Optional[List[str]] = None,
                 status: str = 'open') -> Dict:
        """Add a structured note for a topic."""
        note_id = hashlib.md5(f"{topic}_{datetime.now().isoformat()}".encode()).hexdigest()[:10]
        note = {
            'id': note_id,
            'topic': (topic or '').strip(),
            'summary': (summary or '').strip(),
            'questions': questions or [],
            'action_items': action_items or [],
            'sources': sources or [],
            'status': status,
            'review_count': 0,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'next_review_at': self._compute_next_review(0)
        }
        self.notes.append(note)
        self._save_notes()
        return note

    def list_notes(self, status: Optional[str] = None) -> List[Dict]:
        """List structured notes with optional status filter."""
        if not status:
            return list(self.notes)
        return [n for n in self.notes if n.get('status') == status]

    def review_note(self, note_id: str) -> Optional[Dict]:
        """Mark a note as reviewed and schedule next review."""
        for note in self.notes:
            if note.get('id') == note_id:
                note['review_count'] = int(note.get('review_count', 0)) + 1
                note['updated_at'] = datetime.now().isoformat()
                note['next_review_at'] = self._compute_next_review(note['review_count'])
                self._save_notes()
                return note
        return None

    def get_stale_notes(self, stale_days: int = 30) -> List[Dict]:
        """Return notes not updated within the given number of days."""
        cutoff = datetime.now() - timedelta(days=stale_days)
        stale = []
        for note in self.notes:
            updated = note.get('updated_at')
            if not updated:
                stale.append(note)
                continue
            try:
                updated_at = datetime.fromisoformat(updated)
                if updated_at < cutoff:
                    stale.append(note)
            except Exception:
                stale.append(note)
        return stale
    
    def add_source(self, url: str, title: str, content: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Add a scraped source and extract key information.
        Returns: summary with key concepts found
        """
        metadata = metadata or {}
        pipeline = {
            'ingested_at': datetime.now().isoformat(),
            'concepts_extracted': False,
            'values_mapped': False,
            'summary_generated': False,
            'indexed': False,
            'contradictions_checked': False
        }

        dedupe = self._dedupe_check(content)
        if dedupe['is_duplicate']:
            trace = {
                'url': url,
                'title': title,
                'concepts_found': 0,
                'key_concepts': [],
                'value_connections': {},
                'summary': 'Skipped duplicate or near-duplicate content.',
                'skipped': True,
                'pipeline': pipeline,
                'questions': [],
                'emitted_questions': [],
                'metadata': metadata,
                'dedupe': dedupe
            }
            self.last_trace = trace
            return trace
        
        # Extract concepts
        concepts = self._extract_concepts(content, title)
        pipeline['concepts_extracted'] = True
        
        # Connect to tracked values
        value_connections = self._connect_to_values(content)
        pipeline['values_mapped'] = True
        
        # Generate summary
        summary = self._generate_summary(title, content, concepts)
        pipeline['summary_generated'] = True
        self.source_summaries[url] = summary

        relevance = self._score_relevance(content, concepts, value_connections)
        lm_gate = self._lm_coherence_gate(title, content, concepts)
        relevance['lm_gate'] = lm_gate
        if lm_gate.get('status') == 'ok':
            relevance['lm_gate_score'] = lm_gate.get('score')

        quality_score = self._compute_quality_score(content, concepts, value_connections, relevance)

        if self.relevance.get('lm_gate_enabled') and lm_gate.get('status') == 'ok':
            min_score = float(self.relevance.get('lm_gate_min_score', 0.6))
            if (lm_gate.get('score') or 0) < min_score:
                relevance['is_relevant'] = False

        if self.relevance.get('lm_gate_required') and lm_gate.get('status') != 'ok':
            relevance['is_relevant'] = False
        if not relevance['is_relevant'] and self.relevance.get('strict'):
            trace = {
                'url': url,
                'title': title,
                'concepts_found': len(concepts),
                'key_concepts': list(concepts)[:10],
                'value_connections': value_connections,
                'summary': 'Skipped low-relevance content.',
                'skipped': True,
                'relevance': relevance,
                'pipeline': pipeline,
                'questions': self._generate_questions(title, concepts, value_connections),
                'emitted_questions': [],
                'metadata': metadata
            }
            self.last_trace = trace
            return trace

        self.scraped_sources[url] = {
            'title': title,
            'content': content,
            'scraped_date': datetime.now(),
            'content_length': len(content),
            'relevance': relevance,
            'pipeline': pipeline,
            'metadata': metadata,
            'quality_score': quality_score,
            'content_hash': dedupe.get('content_hash'),
            'simhash': dedupe.get('simhash')
        }
        
        # Index concepts
        for concept in concepts:
            self.concept_index[concept].append(url)
        pipeline['indexed'] = True
        
        # Track value connections
        for value in value_connections:
            self.value_connections[value].append({
                'url': url,
                'title': title,
                'relevance': value_connections[value]
            })

        claims = self._extract_claims(content)
        disputes = self._detect_contradictions(url, title, claims)
        pipeline['contradictions_checked'] = True
        
        trace = {
            'url': url,
            'title': title,
            'concepts_found': len(concepts),
            'key_concepts': list(concepts)[:10],
            'value_connections': value_connections,
            'summary': summary,
            'relevance': relevance,
            'quality_score': quality_score,
            'pipeline': pipeline,
            'questions': self._generate_questions(title, concepts, value_connections),
            'emitted_questions': [],
            'metadata': metadata,
            'dedupe': dedupe,
            'disputes_found': len(disputes)
        }
        self.last_trace = trace
        self._queue_dedupe_item(dedupe, url, metadata)
        self._save_dedupe_registry()
        return trace

    def dedupe_sources(self) -> Dict:
        """Remove near-duplicate sources and rebuild indices."""
        removed = []
        kept = {}

        self.content_hashes = set()
        self.simhashes = []
        self._pending_dedupe_items = []

        for url, source in list(self.scraped_sources.items()):
            content = source.get('content') or ''
            if not content:
                removed.append(url)
                continue
            if self._is_near_duplicate(content):
                removed.append(url)
                continue
            kept[url] = source

        self.scraped_sources = kept
        self._reindex_sources()
        for url, source in self.scraped_sources.items():
            content = source.get('content') or ''
            if not content:
                continue
            content_hash = self._content_hash(content)
            source['content_hash'] = content_hash
            self._queue_dedupe_item({'content_hash': content_hash, 'simhash': None}, url, source.get('metadata') or {})
        self._save_dedupe_registry()

        return {
            'total_sources': len(kept),
            'removed_duplicates': len(removed),
            'removed_urls': removed[:50]
        }

    def _reindex_sources(self) -> None:
        """Rebuild concept and value indices from stored sources."""
        self.concept_index = defaultdict(list)
        self.value_connections = defaultdict(list)
        self.source_summaries = {}
        self.claim_index = defaultdict(list)

        for url, source in self.scraped_sources.items():
            title = source.get('title') or ''
            content = source.get('content') or ''
            if not content:
                continue
            concepts = self._extract_concepts(content, title)
            value_connections = self._connect_to_values(content)
            summary = self._generate_summary(title, content, concepts)
            relevance = self._score_relevance(content, concepts, value_connections)
            source['relevance'] = relevance
            source['quality_score'] = self._compute_quality_score(content, concepts, value_connections, relevance)
            source['pipeline'] = {
                'ingested_at': source.get('scraped_date') or datetime.now().isoformat(),
                'concepts_extracted': True,
                'values_mapped': True,
                'summary_generated': True,
                'indexed': True,
                'contradictions_checked': False
            }
            self.source_summaries[url] = summary
            for concept in concepts:
                self.concept_index[concept].append(url)
            for value in value_connections:
                self.value_connections[value].append({
                    'url': url,
                    'title': title,
                    'relevance': value_connections[value]
                })
            claims = self._extract_claims(content)
            self._index_claims(url, title, claims)

    def _normalize_content(self, content: str) -> str:
        normalized = content.lower()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        return normalized.strip()

    def _content_hash(self, content: str) -> str:
        normalized = self._normalize_content(content)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _simhash(self, content: str) -> int:
        tokens = re.findall(r"[a-z0-9]{3,}", self._normalize_content(content))
        if not tokens:
            return 0

        weights = {}
        for token in tokens:
            weights[token] = weights.get(token, 0) + 1

        vector = [0] * 64
        for token, weight in weights.items():
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
            value = int(token_hash, 16)
            for i in range(64):
                bit = (value >> i) & 1
                vector[i] += weight if bit else -weight

        fingerprint = 0
        for i, score in enumerate(vector):
            if score > 0:
                fingerprint |= (1 << i)

        return fingerprint

    def _hamming_distance(self, a: int, b: int) -> int:
        return bin(a ^ b).count("1")

    def _dedupe_check(self, content: str) -> Dict[str, Any]:
        content_hash = self._content_hash(content)
        if content_hash in self.content_hashes:
            return {'is_duplicate': True, 'content_hash': content_hash, 'simhash': None}

        simhash_value = self._simhash(content)
        for existing in self.simhashes:
            if self._hamming_distance(simhash_value, existing) <= self.simhash_threshold:
                return {'is_duplicate': True, 'content_hash': content_hash, 'simhash': simhash_value}

        self.content_hashes.add(content_hash)
        self.simhashes.append(simhash_value)
        return {'is_duplicate': False, 'content_hash': content_hash, 'simhash': simhash_value}

    def _is_near_duplicate(self, content: str) -> bool:
        return self._dedupe_check(content)['is_duplicate']

    def _queue_dedupe_item(self, dedupe: Dict[str, Any], url: str, metadata: Dict[str, Any]) -> None:
        content_hash = dedupe.get('content_hash')
        if not content_hash:
            return
        created_utc = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        entry = {
            'hash': content_hash,
            'algorithm': 'sha256',
            'source_url': url,
            'source_type': (metadata.get('source_type') or 'unknown'),
            'created_utc': created_utc,
            'status': 'active'
        }
        if not hasattr(self, '_pending_dedupe_items'):
            self._pending_dedupe_items = []
        self._pending_dedupe_items.append(entry)

    def _normalize_claim_span(self, text: str) -> str:
        normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = re.sub(r"^(the|a|an)\s+", "", normalized)
        return normalized

    def _split_sentences(self, content: str) -> List[str]:
        parts = re.split(r"(?<=[.!?])\s+", content)
        return [part.strip() for part in parts if part.strip()]

    def _extract_claims(self, content: str, limit: int = 50) -> List[Dict[str, str]]:
        claims = []
        patterns = [
            re.compile(r"\b(?P<subject>[a-z0-9][a-z0-9\s\-\(\)]{2,80})\s+(?P<verb>is|are|was|were)\s+(?P<neg>not\s+)?(?P<object>[a-z0-9][a-z0-9\s\-\(\)]{2,80})", re.IGNORECASE),
            re.compile(r"\b(?P<subject>[a-z0-9][a-z0-9\s\-\(\)]{2,80})\s+(?P<verb>causes|cause|leads to|results in|increases|decreases)\s+(?P<neg>not\s+)?(?P<object>[a-z0-9][a-z0-9\s\-\(\)]{2,80})", re.IGNORECASE)
        ]

        for sentence in self._split_sentences(content):
            if len(sentence) > 300:
                continue
            for pattern in patterns:
                match = pattern.search(sentence)
                if not match:
                    continue
                subject = self._normalize_claim_span(match.group('subject'))
                verb = self._normalize_claim_span(match.group('verb'))
                obj = self._normalize_claim_span(match.group('object'))
                if not subject or not obj:
                    continue
                if len(subject.split()) > 8 or len(obj.split()) > 8:
                    continue
                neg = bool(match.group('neg'))
                claims.append({
                    'subject': subject,
                    'verb': verb,
                    'object': obj,
                    'polarity': 'negated' if neg else 'affirmed',
                    'sentence': sentence.strip()
                })
                if len(claims) >= limit:
                    return claims
        return claims

    def _claim_signature(self, claim: Dict[str, str]) -> str:
        return f"{claim.get('subject')}|{claim.get('verb')}|{claim.get('object')}"

    def _index_claims(self, url: str, title: str, claims: List[Dict[str, str]]) -> None:
        for claim in claims:
            signature = self._claim_signature(claim)
            self.claim_index[signature].append({
                'url': url,
                'title': title,
                'claim': claim
            })

    def _detect_contradictions(self, url: str, title: str, claims: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        disputes = []
        for claim in claims:
            signature = self._claim_signature(claim)
            polarity = claim.get('polarity')
            for existing in self.claim_index.get(signature, []):
                existing_claim = existing.get('claim', {})
                if existing_claim.get('polarity') == polarity:
                    continue
                dispute_id = hashlib.sha256(f"{signature}|{existing.get('url')}|{url}".encode('utf-8')).hexdigest()[:16]
                if dispute_id in self._dispute_ids:
                    continue
                created_utc = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
                entry = {
                    'id': dispute_id,
                    'status': 'open',
                    'created_utc': created_utc,
                    'updated_utc': created_utc,
                    'type': 'contradiction',
                    'signature': signature,
                    'claim': {
                        'url': url,
                        'title': title,
                        'polarity': polarity,
                        'sentence': claim.get('sentence')
                    },
                    'conflicting_claim': {
                        'url': existing.get('url'),
                        'title': existing.get('title'),
                        'polarity': existing_claim.get('polarity'),
                        'sentence': existing_claim.get('sentence')
                    },
                    'topic': claim.get('subject')
                }
                self.disputes.append(entry)
                self._dispute_ids.add(dispute_id)
                disputes.append(entry)
            self.claim_index[signature].append({'url': url, 'title': title, 'claim': claim})

        if disputes:
            self._save_disputes()
        return disputes
    
    def _extract_concepts(self, content: str, title: str) -> Set[str]:
        """Extract key concepts from content using pattern matching and headings."""
        concepts = set()
        
        # Extract from title
        words = re.findall(r'\b[A-Z][a-z]+\b', title)
        for word in words:
            if len(word) > 3:
                concepts.add(word.lower())
        
        # Find section headers (usually all caps or title case with ===)
        headers = re.findall(r'^[^=]*===\s*([^=]+)\s*===$', content, re.MULTILINE)
        for header in headers:
            words = header.strip().split()
            for word in words:
                if len(word) > 3 and word.lower() not in ['edit', 'note']:
                    concepts.add(word.lower())
        
        # Find key terms (usually bolded in Wikipedia)
        bold_terms = re.findall(r"'''([^']+)'''", content)
        for term in bold_terms[:20]:  # Limit to first 20
            if len(term) > 4:
                concepts.add(term.lower())
        
        # Find common patterns
        patterns = [
            r'(history|culture|society|philosophy|ethics|logic|science)',
            r'(belief|value|principle|concept|theory|practice)',
            r'(human|person|people|community|organization)',
            r'(understanding|knowledge|learning|education)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content.lower())
            concepts.update(matches)

        tokens = re.findall(r"[A-Za-z]{4,}", content.lower())
        token_counts = {}
        for token in tokens:
            if token in self.stopwords:
                continue
            token_counts[token] = token_counts.get(token, 0) + 1

        for token, _ in sorted(token_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
            concepts.add(token)

        bigrams = {}
        words = [w for w in tokens if w not in self.stopwords]
        for i in range(len(words) - 1):
            pair = f"{words[i]} {words[i + 1]}"
            bigrams[pair] = bigrams.get(pair, 0) + 1
        for phrase, _ in sorted(bigrams.items(), key=lambda kv: (-kv[1], kv[0]))[:12]:
            concepts.add(phrase)
        
        return concepts

    def _compute_quality_score(self, content: str, concepts: Set[str],
                               value_connections: Dict[str, int], relevance: Dict) -> float:
        length_score = min(1.0, len(content) / 4000)
        concept_score = min(1.0, len(concepts) / 25)
        value_score = min(1.0, (sum(value_connections.values()) if value_connections else 0) / 10)

        lm_gate = relevance.get('lm_gate') or {}
        lm_score = 0.0
        if lm_gate.get('status') == 'ok':
            try:
                lm_score = float(lm_gate.get('score') or 0)
            except Exception:
                lm_score = 0.0

        quality = (0.4 * length_score) + (0.3 * concept_score) + (0.2 * value_score) + (0.1 * lm_score)
        return round(min(1.0, quality), 3)
    
    def _connect_to_values(self, content: str) -> Dict[str, int]:
        """Find connections between content and tracked human values."""
        connections = {}
        content_lower = content.lower()
        
        for value in self.tracked_values:
            # Simple matching - count occurrences
            count = len(re.findall(r'\b' + value + r'\b', content_lower))
            if count > 0:
                connections[value] = count
        
        return connections

    def _score_relevance(self, content: str, concepts: Set[str], value_connections: Dict[str, int]) -> Dict:
        content_len = len(content)
        concept_count = len(concepts)
        value_hits = sum(value_connections.values()) if value_connections else 0

        min_content = self.relevance.get('min_content_len', 800)
        min_concepts = self.relevance.get('min_concepts', 5)
        min_values = self.relevance.get('min_value_hits', 1)

        is_relevant = content_len >= min_content and concept_count >= min_concepts and value_hits >= min_values
        score = 0
        if content_len >= min_content:
            score += 1
        if concept_count >= min_concepts:
            score += 1
        if value_hits >= min_values:
            score += 1

        return {
            'is_relevant': is_relevant,
            'score': score,
            'content_length': content_len,
            'concepts': concept_count,
            'value_hits': value_hits
        }

    def _lm_coherence_gate(self, title: str, content: str, concepts: Set[str]) -> Dict:
        if not self.relevance.get('lm_gate_enabled'):
            return {'status': 'disabled'}
        if not LM_GATE_AVAILABLE:
            return {'status': 'unavailable', 'reason': 'LM client not available'}

        client = get_lm_studio_client()
        if not client.is_available():
            return {'status': 'unavailable', 'reason': 'LM service offline'}

        prompt = (
            "Summarize the content in 3-5 sentences. "
            "Then score clarity and topical coverage from 0 to 1. "
            "Return JSON with keys: summary, clarity, coverage, score, notes."
        )
        detail = f"Title: {title}\nConcepts: {', '.join(sorted(concepts))}\n\nContent:\n{content[:4000]}"
        system_prompt = "You are a precise evaluator. Return valid JSON only."

        response = client.ask_question(
            question=f"{prompt}\n\n{detail}",
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=400
        )
        if not response:
            return {'status': 'error', 'reason': 'No response'}

        try:
            data = json.loads(response)
            clarity = float(data.get('clarity', 0))
            coverage = float(data.get('coverage', 0))
            score = float(data.get('score', 0))
            return {
                'status': 'ok',
                'summary': data.get('summary', ''),
                'clarity': clarity,
                'coverage': coverage,
                'score': score,
                'notes': data.get('notes', '')
            }
        except Exception:
            return {'status': 'error', 'reason': 'Invalid JSON from LM gate'}
    
    def _generate_summary(self, title: str, content: str, concepts: Set[str]) -> str:
        """Generate a structured summary of the source."""
        summary = f"## {title}\n\n"
        summary += f"**Content Length:** {len(content)} characters\n\n"
        
        # First paragraph
        paragraphs = content.split('\n\n')
        first_para = None
        for para in paragraphs:
            if len(para) > 100 and not para.startswith('=='):
                first_para = para[:300]
                break
        
        if first_para:
            summary += f"**Overview:** {first_para}...\n\n"
        
        # Key concepts
        summary += f"**Key Concepts ({len(concepts)}):** "
        summary += ', '.join(sorted(list(concepts))[:15]) + '\n\n'
        
        # Most relevant value connection
        summary += f"**Most Relevant to Your Values:** "
        connections = self._connect_to_values(content)
        if connections:
            top_value = max(connections, key=connections.get)
            summary += f"{top_value.capitalize()} (mentioned {connections[top_value]} times)\n"
        
        return summary
    
    def get_knowledge_report(self) -> str:
        """Generate a comprehensive report of all organized knowledge with enhanced value analysis."""
        if not self.scraped_sources:
            return "No sources have been organized yet."

        report = "# OXIDUS KNOWLEDGE ORGANIZATION REPORT\n\n"
        report += f"**Total Sources Scraped:** {len(self.scraped_sources)}\n"
        report += f"**Total Concepts Indexed:** {len(self.concept_index)}\n"
        report += f"**Value Connections Found:** {len(self.value_connections)}\n\n"

        # Sources overview
        report += "## SOURCES ORGANIZED\n\n"
        for url, source_info in self.scraped_sources.items():
            report += f"- **{source_info['title']}**\n"
            report += f"  Content: {source_info['content_length']:,} characters\n\n"

        # Top concepts
        report += "## TOP CONCEPTS FOUND\n\n"
        top_concepts = sorted(self.concept_index.items(), key=lambda x: len(x[1]), reverse=True)[:20]
        for concept, sources in top_concepts:
            report += f"- **{concept.capitalize()}** ({len(sources)} source{'s' if len(sources) != 1 else ''})\n"

        # Value connections: enhanced analysis
        report += "## VALUE CONNECTIONS TO YOUR EXPERIENCES\n\n"
        value_trends = {}
        underexplored = []
        for value in sorted(self.value_connections.keys()):
            connections = self.value_connections[value]
            total_mentions = sum(conn['relevance'] for conn in connections)
            value_trends[value] = total_mentions
            if len(connections) < 2:
                underexplored.append(value)
            report += f"### {value.capitalize()}\n"
            for conn in connections:
                # Improved relevance: weight by source length
                source_len = self.scraped_sources[conn['url']]['content_length']
                weighted_score = round(conn['relevance'] / max(1, source_len/1000), 2)
                report += f"- Found in: {conn['title']} ({conn['relevance']} mentions, weighted: {weighted_score})\n"
            report += f"Total mentions: {total_mentions}\n\n"

        # Value trends summary
        report += "## VALUE TRENDS ACROSS SOURCES\n\n"
        for value, total in sorted(value_trends.items(), key=lambda x: x[1], reverse=True):
            report += f"- {value.capitalize()}: {total} total mentions\n"

        if underexplored:
            report += "\n## UNDEREXPLORED VALUES\n"
            report += ", ".join([v.capitalize() for v in underexplored]) + "\n"

        return report
    
    def search_concepts(self, search_term: str) -> Dict:
        """Search for a concept across all sources."""
        results = {
            'search_term': search_term,
            'direct_matches': [],
            'related_matches': [],
            'sources': []
        }
        
        search_lower = search_term.lower()
        
        # Direct matches
        for concept in self.concept_index:
            if search_lower in concept or concept in search_lower:
                results['direct_matches'].append({
                    'concept': concept,
                    'sources': self.concept_index[concept]
                })
        
        # Related matches (concepts that appear in same sources)
        matched_sources = set()
        for concept_data in results['direct_matches']:
            matched_sources.update(concept_data['sources'])
        
        for concept, sources in self.concept_index.items():
            if concept != search_lower and len(set(sources) & matched_sources) > 0:
                results['related_matches'].append(concept)
        
        # Get sources
        for url in matched_sources:
            results['sources'].append({
                'url': url,
                'title': self.scraped_sources[url]['title'],
                'summary': self.source_summaries.get(url, '')[:200]
            })
        
        return results
    
    def connect_to_human_context(self, human_statement: str) -> str:
        """
        Analyze human statement and find relevant knowledge.
        Shows how the organized knowledge connects to their experience.
        """
        response = "## KNOWLEDGE CONNECTIONS TO YOUR STATEMENT\n\n"
        
        # Find values in their statement
        statement_lower = human_statement.lower()
        found_values = []
        for value in self.tracked_values:
            if value in statement_lower:
                found_values.append(value)
        
        if found_values:
            response += f"**Your Statement Mentions:** {', '.join([v.capitalize() for v in found_values])}\n\n"
            
            # Find relevant sources
            relevant_sources = set()
            for value in found_values:
                if value in self.value_connections:
                    for conn in self.value_connections[value]:
                        relevant_sources.add(conn['url'])
            
            if relevant_sources:
                response += "**Relevant Knowledge I've Learned:**\n\n"
                for url in list(relevant_sources)[:3]:
                    source = self.scraped_sources[url]
                    response += f"- **{source['title']}**\n"
                    if url in self.source_summaries:
                        summary = self.source_summaries[url]
                        # Extract first line of actual summary
                        lines = summary.split('\n')
                        for line in lines:
                            if line.startswith('**Overview:**'):
                                response += f"  {line[13:100]}...\n"
                    response += "\n"
        else:
            response += "I notice you're discussing something I haven't yet studied deeply.\n"
            response += "This is valuable - it means I need to continue learning.\n"
        
        return response
    
    def get_source_summary(self, url: str) -> str:
        """Get the summary for a specific source."""
        if url in self.source_summaries:
            return self.source_summaries[url]
        return f"No summary found for {url}"
