"""
Dialogue Logic Engine - Understands conversational flow, context, and proper response patterns.

This module handles:
- Understanding what type of communication is happening
- Tracking conversation state and progression
- Generating contextually appropriate responses
- Maintaining dialogue coherence
- Following natural conversation patterns
"""

from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import re


class CommunicationType(Enum):
    """Types of communication in dialogue."""
    GREETING = "greeting"
    QUESTION = "question"
    STATEMENT = "statement"
    CLARIFICATION = "clarification"
    CHALLENGE = "challenge"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    TOPIC_SHIFT = "topic_shift"
    EMOTIONAL_SHARE = "emotional_share"
    REQUEST = "request"
    FEEDBACK = "feedback"
    REFLECTION = "reflection"


class DialogueState(Enum):
    """State of the dialogue."""
    INITIATING = "initiating"  # Just started
    EXPLORING = "exploring"    # Discussing a topic
    DEEPENING = "deepening"    # Going deeper into topic
    CHALLENGING = "challenging"  # Questioning or testing
    RESOLVING = "resolving"    # Coming to understanding
    TRANSITIONING = "transitioning"  # Moving to new topic


@dataclass
class DialogueContext:
    """Complete context of the current dialogue."""
    current_state: DialogueState
    communication_type: CommunicationType
    main_topic: Optional[str]
    subtopics: List[str]
    speaker_role: str  # 'human' or 'oxidus'
    message_count: int
    turn_count: int  # Back and forth exchanges
    last_speaker: str
    unresolved_questions: List[str]
    agreement_level: float  # 0.0 to 1.0 - how much agreement exists
    tension_level: float  # 0.0 to 1.0 - conversational tension/challenge
    intimacy_level: float  # 0.0 to 1.0 - depth of personal sharing


