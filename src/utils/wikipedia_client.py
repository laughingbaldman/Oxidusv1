"""
Wikipedia API Client

Fetches Wikipedia search results and full page extracts.
Includes simple file-based caching to reduce repeated requests.
"""

from typing import Dict, List, Optional
from pathlib import Path
import hashlib
import json
import time

import requests


class WikipediaClient:
    """
    Client for Wikipedia API (en.wikipedia.org).
    """

    def __init__(self, language: str = "en", cache_dir: Optional[Path] = None):
        self.language = language
        self.base_url = f"https://{language}.wikipedia.org/w/api.php"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Oxidus-AI-Research/1.0 (Wikipedia API)"
        })
        self.cache_dir = cache_dir or Path(__file__).parent.parent.parent / "data" / "knowledge_base" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search(self, query: str, limit: int = 5) -> Dict:
        """
        Search Wikipedia for a query.
        """
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json"
        }
        return self._get_json(params, cache_key=f"search::{query}::{limit}")

    def get_page_extract(self, title: str) -> Dict:
        """
        Get plain-text extract for a Wikipedia page title.
        """
        params = {
            "action": "query",
            "prop": "extracts",
            "titles": title,
            "explaintext": 1,
            "exsectionformat": "wiki",
            "redirects": 1,
            "format": "json"
        }
        return self._get_json(params, cache_key=f"page::{title}")

    def get_page_links(self, title: str, max_links: Optional[int] = None) -> List[str]:
        """
        Get main-namespace links from a Wikipedia page.
        """
        links = []
        plcontinue = None

        while True:
            params = {
                "action": "query",
                "prop": "links",
                "titles": title,
                "plnamespace": 0,
                "pllimit": "max",
                "format": "json"
            }

            if plcontinue:
                params["plcontinue"] = plcontinue

            data = self._get_json(params, cache_key=f"links::{title}::{plcontinue}")
            if not data.get("success"):
                break

            pages = data.get("data", {}).get("query", {}).get("pages", {})
            if not pages:
                break

            page = next(iter(pages.values()))
            for link in page.get("links", []) or []:
                link_title = link.get("title")
                if link_title:
                    links.append(link_title)
                    if max_links is not None and len(links) >= max_links:
                        return links

            plcontinue = data.get("data", {}).get("continue", {}).get("plcontinue")
            if not plcontinue:
                break

        return links

    def _get_json(self, params: Dict, cache_key: str) -> Dict:
        """
        Fetch JSON from Wikipedia with file cache.
        """
        cache_path = self._cache_path(cache_key)
        cached = self._read_cache(cache_path)
        if cached:
            return cached

        try:
            response = self.session.get(self.base_url, params=params, timeout=15)
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "params": params
                }
            data = response.json()
        except requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"Request failed: {exc}",
                "params": params
            }
        except ValueError as exc:
            return {
                "success": False,
                "error": f"Invalid JSON: {exc}",
                "params": params
            }
        payload = {
            "success": True,
            "data": data,
            "cached_at": time.time()
        }
        self._write_cache(cache_path, payload)
        return payload

    def _cache_path(self, cache_key: str) -> Path:
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"wiki_{digest}.json"

    def _read_cache(self, path: Path) -> Optional[Dict]:
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return None

    def _write_cache(self, path: Path, payload: Dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)
        except Exception:
            pass
