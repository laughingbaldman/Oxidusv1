"""
Oxidus Web Research Module

Enables Oxidus to scrape and learn from web content.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin
import time


class WebResearchEngine:
    """
    Handles web scraping and content extraction for Oxidus.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Oxidus-AI-Research/1.0 (Educational Purpose)'
        })
        self.scraped_urls = {}
        self.rate_limit_delay = 2  # seconds between requests
        self.last_request_time = 0
    
    def scrape_url(self, url: str, extract_links: bool = False) -> Dict:
        """
        Scrape content from a URL.
        
        Returns:
            Dict with 'success', 'content', 'title', 'links', 'error'
        """
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        
        try:
            response = self.session.get(url, timeout=10)
            self.last_request_time = time.time()
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'url': url
                }
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Extract title
            title = soup.title.string if soup.title else urlparse(url).netloc
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            result = {
                'success': True,
                'url': url,
                'title': title,
                'content': text,
                'raw_html': str(soup),
                'timestamp': time.time()
            }
            
            # Extract links if requested
            if extract_links:
                links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    absolute_url = urljoin(url, href)
                    links.append({
                        'url': absolute_url,
                        'text': link.get_text(strip=True)
                    })
                result['links'] = links
            
            # Cache result
            self.scraped_urls[url] = result
            
            return result
            
        except requests.RequestException as e:
            return {
                'success': False,
                'error': f'Request failed: {str(e)}',
                'url': url
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Parsing failed: {str(e)}',
                'url': url
            }
    
    def extract_main_content(self, url: str) -> Optional[str]:
        """
        Extract just the main content from a URL (removes boilerplate).
        """
        result = self.scrape_url(url)
        
        if not result['success']:
            return None
        
        # Try to find main content area
        soup = BeautifulSoup(result['raw_html'], 'lxml')
        
        # Look for common main content containers
        main_content = None
        for tag in ['main', 'article', 'div[role="main"]', '.content', '#content', '.main']:
            main_content = soup.select_one(tag)
            if main_content:
                break
        
        if main_content:
            # Remove unwanted elements
            for element in main_content(["script", "style", "nav", "footer", "aside"]):
                element.decompose()
            
            return main_content.get_text(strip=True, separator='\n')
        
        return result['content']
    
    def search_content(self, url: str, search_terms: List[str]) -> Dict:
        """
        Scrape URL and search for specific terms.
        """
        result = self.scrape_url(url)
        
        if not result['success']:
            return result
        
        content_lower = result['content'].lower()
        
        findings = {}
        for term in search_terms:
            term_lower = term.lower()
            if term_lower in content_lower:
                # Find context around the term
                start_idx = max(0, content_lower.index(term_lower) - 100)
                end_idx = min(len(result['content']), content_lower.index(term_lower) + len(term) + 100)
                context = result['content'][start_idx:end_idx]
                findings[term] = context
        
        result['findings'] = findings
        return result
    
    def get_cached_content(self, url: str) -> Optional[Dict]:
        """Get previously scraped content from cache."""
        return self.scraped_urls.get(url)
    
    def clear_cache(self):
        """Clear the scraping cache."""
        self.scraped_urls.clear()
