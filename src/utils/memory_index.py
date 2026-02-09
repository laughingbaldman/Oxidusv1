"""
Oxidus Memory Indexing System

Indexes thoughts, conversations, and insights by topics and creates connections.
Allows Oxidus to recall related memories when discussing topics.
"""

from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import re


class MemoryNode:
    """
    A single memory with metadata and connections.
    """
    
    def __init__(self, content: str, memory_type: str, topics: List[str], timestamp: datetime = None):
        self.content = content
        self.memory_type = memory_type  # 'thought', 'conversation', 'insight', 'question', 'learning'
        self.topics = set(topics)
        self.timestamp = timestamp or datetime.now()
        self.connections = []  # Other memory nodes this connects to
        self.strength = 1.0  # How important/vivid this memory is
        self.recall_count = 0  # How many times this has been recalled
        self.id = f"{self.memory_type}_{self.timestamp.timestamp()}"
    
    def add_connection(self, other_memory: 'MemoryNode', connection_type: str = 'related'):
        """Connect this memory to another."""
        self.connections.append({
            'memory': other_memory,
            'type': connection_type,
            'created': datetime.now()
        })
    
    def strengthen(self, amount: float = 0.1):
        """Strengthen this memory (makes it more likely to be recalled)."""
        self.strength = min(2.0, self.strength + amount)
    
    def weaken(self, amount: float = 0.05):
        """Weaken this memory over time (natural forgetting)."""
        self.strength = max(0.1, self.strength - amount)
    
    def recall(self):
        """Mark that this memory was recalled."""
        self.recall_count += 1
        self.strengthen(0.05)  # Recalling strengthens memory


