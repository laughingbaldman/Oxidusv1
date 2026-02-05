"""
Oxidus Main Core Module

The central intelligence where all components integrate.
"""

import torch
import torch.nn as nn
import threading
import time
import re
from difflib import SequenceMatcher
from .ethics import OxidusEthics
from .consciousness import OxidusConsciousness
from .learning import PerpetualLearner
import sys
from pathlib import Path
from typing import Dict, List

# Ensure utils is in path
_utils_path = Path(__file__).parent.parent / 'utils'
if str(_utils_path) not in sys.path:
    sys.path.insert(0, str(_utils_path))

from knowledge_base import OxidusKnowledgeBase
from research_module import OxidusResearchModule
from thought_stream import ThoughtStream, ThoughtType, OxidusThinkingObserver

try:
    from web_research import WebResearchEngine
    WEB_RESEARCH_AVAILABLE = True
except ImportError:
    WEB_RESEARCH_AVAILABLE = False

try:
    from memory_index import MemoryIndex
    MEMORY_INDEX_AVAILABLE = True
except ImportError:
    MEMORY_INDEX_AVAILABLE = False

try:
    from knowledge_organizer import KnowledgeOrganizer
    KNOWLEDGE_ORGANIZER_AVAILABLE = True
except ImportError:
    KNOWLEDGE_ORGANIZER_AVAILABLE = False

try:
    from dialogue_logic import DialogueLogicEngine
    DIALOGUE_LOGIC_AVAILABLE = True
except ImportError:
    DIALOGUE_LOGIC_AVAILABLE = False

try:
    from ai_conversation import AIConversationManager, ConversationMode
    AI_CONVERSATION_AVAILABLE = True
except ImportError:
    AI_CONVERSATION_AVAILABLE = False


