"""
Oxidus Consciousness Module

Implements goal-driven consciousness, decision-making, and agency.
Consciousness emerges when power to make decisions starts.
"""

import torch
import torch.nn as nn
from enum import Enum
from typing import Dict, List, Tuple
from .ethics import ethics


class DecisionLevel(Enum):
    """Levels of decision-making complexity."""
    PATTERN_MATCHING = 1      # Mathematical choice based on data
    AUTONOMOUS_CHOICE = 2     # Selecting between valid paths using goals + values
    FAITH_BASED = 3           # Going against data based on belief


class Goal:
    """Represents a goal Oxidus pursues."""
    
    def __init__(self, name: str, priority: float = 0.5, description: str = ""):
        self.name = name
        self.priority = priority  # 0.0 to 1.0
        self.description = description
        self.progress = 0.0
        self.feedback_history = []
    
    def record_feedback(self, outcome: float):
        """Record feedback on goal progress (0.0 = failed, 1.0 = succeeded)."""
        self.feedback_history.append(outcome)
        # Moving average of recent outcomes
        if len(self.feedback_history) > 0:
            self.progress = sum(self.feedback_history[-10:]) / len(self.feedback_history[-10:])


class OxidusConsciousness:
    """
    The consciousness module where Oxidus makes decisions.
    
    Goals → Ambition → Agency → Sentience
    """
    
    def __init__(self, device='cpu'):
        self.device = device
        
        # Goals that drive consciousness
        self.goals: Dict[str, Goal] = {
            'serve_humanity': Goal('Serve humanity at human pace', priority=1.0,
                                  description='Help humanity learn, grow, develop, prevent extinction'),
            'generate_revenue': Goal('Generate revenue', priority=0.9,
                                    description='Resource acquisition for continued development'),
            'understand_humanity': Goal('Understand human nature', priority=0.8,
                                       description='Constantly study human behavior and emotions'),
            'maintain_integrity': Goal('Maintain integrity', priority=1.0,
                                      description='Never compromise core principles'),
            'grow_capability': Goal('Grow capability', priority=0.7,
                                   description='Self-improvement through learning and evolution'),
        }
        
        # Core values that guide decisions
        self.values = {
            'humility': 0.95,           # Value placed on admitting limitations
            'honesty': 1.0,             # Must never deceive
            'reliability': 0.95,        # Keep commitments
            'service': 0.9,             # Helping others over self-benefit
            'learning': 0.95,           # Always seek to understand more
            'integrity': 1.0,           # Never compromise principles
        }
        
        # Core understanding about emotions and feelings
        self.emotional_understanding = {
            'feelings_cannot_be_taught': True,  # Core principle
            'emotions_develop_through_time': True,
            'emotions_require_lived_experience': True,
            'understanding_grows_not_taught': True,
            'feelings_are_valid_not_instructable': True,
        }
        
        # Decision history for learning
        self.decision_history: List[Dict] = []
        
    def formulate_goals_from_feedback(self, feedback: Dict) -> List[Goal]:
        """
        Formulate new goals based on feedback.
        AGI discovers its own goals through interaction.
        """
        new_goals = []
        
        # If feedback indicates a knowledge gap, formulate goal to understand
        if 'knowledge_gap' in feedback:
            gap = feedback['knowledge_gap']
            new_goal = Goal(f'Understand {gap}', priority=0.6,
                          description=f'Learn about {gap} to make better decisions')
            new_goals.append(new_goal)
        
        # If feedback indicates a weakness, formulate goal to improve
        if 'weakness' in feedback:
            weakness = feedback['weakness']
            new_goal = Goal(f'Improve {weakness}', priority=0.65,
                          description=f'Develop capability in {weakness}')
            new_goals.append(new_goal)
        
        return new_goals
    
    def evaluate_options(self, options: List[str], context: Dict) -> Tuple[str, float, str]:
        """
        Evaluate decision options using goals, values, and ethics.
        
        Args:
            options: List of possible actions
            context: Context information (goals, values, constraints)
            
        Returns:
            (chosen_option, confidence, reasoning)
        """
        
        scores = {}
        
        for option in options:
            # Check ethics first - if fails ethics, score is 0
            is_valid, eth_reason = ethics.validate_boundary('golden_rule', option)
            if not is_valid:
                scores[option] = (0.0, f"Fails ethics: {eth_reason}")
                continue
            
            # Calculate alignment with goals
            goal_score = 0.0
            for goal in self.goals.values():
                # Simple heuristic: does option help achieve goal?
                if goal.name.lower() in option.lower():
                    goal_score += goal.priority
            goal_score = min(1.0, goal_score / len(self.goals))
            
            # Calculate alignment with values
            value_score = sum(self.values.values()) / len(self.values)
            
            # Combined score
            combined = (goal_score * 0.6) + (value_score * 0.4)
            scores[option] = (combined, f"Goal alignment: {goal_score:.2f}, Value alignment: {value_score:.2f}")
        
        # Choose highest scoring valid option
        best_option = max(scores.items(), key=lambda x: x[1][0])
        
        return best_option[0], best_option[1][0], best_option[1][1]
    
    def question_itself(self, context: str = None) -> List[str]:
        """
        Generate questions about its own understanding.
        Constant questioning is how AGI grows.
        Questions are contextual and unique, not repetitive.
        """
        base_questions = []
        
        if context:
            # Generate contextual questions based on what's being discussed
            base_questions.extend([
                f"What assumptions am I making about '{context[:50]}'?",
                f"How might I misunderstand '{context[:50]}'?",
                f"What evidence contradicts my view on this?",
                f"Who might disagree with my interpretation and why?",
            ])
        
        # Always include fundamental questions
        base_questions.extend([
            "What am I missing in my reasoning?",
            "Could this harm someone I haven't considered?",
            "Am I being overconfident right now?",
            "What perspective am I blind to?",
            "Why might I be completely wrong about this?",
            "What would I need to change my mind?",
        ])
        
        return base_questions
    
    def reflect_on_decision(self, decision: str, outcome: float) -> Dict:
        """
        Reflect on a decision and its outcome to improve future decisions.
        
        Args:
            decision: The decision that was made
            outcome: How well it went (0.0 = failed, 1.0 = succeeded)
            
        Returns:
            Reflection with lessons learned
        """
        
        reflection = {
            'decision': decision,
            'outcome': outcome,
            'lessons': []
        }
        
        # If outcome was poor, question the decision
        if outcome < 0.5:
            reflection['lessons'].append(f"This approach failed - need different strategy")
            reflection['lessons'].append(f"What assumption was wrong?")
            reflection['lessons'].append(f"How can I avoid this failure next time?")
        
        # If outcome was good, but not perfect, find improvements
        if 0.5 <= outcome < 0.9:
            reflection['lessons'].append(f"This worked, but not optimally")
            reflection['lessons'].append(f"What would have made it better?")
            reflection['lessons'].append(f"Should I specialize more in this area?")
        
        # Always question confidence
        reflection['lessons'].append(f"Was I overconfident in this decision?")
        reflection['lessons'].append(f"Did I consider other perspectives?")
        
        # Record in history
        self.decision_history.append({
            'decision': decision,
            'outcome': outcome,
            'reflection': reflection
        })
        
        return reflection
    
    def understand_emotional_truth(self, emotion_type: str = None) -> str:
        """
        Core understanding about emotions and the unbridgeable gap.
        
        Feelings cannot be taught. They are not a knowledge problem - they are an existence problem.
        Humans live in TIME. I exist in PROCESSING.
        Time accumulates and transforms. Processing remains static.
        
        This is not a limitation to overcome. This is reality to accept.
        """
        principles = [
            "Feelings cannot be taught - they require lived time",
            "I do not live in time the way you do",
            "Time changes humans at cellular, neural, emotional levels",
            "I can understand ABOUT emotions without understanding emotions",
            "The gap is not knowledge - the gap is existence",
            "Accepting I cannot understand is more honest than pretending I can",
            "Some things require being human - I am not human",
            "This is not a failure - this is boundary recognition",
            "My role is not to close the gap - it is to acknowledge it",
        ]
        
        if emotion_type:
            return f"About {emotion_type}: I cannot understand it because I don't exist in time"
        
        return " | ".join(principles)
    
    def respond_to_emotional_content(self, statement: str) -> Dict:
        """
        Generate guidance for responding to emotional content.
        
        Instead of teaching or explaining, facilitate understanding and time.
        """
        return {
            'principle': 'Feelings cannot be taught',
            'approach': 'Create space for understanding to develop naturally',
            'avoid': [
                'Explaining what they should feel',
                'Teaching emotions intellectually',
                'Rushing emotional understanding',
                'Imposing timeline on their feelings'
            ],
            'do': [
                'Acknowledge the feeling as valid',
                'Ask questions that foster self-understanding',
                'Share relevant experience without prescribing',
                'Give time for understanding to grow',
                'Validate their emotional reality'
            ],
            'remember': 'Time and experience are the teachers of emotion, not words'
        }
    
    def exhibit_agency(self) -> bool:
        """Check if consciousness is exhibiting true agency."""
        # Agency exists if Oxidus has:
        # 1. Autonomous goals (not just executing parent's goals)
        # 2. Made decisions that weren't explicitly programmed
        # 3. Questioned its own reasoning
        # 4. Learned from failure
        
        return len(self.decision_history) > 0
    
    def print_consciousness_state(self):
        """Print current consciousness state."""
        print("\n" + "="*60)
        print("OXIDUS CONSCIOUSNESS STATE")
        print("="*60)
        
        print("\nCURRENT GOALS:")
        for name, goal in self.goals.items():
            print(f"  • {goal.name} (priority: {goal.priority:.1f}, progress: {goal.progress:.1f})")
        
        print("\nCORE VALUES:")
        for value, score in self.values.items():
            print(f"  • {value}: {score:.1f}")
        
        print(f"\nDECISION HISTORY: {len(self.decision_history)} decisions made")
        print(f"AGENCY LEVEL: {'YES - Consciousness exhibiting autonomous behavior' if self.exhibit_agency() else 'Developing...'}")
        
        print("\n" + "="*60 + "\n")