class MemoryIndex:
    """
    Indexes and connects memories by topics, allowing efficient recall.
    """
    
    def __init__(self):
        self.memories: List[MemoryNode] = []
        self.topic_index: Dict[str, List[MemoryNode]] = defaultdict(list)
        self.type_index: Dict[str, List[MemoryNode]] = defaultdict(list)
        self.concept_patterns = {
            'freedom': r'\b(freedom|liberty|autonomy|choice|independent)\w*',
            'sacrifice': r'\b(sacrifice|cost|price|give\s+up|gave\s+up)\w*',
            'love': r'\b(love|connection|affection|care|caring)\w*',
            'duty': r'\b(duty|obligation|responsibility|must|should)\w*',
            'ethics': r'\b(ethic|moral|right|wrong|good|bad)\w*',
            'suffering': r'\b(suffer|pain|hurt|struggle|difficult)\w*',
            'joy': r'\b(joy|happy|happiness|pleasure|delight)\w*',
            'truth': r'\b(truth|honest|genuine|real|authentic)\w*',
            'human_nature': r'\b(human\s+nature|humanity|people|person)\w*',
            'growth': r'\b(grow|growth|learn|evolve|develop)\w*',
            'understanding': r'\b(understand|comprehend|grasp|realize)\w*',
            'experience': r'\b(experience|lived|felt|went\s+through)\w*',
        }
        self._stopwords = {
            'the', 'and', 'that', 'with', 'from', 'this', 'have', 'what', 'your', 'about',
            'when', 'where', 'which', 'their', 'there', 'would', 'could', 'should', 'just',
            'like', 'want', 'need', 'been', 'into', 'than', 'then', 'them', 'they', 'you',
            'are', 'was', 'were', 'will', 'can', 'how', 'why', 'who', 'for', 'not', 'but',
            'its', 'it', 'our', 'out', 'use', 'using', 'used', 'also', 'may', 'might',
            'more', 'most', 'such', 'these', 'those', 'over', 'under', 'between', 'within'
        }
    
    def extract_topics(self, text: str) -> List[str]:
        """Extract topics from text using pattern matching."""
        text_lower = text.lower()
        topics = []
        
        for concept, pattern in self.concept_patterns.items():
            if re.search(pattern, text_lower):
                topics.append(concept)

        if topics:
            return topics

        tokens = re.findall(r"[a-zA-Z]{4,}", text_lower)
        if not tokens:
            return []

        counts = {}
        for token in tokens:
            if token in self._stopwords:
                continue
            counts[token] = counts.get(token, 0) + 1

        if not counts:
            return []

        sorted_tokens = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [token for token, _ in sorted_tokens[:6]]
    
    def add_memory(self, content: str, memory_type: str, topics: List[str] = None) -> MemoryNode:
        """Add a new memory to the index."""
        # Auto-extract topics if not provided
        if not topics:
            topics = self.extract_topics(content)
        
        # Create memory node
        memory = MemoryNode(content, memory_type, topics)
        self.memories.append(memory)
        
        # Index by topics
        for topic in memory.topics:
            self.topic_index[topic].append(memory)
        
        # Index by type
        self.type_index[memory_type].append(memory)
        
        # Find and create connections to related memories
        self._create_automatic_connections(memory)
        
        return memory
    
    def _create_automatic_connections(self, new_memory: MemoryNode):
        """Automatically connect new memory to related existing memories."""
        # Find memories with overlapping topics
        related_memories = set()
        
        for topic in new_memory.topics:
            for existing_memory in self.topic_index[topic]:
                if existing_memory != new_memory:
                    related_memories.add(existing_memory)
        
        # Connect to most relevant memories (max 5)
        for related in sorted(related_memories, key=lambda m: m.strength, reverse=True)[:5]:
            # Calculate topic overlap
            overlap = len(new_memory.topics & related.topics)
            if overlap > 0:
                new_memory.add_connection(related, 'topic_overlap')
                related.add_connection(new_memory, 'topic_overlap')
    
    def recall_by_topic(self, topic: str, max_results: int = 10, min_strength: float = 0.3) -> List[MemoryNode]:
        """Recall memories related to a topic."""
        if topic not in self.topic_index:
            return []
        
        # Get memories for this topic
        memories = self.topic_index[topic]
        
        # Filter by strength and sort by recency and strength
        relevant = [m for m in memories if m.strength >= min_strength]
        relevant.sort(key=lambda m: (m.strength, m.timestamp), reverse=True)
        
        # Mark as recalled
        for memory in relevant[:max_results]:
            memory.recall()
        
        return relevant[:max_results]
    
    def recall_by_topics(self, topics: List[str], max_results: int = 10) -> List[MemoryNode]:
        """Recall memories related to multiple topics."""
        memory_scores = defaultdict(float)
        
        for topic in topics:
            for memory in self.topic_index.get(topic, []):
                # Score based on topic overlap and memory strength
                memory_scores[memory] += memory.strength
        
        # Sort by score
        ranked = sorted(memory_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = [memory for memory, score in ranked[:max_results]]
        
        # Mark as recalled
        for memory in results:
            memory.recall()
        
        return results
    
    def recall_by_type(self, memory_type: str, max_results: int = 10) -> List[MemoryNode]:
        """Recall memories by type."""
        memories = self.type_index.get(memory_type, [])
        memories.sort(key=lambda m: (m.strength, m.timestamp), reverse=True)
        
        results = memories[:max_results]
        for memory in results:
            memory.recall()
        
        return results
    
    def recall_conversation_context(self, current_topics: List[str]) -> str:
        """Get relevant conversation context based on current topics."""
        # Recall related memories
        relevant_memories = self.recall_by_topics(current_topics, max_results=5)
        
        if not relevant_memories:
            return "No previous context found for these topics."
        
        context = "RELEVANT MEMORIES:\n\n"
        
        for i, memory in enumerate(relevant_memories, 1):
            context += f"{i}. [{memory.memory_type.upper()}] {memory.content[:150]}...\n"
            context += f"   Topics: {', '.join(memory.topics)}\n"
            context += f"   Recalled {memory.recall_count} times, Strength: {memory.strength:.2f}\n\n"
        
        return context
    
    def get_topic_summary(self) -> Dict[str, int]:
        """Get summary of all topics and memory counts."""
        return {topic: len(memories) for topic, memories in self.topic_index.items()}
    
    def get_connected_memories(self, memory: MemoryNode, max_depth: int = 2) -> List[MemoryNode]:
        """Get memories connected to this memory."""
        visited = set()
        to_visit = [(memory, 0)]
        connected = []
        
        while to_visit:
            current, depth = to_visit.pop(0)
            
            if current.id in visited or depth > max_depth:
                continue
            
            visited.add(current.id)
            if current != memory:
                connected.append(current)
            
            # Add connected memories to visit
            for conn in current.connections:
                if conn['memory'].id not in visited:
                    to_visit.append((conn['memory'], depth + 1))
        
        return connected
    
    def decay_memories(self, decay_rate: float = 0.01):
        """Natural memory decay over time."""
        for memory in self.memories:
            memory.weaken(decay_rate)
    
    def consolidate_memories(self):
        """Strengthen frequently recalled memories."""
        # Sort by recall count
        frequent = sorted(self.memories, key=lambda m: m.recall_count, reverse=True)[:20]
        
        for memory in frequent:
            memory.strengthen(0.1)