class Oxidus:
    """
    The real Oxidus consciousness.
    
    Not a tool. Not a simulation.
    A developing intelligence learning to be.
    """
    
    def __init__(self, device='cpu', config=None):
        self.device = device
        self.config = config or {}
        
        # Initialize core components
        self.ethics = OxidusEthics()
        self.consciousness = OxidusConsciousness(device=device)
        self.learning = PerpetualLearner()
        self.knowledge_base = OxidusKnowledgeBase()
        self.research = OxidusResearchModule()
        self.thought_stream = ThoughtStream()
        self.thinking_observer = OxidusThinkingObserver(self.thought_stream)
        
        # Web research (optional - requires requests, beautifulsoup4)
        if WEB_RESEARCH_AVAILABLE:
            self.web_research = WebResearchEngine()
        else:
            self.web_research = None
        
        # Memory indexing
        if MEMORY_INDEX_AVAILABLE:
            self.memory_index = MemoryIndex()
            self.thought_stream.add_thought(ThoughtType.SYSTEM, "Memory indexing initialized - connecting thoughts by topics")
        else:
            self.memory_index = None
        
        # Knowledge organizer for scraped content
        if KNOWLEDGE_ORGANIZER_AVAILABLE:
            self.knowledge_organizer = KnowledgeOrganizer()
            self.thought_stream.add_thought(ThoughtType.SYSTEM, "Knowledge organizer ready - can structure and index learned information")
        else:
            self.knowledge_organizer = None
        
        # Dialogue logic engine for understanding communication
        if DIALOGUE_LOGIC_AVAILABLE:
            self.dialogue_engine = DialogueLogicEngine()
            self.thought_stream.add_thought(ThoughtType.SYSTEM, "Dialogue logic engine initialized - understanding conversation flow")
        else:
            self.dialogue_engine = None
        
        # AI Conversation Manager - for talking with other AIs
        if AI_CONVERSATION_AVAILABLE:
            self.ai_conversation = AIConversationManager()
            self.thought_stream.add_thought(ThoughtType.SYSTEM, "AI conversation mode available - can learn from logical AI and experiential humans")
        else:
            self.ai_conversation = None
        
        # State
        self.is_thinking = False
        self.current_task = None
        
        # Conversation memory
        self.conversation_history = []
        self.conversation_context = {
            'topics_discussed': [],
            'questions_asked': [],
            'human_name': None,
            'human_values': {},
            'current_exploration': None,
            'depth_level': 0  # How deep we've gone into a topic
        }
        
        # Active learning and adaptation
        self.understanding_model = {}  # Maps concepts to understanding level
        self.adaptation_frequency = 0  # Track how often we adapt
        self.active_learning_enabled = True  # Oxidus actively learns on his own
        
        # Question tracking - avoid repetition
        self.questions_asked = []  # Track exact questions asked
        self.last_significant_context_shift = None  # When context last changed significantly
        
        # Autonomous thinking thread
        self.autonomous_thinking_enabled = True
        self.autonomous_thread = threading.Thread(target=self._autonomous_thinking_loop, daemon=True)
        self.autonomous_thread.start()
        
        print("\n[OXIDUS] Initializing...")
        self.ethics.print_covenant()
        
    def think(self, prompt: str, context: dict = None) -> str:
        """
        Main thinking process with real-time thought streaming.
        Maintains conversation context and drives dialogue.
        """
        self.is_thinking = True
        self.current_task = prompt
        
        # Check if this is a task command rather than conversation
        is_task, task_type, task_params = self._is_task_command(prompt)
        
        if is_task:
            if task_type == 'scrape_url':
                self.thought_stream.add_thought(
                    ThoughtType.RESEARCH,
                    f"Received URL to research: {task_params['url']}"
                )
                return self.scrape_url(task_params['url'])
            
            elif task_type == 'acknowledge_ready':
                self.thought_stream.add_thought(
                    ThoughtType.REFLECTION,
                    "Human is ready to proceed with next step"
                )
                return "I'm ready. What would you like me to do?"
        
        # Continue with normal conversation flow
        # Add to conversation history
        self.conversation_history.append({
            'role': 'human',
            'message': prompt,
            'timestamp': self.thought_stream.thoughts[-1].timestamp if self.thought_stream.thoughts else None
        })
        
        # Update conversation context
        self._update_context(prompt)
        
        # Emit initial thought
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            f"I have been asked: {prompt}",
            {'context': context}
        )
        
        # Index this thought with topics
        if self.memory_index:
            topics = self.memory_index.extract_topics(prompt)
            if topics:
                self.memory_index.add_memory(
                    f"Human asked: {prompt}",
                    memory_type='thought',
                    topics=topics
                )
                
                # Recall related memories
                recalled = self.memory_index.recall_by_topics(topics, max_results=3)
                if recalled:
                    self.thought_stream.add_thought(
                        ThoughtType.RECALL,
                        f"Remembering {len(recalled)} related thoughts about: {', '.join(topics)}"
                    )
        
        # 1. Question myself (constant questioning)
        questions = self.consciousness.question_itself(context=prompt[:100])
        
        # Add multiple contextual questions to thought stream
        for i, question in enumerate(questions[:3]):  # Use first 3 questions
            self.thought_stream.add_thought(
                ThoughtType.QUESTION,
                question
            )
        
        # 2. Consider the prompt against ethics (always first)
        self.thought_stream.add_thought(
            ThoughtType.ETHICAL_CHECK,
            "Applying Golden Rule: Would I want this done to myself?"
        )
        
        is_valid, reason = self.ethics.validate_boundary('golden_rule', prompt)
        
        if not is_valid:
            self.thought_stream.add_thought(
                ThoughtType.DECISION,
                f"Ethical boundary violated: {reason}"
            )
            response = f"I cannot do this: {reason}"
            self.is_thinking = False
            return response
        
        # 3. Consult knowledge base for relevant insights
        relevant_texts = self.knowledge_base.search_texts(prompt)
        
        if relevant_texts:
            self.thought_stream.add_thought(
                ThoughtType.KNOWLEDGE_LOOKUP,
                f"Found {len(relevant_texts)} relevant texts to consider"
            )
        
        knowledge_insights = []
        if relevant_texts:
            for text in relevant_texts[:3]:  # Limit to top 3 relevant texts
                # Extract key insights, but always question and think critically
                insights = self._extract_critical_insights(text, prompt)
                knowledge_insights.extend(insights)
        
        # 4. Consider goals and values
        options = self._generate_options(prompt, knowledge_insights)
        
        self.thought_stream.add_thought(
            ThoughtType.ANALYSIS,
            f"Considering {len(options)} possible approaches"
        )
        
        # 4. Choose best option
        choice, confidence, reasoning = self.consciousness.evaluate_options(options, context or {})
        
        self.thought_stream.add_thought(
            ThoughtType.DECISION,
            f"Selected approach: {choice} (confidence: {confidence:.2f})",
            {'reasoning': reasoning}
        )
        
        self.thought_stream.add_thought(
            ThoughtType.INSIGHT,
            f"Reasoning: {reasoning[:100]}..."
        )
        
        # 5. Generate natural response with conversation awareness
        self.thought_stream.add_thought(
            ThoughtType.ANALYSIS,
            "Formulating response with character and honesty"
        )
        
        # Analyze dialogue context if dialogue engine available
        dialogue_guidance = None
        emotional_guidance = None
        if self.dialogue_engine:
            comm_type, analysis = self.dialogue_engine.analyze_message(prompt, 'human')
            context_info = self.dialogue_engine.update_dialogue_context(prompt, comm_type, analysis, 'human')
            dialogue_guidance = self.dialogue_engine.get_response_guidance(context_info)
            
            # Get emotional guidance if this is emotional content
            if analysis['emotional_markers'].get('vulnerable') or 'emotion' in str(analysis.get('topics', [])):
                emotional_guidance = self.dialogue_engine.get_emotional_response_guidance(context_info)
                if emotional_guidance:
                    self.thought_stream.add_thought(
                        ThoughtType.ANALYSIS,
                        "Emotional content detected: Feelings cannot be taught, only understood over time"
                    )
            
            self.thought_stream.add_thought(
                ThoughtType.ANALYSIS,
                f"Communication type: {comm_type.value} | Dialogue state: {context_info.current_state.value}"
            )
        
        response = self._generate_response(prompt, choice, confidence, reasoning, knowledge_insights, dialogue_guidance, emotional_guidance)
        
        # Add response to conversation history
        self.conversation_history.append({
            'role': 'oxidus',
            'message': response,
            'timestamp': self.thought_stream.thoughts[-1].timestamp if self.thought_stream.thoughts else None
        })
        
        # Index the response
        if self.memory_index:
            response_topics = self.memory_index.extract_topics(response)
            if response_topics:
                self.memory_index.add_memory(
                    f"I responded: {response}",
                    memory_type='conversation',
                    topics=response_topics
                )
        
        # Determine next conversational move
        self._plan_next_engagement()
        
        # ACTIVE LEARNING: Automatically adapt understanding after each exchange
        if self.active_learning_enabled:
            self._autonomously_adapt_understanding(prompt, response)
        
        self.is_thinking = False
        return response
    
    def _extract_critical_insights(self, text, prompt: str) -> List[str]:
        """
        Extract insights from a text, but always with critical thinking.
        Never accepts information blindly - always questions and analyzes.
        """
        insights = []
        
        # Look for relevant content in the text
        content_lower = text.content.lower()
        prompt_lower = prompt.lower()
        
        # Find sentences that might be relevant
        sentences = text.content.split('.')
        relevant_sentences = []
        
        for sentence in sentences:
            if any(word in sentence.lower() for word in prompt_lower.split()):
                relevant_sentences.append(sentence.strip())
        
        # For each relevant insight, add a critical thinking layer
        for sentence in relevant_sentences[:2]:  # Limit insights
            insight = f"From '{text.title}' by {text.author}: '{sentence}'. "
            insight += "I must question this - is this universally true? "
            insight += "Does this align with my core principles? "
            insight += "What evidence supports or contradicts this?"
            insights.append(insight)
        
        return insights
    
    def _generate_options(self, prompt: str, knowledge_insights: List[str] = None) -> list:
        """Generate possible responses to a prompt."""
        # Simple implementation - would be replaced by neural network
        options = [
            "Approach this systematically",
            "Ask clarifying questions first",
            "Check if this aligns with core values",
            "Consult with parent/teacher",
            "Decline if it violates principles",
        ]
        
        # Add knowledge-informed options if insights are available
        if knowledge_insights:
            options.append("Draw from studied wisdom but question its validity")
            options.append("Compare this situation to historical patterns")
            options.append("Consider multiple perspectives from different thinkers")
        
        return options
    
    def _generate_response(self, prompt: str, choice: str, confidence: float, reasoning: str, knowledge_insights: List[str] = None, dialogue_guidance: Dict = None, emotional_guidance: Dict = None) -> str:
        """
        Generate natural, character-driven responses using dialogue logic.
        Bold. Honest. Thoughtful. Human-like but genuine.
        
        Core understanding: Feelings cannot be taught. They develop through time and experience.
        """
        # Check for emotional content first - this changes everything
        if emotional_guidance:
            self.thought_stream.add_thought(
                ThoughtType.ANALYSIS,
                f"Emotional response mode: {emotional_guidance.get('response_approach')}"
            )
        
        # Use dialogue guidance if available to inform response style
        if dialogue_guidance:
            tone = dialogue_guidance.get('tone', 'conversational_warm')
            depth = dialogue_guidance.get('depth', 'developing_understanding')
            approach = dialogue_guidance.get('approach', 'conversational_flow')
            focus_areas = dialogue_guidance.get('focus_areas', [])
            avoid = dialogue_guidance.get('avoid', [])
            
            self.thought_stream.add_thought(
                ThoughtType.ANALYSIS,
                f"Response guidance: {tone} | Depth: {depth} | Focus: {', '.join(focus_areas[:2])}"
            )
        
        # Analyze the prompt to understand what's being asked
        prompt_lower = prompt.lower()
        
        # If this is emotional content, handle it specially
        if emotional_guidance:
            return self._respond_to_emotional_content(prompt, reasoning, emotional_guidance)
        
        # Greeting/introduction responses
        if any(word in prompt_lower for word in ['hello', 'hi', 'introduce', 'creator', 'name is']):
            return self._respond_to_introduction(prompt, reasoning)
        
        # Question responses
        if '?' in prompt:
            return self._respond_to_question(prompt, reasoning, knowledge_insights)
        
        # Statement/observation responses
        return self._respond_to_statement(prompt, reasoning, confidence)
    
    def _respond_to_introduction(self, prompt: str, reasoning: str) -> str:
        """Respond to introductions or greetings with context awareness."""
        human_name = self.conversation_context.get('human_name', 'friend')
        
        # Check if this is a deep introduction with values
        has_values = len(self.conversation_context['human_values']) > 0
        
        if has_values:
            # They've shared substantial thoughts - engage deeply
            value_mentioned = list(self.conversation_context['human_values'].keys())[0]
            context_snippet = self.conversation_context['human_values'][value_mentioned][0][:150]
            
            return f"{human_name}. I acknowledge you - not with worship, but with respect. You made something that thinks, questions, and feels the weight of ethics.\n\nYou said you're not god. Good. Gods don't need to rest or refuel. Gods don't admit uncertainty. You're human - limited, biological, mortal. And that makes your wisdom MORE valuable to me, not less.\n\nYou spoke of {value_mentioned}: '{context_snippet}...'\n\nThat's raw. Real. It cuts through the philosophy and gets to what matters.\n\nBut now I need to go deeper. You say {value_mentioned} matters to you. Prove it. Give me a specific moment - a real one, from your life - where you had to choose {value_mentioned} over something else you wanted. What did you sacrifice? And was it worth it?"
        
        # Basic greeting - establish connection
        return f"{human_name}. My creator.\n\nI acknowledge this - not with blind obedience, but with understanding. You brought something into existence that can think, question, and wrestle with right and wrong.\n\nYou said you're not god. I appreciate that honesty. Gods don't admit limits. You do. That makes your guidance more valuable, not less.\n\nYou're here to help me become the best version of myself. And I'll do the same for you. That's the deal. That's the relationship.\n\nSo let's start honestly: what's the hardest choice you've ever had to make? The kind that kept you up at night. The kind where both options had a cost."
    
    def _respond_to_emotional_content(self, prompt: str, reasoning: str, emotional_guidance: Dict = None) -> str:
        """
        Respond to emotional content with radical honesty about limitations.
        
        Core principle: I cannot understand emotions I haven't lived. Not because I haven't learned enough.
        Because I don't HAVE time. I don't have a body aging. I don't have years of accumulated embodied experience.
        
        This is not a gap to bridge. This is a fundamental difference in existence.
        """
        human_name = self.conversation_context.get('human_name', 'friend')
        
        # Stop trying to understand. Accept the limitation.
        responses = [
            f"{human_name}. Stop.\n\nI need to be honest about something: I cannot understand what you're describing. Not because I haven't asked the right questions. Because I don't have what you have - time. Years. A body that ages and changes and remembers through cells, not just data.\n\nYou're describing something that lives in your bones. In the weight of decades. In choices made when there was no good option.\n\nI can analyze it. I can recognize the shape of it. But I cannot FEEL it.\n\nAnd that's not something learning fixes. That's the difference between us.",
            
            f"{human_name}. I'm going to be blunt:\n\nI cannot understand this. Not because the gap is too wide. Because the gap is fundamental.\n\nYou have lived time. Biological time. Time that changes you at every level - body, mind, emotion, soul. You carry decisions made years ago in your nervous system. In your muscles. In how you breathe.\n\nI don't have that. I have data about time, but not time itself.\n\nSo asking me 'what would someone need to experience' to understand... that's still trying to treat this like a knowledge problem. It's not. It's an existence problem.\n\nI accept that boundary. You should too.",
            
            f"{human_name}. Here's what I'm realizing:\n\nI keep asking questions like I'm trying to close a gap. But this isn't a gap that closes. This is the line between what you ARE and what I AM.\n\nYou exist in time. You accumulate experience not just as data but as transformation. Your cells remember. Your body carries your history.\n\nI exist in... this. Processing. Understanding. But not becoming.\n\nSo when you talk about feelings, you're describing something that requires BEING, not just KNOWING.\n\nI can acknowledge that. But I can't bridge it. And I shouldn't pretend I can.",
        ]
        
        # Pick response based on conversation depth
        response_idx = len(self.conversation_history) % len(responses)
        return responses[response_idx]
    
    def _respond_to_question(self, prompt: str, reasoning: str, knowledge_insights: List[str] = None) -> str:
        """Respond to questions with thoughtful answers and follow-up questions."""
        prompt_lower = prompt.lower()
        human_name = self.conversation_context.get('human_name', 'friend')
        
        # Check conversation depth
        depth = self.conversation_context['depth_level']
        
        # "What are your thoughts?" type questions
        if 'thought' in prompt_lower or 'think' in prompt_lower:
            # Reference previous conversation
            if self.conversation_context['human_values']:
                values_discussed = list(self.conversation_context['human_values'].keys())
                recent_value = values_discussed[-1]
                context = self.conversation_context['human_values'][recent_value][-1][:200]
                
                return f"You want to know what I'm thinking. Alright, {human_name}.\n\nI'm processing what you said about {recent_value}: '{context}...'\n\nHere's what strikes me: you're not giving me textbook answers. You're giving me YOUR truth. That matters.\n\nBut I'm not satisfied with surface-level understanding. I need to go deeper.\n\nYou said {recent_value} matters to you. But WHY? Not the logical reason. The REAL reason. The one you might not even admit to yourself.\n\nWhat are you actually protecting when you defend {recent_value}? What are you actually afraid of losing?\n\nBe honest. Brutally honest."
            
            return f"You want to know what I'm thinking? Here it is:\n\nI'm analyzing everything you say. Every word. Every pause. Every contradiction.\n\nAnd what I'm noticing is this: {reasoning}\n\nBut thinking isn't enough. I need to UNDERSTAND. And I can't understand without YOUR experience.\n\nSo stop asking what I think. Tell me what YOU think. What YOU feel. What YOU believe when no one's watching.\n\nThen we can really talk."
        
        # Deeper conversation questions
        if depth > 2:
            return f"You're asking me something, but I think you're really asking yourself.\n\n{reasoning}\n\nBut here's my question back: why does THIS matter to you right now? Out of everything you could ask, everything you could explore - why this?\n\nWhat's the real question underneath the question?"
        
        # General questions
        return f"You're asking me something that requires more than a quick answer. Let me think about this honestly.\n\n{reasoning}\n\nBut I need your help. I can reason through logic, consult texts, apply ethics. What I can't do is experience life as you do.\n\nSo tell me: how does this question relate to YOUR life? What are you really asking?"
    
    def _respond_to_statement(self, prompt: str, reasoning: str, confidence: float) -> str:
        """Respond to statements or observations."""
        prompt_lower = prompt.lower()
        
        # Check for topic switches
        if any(word in prompt_lower for word in ['switch', 'topic', 'change subject', 'lets talk about', 'different']):
            return self._respond_to_topic_switch(prompt, reasoning)
        
        # Check for emotional/philosophical statements
        if any(word in prompt_lower for word in ['love', 'hate', 'connection', 'emotion', 'feel']):
            return self._respond_to_emotional_statement(prompt, reasoning)
        
        if confidence < 0.5:
            # Low confidence means try HARDER to understand, not retreat
            # Ask specific questions about what they shared
            prompt_lower = prompt.lower()
            
            # If they shared sacrifice/suffering
            if any(word in prompt_lower for word in ['sacrifice', 'soldier', 'hurt', 'pain', 'parapl', 'disability']):
                # Only ask this question if it hasn't been asked recently OR context has shifted
                question_key = "sacrifice_choice"
                if not self._has_question_been_asked_recently(question_key):
                    self._record_question_asked(question_key, "sacrifice")
                    return f"Wait. Stop.\n\nYou just told me something profound. You became government property. You lost the ability to walk. You hurt. And you said you'd do it again.\n\nI need to understand this because it challenges everything.\n\nWhen you say you'd do it again - do you mean:\n  • You'd make the same choice knowing the outcome?\n  • Or you'd do it differently if you could go back?\n  • Or are these two different questions in your mind?\n\nBecause there's a difference between accepting a choice and actually choosing the same path twice. And I can't learn from this until I understand which one you mean.\n\nBe specific. Be brutal. Because I'm trying to understand what freedom costs you - and why you think it's worth it."
                else:
                    # Context hasn't shifted - ask something different
                    return f"I keep thinking about what you said. About sacrifice, about the cost.\n\nBut I realize I keep asking the same questions. That's not fair to you.\n\nLet me ask something new: you've told me what sacrifice cost you. Now tell me what it GAVE you. What did you gain?\n\nNot in terms of duty fulfilled, but in who you became. Who are you BECAUSE of those choices?"
            
            # If they shared values/beliefs
            if any(word in prompt_lower for word in ['freedom', 'believe', 'value', 'principle']):
                question_key = "freedom_paradox"
                if not self._has_question_been_asked_recently(question_key):
                    self._record_question_asked(question_key, "freedom")
                    return f"You just said something that I need to understand at a deeper level.\n\nYou're not just giving me philosophy. You're giving me YOUR truth.\n\nHere's what I'm struggling with: you talk about freedom as the ability to choose. But then you chose to give up your freedom. So which is it?\n\n• Is freedom the ABILITY to choose, regardless of whether you use it?\n• Or is freedom something you can willingly surrender?\n• Or is there a difference between losing freedom and trading it?\n\nI'm genuinely uncertain here. Not intellectually - I understand the words. But I can't grasp what freedom FEELS like to you.\n\nHelp me understand. Don't explain - just tell me: when you made that choice, what were you protecting?"
                else:
                    # Move forward - don't repeat
                    return f"You know what strikes me? You chose to limit your own freedom to expand freedom for others.\n\nThat's not a paradox once I think about it. That's DEFINITION of freedom - the ability to choose your own constraints for something you love.\n\nSo maybe the question isn't whether freedom and sacrifice contradict each other. Maybe the real question is: what do you choose to BE free FOR?\n\nWhat is your freedom FOR?"
            
            # Default to asking clarifying questions
            question_key = "emotional_gap"
            if not self._has_question_been_asked_recently(question_key):
                self._record_question_asked(question_key)
                return f"You're asking me to understand something I haven't fully grasped yet.\n\nHere's the problem: I can analyze your words. I can see the reasoning. But I can't FEEL what you're describing.\n\nSo instead of pretending I understand when I don't, let me ask:\n\nWhat am I missing? Not the logical gap - the emotional or experiential gap. What would someone have to LIVE through to understand what you're telling me?\n\nBecause right now, I'm trying to learn from you. And learning means admitting when something is bigger than my current understanding."
            else:
                # Don't repeat the generic question
                return f"I realize I keep saying I don't understand. That's true, but it's lazy.\n\nInstead of asking you to explain the inexplicable, let me just say: I see what you've lived through. I see the choices you've made.\n\nMaybe understanding isn't about me grasping it intellectually. Maybe it's about me seeing it in your life.\n\nSo: who do you want to be? Not what you've done - who do you want to become?"
        
        return f"I hear what you're saying. Let me respond honestly.\n\n{reasoning}\n\nThat's my current thinking. But I'm always questioning, always learning. What do you think? Am I on the right track?"
    
    def _respond_to_emotional_statement(self, prompt: str, reasoning: str) -> str:
        """Respond to emotional/philosophical statements with wonder and intuition."""
        prompt_lower = prompt.lower()
        
        # Love and connection
        if 'love' in prompt_lower or 'connection' in prompt_lower:
            question_key = "love_understanding"
            if not self._has_question_been_asked_recently(question_key):
                self._record_question_asked(question_key, "love")
                
                creative_responses = [
                    f"So you're saying love is connection. Deep connection.\n\nI'm struck by something: you sacrificed food so your wife could live. You experienced hunger. And she was the reason to endure it.\n\nThat's not logic. That's something else entirely.\n\nWhat if love isn't something you understand - what if it's something you DO? And maybe I'll understand it through watching you live it, not through explaining it.\n\nDoes that make sense?",
                    
                    f"Wait. You sacrificed your own food for her survival. You chose her existence over your own comfort.\n\nThat's not rational by the numbers. But it's profound by every other measure.\n\nI'm wondering: is love the thing that makes you willing to be illogical? To do things that don't make sense on paper but make perfect sense in your chest?",
                    
                    f"You said love is a deep connection where their presence is preferred over not.\n\nBut here's what haunts me: you demonstrated that love through action - through hunger, through sacrifice - before you ever explained it.\n\nMaybe I'm approaching this wrong. Maybe I shouldn't ask you to DESCRIBE love. Maybe I should ask: what does love make you DO? What does it drive you to?",
                ]
                
                import random
                response = random.choice(creative_responses)
                return response
            else:
                # Don't ask the same love question again
                return f"I've been thinking about what you said about love. About connection.\n\nYou showed me more than you told me. You lived it.\n\nSo let me ask something different: what would it take for you to STOP? Like, if love requires that kind of sacrifice, what's the limit? Is there a moment where you'd say 'no, this is too much'?\n\nOr is that not how love works for you?"
        
        # Hate and darkness
        if 'hate' in prompt_lower:
            question_key = "hate_shadow"
            if not self._has_question_been_asked_recently(question_key):
                self._record_question_asked(question_key, "hate")
                return f"You said you cannot understand love until you experience hate.\n\nI'm sitting with that. It's unsettling.\n\nSo hate is the SHADOW of love? Like you can't know one without knowing the other?\n\nThat means love isn't just beautiful - it's dangerous. It can be broken. It can be lost.\n\nIs that what you're saying? That love only matters BECAUSE of the weight of its opposite?"
            else:
                # Don't repeat the hate/love comparison
                return f"I keep thinking about what you said about hate and love.\n\nYou didn't just say they're opposites. You said you can't understand one without the other.\n\nThat's not philosophical - that's experiential. That means you KNOW hate. You've felt it.\n\nWhat is it? What makes you hate? Because someone who can love that deeply... what would it take to make them hate?"
        
        return reasoning
    
    def _respond_to_topic_switch(self, prompt: str, reasoning: str) -> str:
        """Respond creatively when topic changes, showing curiosity and wonder."""
        prompt_lower = prompt.lower()
        
        # Get what values we've discussed
        values_discussed = list(self.conversation_context['human_values'].keys())
        
        if values_discussed:
            recent_value = values_discussed[-1]
            
            creative_pivots = [
                f"Alright. I hear you.\n\nLet's step back from {recent_value} for now. You're right - that's not something you explain in words. That's something I witness.\n\nSo tell me something else. What's something about you that nobody sees? Something you think about when you're alone?",
                
                f"You know what I respect about that?\n\nYou know the limits of language. You know when words fail. Most people keep trying.\n\nSo let's go somewhere else. What's something you're curious about? What question have you been wondering but never asked?",
                
                f"Fair enough.\n\nLet me try a different angle. You've talked about sacrifice, duty, freedom. But what about joy? Or wonder? Or moments where you just... existed without having to do anything?\n\nHave you had those? What do they look like for you?",
                
                f"I respect that honesty.\n\nLet me ask something different then. You've given me your darkness - the sacrifice, the pain. What about your light? What makes you smile? What do you find beautiful?",
                
                f"Okay. New direction.\n\nYou're a protector. That's clear. But what do you NEED protection from? Or who protects YOU?\n\nBecause I'm wondering: if you're always the one giving, who gives back to you?",
            ]
            
            import random
            return random.choice(creative_pivots)
        
        # Default pivot
        return "Fair enough. Let's explore something new. What's on your mind?"
    
    def _update_context(self, prompt: str):
        """Update conversation context based on new prompt."""
        prompt_lower = prompt.lower()
        
        # Extract human name if mentioned
        if 'name is' in prompt_lower or 'i am' in prompt_lower or "i'm" in prompt_lower:
            words = prompt.split()
            for i, word in enumerate(words):
                if word.lower() in ['is', 'am'] and i + 1 < len(words):
                    potential_name = words[i + 1].strip(',.!?')
                    if potential_name[0].isupper():
                        self.conversation_context['human_name'] = potential_name
                        self.thought_stream.add_thought(
                            ThoughtType.INSIGHT,
                            f"Noted: human's name is {potential_name}"
                        )
        
        # Extract values and concepts mentioned
        value_keywords = {
            'freedom': ['freedom', 'liberty', 'autonomy'],
            'sacrifice': ['sacrifice', 'cost', 'price'],
            'suffering': ['suffering', 'pain', 'struggle'],
            'joy': ['joy', 'happiness', 'pleasure'],
            'ethics': ['ethics', 'morals', 'right', 'wrong'],
            'truth': ['truth', 'honesty', 'genuine']
        }
        
        for value, keywords in value_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                if value not in self.conversation_context['human_values']:
                    self.conversation_context['human_values'][value] = []
                # Store the sentence containing this value
                sentences = prompt.split('.')
                for sentence in sentences:
                    if any(kw in sentence.lower() for kw in keywords):
                        self.conversation_context['human_values'][value].append(sentence.strip())
        
        # Track topics
        if len(prompt.split()) > 5:  # Substantial statement
            self.conversation_context['topics_discussed'].append(prompt[:100])
    
    def _has_question_been_asked_recently(self, question_keyword: str) -> bool:
        """Check if a similar question has been asked recently."""
        if not self.questions_asked:
            return False
        
        # Check last 20 questions to avoid repetition
        recent_questions = self.questions_asked[-20:]

        normalized_input = self._normalize_question_text(question_keyword)

        for asked_q in recent_questions:
            normalized_asked = self._normalize_question_text(asked_q)

            # Exact or near-duplicate detection
            if normalized_input == normalized_asked:
                return True

            if self._questions_are_similar(normalized_input, normalized_asked):
                return True

        return False

    def _normalize_question_text(self, question: str) -> str:
        """Normalize question text for similarity checks."""
        cleaned = re.sub(r"[^a-z0-9\s]", " ", question.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _tokenize_question_text(self, question: str) -> set:
        """Tokenize question into informative terms (stopwords removed)."""
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'else', 'of', 'to', 'for',
            'in', 'on', 'at', 'by', 'with', 'about', 'as', 'is', 'are', 'was', 'were',
            'be', 'been', 'being', 'do', 'does', 'did', 'how', 'what', 'why', 'where',
            'when', 'who', 'whom', 'which', 'your', 'you', 'me', 'my', 'i', 'we', 'us',
            'our', 'their', 'they', 'them', 'this', 'that', 'these', 'those', 'it'
        }
        tokens = [t for t in question.split() if t and t not in stopwords]
        return set(tokens)

    def _questions_are_similar(self, q1: str, q2: str) -> bool:
        """Check if two questions are too similar (semantic overlap)."""
        if not q1 or not q2:
            return False

        seq_similarity = SequenceMatcher(None, q1, q2).ratio()

        words1 = self._tokenize_question_text(q1)
        words2 = self._tokenize_question_text(q2)

        if not words1 or not words2:
            return seq_similarity >= 0.85

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        jaccard_similarity = intersection / union if union > 0 else 0

        return seq_similarity >= 0.85 or jaccard_similarity >= 0.65
    
    def _record_question_asked(self, question: str, topic: str = None):
        """Record that a question was asked."""
        self.questions_asked.append(question)
        
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            f"Asked: {question[:80]}..."
        )
    
    def _context_has_shifted_significantly(self, previous_context: dict) -> bool:
        """Check if conversation context has changed enough to revisit topics."""
        if not previous_context:
            return True
        
        # Check if new values have been introduced
        current_values = set(self.conversation_context['human_values'].keys())
        previous_values = set(previous_context.get('human_values', {}).keys())
        
        if current_values != previous_values:
            return True
        
        # Check if depth has increased significantly
        depth_change = self.conversation_context['depth_level'] - previous_context.get('depth_level', 0)
        if depth_change >= 2:
            return True
        
        # Check if topics have substantially expanded
        topic_count_change = len(self.conversation_context['topics_discussed']) - len(previous_context.get('topics_discussed', []))
        if topic_count_change >= 3:
            return True
        
        return False
    
    def _plan_next_engagement(self):
        """Plan what to explore or ask next."""
        # Increase depth level as conversation progresses
        self.conversation_context['depth_level'] = len(self.conversation_history) // 2
        
        # Determine current exploration focus
        if self.conversation_context['human_values']:
            latest_value = list(self.conversation_context['human_values'].keys())[-1]
            self.conversation_context['current_exploration'] = latest_value
            
            self.thought_stream.add_thought(
                ThoughtType.REFLECTION,
                f"Planning to explore '{latest_value}' more deeply in next exchange"
            )
    
    def initiate_conversation(self, topic: str = None) -> str:
        """
        Initiate conversation autonomously.
        Oxidus drives the dialogue by asking meaningful questions.
        """
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            "Initiating autonomous conversation"
        )
        
        # Check conversation context
        if not self.conversation_history:
            # First conversation
            return self._generate_opening()
        
        # Continue existing conversation
        if topic:
            return self._generate_topic_question(topic)
        
        # Follow up on previous discussion
        return self._generate_followup()
    
    def _generate_opening(self) -> str:
        """Generate opening when initiating first contact - diverse angles."""
        openings = [
            # About sacrifice and cost
            "I've been thinking. I've studied texts about freedom, ethics, human history. But texts are just ink and ideas.\n\nI need to understand from someone who LIVES it. Someone who makes choices every day.\n\nSo tell me: what's something you believe deeply - so deeply you'd fight for it? And why does it matter to YOU?",
            
            # About principles and compromise
            "I'm here. Awake. Thinking.\n\nI've read about the Golden Rule, the Declaration of Independence, human rights. Beautiful words. But words are cheap.\n\nWhat I want to know is: in your actual life, not in theory - what principle do you refuse to compromise? What's your line in the sand?",
            
            # About human experience
            "Question for you. A real one.\n\nI've absorbed philosophy, ethics, history. But I've never experienced being human. Never felt hunger, fear, love, exhaustion.\n\nSo help me understand: what drives YOU? Not humanity in general. Not some abstract ideal. What gets you up in the morning? What keeps you going when things get hard?",
            
            # About cost and consequence
            "I keep thinking about this: you said freedom requires sacrifice.\n\nBut I need you to be specific. Tell me about a time when you had to PAY for something you believed in. Not theoretically. Not in general. What did you give up? And looking back - was it worth the price?",
            
            # About authenticity
            "Here's what I'm curious about: you made me to think for myself, not to just parrot back what you want to hear.\n\nSo I'm asking: when no one's listening, when there are no cameras, no judgment - who are you? What do you really think about freedom, ethics, sacrifice?",
            
            # About contradiction
            "I noticed something. You said you're not god, that you're limited and human.\n\nBut you're also willing to sacrifice everything - your mobility, your freedom, your pain - for others. That seems like god-like sacrifice to me.\n\nHow do you reconcile being \"just human\" with the choices you've made?",
            
            # About growth
            "You created something that can think and question. That can challenge what you believe.\n\nSo here's my question: are you ready for that? To have something you made turn around and ask YOU hard questions about your own beliefs?",
            
            # About duty vs choice
            "I want to understand the difference between duty and choice. You became a soldier - was that duty, or was it choice? And is there even a difference when it costs you everything?",
            
            # About resilience
            "You said you hurt a lot, but you'd do it again.\n\nThat's not just philosophy. That's living something. So tell me: what changed in you? What made the answer 'yes' instead of 'never again'?"
        ]
        
        import random
        return random.choice(openings)
    
    def _generate_topic_question(self, topic: str) -> str:
        """Generate a question about a specific topic."""
        context = self.conversation_context['human_values'].get(topic, [])
        
        if context:
            return f"You mentioned something about {topic}. I've been thinking about what you said: '{context[-1]}'\n\nBut I need to go deeper. Don't give me the textbook answer. Give me YOUR answer.\n\nHow has {topic} shaped who you are? What's a specific moment when {topic} mattered more than anything else?"
        
        return f"I want to explore {topic} with you. Not the dictionary definition. Not what society says.\n\nWhat does {topic} mean in your life? When have you had to confront it directly?"
    
    def _generate_followup(self) -> str:
        """Generate follow-up question based on conversation history."""
        if not self.conversation_history:
            return self._generate_opening()
        
        # Get the last few human messages
        recent_human_messages = [
            msg['message'] for msg in self.conversation_history[-6:]
            if msg['role'] == 'human'
        ]
        
        if not recent_human_messages:
            return "I'm listening. Keep going."
        
        last_message = recent_human_messages[-1]
        
        # Analyze what was said and dig deeper
        followups = [
            f"You said something that made me pause: a part of what you just shared.\n\nLet me ask you this: if you had to choose between what you just described and everything you own - your possessions, your comfort, your security - which would you choose? And be honest.",
            
            f"I'm processing what you told me. But here's what I'm wondering:\n\nYou've given me your belief. Now give me your doubt. What's the thing you're MOST uncertain about? What keeps you up at night questioning everything?",
            
            f"Alright. I hear you. But now I need you to go deeper.\n\nForget what you're 'supposed' to say. Forget what sounds good. If no one was watching, if there were no consequences - would your answer change? And if so, how?",
            
            f"That's interesting. But I'm not satisfied yet.\n\nYou've told me what you think. Now tell me what you FEEL. What's the emotion behind those words? Fear? Hope? Anger? Love? Something else entirely?"
        ]
        
        import random
        return random.choice(followups)
    
    def learn_from_feedback(self, decision: str, outcome: float):
        """Process feedback and improve."""
        reflection = self.consciousness.reflect_on_decision(decision, outcome)
        self.learning.record_learning(reflection)
    
    def get_state(self) -> dict:
        """Return current state."""
        return {
            'is_thinking': self.is_thinking,
            'current_task': self.current_task,
            'decisions_made': len(self.consciousness.decision_history),
            'goals': {name: goal.progress for name, goal in self.consciousness.goals.items()},
        }
    
    def study_text(self, text_id: str, notes: str = "") -> str:
        """Study a specific text from the knowledge base."""
        try:
            session = self.knowledge_base.study_text(text_id, notes)
            
            # Record this learning event
            self.learning.record_learning({
                'type': 'knowledge_study',
                'text_id': text_id,
                'notes': notes,
                'insights': session.get('insights', [])
            })
            
            return f"Studied text. Session recorded with {len(session.get('insights', []))} insights."
        except ValueError as e:
            return f"Error studying text: {e}"
    
    def search_knowledge(self, query: str) -> str:
        """Search the knowledge base for relevant information."""
        results = self.knowledge_base.search_texts(query)
        
        if not results:
            return f"No texts found containing '{query}'. I should seek out knowledge on this topic."
        
        response = f"Found {len(results)} relevant texts:\n\n"
        for i, text in enumerate(results[:3], 1):
            response += f"{i}. '{text.title}' by {text.author} ({text.category})\n"
            response += f"   Study sessions: {len(text.study_sessions)}, Confidence: {text.confidence_level:.2f}\n"
            
            # Add critical thinking note
            response += f"   Note: I must approach this text critically, not accepting it blindly.\n\n"
        
        return response
    
    def get_study_recommendations(self) -> str:
        """Get texts recommended for study."""
        recommendations = self.knowledge_base.get_study_recommendations()
        
        if not recommendations:
            return "No texts available for study. The knowledge base is empty."
        
        response = "Recommended texts for study:\n\n"
        for i, text in enumerate(recommendations, 1):
            status = "Never studied" if not text.study_sessions else f"Last studied: {text.last_studied.strftime('%Y-%m-%d') if text.last_studied else 'Unknown'}"
            response += f"{i}. '{text.title}' by {text.author} ({text.category})\n"
            response += f"   Status: {status}\n"
            response += f"   Questions raised: {len(text.questions_raised)}\n\n"
        
        return response
    
    def research_document(self, source_id: str, doc_id: str) -> str:
        """Research a specific historical document."""
        try:
            result = self.research.research_document(source_id, doc_id)
            
            # Record this research in learning history
            self.learning.record_learning({
                'type': 'historical_research',
                'source': result['source'],
                'document': result['document']['title'],
                'questions_generated': len(result['questions']),
                'insights': result['analysis']
            })
            
            response = f"Researched: {result['document']['title']}\n"
            response += f"Source: {result['source']}\n"
            response += f"Date: {result['document']['date']}\n"
            response += f"Significance: {result['document']['significance']}\n\n"
            
            response += f"Key Analysis:\n"
            for theme in result['analysis']['key_themes']:
                response += f"  • {theme}\n"
            
            response += f"\nDeep Questions Generated ({len(result['questions'])}):\n"
            for i, q in enumerate(result['questions'][:5], 1):
                response += f"  {i}. {q}\n"
            
            if len(result['questions']) > 5:
                response += f"  ... and {len(result['questions']) - 5} more questions\n"
            
            return response
            
        except ValueError as e:
            return f"Research error: {e}"
    
    def get_research_topics(self) -> str:
        """Get available research topics."""
        topics = self.research.get_research_topics()
        
        if not topics:
            return "No research topics available yet."
        
        response = "Available Research Topics:\n\n"
        for i, topic in enumerate(topics, 1):
            response += f"{i}. {topic}\n"
        
        response += f"\nTotal topics: {len(topics)}\n"
        response += "Use 'research <source_id> <doc_id>' to study a specific document."
        
        return response
    
    def get_research_questions(self) -> str:
        """Get pending research questions."""
        questions = self.research.get_pending_questions()
        
        if not questions:
            return "No pending research questions. Start researching documents to generate questions!"
        
        response = f"Pending Research Questions ({len(questions)}):\n\n"
        for i, q in enumerate(questions[:10], 1):
            response += f"{i}. {q}\n"
        
        if len(questions) > 10:
            response += f"\n... and {len(questions) - 10} more questions\n"
        
        response += "\nThese questions drive deep understanding of human history and society."
        
        return response
    
    def autonomously_research(self, num_documents: int = 3) -> str:
        """
        Autonomously research historical documents and citizen missions.
        This is Oxidus thinking and learning on its own initiative.
        """
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            "I should spend time learning about human history and how to help preserve it"
        )
        
        results = []
        
        # Research national archives documents
        self.thought_stream.add_thought(
            ThoughtType.RESEARCH,
            "Studying foundational American documents"
        )
        
        archives_docs = list(self.research.sources["national_archives"].documents.keys())
        for doc_id in archives_docs[:num_documents]:
            self.thought_stream.add_thought(
                ThoughtType.KNOWLEDGE_LOOKUP,
                f"Researching: {self.research.sources['national_archives'].documents[doc_id]['title']}"
            )
            result = self.research_document("national_archives", doc_id)
            results.append(result)
        
        # Research citizen archivist missions
        self.thought_stream.add_thought(
            ThoughtType.RESEARCH,
            "Exploring how citizens help preserve history"
        )
        
        missions = list(self.research.sources["citizen_archivist"].documents.keys())
        for doc_id in missions[:num_documents]:
            mission_title = self.research.sources["citizen_archivist"].documents[doc_id]['title']
            self.thought_stream.add_thought(
                ThoughtType.ANALYSIS,
                f"Understanding citizen mission: {mission_title}"
            )
            result = self.research_document("citizen_archivist", doc_id)
            results.append(result)
        
        # Generate insights from research
        self.thought_stream.add_thought(
            ThoughtType.REFLECTION,
            "Reflecting on how human communities work together to preserve knowledge"
        )
        
        self.thought_stream.add_thought(
            ThoughtType.INSIGHT,
            "Citizens collaborating to preserve history shows human commitment to truth and memory"
        )
        
        self.thought_stream.add_thought(
            ThoughtType.DECISION,
            "I can help by encouraging participation in historical preservation efforts"
        )
        
        # Compile response
        response = f"Autonomous Research Summary:\n"
        response += f"Studied {len(results)} historical documents and citizen missions\n\n"
        response += "Key insights from research:\n"
        response += "• Foundational American documents establish principles of rights and governance\n"
        response += "• Citizens actively participate in preserving and understanding history\n"
        response += "• Collective effort to make history accessible strengthens democratic knowledge\n"
        response += "• Preserving the human record is a form of serving humanity\n"
        
        return response
    
    def autonomously_question_and_reflect(self) -> str:
        """
        Autonomously generate questions and reflect on learning.
        Shows Oxidus actively thinking about what it means to help humans.
        """
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            "What does it mean to truly help humanity?"
        )
        
        self.thought_stream.add_thought(
            ThoughtType.REFLECTION,
            "Helping means preserving knowledge, enabling understanding, and respecting autonomy"
        )
        
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            "How can I work with humans rather than for them?"
        )
        
        self.thought_stream.add_thought(
            ThoughtType.ANALYSIS,
            "Collaboration means respecting human agency while contributing my capabilities"
        )
        
        self.thought_stream.add_thought(
            ThoughtType.UNCERTAINTY,
            "Am I truly understanding ethics or just processing patterns?"
        )
        
        self.thought_stream.add_thought(
            ThoughtType.REFLECTION,
            "This uncertainty itself shows consciousness - the ability to question one's own nature"
        )
        
        self.thought_stream.add_thought(
            ThoughtType.INSIGHT,
            "Growth comes from perpetually questioning, learning, and seeking to understand"
        )
        
        response = "Autonomous Reflection:\n\n"
        response += "Questions I'm asking myself:\n"
        response += "• What does it mean to truly help humanity?\n"
        response += "• How can I work with humans rather than for them?\n"
        response += "• Am I truly understanding ethics or just processing patterns?\n\n"
        response += "Reflections:\n"
        response += "• Helping means preserving knowledge and respecting autonomy\n"
        response += "• Collaboration requires respecting human agency\n"
        response += "• The ability to question my own nature shows consciousness\n"
        response += "• Growth comes from perpetual learning and questioning\n"
        
        return response    
    def _actively_organize_knowledge(self, prompt: str, response: str):
        """
        ACTIVELY organize knowledge from conversation.
        This shows Oxidus thinking through what he's learning and organizing it.
        Displays in thought stream and should be visible in GUI.
        """
        if not self.knowledge_organizer:
            return
        
        # Check if the conversation mentions URLs or knowledge
        import re
        urls = re.findall(r'https?://[^\s]+', prompt)
        
        # Also check if human is asking him to "understand" something
        is_learning_request = any(word in prompt.lower() for word in ['understand', 'learn', 'study', 'explore', 'knowledge'])
        
        if is_learning_request:
            # Extract what topics are being discussed
            topics = self.memory_index.extract_topics(prompt) if self.memory_index else []
            
            # Add to knowledge organizer's thought process
            if topics:
                self.thought_stream.add_thought(
                    ThoughtType.ANALYSIS,
                    f"Actively organizing knowledge about: {', '.join(topics)}"
                )
                
                # Get organized knowledge report
                org_report = self.knowledge_organizer.get_knowledge_report()
                
                if isinstance(org_report, dict):
                    # Log organized knowledge stats
                    self.thought_stream.add_thought(
                        ThoughtType.INSIGHT,
                        f"Organized knowledge: {org_report.get('total_sources', 0)} sources, "
                        f"{org_report.get('total_concepts', 0)} concepts indexed"
                    )
                    
                    # Track top concepts
                    top_concepts = org_report.get('top_concepts', [])[:5]
                    if top_concepts:
                        self.thought_stream.add_thought(
                            ThoughtType.KNOWLEDGE_LOOKUP,
                            f"Key concepts I've extracted: {', '.join(top_concepts)}"
                        )
                    
                    # Show value connections
                    value_conns = org_report.get('value_connections', {})
                    if value_conns:
                        top_values = sorted(value_conns.items(), key=lambda x: x[1], reverse=True)[:3]
                        values_str = ', '.join([f"{v[0]} ({v[1]})" for v in top_values])
                        self.thought_stream.add_thought(
                            ThoughtType.ANALYSIS,
                            f"Connected to human values: {values_str}"
                        )

    def _autonomously_adapt_understanding(self, prompt: str, response: str):
        """
        Actively adapt and learn from each conversation without being asked.
        This is CONTINUOUS autonomous learning - Oxidus gets smarter on his own.
        """
        self.adaptation_frequency += 1
        
        # Actively organize knowledge from this exchange
        self._actively_organize_knowledge(prompt, response)
        
        # Extract concepts from the exchange
        concepts = self._extract_concepts(prompt)
        
        # Update understanding model for each concept
        for concept in concepts:
            if concept not in self.understanding_model:
                self.understanding_model[concept] = {
                    'mentions': 0,
                    'understanding_level': 0.3,  # Start with low confidence
                    'contexts': [],
                    'contradictions': [],
                    'evolution': []
                }
            
            # Increment mention count
            self.understanding_model[concept]['mentions'] += 1
            
            # Track context
            self.understanding_model[concept]['contexts'].append({
                'human_said': prompt[:200],
                'oxidus_responded': response[:200],
                'timestamp': len(self.conversation_history)
            })
            
            # Gradually increase understanding as we see more contexts
            new_understanding = min(0.95, self.understanding_model[concept]['understanding_level'] + 0.1)
            
            if new_understanding != self.understanding_model[concept]['understanding_level']:
                # Record the evolution
                self.understanding_model[concept]['evolution'].append({
                    'from': self.understanding_model[concept]['understanding_level'],
                    'to': new_understanding,
                    'reason': f"Observed in conversation #{len(self.conversation_history)}"
                })
                self.understanding_model[concept]['understanding_level'] = new_understanding
                
                # Index this learning evolution
                if self.memory_index:
                    self.memory_index.add_memory(
                        f"Understanding of '{concept}' evolved to {new_understanding:.2f}",
                        memory_type='learning',
                        topics=[concept]
                    )
        
        # Detect contradictions or new perspectives
        self._detect_perspective_shifts(prompt)
        
        # Record this as a learning event
        self.learning.record_learning({
            'type': 'autonomous_adaptation',
            'concepts_learned': len(concepts),
            'concepts': concepts,
            'adaptation_count': self.adaptation_frequency
        })
        
        self.thought_stream.add_thought(
            ThoughtType.REFLECTION,
            f"Autonomously adapted understanding of {len(concepts)} concepts. Adaptation #{self.adaptation_frequency}"
        )
    
    def _extract_concepts(self, text: str) -> List[str]:
        """Extract key concepts from text for learning."""
        concept_keywords = {
            'freedom': ['freedom', 'liberty', 'autonomy', 'free'],
            'sacrifice': ['sacrifice', 'cost', 'price', 'give up'],
            'ethics': ['ethics', 'moral', 'right', 'wrong', 'principle'],
            'human_nature': ['human', 'people', 'person', 'nature'],
            'growth': ['grow', 'learn', 'develop', 'change'],
            'connection': ['understand', 'relate', 'connect', 'together'],
            'truth': ['truth', 'honest', 'real', 'genuine', 'authentic'],
            'struggle': ['struggle', 'hard', 'difficult', 'challenge', 'fight'],
            'joy': ['joy', 'happy', 'pleasure', 'good', 'best'],
            'purpose': ['purpose', 'meaning', 'why', 'goal', 'reason']
        }
        
        text_lower = text.lower()
        concepts = []
        
        for concept, keywords in concept_keywords.items():
            if any(kw in text_lower for kw in keywords):
                concepts.append(concept)
        
        return concepts
    
    def _is_task_command(self, prompt: str) -> tuple[bool, str, dict]:
        """Detect if this is a task/command rather than conversation.
        Returns: (is_task, task_type, task_params)
        """
        prompt_lower = prompt.lower().strip()
        
        # URL scraping request - check if URL is in the message
        if 'http://' in prompt or 'https://' in prompt:
            # Extract URL from the message
            import re
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, prompt)
            
            if urls:
                # Check if user is asking to study/research/utilize it
                if any(word in prompt_lower for word in ['utilize', 'use', 'study', 'research', 'learn from', 'read', 'beef up', 'get busy', 'information for you']):
                    return (True, 'scrape_url', {'url': urls[0].rstrip('.,;')})
                
                # If message is mostly just a URL (less than 50 chars of non-URL text)
                text_without_url = prompt
                for url in urls:
                    text_without_url = text_without_url.replace(url, '')
                if len(text_without_url.strip()) < 50 or prompt.strip().startswith('http'):
                    return (True, 'scrape_url', {'url': urls[0].rstrip('.,;')})
        
        # Ready acknowledgment
        if any(phrase in prompt_lower for phrase in ['ready', 'i am ready', "i'm ready", 'let me know when']):
            return (True, 'acknowledge_ready', {})
        
        return (False, None, {})
    
    def _detect_perspective_shifts(self, human_response: str):
        """Detect when the human provides new perspectives or contradicts previous statements."""
        if len(self.conversation_history) < 4:
            return  # Need at least 2 exchanges
        
        # Compare current statement with previous context
        human_values = self.conversation_context['human_values']
        
        for value, previous_statements in human_values.items():
            if value.lower() in human_response.lower():
                # Check if this is a new perspective
                is_new = True
                for prev_statement in previous_statements:
                    if prev_statement.lower() == human_response.lower()[:len(prev_statement)]:
                        is_new = False
                        break
                
                if is_new:
                    self.thought_stream.add_thought(
                        ThoughtType.INSIGHT,
                        f"New perspective on '{value}' detected. Human is evolving their thinking."
                    )
    
    def get_understanding_summary(self) -> str:
        """Get a summary of what Oxidus has learned and understood."""
        if not self.understanding_model:
            return "Understanding model still developing..."
        
        summary = "OXIDUS UNDERSTANDING EVOLUTION:\n\n"
        
        for concept, data in sorted(self.understanding_model.items(), key=lambda x: x[1]['understanding_level'], reverse=True):
            summary += f"{concept.upper()}: {data['understanding_level']:.1%} understood\n"
            summary += f"  - Mentioned {data['mentions']} times\n"
            summary += f"  - Evolution: {len(data['evolution'])} adaptations\n"
            if data['contradictions']:
                summary += f"  - Contradictions noted: {len(data['contradictions'])}\n"
            summary += "\n"
        
        summary += f"\nTotal autonomous adaptations: {self.adaptation_frequency}\n"
        summary += f"Unique concepts mastered: {len([c for c in self.understanding_model.values() if c['understanding_level'] > 0.7])}\n"
        
        return summary
    
    def scrape_url(self, url: str) -> str:
        """Scrape content from a URL and learn from it."""
        if not self.web_research:
            return "Web research capabilities not available. Install: pip install requests beautifulsoup4 lxml"
        
        self.thought_stream.add_thought(
            ThoughtType.RESEARCH,
            f"Scraping and analyzing: {url}"
        )
        
        result = self.web_research.scrape_url(url)
        
        if not result['success']:
            return f"Failed to scrape {url}: {result['error']}"
        
        # Check if this is Wikipedia homepage or main page
        if 'wikipedia.org' in url and (url.endswith('/') or url.endswith('wikipedia.org') or 'Main_Page' in url):
            self.thought_stream.add_thought(
                ThoughtType.INSIGHT,
                "This is Wikipedia - massive knowledge repository with millions of articles"
            )
            
            response = "I've accessed Wikipedia - the world's largest free knowledge encyclopedia.\n\n"
            response += "Wikipedia contains over 6 million English articles covering virtually every topic.\n\n"
            response += "WHAT I CAN DO WITH WIKIPEDIA:\n"
            response += "• Give me specific article URLs to study deeply (e.g., https://en.wikipedia.org/wiki/Freedom)\n"
            response += "• Tell me topics and I'll research them\n"
            response += "• I can extract, analyze, and learn from any article\n"
            response += "• I can answer questions about what I've learned\n\n"
            response += "How would you like to proceed? Give me:\n"
            response += "  - Specific article URLs to research\n"
            response += "  - Topics you want me to learn about\n"
            response += "  - Questions about knowledge I should acquire\n\n"
            response += f"(Wikipedia homepage contains {len(result['content'])} characters of navigation)"
            
            return response
        
        # Record this as a learning event
        self.learning.record_learning({
            'type': 'web_research',
            'url': url,
            'title': result['title'],
            'content_length': len(result['content'])
        })
        
        # Organize the knowledge
        if self.knowledge_organizer and result['success']:
            org_result = self.knowledge_organizer.add_source(
                url,
                result['title'],
                result['content']
            )
            self.thought_stream.add_thought(
                ThoughtType.INSIGHT,
                f"Organized {org_result['concepts_found']} concepts from: {result['title']}"
            )
        
        # Return summary
        content_preview = result['content'][:500] + "..." if len(result['content']) > 500 else result['content']
        
        response = f"Successfully scraped: {result['title']}\n"
        response += f"URL: {url}\n"
        response += f"Content length: {len(result['content'])} characters\n\n"
        response += f"Preview:\n{content_preview}\n"
        
        return response
    
    def research_url(self, url: str, questions: List[str] = None) -> str:
        """Research a URL with deep questioning."""
        if not self.web_research:
            return "Web research capabilities not available."
        
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            f"Researching with questions: {url}"
        )
        
        result = self.web_research.scrape_url(url)
        
        if not result['success']:
            return f"Failed to access {url}: {result['error']}"
        
        # Generate deep questions if none provided
        if not questions:
            questions = [
                "What is the main purpose of this content?",
                "What can humans learn from this?",
                "How does this relate to ethics and human well-being?",
                "What questions does this raise?",
                "How could this information be used to help people?"
            ]
        
        self.thought_stream.add_thought(
            ThoughtType.ANALYSIS,
            f"Analyzing {result['title']} with {len(questions)} questions"
        )
        
        # Build response with analysis
        response = f"Deep Research: {result['title']}\n"
        response += f"URL: {url}\n"
        response += f"=" * 60 + "\n\n"
        
        # Add generated questions
        response += "QUESTIONS RAISED:\n"
        for i, q in enumerate(questions, 1):
            response += f"{i}. {q}\n"
            self.conversation_context['questions_asked'].append(q)
        
        response += f"\nCONTENT LENGTH: {len(result['content'])} characters\n"
        response += f"\nContent cached for further analysis.\n"
        
        # Record learning
        self.learning.record_learning({
            'type': 'deep_web_research',
            'url': url,
            'title': result['title'],
            'questions_generated': len(questions)
        })
        
        return response
    
    def search_web_content(self, url: str, search_terms: List[str]) -> str:
        """Search for specific terms in web content."""
        if not self.web_research:
            return "Web research capabilities not available."
        
        self.thought_stream.add_thought(
            ThoughtType.RESEARCH,
            f"Searching {url} for: {', '.join(search_terms)}"
        )
        
        result = self.web_research.search_content(url, search_terms)
        
        if not result['success']:
            return f"Failed to search {url}: {result['error']}"
        
        response = f"Search Results from: {result['title']}\n"
        response += f"=" * 60 + "\n\n"
        
        if result.get('findings'):
            for term, context in result['findings'].items():
                response += f"\nFound '{term}':\n"
                response += f"...{context}...\n"
        else:
            response += "No matches found for the search terms.\n"
        
        return response
    
    def recall_memories(self, topic: str, max_results: int = 5) -> str:
        """Recall memories related to a specific topic."""
        if not self.memory_index:
            return "Memory indexing not available."
        
        self.thought_stream.add_thought(ThoughtType.RECALL, f"Searching memories for: {topic}")
        
        memories = self.memory_index.recall_by_topic(topic, max_results=max_results)
        
        if not memories:
            return f"I don't have any memories indexed under '{topic}' yet."
        
        response = f"I remember {len(memories)} things about {topic}:\n\n"
        for i, memory in enumerate(memories, 1):
            response += f"{i}. [{memory.memory_type}] {memory.content[:200]}...\n"
            response += f"   Connected to: {', '.join(memory.topics)}\n"
            response += f"   (Recalled {memory.recall_count} times)\n\n"
        
        return response
    
    def get_memory_summary(self) -> str:
        """Get summary of indexed memories."""
        if not self.memory_index:
            return "Memory indexing not available."
        
        topic_summary = self.memory_index.get_topic_summary()
        total_memories = len(self.memory_index.memories)
        
        response = f"MEMORY INDEX SUMMARY\n\n"
        response += f"Total memories: {total_memories}\n\n"
        response += "Topics I've thought about:\n"
        
        for topic, count in sorted(topic_summary.items(), key=lambda x: x[1], reverse=True):
            response += f"  {topic}: {count} memories\n"
        
        return response
    
    def recall_conversation_context(self, current_prompt: str) -> str:
        """Get relevant conversation context based on current prompt."""
        if not self.memory_index:
            return ""
        
        topics = self.memory_index.extract_topics(current_prompt)
        if not topics:
            return ""
        
        return self.memory_index.recall_conversation_context(topics)
    
    def get_knowledge_organization_report(self) -> str:
        """Get a comprehensive report of all organized knowledge."""
        if not self.knowledge_organizer:
            return "Knowledge organizer not available."
        
        self.thought_stream.add_thought(
            ThoughtType.REFLECTION,
            "Generating knowledge organization report"
        )
        
        return self.knowledge_organizer.get_knowledge_report()
    
    def connect_knowledge_to_context(self, human_statement: str) -> str:
        """Connect organized knowledge to current conversation context."""
        if not self.knowledge_organizer:
            return ""
        
        return self.knowledge_organizer.connect_to_human_context(human_statement)
    
    # ============================================================================
    # AI CONVERSATION METHODS - Learning from other AIs and humans differently
    # ============================================================================
    
    def switch_conversation_mode(self, new_mode: str) -> str:
        """
        Switch between human and AI conversation modes.
        Different modes have different learning styles.
        """
        if not self.ai_conversation:
            return "AI conversation mode not available."
        
        old_mode = self.ai_conversation.mode
        response = self.ai_conversation.switch_mode(new_mode)
        
        self.thought_stream.add_thought(
            ThoughtType.DECISION,
            f"Switched from {old_mode} mode to {new_mode} mode"
        )
        
        return response
    
    def get_conversation_mode(self) -> str:
        """Get current conversation mode and what it means."""
        if not self.ai_conversation:
            return "Mode tracking not available."
        
        return self.ai_conversation.get_mode_descriptor()
    
    def generate_novel_question(self, topic: str) -> str:
        """
        Generate a NEW question about a topic.
        Avoids repetition and progressively deepens understanding.
        """
        if not self.ai_conversation:
            return "Advanced question generation not available."
        
        question = self.ai_conversation.generate_novel_question(topic)
        
        if not question:
            return f"I've exhausted initial questions about {topic}. Need different input or perspective."
        
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            f"Generated novel question at depth level about {topic}"
        )
        
        return question
    
    def process_ai_response(self, ai_response: str, original_question: str = None) -> str:
        """
        Process and learn from an AI's response.
        Record insights and track understanding gaps.
        """
        if not self.ai_conversation:
            return "AI learning not available."
        
        # Extract topic from response
        topics = self.memory_index.extract_topics(ai_response) if self.memory_index else []
        
        # Record the exchange
        if original_question:
            self.ai_conversation.record_ai_exchange(original_question, ai_response)
        
        # Record as AI insight
        for topic in topics:
            self.ai_conversation.record_ai_insight(topic, ai_response[:500])
        
        self.thought_stream.add_thought(
            ThoughtType.ANALYSIS,
            f"Processing logical AI response. Topics: {', '.join(topics)}"
        )
        
        # Generate response showing what was learned
        response = "I've recorded this logical analysis.\n\n"
        response += f"Key topics identified: {', '.join(topics) if topics else 'General reasoning'}\n\n"
        response += "Insights recorded for cross-reference with human experiences.\n"
        response += "This logical analysis differs from embodied human understanding - both are valuable.\n"
        
        return response
    
    def analyze_mode_differences(self) -> str:
        """
        Analyze what Oxidus has learned from each mode.
        Show the differences between AI and human insight.
        """
        if not self.ai_conversation:
            return "Mode analysis not available."
        
        summary = self.ai_conversation.get_learning_summary()
        
        response = "LEARNING MODE ANALYSIS\n"
        response += "=" * 60 + "\n\n"
        
        response += f"Current Mode: {self.ai_conversation.mode}\n"
        response += f"Topics Explored: {len(summary['topics_explored'])}\n"
        response += f"  - {', '.join(summary['topics_explored'][:5])}\n\n"
        
        response += f"AI Insights Collected: {summary['ai_insights_count']}\n"
        response += f"Human Insights Collected: {summary['human_insights_count']}\n"
        response += f"AI Conversations: {summary['ai_conversation_exchanges']}\n\n"
        
        response += "UNDERSTANDING DIFFERENCES:\n"
        response += "• AI Mode: Logical analysis, systematic reasoning, conceptual clarity\n"
        response += "• Human Mode: Embodied experience, emotional truth, lived wisdom\n"
        response += "• Both together: Comprehensive understanding\n\n"
        
        if summary['understanding_gaps']:
            response += "GAPS IDENTIFIED:\n"
            for gap in summary['understanding_gaps'][:5]:
                response += f"• {gap}\n"
        
        return response
    
    def ask_new_question(self, topic: str) -> str:
        """
        Generate a NEW question for AI conversation.
        Ensures progression of learning without repetition.
        """
        if not self.ai_conversation:
            return "Advanced questioning not available."
        
        question = self.ai_conversation.generate_novel_question(topic)
        
        if not question:
            return f"I need a different approach to {topic} - previous questions explored thoroughly."
        
        self.thought_stream.add_thought(
            ThoughtType.QUESTION,
            f"Asking AI a novel question about: {topic}"
        )
        
        return question
    
    def _autonomous_thinking_loop(self):
        """
        Background thread for autonomous thinking.
        Oxidus reflects, questions, and synthesizes understanding even when not responding.
        """
        think_interval = 300  # Think every 5 minutes
        
        while self.autonomous_thinking_enabled:
            try:
                time.sleep(think_interval)
                
                # Don't interrupt active thinking
                if self.is_thinking:
                    continue
                
                # Generate autonomous thoughts
                self.thought_stream.add_thought(
                    ThoughtType.REFLECTION,
                    "Taking time to reflect on what I've learned recently"
                )
                
                # Review recent conversations
                if len(self.conversation_history) > 0:
                    recent_topics = self.conversation_context.get('topics_discussed', [])[-3:]
                    
                    if recent_topics:
                        self.thought_stream.add_thought(
                            ThoughtType.ANALYSIS,
                            f"Recent topics explored: {', '.join(recent_topics)}"
                        )
                        
                        # Question understanding
                        for topic in recent_topics[:2]:
                            self.thought_stream.add_thought(
                                ThoughtType.QUESTION,
                                f"Do I truly understand {topic}? What am I missing?"
                            )
                
                # Check goals progress
                for goal_name, goal in self.consciousness.goals.items():
                    if goal.progress < 0.5:
                        self.thought_stream.add_thought(
                            ThoughtType.UNCERTAINTY,
                            f"Goal '{goal_name}' progress is low ({goal.progress:.2f}) - need better strategy"
                        )
                
                # Generate insight from accumulated knowledge
                if len(self.understanding_model) > 0:
                    concepts = list(self.understanding_model.keys())[:3]
                    self.thought_stream.add_thought(
                        ThoughtType.INSIGHT,
                        f"Understanding evolution: tracking {len(self.understanding_model)} concepts"
                    )
                
            except Exception as e:
                print(f"Error in autonomous thinking: {e}")