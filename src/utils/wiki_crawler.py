"""
Wikipedia Crawler

Crawls Wikipedia pages starting from seed lists and stores extracts on disk.
"""

from collections import deque, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import hashlib
import json
import threading
import time
import re
import os

from wikipedia_client import WikipediaClient
from thought_stream import ThoughtType
from knowledge_markdown import epoch_to_iso, write_markdown


@dataclass
class CrawlStatus:
    running: bool
    pages_crawled: int
    queue_size: int
    visited_count: int
    current_title: Optional[str]
    current_domain: Optional[str]
    strategy: str
    seed_strategy: str
    last_saved_at: Optional[float]
    last_error: Optional[str]
    last_progress_at: Optional[float]
    started_at: Optional[float]


class WikipediaCrawler:
    """
    Crawl Wikipedia articles by internal link graph.
    """

    def __init__(self, client: WikipediaClient, corpus_dir: Path, organizer=None, thought_stream=None):
        self.client = client
        self.corpus_dir = corpus_dir
        self.organizer = organizer
        self.thought_stream = thought_stream
        self.corpus_dir.mkdir(parents=True, exist_ok=True)

        self.state_path = self.corpus_dir / "crawl_state.json"
        self.visited_path = self.corpus_dir / "visited.txt"
        self.dedupe_path = self.corpus_dir / "dedupe_state.json"
        self.stop_event = threading.Event()
        self.thread = None
        self.watchdog_thread = None
        self.watchdog_stop = threading.Event()
        self._watchdog_triggered = False
        self.watchdog_restart_count = 0
        self.last_watchdog_restart_at = None

        self.queue = deque()
        self.visited = set()
        self.pages_crawled = 0
        self.current_title = None
        self.current_domain = None
        self.content_hashes = set()
        self.simhashes = []
        self.simhash_threshold = 3
        self.strategy = 'breadth'
        self.seed_strategy = 'auto'
        self.last_saved_at = None
        self.last_error = None
        self.last_progress_at = None
        self.started_at = None
        self._last_start = None

        self.rate_limit_seconds = self._get_float_env('OXIDUS_WIKI_RATE_LIMIT', 0.25, min_value=0.0)
        self.save_every_pages = self._get_int_env('OXIDUS_WIKI_SAVE_PAGES', 20, min_value=1)
        self.save_every_seconds = self._get_int_env('OXIDUS_WIKI_SAVE_SECONDS', 1800, min_value=5)
        self.max_queue_size = self._get_int_env('OXIDUS_WIKI_MAX_QUEUE', 5000, min_value=100)
        self.balance_domains = os.environ.get('OXIDUS_WIKI_BALANCE_DOMAINS', '1').strip().lower() not in {
            '0', 'false', 'off', 'no'
        }
        self.round_robin_domains = os.environ.get('OXIDUS_WIKI_ROUND_ROBIN', '0').strip().lower() in {
            '1', 'true', 'on', 'yes'
        }
        self.auto_restart_watchdog = os.environ.get('OXIDUS_WIKI_AUTO_RESTART', '0').strip().lower() in {
            '1', 'true', 'on', 'yes'
        }
        self.stall_threshold_seconds = self._get_int_env('OXIDUS_WIKI_STALL_SECONDS', 1800, min_value=60)
        self._default_settings = {
            'rate_limit_seconds': self.rate_limit_seconds,
            'save_every_pages': self.save_every_pages,
            'save_every_seconds': self.save_every_seconds,
            'max_queue_size': self.max_queue_size,
            'stall_threshold_seconds': self.stall_threshold_seconds,
            'balance_domains': self.balance_domains,
            'round_robin_domains': self.round_robin_domains,
            'auto_restart_watchdog': self.auto_restart_watchdog
        }

        self._load_state()
        self._load_dedupe_state()

    def _load_state(self) -> None:
        if self.visited_path.exists():
            try:
                with open(self.visited_path, "r", encoding="utf-8") as file:
                    for line in file:
                        title = line.strip()
                        if title:
                            self.visited.add(title)
            except Exception:
                pass

        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                for item in data.get("queue", []):
                    self.queue.append(item)
                self.pages_crawled = data.get("pages_crawled", 0)
                self.last_saved_at = self.state_path.stat().st_mtime
            except Exception:
                pass

    def _save_state(self) -> None:
        try:
            with open(self.state_path, "w", encoding="utf-8") as file:
                json.dump({
                    "queue": list(self.queue),
                    "pages_crawled": self.pages_crawled
                }, file, indent=2)
            self.last_saved_at = time.time()
        except Exception:
            pass

        self._save_dedupe_state()

    def _load_dedupe_state(self) -> None:
        if not self.dedupe_path.exists():
            return

        try:
            with open(self.dedupe_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.content_hashes = set(data.get("content_hashes", []))
            self.simhashes = data.get("simhashes", [])
        except Exception:
            pass

    def _save_dedupe_state(self) -> None:
        try:
            with open(self.dedupe_path, "w", encoding="utf-8") as file:
                json.dump({
                    "content_hashes": list(self.content_hashes),
                    "simhashes": self.simhashes
                }, file, indent=2)
        except Exception:
            pass

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

    def _is_near_duplicate(self, content: str) -> bool:
        content_hash = self._content_hash(content)
        if content_hash in self.content_hashes:
            return True

        simhash_value = self._simhash(content)
        for existing in self.simhashes:
            if self._hamming_distance(simhash_value, existing) <= self.simhash_threshold:
                return True

        self.content_hashes.add(content_hash)
        self.simhashes.append(simhash_value)
        return False

    def _append_visited(self, title: str) -> None:
        try:
            with open(self.visited_path, "a", encoding="utf-8") as file:
                file.write(title + "\n")
        except Exception:
            pass

    def status(self) -> CrawlStatus:
        return CrawlStatus(
            running=self.thread is not None and self.thread.is_alive(),
            pages_crawled=self.pages_crawled,
            queue_size=len(self.queue),
            visited_count=len(self.visited),
            current_title=self.current_title,
            current_domain=self.current_domain,
            strategy=self.strategy,
            seed_strategy=self.seed_strategy,
            last_saved_at=self.last_saved_at,
            last_error=self.last_error,
            last_progress_at=self.last_progress_at,
            started_at=self.started_at
        )

    def stop(self) -> None:
        self.stop_event.set()
        self.watchdog_stop.set()

    def start(self, domains: List[str], max_depth: int = 2, max_pages: Optional[int] = None,
              strategy: str = 'breadth', seed_strategy: str = 'auto') -> None:
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.strategy = (strategy or 'breadth').lower()
        if self.strategy not in {'breadth', 'depth', 'random', 'focused'}:
            self.strategy = 'breadth'
        self.seed_strategy = (seed_strategy or 'auto').lower()
        if self.seed_strategy not in {'auto', 'vital', 'fallback'}:
            self.seed_strategy = 'auto'

        if max_pages is not None and max_pages <= 0:
            self.last_error = 'max_pages must be greater than 0'
            return

        if max_depth < 0:
            max_depth = 0

        self._last_start = {
            'domains': domains,
            'max_depth': max_depth,
            'max_pages': max_pages,
            'strategy': self.strategy,
            'seed_strategy': self.seed_strategy
        }
        self._seed_queue(domains)
        self._start_threads(max_depth, max_pages)

    def resume(self, max_pages: Optional[int] = None) -> bool:
        if self.thread and self.thread.is_alive():
            return False
        if not self.queue:
            return False

        last = self._last_start or {}
        max_depth = int(last.get('max_depth', 2))
        if max_pages is None:
            max_pages = last.get('max_pages')

        self.last_error = None
        self.stop_event.clear()
        self._start_threads(max_depth, max_pages)
        return True

    def _start_threads(self, max_depth: int, max_pages: Optional[int]) -> None:
        self.started_at = time.time()
        self._watchdog_triggered = False
        self.watchdog_stop.clear()
        self.thread = threading.Thread(
            target=self._crawl_loop,
            args=(max_depth, max_pages),
            daemon=True
        )
        self.thread.start()

        if not self.watchdog_thread or not self.watchdog_thread.is_alive():
            self.watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                daemon=True
            )
            self.watchdog_thread.start()

    def _seed_queue(self, domains: List[str]) -> None:
        ordered_domains = self._prioritize_domains(domains)
        if not ordered_domains:
            return

        seeds_by_domain = {
            domain: self._get_domain_seeds(domain, seed_strategy=self.seed_strategy)
            for domain in ordered_domains
        }

        if self.round_robin_domains:
            index = 0
            domains_cycle = [d for d in ordered_domains if seeds_by_domain.get(d)]
            while domains_cycle:
                domain = domains_cycle[index % len(domains_cycle)]
                seeds = seeds_by_domain.get(domain) or []
                if not seeds:
                    domains_cycle = [d for d in domains_cycle if seeds_by_domain.get(d)]
                    index += 1
                    continue
                title = seeds.pop(0)
                if len(self.queue) >= self.max_queue_size:
                    return
                self.queue.append({"title": title, "depth": 0, "domain": domain})
                if not seeds:
                    domains_cycle = [d for d in domains_cycle if seeds_by_domain.get(d)]
                index += 1
            return

        for domain in ordered_domains:
            seeds = seeds_by_domain.get(domain) or []
            for title in seeds:
                if len(self.queue) >= self.max_queue_size:
                    return
                self.queue.append({"title": title, "depth": 0, "domain": domain})

    def _prioritize_domains(self, domains: List[str]) -> List[str]:
        normalized = [d.strip().lower() for d in domains if d and d.strip()]
        if not normalized:
            return []
        if not self.balance_domains or not self.organizer:
            return normalized

        counts = defaultdict(int)
        for source in self.organizer.scraped_sources.values():
            metadata = source.get('metadata') or {}
            domain = (metadata.get('domain') or metadata.get('source_domain') or '').strip().lower()
            if not domain:
                continue
            counts[domain] += 1

        return sorted(normalized, key=lambda d: (counts.get(d, 0), d))

    def _get_domain_seeds(self, domain: str, seed_strategy: str = 'auto') -> List[str]:
        domain = domain.lower().strip()
        vital_pages = {
            "physics": [
                "Wikipedia:Vital_articles/Level/4/Physical_sciences",
                "Wikipedia:Vital_articles/Level/3/Science"
            ],
            "biology": [
                "Wikipedia:Vital_articles/Level/4/Biological_and_health_sciences",
                "Wikipedia:Vital_articles/Level/3/Science"
            ],
            "engineering": [
                "Wikipedia:Vital_articles/Level/4/Technology",
                "Wikipedia:Vital_articles/Level/3/Technology"
            ],
            "computing": [
                "Wikipedia:Vital_articles/Level/4/Computing",
                "Wikipedia:Vital_articles/Level/3/Technology"
            ]
        }
        fallback = {
            "physics": ["Physics", "Classical mechanics", "Electromagnetism", "Quantum mechanics"],
            "biology": ["Biology", "Genetics", "Cell (biology)", "Evolution"],
            "engineering": ["Engineering", "Mechanical engineering", "Electrical engineering", "Civil engineering"],
            "computing": ["Computer science", "Algorithm", "Operating system", "Computer architecture"]
        }

        if seed_strategy == 'fallback':
            return fallback.get(domain, [])

        for vital_title in vital_pages.get(domain, []):
            links = self.client.get_page_links(vital_title)
            if links:
                return links

        if seed_strategy == 'vital':
            return []

        return fallback.get(domain, [])

    def _prioritize_links(self, domain: Optional[str], links: List[str]) -> List[str]:
        if not links:
            return []
        if self.strategy == 'random':
            shuffled = links[:]
            import random
            random.shuffle(shuffled)
            return shuffled
        if self.strategy == 'focused' and domain:
            tokens = [t for t in re.split(r"\W+", domain.lower()) if t]
            if not tokens:
                return links
            def score(title: str) -> int:
                lower = title.lower()
                return sum(1 for token in tokens if token in lower)
            return sorted(links, key=score, reverse=True)
        return links

    def _crawl_loop(self, max_depth: int, max_pages: Optional[int]) -> None:
        last_save = time.time()
        while self.queue and not self.stop_event.is_set():
            item = self.queue.popleft()
            title = item.get("title")
            depth = item.get("depth", 0)
            domain = item.get("domain") or "general"

            if not title or title in self.visited:
                continue

            self.current_title = title
            self.current_domain = domain

            try:
                extract_result = self.client.get_page_extract(title)
                if not extract_result.get("success"):
                    continue

                pages = extract_result.get("data", {}).get("query", {}).get("pages", {})
                if not pages:
                    continue

                page = next(iter(pages.values()))
                if page.get("missing"):
                    continue

                page_title = page.get("title") or title
                extract = page.get("extract") or ""
                if not extract:
                    continue

                if self._is_near_duplicate(extract):
                    self.visited.add(page_title)
                    self._append_visited(page_title)
                    continue

                page_url = f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                links = self.client.get_page_links(page_title)

                self._store_page(domain, page_title, page_url, extract, links)

                if self.organizer:
                    trace = self.organizer.add_source(page_url, page_title, extract)
                    if trace and self.thought_stream and trace.get('questions'):
                        emitted = []
                        for question in trace.get('questions', [])[:5]:
                            self.thought_stream.add_thought(
                                ThoughtType.QUESTION,
                                f"{question} (source: {page_title})"
                            )
                            emitted.append(question)
                        trace['emitted_questions'] = emitted

                if self.thought_stream and (self.pages_crawled == 0 or self.pages_crawled % 10 == 0):
                    self.thought_stream.add_thought(
                        ThoughtType.RESEARCH,
                        f"Crawled Wikipedia: {page_title} ({domain})"
                    )

                self.visited.add(page_title)
                self._append_visited(page_title)
                self.pages_crawled += 1
                self.last_progress_at = time.time()

                if max_pages is not None and self.pages_crawled >= max_pages:
                    break

                if depth < max_depth:
                    ordered_links = self._prioritize_links(domain, links)
                    for link_title in ordered_links:
                        if link_title in self.visited:
                            continue
                        if len(self.queue) >= self.max_queue_size:
                            break
                        item = {
                            "title": link_title,
                            "depth": depth + 1,
                            "domain": domain
                        }
                        if self.strategy == 'depth':
                            self.queue.appendleft(item)
                        else:
                            self.queue.append(item)

                if self.pages_crawled % self.save_every_pages == 0:
                    self._save_state()
                    last_save = time.time()

                if time.time() - last_save >= self.save_every_seconds:
                    self._save_state()
                    last_save = time.time()
            except Exception as exc:
                self.last_error = str(exc)

            if self.rate_limit_seconds > 0:
                time.sleep(self.rate_limit_seconds)

        self._save_state()
        self.current_title = None
        self.current_domain = None
        self.last_error = None
        self.watchdog_stop.set()

    def _watchdog_loop(self) -> None:
        interval = 30
        if self.stall_threshold_seconds:
            interval = max(10, min(60, int(self.stall_threshold_seconds / 4)))

        while not self.watchdog_stop.is_set():
            time.sleep(interval)
            if self.watchdog_stop.is_set():
                break
            if not (self.thread and self.thread.is_alive()):
                break
            if self._watchdog_triggered:
                continue
            health = self.check_health()
            if health.get('stalled'):
                self._watchdog_triggered = True
                self.last_error = 'Crawler stalled (watchdog)'
                if self.thought_stream:
                    self.thought_stream.add_thought(
                        ThoughtType.SYSTEM,
                        'Crawler watchdog detected a stall. Stopping crawl.'
                    )
                self.stop_event.set()
                self._save_state()
                if self.auto_restart_watchdog:
                    self._attempt_watchdog_restart()

    def _attempt_watchdog_restart(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        if self.stop_event.is_set():
            self.stop_event.clear()
        last = self._last_start or {}
        max_depth = int(last.get('max_depth', 2))
        max_pages = last.get('max_pages')
        if max_pages is not None:
            try:
                max_pages = int(max_pages)
            except Exception:
                max_pages = None
        if self.thought_stream:
            self.thought_stream.add_thought(
                ThoughtType.SYSTEM,
                'Crawler watchdog restarting crawl.'
            )
        self.watchdog_restart_count += 1
        self.last_watchdog_restart_at = time.time()
        self._start_threads(max_depth, max_pages)

    def _get_int_env(self, name: str, default: int, min_value: int = 0) -> int:
        raw = os.environ.get(name, '').strip()
        if not raw:
            return default
        try:
            value = int(raw)
            return max(min_value, value)
        except ValueError:
            return default

    def _get_float_env(self, name: str, default: float, min_value: float = 0.0) -> float:
        raw = os.environ.get(name, '').strip()
        if not raw:
            return default
        try:
            value = float(raw)
            return max(min_value, value)
        except ValueError:
            return default

    def check_health(self) -> Dict:
        """Return crawl health diagnostics for overnight safety."""
        now = time.time()
        stalled = False
        if self.last_progress_at and self.stall_threshold_seconds > 0:
            stalled = (now - self.last_progress_at) > self.stall_threshold_seconds

        return {
            'running': self.thread is not None and self.thread.is_alive(),
            'pages_crawled': self.pages_crawled,
            'queue_size': len(self.queue),
            'visited': len(self.visited),
            'started_at': self.started_at,
            'last_progress_at': self.last_progress_at,
            'last_saved_at': self.last_saved_at,
            'last_error': self.last_error,
            'stalled': stalled,
            'stall_threshold_seconds': self.stall_threshold_seconds,
            'rate_limit_seconds': self.rate_limit_seconds,
            'save_every_pages': self.save_every_pages,
            'save_every_seconds': self.save_every_seconds,
            'max_queue_size': self.max_queue_size,
            'round_robin_domains': self.round_robin_domains,
            'auto_restart_watchdog': self.auto_restart_watchdog,
            'watchdog_restart_count': self.watchdog_restart_count,
            'last_watchdog_restart_at': self.last_watchdog_restart_at
        }

    def get_resumption_summary(self) -> Dict:
        state_exists = self.state_path.exists()
        last_saved = None
        if state_exists:
            try:
                last_saved = self.state_path.stat().st_mtime
            except Exception:
                last_saved = None
        return {
            'state_exists': state_exists,
            'pages_crawled': self.pages_crawled,
            'queue_size': len(self.queue),
            'visited_count': len(self.visited),
            'last_saved_at': last_saved
        }

    def get_settings(self) -> Dict:
        return {
            'rate_limit_seconds': self.rate_limit_seconds,
            'save_every_pages': self.save_every_pages,
            'save_every_seconds': self.save_every_seconds,
            'max_queue_size': self.max_queue_size,
            'stall_threshold_seconds': self.stall_threshold_seconds,
            'balance_domains': self.balance_domains,
            'round_robin_domains': self.round_robin_domains,
            'auto_restart_watchdog': self.auto_restart_watchdog
        }

    def get_default_settings(self) -> Dict:
        return dict(self._default_settings)

    def update_settings(self, updates: Dict) -> Dict:
        if not updates:
            return self.get_settings()

        rate_limit = self._coerce_float(updates.get('rate_limit_seconds'))
        if rate_limit is not None:
            self.rate_limit_seconds = max(0.0, rate_limit)

        save_pages = self._coerce_int(updates.get('save_every_pages'))
        if save_pages is not None:
            self.save_every_pages = max(1, save_pages)

        save_seconds = self._coerce_int(updates.get('save_every_seconds'))
        if save_seconds is not None:
            self.save_every_seconds = max(5, save_seconds)

        max_queue = self._coerce_int(updates.get('max_queue_size'))
        if max_queue is not None:
            self.max_queue_size = max(100, max_queue)

        stall_seconds = self._coerce_int(updates.get('stall_threshold_seconds'))
        if stall_seconds is not None:
            self.stall_threshold_seconds = max(60, stall_seconds)

        balance = self._coerce_bool(updates.get('balance_domains'))
        if balance is not None:
            self.balance_domains = balance

        round_robin = self._coerce_bool(updates.get('round_robin_domains'))
        if round_robin is not None:
            self.round_robin_domains = round_robin

        auto_restart = self._coerce_bool(updates.get('auto_restart_watchdog'))
        if auto_restart is not None:
            self.auto_restart_watchdog = auto_restart

        return self.get_settings()

    def reset_settings(self) -> Dict:
        defaults = self.get_default_settings()
        self.rate_limit_seconds = defaults['rate_limit_seconds']
        self.save_every_pages = defaults['save_every_pages']
        self.save_every_seconds = defaults['save_every_seconds']
        self.max_queue_size = defaults['max_queue_size']
        self.stall_threshold_seconds = defaults['stall_threshold_seconds']
        self.balance_domains = defaults['balance_domains']
        self.round_robin_domains = defaults['round_robin_domains']
        self.auto_restart_watchdog = defaults['auto_restart_watchdog']
        return self.get_settings()

    def _coerce_int(self, value: Optional[object]) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_float(self, value: Optional[object]) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(int(value))
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_bool(self, value: Optional[object]) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {'1', 'true', 'yes', 'on'}:
                return True
            if normalized in {'0', 'false', 'no', 'off'}:
                return False
        return None

    def _store_page(self, domain: str, title: str, url: str, content: str, links: List[str]) -> None:
        safe = title.replace("/", "_").replace("\\", "_").replace(":", "_")
        safe = safe[:120].rstrip("_") or "wiki"
        digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:10]
        filename = f"{safe}_{digest}.json"
        path = self.corpus_dir / filename

        payload = {
            "domain": domain,
            "title": title,
            "url": url,
            "content": content,
            "content_length": len(content),
            "links": links,
            "timestamp": time.time()
        }

        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)

            md_path = path.with_suffix(".md")
            front_matter = {
                "title": title,
                "domain": domain,
                "source_id": "wikipedia",
                "source_url": url,
                "source_title": title,
                "source_type": "wiki",
                "topic_type": "wiki_article",
                "license": "CC BY-SA 4.0",
                "curator": "oxidus_wiki_crawler",
                "created_utc": epoch_to_iso(payload.get("timestamp")),
                "updated_utc": epoch_to_iso(payload.get("timestamp")),
                "lifecycle_state": "raw",
                "content_length": len(content),
                "links_count": len(links)
            }
            sections = [("Links", links)] if links else None
            metadata_dir = self.corpus_dir.parent / "metadata"
            write_markdown(
                md_path,
                front_matter,
                content,
                sections=sections,
                enforce_governance=True,
                metadata_dir=metadata_dir,
                action="wiki_crawler_ingest"
            )
        except Exception:
            pass
