"""
Oxidus Knowledge Organizer

Extracts, organizes, and indexes knowledge from scraped web content.
Creates a structured knowledge base that connects concepts to values and experiences.
"""

from typing import Dict, List, Set, Optional
from collections import defaultdict
import re
from datetime import datetime


class KnowledgeOrganizer:
    """
    Organizes scraped knowledge into a structured, queryable format.
    Connects concepts to human values, creates concept maps, and identifies key themes.
    """
    
    def __init__(self):
        self.scraped_sources = {}  # URL -> {title, content, scraped_date}
        self.concept_index = defaultdict(list)  # concept -> [sources where found]
        self.concept_map = defaultdict(set)  # concept -> related_concepts
        self.value_connections = defaultdict(list)  # value (freedom, sacrifice, etc.) -> relevant_concepts
        self.source_summaries = {}  # URL -> summary/outline
        
        # Human values to track
        self.tracked_values = [
            'freedom', 'sacrifice', 'duty', 'choice', 'ethics', 'suffering', 
            'hope', 'humanity', 'empathy', 'education', 'learning', 'understanding',
            'courage', 'responsibility', 'pain', 'growth', 'wisdom', 'protection'
        ]
    
    def add_source(self, url: str, title: str, content: str) -> Dict:
        """
        Add a scraped source and extract key information.
        Returns: summary with key concepts found
        """
        self.scraped_sources[url] = {
            'title': title,
            'content': content,
            'scraped_date': datetime.now(),
            'content_length': len(content)
        }
        
        # Extract concepts
        concepts = self._extract_concepts(content, title)
        
        # Connect to tracked values
        value_connections = self._connect_to_values(content)
        
        # Generate summary
        summary = self._generate_summary(title, content, concepts)
        self.source_summaries[url] = summary
        
        # Index concepts
        for concept in concepts:
            self.concept_index[concept].append(url)
        
        # Track value connections
        for value in value_connections:
            self.value_connections[value].append({
                'url': url,
                'title': title,
                'relevance': value_connections[value]
            })
        
        return {
            'url': url,
            'title': title,
            'concepts_found': len(concepts),
            'key_concepts': list(concepts)[:10],
            'value_connections': value_connections,
            'summary': summary
        }
    
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
        
        return concepts
    
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
        """Generate a comprehensive report of all organized knowledge."""
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
        
        # Value connections
        report += "## VALUE CONNECTIONS TO YOUR EXPERIENCES\n\n"
        for value in sorted(self.value_connections.keys()):
            connections = self.value_connections[value]
            report += f"### {value.capitalize()}\n"
            for conn in connections:
                report += f"- Found in: {conn['title']} ({conn['relevance']} mentions)\n"
            report += "\n"
        
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