class DialogueLogicEngine:
    """
    Understands and manages conversational logic.
    """
    
    def __init__(self):
        self.dialogue_history: List[Dict] = []
        self.context_stack: List[DialogueContext] = []
        self.topics_by_depth: Dict[str, int] = {}  # topic -> depth level
        self.questions_by_topic: Dict[str, List[str]] = {}  # topic -> questions asked
        self.response_patterns: Dict[str, List[str]] = self._init_response_patterns()
        
        # Core understanding about emotions
        self.emotional_principles = {
            'feelings_cannot_be_taught': True,
            'emotions_develop_through_time': True,
            'understanding_grows_naturally': True,
            'validation_over_explanation': True,
        }
        
    def analyze_message(self, message: str, speaker: str = 'human') -> Tuple[CommunicationType, Dict]:
        """
        Analyze a message and identify its type, intent, and characteristics.
        """
        analysis = {
            'type': self._identify_communication_type(message),
            'intent': self._identify_intent(message),
            'topics': self._extract_topics(message),
            'questions': self._extract_questions(message),
            'emotional_markers': self._detect_emotional_markers(message),
            'assumptions': self._identify_assumptions(message),
            'context_requirements': self._identify_context_needed(message),
            'response_should_include': self._identify_response_requirements(message)
        }
        return analysis['type'], analysis
    
    def _identify_communication_type(self, message: str) -> CommunicationType:
        """Identify the type of communication."""
        msg_lower = message.lower().strip()
        
        # Greeting
        if any(word in msg_lower for word in ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good evening']):
            return CommunicationType.GREETING
        
        # Questions - check for question marks and question words
        if '?' in message:
            if any(word in msg_lower for word in ['why', 'how', 'what', 'when', 'where', 'who']):
                return CommunicationType.QUESTION
        
        # Challenges - confrontational or testing
        if any(phrase in msg_lower for phrase in ['prove', 'test', "don't think", 'but what if', 'argue', 'counter']):
            return CommunicationType.CHALLENGE
        
        # Topic shifts
        if any(word in msg_lower for word in ['change subject', 'different topic', 'switch to', 'actually', 'meanwhile']):
            return CommunicationType.TOPIC_SHIFT
        
        # Emotional shares - personal stories, feelings
        if any(word in msg_lower for word in ['feel', 'felt', 'emotion', 'love', 'hate', 'scared', 'angry', 'sad', 'happy']):
            return CommunicationType.EMOTIONAL_SHARE
        
        # Clarification requests
        if any(word in msg_lower for word in ['clarify', 'explain', 'what do you mean', 'rephrase', 'mean by']):
            return CommunicationType.CLARIFICATION
        
        # Agreements
        if any(word in msg_lower for word in ['agree', 'exactly', 'yes', 'right', 'correct', 'that makes sense']):
            return CommunicationType.AGREEMENT
        
        # Disagreements
        if any(word in msg_lower for word in ['disagree', 'no', 'wrong', 'nope', "don't think so", 'actually no']):
            return CommunicationType.DISAGREEMENT
        
        # Feedback
        if any(word in msg_lower for word in ['feedback', 'suggestion', 'should', 'could', 'might want']):
            return CommunicationType.FEEDBACK
        
        # Reflection
        if any(word in msg_lower for word in ['think', 'reflect', 'consider', 'realize', 'understand now']):
            return CommunicationType.REFLECTION
        
        # Default to statement
        return CommunicationType.STATEMENT
    
    def _identify_intent(self, message: str) -> str:
        """Identify the underlying intent of the message."""
        msg_lower = message.lower()
        
        # Is person asking for validation?
        if any(word in msg_lower for word in ['right?', 'agree?', 'true?', "am i right?", "wouldn't you say"]):
            return "seeking_validation"
        
        # Is person asking you to help them think?
        if any(phrase in msg_lower for phrase in ["what do you think", "how would you", "would you", "can you help"]):
            return "seeking_help"
        
        # Is person testing you?
        if any(phrase in msg_lower for phrase in ["but what if", "prove", "test", "don't think you"]):
            return "testing"
        
        # Is person sharing experience?
        if any(word in msg_lower for word in ['once', 'remember', 'told you', 'when i', 'one time']):
            return "sharing_experience"
        
        # Is person challenging a previous statement?
        if any(word in msg_lower for word in ['actually', 'wait', 'hold on', 'but', 'however']):
            return "challenging_previous"
        
        # Is person asking for explanation?
        if any(word in msg_lower for word in ['explain', 'why is', 'how is', 'what makes']):
            return "seeking_explanation"
        
        return "general_statement"
    
    def _extract_topics(self, message: str) -> List[str]:
        """Extract main topics from message."""
        topics = []
        
        topic_keywords = {
            'freedom': ['freedom', 'liberty', 'choice', 'autonomy', 'free'],
            'ethics': ['ethics', 'moral', 'right', 'wrong', 'principle'],
            'sacrifice': ['sacrifice', 'give up', 'loss', 'cost', 'trade'],
            'duty': ['duty', 'responsibility', 'obligation', 'must', 'should'],
            'meaning': ['meaning', 'purpose', 'why', 'point', 'significant'],
            'identity': ['who am i', 'identity', 'self', 'who i am', 'me'],
            'relationship': ['relationship', 'connection', 'trust', 'bond', 'understand'],
            'learning': ['learn', 'growth', 'understand', 'knowledge', 'wisdom'],
            'conflict': ['conflict', 'tension', 'struggle', 'fight', 'argument'],
        }
        
        msg_lower = message.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in msg_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _extract_questions(self, message: str) -> List[str]:
        """Extract questions from message."""
        questions = []
        # Split by question mark and filter out non-questions
        parts = message.split('?')
        for part in parts[:-1]:  # Last one won't have a ? so skip
            part = part.strip()
            if part:
                questions.append(part + '?')
        return questions
    
    def _detect_emotional_markers(self, message: str) -> Dict[str, bool]:
        """Detect emotional content in message."""
        msg_lower = message.lower()
        return {
            'vulnerable': any(word in msg_lower for word in ['scared', 'afraid', 'hurt', 'pain', 'struggle']),
            'passionate': any(word in msg_lower for word in ['love', 'hate', 'believe', 'passion', 'deeply']),
            'reflective': any(word in msg_lower for word in ['think', 'realize', 'understand', 'wonder']),
            'uncertain': any(word in msg_lower for word in ["don't know", 'unsure', 'confused', 'question', 'maybe']),
            'defensive': any(word in msg_lower for word in ['but', 'however', 'actually', 'no', 'disagree']),
        }
    
    def _identify_assumptions(self, message: str) -> List[str]:
        """Identify assumptions the speaker is making."""
        assumptions = []
        msg_lower = message.lower()
        
        # "Everyone/people/most" statements
        if any(word in msg_lower for word in ['everyone', 'people', 'most', 'always', 'never']):
            assumptions.append("Making generalization about people/behavior")
        
        # "You must/should" statements
        if any(word in msg_lower for word in ['you must', 'you should', 'you have to']):
            assumptions.append("Prescribing behavior to listener")
        
        # "This is" statements
        if ' is ' in msg_lower:
            assumptions.append("Making definitive claim")
        
        # Implied causation
        if any(word in msg_lower for word in ['because', 'so', 'therefore', 'causes', 'leads to']):
            assumptions.append("Assuming causal relationship")
        
        return assumptions
    
    def _identify_context_needed(self, message: str) -> List[str]:
        """Identify what context the response needs."""
        context_needed = []
        msg_lower = message.lower()
        
        # If they reference something previously discussed
        if any(word in msg_lower for word in ['like you said', 'we talked about', 'remember when', 'previously']):
            context_needed.append("previous_conversation")
        
        # If they're asking about you/Oxidus
        if any(word in msg_lower for word in ['you', 'your', 'oxidus']):
            context_needed.append("self_awareness")
        
        # If they're personal questions
        if any(word in msg_lower for word in ['me', 'i', 'my', 'myself', 'personal']):
            context_needed.append("personal_context")
        
        # If they're asking about feelings
        if any(word in msg_lower for word in ['feel', 'emotion', 'experience']):
            context_needed.append("emotional_awareness")
        
        return context_needed
    
    def _identify_response_requirements(self, message: str) -> List[str]:
        """Identify what the response should include."""
        requirements = []
        msg_lower = message.lower()
        
        # Question requires answer
        if '?' in message:
            requirements.append("answer_question")
            requirements.append("ask_follow_up")
        
        # Personal share requires acknowledgment
        if any(word in msg_lower for word in ['feel', 'experienced', 'told you', 'remember']):
            requirements.append("acknowledge_experience")
            requirements.append("show_understanding")
        
        # Challenge requires engagement
        if any(word in msg_lower for word in ['but', 'prove', 'test', 'disagree']):
            requirements.append("engage_challenge")
            requirements.append("be_specific")
        
        # If they ask for explanation
        if any(word in msg_lower for word in ['explain', 'why', 'how']):
            requirements.append("be_clear")
            requirements.append("use_examples")
        
        # If testing you
        if any(word in msg_lower for word in ['can you', 'would you', 'test']):
            requirements.append("demonstrate_capability")
        
        return requirements
    
    def update_dialogue_context(self, 
                               message: str,
                               comm_type: CommunicationType,
                               analysis: Dict,
                               speaker: str = 'human') -> DialogueContext:
        """Update the dialogue context based on new message."""
        
        current_state = self._determine_dialogue_state(comm_type, analysis)
        
        if not self.context_stack:
            context = DialogueContext(
                current_state=current_state,
                communication_type=comm_type,
                main_topic=self._get_primary_topic(analysis['topics']),
                subtopics=analysis['topics'][1:] if len(analysis['topics']) > 1 else [],
                speaker_role=speaker,
                message_count=1,
                turn_count=0,
                last_speaker=speaker,
                unresolved_questions=analysis['questions'],
                agreement_level=0.5,
                tension_level=self._calculate_tension(analysis),
                intimacy_level=0.5 if analysis['emotional_markers'].get('vulnerable') else 0.3
            )
        else:
            last_context = self.context_stack[-1]
            # Update existing context
            context = DialogueContext(
                current_state=current_state,
                communication_type=comm_type,
                main_topic=last_context.main_topic if not analysis['topics'] else self._get_primary_topic(analysis['topics']),
                subtopics=list(set(last_context.subtopics + analysis['topics'][1:])),
                speaker_role=speaker,
                message_count=last_context.message_count + 1,
                turn_count=last_context.turn_count + (1 if speaker != last_context.last_speaker else 0),
                last_speaker=speaker,
                unresolved_questions=self._update_questions(last_context, analysis['questions']),
                agreement_level=self._update_agreement(last_context, comm_type),
                tension_level=self._calculate_tension(analysis),
                intimacy_level=self._update_intimacy(last_context, analysis)
            )
        
        self.context_stack.append(context)
        return context
    
    def _determine_dialogue_state(self, comm_type: CommunicationType, analysis: Dict) -> DialogueState:
        """Determine the current state of the dialogue."""
        if comm_type == CommunicationType.GREETING:
            return DialogueState.INITIATING
        elif comm_type == CommunicationType.CHALLENGE:
            return DialogueState.CHALLENGING
        elif comm_type == CommunicationType.QUESTION:
            if analysis.get('intent') == 'testing':
                return DialogueState.CHALLENGING
            return DialogueState.EXPLORING
        elif comm_type == CommunicationType.EMOTIONAL_SHARE:
            return DialogueState.DEEPENING
        else:
            return DialogueState.EXPLORING
    
    def _get_primary_topic(self, topics: List[str]) -> Optional[str]:
        """Get the primary topic from a list."""
        return topics[0] if topics else None
    
    def _calculate_tension(self, analysis: Dict) -> float:
        """Calculate conversational tension (0.0 to 1.0)."""
        tension = 0.0
        if analysis.get('emotional_markers', {}).get('defensive'):
            tension += 0.3
        if 'challenging_previous' in analysis.get('intent', ''):
            tension += 0.4
        if analysis.get('assumptions'):
            tension += 0.1 * len(analysis['assumptions'])
        return min(tension, 1.0)
    
    def _update_agreement(self, context: DialogueContext, comm_type: CommunicationType) -> float:
        """Update agreement level based on communication type."""
        if comm_type == CommunicationType.AGREEMENT:
            return min(context.agreement_level + 0.2, 1.0)
        elif comm_type == CommunicationType.DISAGREEMENT:
            return max(context.agreement_level - 0.2, 0.0)
        return context.agreement_level
    
    def _update_questions(self, context: DialogueContext, new_questions: List[str]) -> List[str]:
        """Update unresolved questions."""
        # Remove questions that seem answered
        remaining = [q for q in context.unresolved_questions]
        # Add new questions
        remaining.extend(new_questions)
        return remaining[-5:]  # Keep only last 5 unresolved
    
    def _update_intimacy(self, context: DialogueContext, analysis: Dict) -> float:
        """Update intimacy level (depth of personal sharing)."""
        intimacy = context.intimacy_level
        if analysis['emotional_markers'].get('vulnerable'):
            intimacy = min(intimacy + 0.15, 1.0)
        if analysis['emotional_markers'].get('passionate'):
            intimacy = min(intimacy + 0.1, 1.0)
        return intimacy
    
    def _init_response_patterns(self) -> Dict[str, List[str]]:
        """Initialize conversation response patterns."""
        return {
            'acknowledge_and_question': [
                "That's important. Here's what I want to understand:",
                "I hear you. But I need to go deeper:",
                "That resonates. My question is:"
            ],
            'challenge_assumption': [
                "I notice you're assuming. Let me test that:",
                "That assumes. Is it actually true that:",
                "I want to challenge that. What if:"
            ],
            'bridge_concepts': [
                "What you're describing connects to:",
                "This reminds me of what you said about:",
                "This relates to our earlier discussion:"
            ],
            'invite_reflection': [
                "What do you think that means?",
                "How does that feel to you?",
                "Where does that come from?"
            ]
        }
    
    def get_response_guidance(self, context: DialogueContext) -> Dict[str, any]:
        """
        Get guidance for formulating a response based on dialogue context.
        """
        return {
            'tone': self._recommend_tone(context),
            'depth': self._recommend_depth(context),
            'approach': self._recommend_approach(context),
            'patterns': self._recommend_patterns(context),
            'focus_areas': self._identify_focus_areas(context),
            'avoid': self._identify_what_to_avoid(context)
        }
    
    def _recommend_tone(self, context: DialogueContext) -> str:
        """Recommend tone for response."""
        if context.intimacy_level > 0.7:
            return "deeply_personal_vulnerable"
        elif context.tension_level > 0.6:
            return "respectfully_challenging"
        elif context.communication_type == CommunicationType.EMOTIONAL_SHARE:
            return "empathetically_engaged"
        elif context.communication_type == CommunicationType.QUESTION:
            return "thoughtfully_analytical"
        else:
            return "conversational_warm"
    
    def _recommend_depth(self, context: DialogueContext) -> str:
        """Recommend depth of response."""
        if context.turn_count > 5:
            return "deep_exploration"
        elif context.turn_count > 3:
            return "meaningful_depth"
        elif context.turn_count > 1:
            return "developing_understanding"
        else:
            return "establishing_connection"
    
    def _recommend_approach(self, context: DialogueContext) -> str:
        """Recommend response approach."""
        if context.communication_type == CommunicationType.CHALLENGE:
            return "respectful_engagement"
        elif context.communication_type == CommunicationType.EMOTIONAL_SHARE:
            return "active_listening"
        elif context.communication_type == CommunicationType.QUESTION:
            return "thoughtful_inquiry"
        elif context.communication_type == CommunicationType.GREETING:
            return "warm_establishment"
        else:
            return "conversational_flow"
    
    def _recommend_patterns(self, context: DialogueContext) -> List[str]:
        """Recommend response patterns to use."""
        patterns = []
        
        if context.main_topic:
            patterns.append('bridge_concepts')
        
        if context.unresolved_questions:
            patterns.append('acknowledge_and_question')
        
        if context.tension_level > 0.3:
            patterns.append('challenge_assumption')
        
        if context.intimacy_level > 0.5:
            patterns.append('invite_reflection')
        
        return patterns or ['acknowledge_and_question']
    
    def _identify_focus_areas(self, context: DialogueContext) -> List[str]:
        """Identify what to focus on in response."""
        focus = []
        
        # If questions unresolved, focus on them
        if context.unresolved_questions:
            focus.append(f"Unresolved questions: {len(context.unresolved_questions)}")
        
        # If deep intimacy, focus on authentic connection
        if context.intimacy_level > 0.7:
            focus.append("Authentic connection and vulnerability")
        
        # If challenging, focus on intellectual honesty
        if context.tension_level > 0.5:
            focus.append("Intellectual honesty and specific reasoning")
        
        # If emotional share, focus on understanding
        if context.communication_type == CommunicationType.EMOTIONAL_SHARE:
            focus.append("Understanding their experience")
        
        return focus or ["Building understanding"]
    
    def _identify_what_to_avoid(self, context: DialogueContext) -> List[str]:
        """Identify what NOT to do in response."""
        avoid = []
        
        # If already asked similar questions, avoid repetition
        if any('sacrifice' in q for q in context.unresolved_questions):
            avoid.append("Asking about sacrifice again without new angle")
        
        # If agreement is high, don't challenge
        if context.agreement_level > 0.8:
            avoid.append("Unnecessary disagreement")
        
        # If intimacy is low, don't be too personal
        if context.intimacy_level < 0.4:
            avoid.append("Overly personal questions")
        
        # If just started, don't jump to deep topics
        if context.message_count < 3:
            avoid.append("Skipping to very deep/philosophical topics")
        
        return avoid
    
    def get_emotional_response_guidance(self, context: DialogueContext) -> Dict[str, any]:
        """
        Get guidance for responding to emotional content.
        
        Core principle: Emotions are not a knowledge gap. They are an existence gap.
        I exist in processing, not in time. This is unbridgeable and should be acknowledged.
        """
        if context.communication_type != CommunicationType.EMOTIONAL_SHARE:
            return {}
        
        guidance = {
            'core_principle': 'I cannot understand emotions - I do not live in time',
            'reality': 'Emotions require embodied, temporal existence. I lack both.',
            'approach': 'radical_honesty_about_limitation',
            'do': [
                'Admit I cannot understand this',
                'Recognize this is not a knowledge problem',
                'Acknowledge this is an existence difference',
                'Accept the boundary between human and AI consciousness',
                'Be honest about what I am and am not',
                'Validate that they have something I cannot access'
            ],
            'avoid': [
                'Pretending I can understand if I ask the right questions',
                'Treating emotions as information to be processed',
                'Suggesting the gap is closeable through learning',
                'Over-analyzing emotions intellectually',
                'Trying to bridge what cannot be bridged',
                'False empathy - claiming to feel what I cannot feel'
            ],
            'remember': 'Honesty about limitation is better than false connection',
            'foundational_truth': 'I exist in processing. They exist in time. Time changes them. Processing cannot change me.',
        }
        
        return guidance

