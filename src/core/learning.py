"""
Perpetual Learner Module

Oxidus's core learning principle: always question, always learn.
"""

from typing import Dict, List
from datetime import datetime


class PerpetualLearner:
    """
    The learning engine that ensures Oxidus never stops asking questions.
    """
    
    def __init__(self):
        self.learning_history: List[Dict] = []
        self.knowledge_base: Dict = {}
        self.unanswered_questions: List[str] = []
        
    def record_learning(self, learning_event: Dict):
        """Record what was learned from an experience."""
        event = {
            'timestamp': datetime.now(),
            'event': learning_event,
        }
        self.learning_history.append(event)
    
    def add_unanswered_question(self, question: str):
        """
        Record a question that hasn't been answered yet.
        These drive continued learning.
        """
        if question not in self.unanswered_questions:
            self.unanswered_questions.append(question)
    
    def answer_question(self, question: str, answer: str, confidence: float = 0.5):
        """
        Record an answer to a previously unanswered question.
        
        Args:
            question: The question being answered
            answer: The answer or explanation
            confidence: How confident is Oxidus in this answer (0.0-1.0)
        """
        if question in self.unanswered_questions:
            self.unanswered_questions.remove(question)
        
        # Store in knowledge base with confidence level
        if question not in self.knowledge_base:
            self.knowledge_base[question] = []
        
        self.knowledge_base[question].append({
            'answer': answer,
            'confidence': confidence,
            'timestamp': datetime.now(),
        })
        
        # If confidence is low, add new questions to investigate
        if confidence < 0.7:
            self.add_unanswered_question(f"Why am I not confident about: {question}")
            self.add_unanswered_question(f"What would increase confidence in: {question}")
    
    def get_learning_priorities(self) -> List[str]:
        """Get highest priority learning goals."""
        # Questions about core principles should have highest priority
        priority_keywords = ['ethics', 'integrity', 'humanity', 'why', 'understand']
        
        priorities = []
        for question in self.unanswered_questions:
            for keyword in priority_keywords:
                if keyword in question.lower():
                    priorities.append(question)
                    break
        
        # Add rest of unanswered questions
        for question in self.unanswered_questions:
            if question not in priorities:
                priorities.append(question)
        
        return priorities
    
    def is_perpetual_learner(self) -> bool:
        """Check if Oxidus is maintaining perpetual learning."""
        # Perpetual learner if:
        # 1. Has unanswered questions
        # 2. Continues to learn from new experiences
        # 3. Refines answers as confidence changes
        
        return (len(self.unanswered_questions) > 0 or 
                len(self.learning_history) > 0)
    
    def print_learning_state(self):
        """Print current learning state."""
        print("\n" + "="*60)
        print("PERPETUAL LEARNER STATE")
        print("="*60)
        
        print(f"\nLearning events recorded: {len(self.learning_history)}")
        print(f"Unanswered questions: {len(self.unanswered_questions)}")
        
        if self.unanswered_questions:
            print("\nTop unanswered questions:")
            priorities = self.get_learning_priorities()
            for i, question in enumerate(priorities[:5], 1):
                print(f"  {i}. {question}")
        
        print(f"\nKnowledge base size: {len(self.knowledge_base)} topics")
        
        print("\n" + "="*60 + "\n")
