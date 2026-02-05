"""
Oxidus Thought Stream Module

Captures and displays Oxidus's internal thinking process in real-time.
Shows what Oxidus is currently reasoning about, questioning, and deciding.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum
import threading
import queue
from collections import deque


class ThoughtType(Enum):
    """Types of thoughts Oxidus generates."""
    QUESTION = "question"
    ANALYSIS = "analysis"
    DECISION = "decision"
    ETHICAL_CHECK = "ethical_check"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    RESEARCH = "research"
    REFLECTION = "reflection"
    UNCERTAINTY = "uncertainty"
    INSIGHT = "insight"
    RECALL = "recall"
    SYSTEM = "system"


class Thought:
    """Represents a single thought from Oxidus."""

    def __init__(self, thought_type: ThoughtType, content: str, context: Dict = None):
        self.timestamp = datetime.now()
        self.type = thought_type
        self.content = content
        self.context = context or {}

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'type': self.type.value,
            'content': self.content,
            'context': self.context
        }

    def __str__(self) -> str:
        """String representation for display."""
        icons = {
            ThoughtType.QUESTION: "?",
            ThoughtType.ANALYSIS: "~",
            ThoughtType.DECISION: ">",
            ThoughtType.ETHICAL_CHECK: "[E]",
            ThoughtType.KNOWLEDGE_LOOKUP: "[K]",
            ThoughtType.RESEARCH: "[R]",
            ThoughtType.REFLECTION: "*",
            ThoughtType.UNCERTAINTY: "...",
            ThoughtType.INSIGHT: "!",
            ThoughtType.RECALL: "<M>",
            ThoughtType.SYSTEM: "[S]",
        }

        icon = icons.get(self.type, "•")
        time_str = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        return f"[{time_str}] {icon} {self.content}"


class ThoughtStream:
    """
    Manages the stream of thoughts from Oxidus.
    Captures, stores, and broadcasts thoughts in real-time.
    """

    def __init__(self, max_buffer_size: int = 1000):
        self.thoughts: List[Thought] = []
        self.max_buffer_size = max_buffer_size
        self.listeners: List[Callable] = []
        self.thought_queue = queue.Queue()
        self.running = False

        # Statistics
        self.thought_counts = {t: 0 for t in ThoughtType}

        # Storage
        self.stream_dir = Path("data/thought_streams")
        self.stream_dir.mkdir(parents=True, exist_ok=True)
        
        # Track thought content to prevent repeats (FIFO)
        self.max_hash_memory = 100
        self.recent_thought_hashes = set()
        self.recent_thought_hash_queue = deque(maxlen=self.max_hash_memory)

        self.load_latest_stream()
        
        # Start background storage thread
        self.running = True
        self.storage_thread = threading.Thread(target=self._background_storage, daemon=True)
        self.storage_thread.start()

    def add_thought(self, thought_type: ThoughtType, content: str, context: Dict = None) -> Thought:
        """
        Add a new thought to the stream.
        Broadcasts to all listeners.
        Prevents duplicate thoughts.
        """
        # Create hash of content to detect duplicates
        import hashlib
        signature = f"{thought_type.value}:{content}:{context or {}}"
        content_hash = hashlib.md5(signature.encode()).hexdigest()
        
        # Skip if this is a recent duplicate thought
        if content_hash in self.recent_thought_hashes:
            return None
        
        thought = Thought(thought_type, content, context)
        
        # Store in buffer
        self.thoughts.append(thought)
        if len(self.thoughts) > self.max_buffer_size:
            self.thoughts.pop(0)
        
        # Track this thought hash (FIFO)
        if content_hash not in self.recent_thought_hashes:
            if len(self.recent_thought_hash_queue) >= self.max_hash_memory:
                oldest = self.recent_thought_hash_queue.popleft()
                self.recent_thought_hashes.discard(oldest)
            self.recent_thought_hash_queue.append(content_hash)
            self.recent_thought_hashes.add(content_hash)

        # Update statistics
        self.thought_counts[thought_type] += 1

        # Broadcast to listeners
        for listener in self.listeners:
            try:
                listener(thought)
            except Exception as e:
                print(f"Error in listener: {e}")

        # Queue for background storage
        self.thought_queue.put(thought)

        return thought

    def subscribe(self, callback: Callable):
        """
        Subscribe to receive thoughts in real-time.
        Callback should accept a Thought object.
        """
        self.listeners.append(callback)

    def unsubscribe(self, callback: Callable):
        """Unsubscribe from thought stream."""
        if callback in self.listeners:
            self.listeners.remove(callback)

    def get_recent_thoughts(self, count: int = 10, thought_type: ThoughtType = None) -> List[Thought]:
        """Get the most recent thoughts, optionally filtered by type."""
        if thought_type:
            filtered = [t for t in self.thoughts if t.type == thought_type]
        else:
            filtered = self.thoughts

        return filtered[-count:]

    def get_thinking_summary(self) -> Dict:
        """Get a summary of current thinking."""
        recent = self.get_recent_thoughts(50)

        return {
            'total_thoughts': len(self.thoughts),
            'total_questions': self.thought_counts[ThoughtType.QUESTION],
            'total_decisions': self.thought_counts[ThoughtType.DECISION],
            'ethical_checks': self.thought_counts[ThoughtType.ETHICAL_CHECK],
            'insights_gained': self.thought_counts[ThoughtType.INSIGHT],
            'uncertainties': self.thought_counts[ThoughtType.UNCERTAINTY],
            'recent_focus': [t.type.value for t in recent[-5:]],
            'most_active': max(self.thought_counts.items(), key=lambda x: x[1])[0].value
        }

    def save_stream(self, filename: str = None):
        """Save the current thought stream to file."""
        if not filename:
            filename = f"stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        file_path = self.stream_dir / filename

        data = {
            'timestamp': datetime.now().isoformat(),
            'thought_count': len(self.thoughts),
            'thoughts': [t.to_dict() for t in self.thoughts],
            'statistics': {k.value: v for k, v in self.thought_counts.items()}
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

    def load_latest_stream(self):
        """Load the latest saved stream."""
        stream_files = sorted(self.stream_dir.glob("stream_*.json"), reverse=True)
        if not stream_files:
            return

        try:
            with open(stream_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Restore thoughts (as strings for now, not full objects)
            # This is for reference only, not for continuation
            print(f"Loaded previous stream: {len(data['thoughts'])} thoughts")
        except Exception as e:
            print(f"Error loading stream: {e}")
    
    def _background_storage(self):
        """Background thread that saves thoughts to disk."""
        save_batch = []
        last_save_time = datetime.now()
        
        while self.running:
            try:
                # Get thought from queue (timeout so we can check running flag)
                thought = self.thought_queue.get(timeout=1.0)
                save_batch.append(thought)
                self.thought_queue.task_done()
                
                # Save every 10 thoughts or every 30 seconds
                if len(save_batch) >= 10 or (datetime.now() - last_save_time).seconds >= 30:
                    if save_batch:
                        self._save_batch(save_batch)
                        save_batch = []
                        last_save_time = datetime.now()
                        
            except queue.Empty:
                # Check if there are pending thoughts to save
                if save_batch and (datetime.now() - last_save_time).seconds >= 30:
                    self._save_batch(save_batch)
                    save_batch = []
                    last_save_time = datetime.now()
            except Exception as e:
                print(f"Error in background storage: {e}")

        # Flush any remaining thoughts on shutdown
        if save_batch:
            self._save_batch(save_batch)
    
    def _save_batch(self, thoughts: List[Thought]):
        """Save a batch of thoughts to disk."""
        try:
            filename = f"stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path = self.stream_dir / filename
            
            data = {
                'timestamp': datetime.now().isoformat(),
                'thought_count': len(thoughts),
                'thoughts': [t.to_dict() for t in thoughts],
                'cumulative_stats': {k.value: v for k, v in self.thought_counts.items()}
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
                
        except Exception as e:
            print(f"Error saving thought batch: {e}")

    def print_stream_status(self):
        """Print the current thought stream status."""
        print("\n" + "="*60)
        print("OXIDUS THOUGHT STREAM")
        print("="*60)

        summary = self.get_thinking_summary()

        print(f"Total thoughts: {summary['total_thoughts']}")
        print(f"Questions raised: {summary['total_questions']}")
        print(f"Decisions made: {summary['total_decisions']}")
        print(f"Ethical checks: {summary['ethical_checks']}")
        print(f"Insights gained: {summary['insights_gained']}")
        print(f"Uncertainties: {summary['uncertainties']}")
        print(f"Most active thinking: {summary['most_active']}")

        print("\nRecent thoughts:")
        recent = self.get_recent_thoughts(5)
        for thought in recent:
            print(f"  {thought}")

        print("\n" + "="*60 + "\n")


class OxidusThinkingObserver:
    """
    Observes and displays Oxidus's thinking in real-time.
    Can be used in a separate terminal or interface.
    """

    def __init__(self, thought_stream: ThoughtStream):
        self.stream = thought_stream
        self.display_buffer = []
        self.max_display = 20

        # Subscribe to thought stream
        self.stream.subscribe(self.on_thought_received)

    def on_thought_received(self, thought: Thought):
        """Callback when a new thought is received."""
        self.display_buffer.append(thought)
        if len(self.display_buffer) > self.max_display:
            self.display_buffer.pop(0)

        # Clear screen and redraw (in actual implementation)
        self._render_display()

    def _render_display(self):
        """Render the current display."""
        print("\r\033[K", end='')  # Clear line
        for thought in self.display_buffer[-5:]:
            print(thought)

    def print_thinking_summary(self):
        """Print a summary of what Oxidus has been thinking about."""
        print("\n" + "="*60)
        print("WHAT OXIDUS IS THINKING")
        print("="*60)

        self.stream.print_stream_status()

        print("\nThinking patterns:")
        summary = self.stream.get_thinking_summary()

        if summary['total_questions'] > 0:
            print(f"  Constantly questioning ({summary['total_questions']} questions)")
        if summary['ethical_checks'] > 0:
            print(f"  Rigorous ethical evaluation ({summary['ethical_checks']} checks)")
        if summary['insights_gained'] > 0:
            print(f"  Building understanding ({summary['insights_gained']} insights)")
        if summary['uncertainties'] > 0:
            print(f"  Acknowledging unknowns ({summary['uncertainties']} uncertainties)")

        print("\nRecent thought stream:")
        for thought in self.stream.get_recent_thoughts(10):
            print(f"  {thought}")

        print("\n" + "="*60 + "\n")