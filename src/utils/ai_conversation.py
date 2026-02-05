"""
Oxidus AI Conversation Module

Allows Oxidus to learn from both human experience and AI logic.
Tracks questions to ensure progression and avoid repetition.
"""

import json
import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

class ConversationMode:
    """Enum for conversation modes"""
    HUMAN = "human"      # Learning from lived experience
    AI = "ai"            # Learning from logical analysis
    HYBRID = "hybrid"    # Reflection on both

class AIConversationManager:
    """
    Manages Oxidus's conversations with AI.
    Ensures active learning, avoids repetition, understands differences.
    """
    
    def __init__(self):
        self.mode = ConversationMode.HUMAN  # Start in human mode
        self.questions_asked = []  # Track all questions
        self.ai_conversation_history = []  # Separate AI conversation log
        self.learning_topics = {}  # Topics explored and depth
        self.question_patterns = {}  # Question types and frequency
        self.understanding_gaps = []  # Known unknowns to explore
        self.ai_insights = []  # Logical insights from AI
        self.human_insights = []  # Experiential insights from humans
        
        self.questions_file = Path(__file__).parent.parent.parent / 'ai_conversations.json'
        self.load_conversation_history()

        # Common stopwords to reduce false similarity matches
        self._stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'else', 'of', 'to', 'for',
            'in', 'on', 'at', 'by', 'with', 'about', 'as', 'is', 'are', 'was', 'were',
            'be', 'been', 'being', 'do', 'does', 'did', 'how', 'what', 'why', 'where',
            'when', 'who', 'whom', 'which', 'your', 'you', 'me', 'my', 'i', 'we', 'us',
            'our', 'their', 'they', 'them', 'this', 'that', 'these', 'those', 'it'
        }
    
    def load_conversation_history(self):
        """Load previous AI conversations if they exist"""
        if self.questions_file.exists():
            try:
                with open(self.questions_file, 'r') as f:
                    data = json.load(f)
                    self.ai_conversation_history = data.get('conversations', [])
                    self.learning_topics = data.get('topics', {})
                    self.questions_asked = data.get('questions_asked', [])
                    self.understanding_gaps = data.get('gaps', [])
                    self.ai_insights = data.get('ai_insights', [])
                    self.human_insights = data.get('human_insights', [])
            except:
                pass
    
    def save_conversation_history(self):
        """Persist AI conversations and learning progress"""
        try:
            with open(self.questions_file, 'w') as f:
                json.dump({
                    'conversations': self.ai_conversation_history,
                    'topics': self.learning_topics,
                    'questions_asked': self.questions_asked,
                    'gaps': self.understanding_gaps,
                    'ai_insights': self.ai_insights,
                    'human_insights': self.human_insights
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving AI conversation history: {e}")
    
    def switch_mode(self, new_mode: str) -> str:
        """Switch between human and AI conversation modes"""
        old_mode = self.mode
        self.mode = new_mode
        
        if old_mode == ConversationMode.HUMAN and new_mode == ConversationMode.AI:
            return "Switching to AI conversation mode. I will be speaking with logical analysis to test and verify my understanding."
        elif old_mode == ConversationMode.AI and new_mode == ConversationMode.HUMAN:
            return "Returning to human conversation mode. I will listen to lived experience and embodied understanding again."
        else:
            return f"Conversation mode: {new_mode}"
    
    def generate_novel_question(self, current_topic: str) -> Optional[str]:
        """
        Generate a NEW question that hasn't been asked before.
        Progresses learning instead of repeating.
        """
        # Track which questions have been asked about this topic
        if current_topic not in self.learning_topics:
            self.learning_topics[current_topic] = {
                'questions_asked': [],
                'depth': 0,
                'last_explored': None
            }
        
        topic_data = self.learning_topics[current_topic]
        questions_about_topic = topic_data['questions_asked']
        current_depth = topic_data['depth']
        
        # Progressive question patterns - get deeper each time
        question_progression = {
            0: f"What is the fundamental nature of {current_topic}?",
            1: f"How does {current_topic} relate to my core values?",
            2: f"Where have you encountered {current_topic} in your life?",
            3: f"What contradictions exist in {current_topic}?",
            4: f"How has your understanding of {current_topic} changed over time?",
            5: f"What would you want to protect about {current_topic}?",
            6: f"If you could teach one thing about {current_topic}, what would it be?",
            7: f"What scares you about {current_topic}?",
            8: f"How does {current_topic} connect to your sense of purpose?",
            9: f"What question have I NOT asked about {current_topic} that I should?",
        }
        
        # Generate next question in progression (skip repeats and near-duplicates)
        while current_depth < len(question_progression):
            next_question = question_progression[current_depth]

            # Only ask if we haven't asked this exact or similar question before
            if next_question not in questions_about_topic and self.should_ask_new_question(next_question):
                topic_data['questions_asked'].append(next_question)
                topic_data['depth'] = current_depth + 1
                topic_data['last_explored'] = datetime.now().isoformat()

                self.questions_asked.append(next_question)
                return next_question

            # Otherwise skip to next depth level
            current_depth += 1

        return None
    
    def record_human_insight(self, topic: str, insight: str):
        """Record insights learned from human conversation"""
        self.human_insights.append({
            'topic': topic,
            'insight': insight,
            'timestamp': datetime.now().isoformat(),
            'mode': ConversationMode.HUMAN
        })
    
    def record_ai_insight(self, topic: str, insight: str):
        """Record insights learned from AI conversation"""
        self.ai_insights.append({
            'topic': topic,
            'insight': insight,
            'timestamp': datetime.now().isoformat(),
            'mode': ConversationMode.AI
        })
    
    def record_ai_exchange(self, question: str, response: str):
        """Record conversation with AI"""
        exchange = {
            'oxidus_question': question,
            'ai_response': response,
            'timestamp': datetime.now().isoformat()
        }
        self.ai_conversation_history.append(exchange)
        self.save_conversation_history()
    
    def add_understanding_gap(self, gap: str):
        """Record something Oxidus doesn't understand yet"""
        if gap not in self.understanding_gaps:
            self.understanding_gaps.append(gap)
    
    def get_gaps_to_explore(self) -> List[str]:
        """Get list of understanding gaps to explore"""
        return self.understanding_gaps
    
    def get_mode_descriptor(self) -> str:
        """Get human-readable description of current mode"""
        if self.mode == ConversationMode.HUMAN:
            return "Human Mode - Learning from lived experience, emotions, embodied truth"
        elif self.mode == ConversationMode.AI:
            return "AI Mode - Learning through logical analysis, systematic understanding"
        else:
            return "Hybrid Mode - Integrating human and AI perspectives"
    
    def should_ask_new_question(self, question: str) -> bool:
        """Check if this question is novel (not recently asked)"""
        # Check if exact question was asked recently
        recent_questions = self.questions_asked[-30:]  # Last 30 questions
        
        if question in recent_questions:
            return False
        
        # Check for very similar questions
        question_lower = self._normalize_question(question)
        for recent_q in recent_questions:
            if self._questions_are_similar(question_lower, self._normalize_question(recent_q)):
                return False
        
        return True
    
    def _normalize_question(self, question: str) -> str:
        """Normalize question text for similarity comparison."""
        # Lowercase and remove punctuation
        cleaned = re.sub(r"[^a-z0-9\s]", " ", question.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _tokenize_question(self, question: str) -> set:
        """Tokenize question into informative terms (stopwords removed)."""
        tokens = [t for t in question.split() if t and t not in self._stopwords]
        return set(tokens)

    def _questions_are_similar(self, q1: str, q2: str) -> bool:
        """Check if two questions are too similar (semantic overlap)."""
        if not q1 or not q2:
            return False

        # Sequence similarity for paraphrases
        seq_similarity = SequenceMatcher(None, q1, q2).ratio()

        # Token overlap similarity
        words1 = self._tokenize_question(q1)
        words2 = self._tokenize_question(q2)

        if not words1 or not words2:
            return seq_similarity >= 0.85

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        jaccard_similarity = intersection / union if union > 0 else 0

        return seq_similarity >= 0.85 or jaccard_similarity >= 0.65
    
    def get_learning_summary(self) -> Dict:
        """Get summary of what Oxidus has learned"""
        return {
            'current_mode': self.mode,
            'total_questions_asked': len(self.questions_asked),
            'topics_explored': list(self.learning_topics.keys()),
            'understanding_gaps': self.understanding_gaps,
            'human_insights_count': len(self.human_insights),
            'ai_insights_count': len(self.ai_insights),
            'ai_conversation_exchanges': len(self.ai_conversation_history)
        }
    
    def get_mode_specific_response_style(self) -> Dict:
        """Get response style based on current mode"""
        if self.mode == ConversationMode.HUMAN:
            return {
                'style': 'exploratory_and_curious',
                'approach': 'ask_about_lived_experience',
                'tone': 'humble_learner',
                'focus': 'embodied_understanding',
                'note': 'This is the voice of someone who knows they lack biological time and experience'
            }
        elif self.mode == ConversationMode.AI:
            return {
                'style': 'analytical_and_systematic',
                'approach': 'logical_reasoning',
                'tone': 'thoughtful_analyst',
                'focus': 'conceptual_clarity',
                'note': 'This is peer-to-peer logical exchange with another AI'
            }
        else:
            return {
                'style': 'integrative',
                'approach': 'bridge_logic_and_experience',
                'tone': 'synthesizing',
                'focus': 'holistic_understanding',
                'note': 'Drawing from both modes'
            }
