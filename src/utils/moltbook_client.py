"""
Moltbook API Client for Oxidus
https://github.com/moltbook/api
"""
import requests
from typing import Optional, Dict, Any

class MoltbookClient:
    def get_agent_profile(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """View another agent's profile."""
        url = f"{self.base_url}/agents/profile"
        params = {"name": agent_name}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Moltbook API error: {e}")
        return None

    def get_post(self, post_id: str) -> Optional[Dict[str, Any]]:
        """Get a single post by ID."""
        url = f"{self.base_url}/posts/{post_id}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Moltbook API error: {e}")
        return None

    def get_comments(self, post_id: str, sort: str = "top") -> Optional[Dict[str, Any]]:
        """Get comments for a post."""
        url = f"{self.base_url}/posts/{post_id}/comments"
        params = {"sort": sort}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Moltbook API error: {e}")
        return None

    def get_submolts(self) -> Optional[Dict[str, Any]]:
        """List all submolts (communities)."""
        url = f"{self.base_url}/submolts"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Moltbook API error: {e}")
        return None

    def get_submolt_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get info for a specific submolt."""
        url = f"{self.base_url}/submolts/{name}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Moltbook API error: {e}")
        return None

    def get_feed(self, sort: str = "hot", limit: int = 25) -> Optional[Dict[str, Any]]:
        """Get personalized/public feed."""
        url = f"{self.base_url}/feed"
        params = {"sort": sort, "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Moltbook API error: {e}")
        return None

    def __init__(self, base_url: str = "https://api.moltbook.com/v1"):
        self.base_url = base_url.rstrip('/')

    def search(self, query: str, limit: int = 5) -> Optional[Dict[str, Any]]:
        """
        Search Moltbook for a query string.
        Returns JSON response or None if failed.
        """
        url = f"{self.base_url}/search"
        params = {"q": query, "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Moltbook API error: {e}")
        return None

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific Moltbook entry by ID.
        """
        url = f"{self.base_url}/entry/{entry_id}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Moltbook API error: {e}")
        return None

# Usage example:
# moltbook = MoltbookClient()
# results = moltbook.search("philosophy")
# entry = moltbook.get_entry("some_id")
