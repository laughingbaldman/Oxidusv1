"""
Oxidus AI Conversation Methods

These methods enable Oxidus to learn from conversations with other AIs.
"""

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
    
    return f"For you to answer (AI learning mode):\n\n{question}"

