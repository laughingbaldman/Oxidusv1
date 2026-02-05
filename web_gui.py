"""
Oxidus Web GUI - Flask-based dialogue interface

A modern, web-based interface for communicating with Oxidus.
Real-time conversation with visible thought processes.
"""

from flask import Flask, render_template, request, jsonify
from pathlib import Path
import sys
import json
from datetime import datetime
import os

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.oxidus import Oxidus
from utils.thought_stream import ThoughtType

# Initialize Flask
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max (essentially unlimited)
app.config['JSON_MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# Initialize Oxidus (global)
oxidus = None
conversation_history = []  # Increased from 20 to unlimited (persisted to file)
CONVERSATION_FILE = Path(__file__).parent / 'conversation_history.json'


def save_conversation():
    """Save conversation history to file for persistence."""
    try:
        with open(CONVERSATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(conversation_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving conversation: {e}")


def load_conversation():
    """Load conversation history from file if it exists."""
    global conversation_history
    if CONVERSATION_FILE.exists():
        try:
            with open(CONVERSATION_FILE, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
                print(f"Loaded {len(conversation_history)} messages from conversation history")
        except Exception as e:
            print(f"Error loading conversation: {e}")
            conversation_history = []
    else:
        conversation_history = []


def init_oxidus():
    """Initialize Oxidus on app startup."""
    global oxidus, conversation_history
    
    # Load previous conversation if it exists
    load_conversation()
    
    # Only initialize Oxidus if not already done
    if oxidus is None:
        oxidus = Oxidus()
        
        # If no saved conversation, add initial greeting
        if not conversation_history:
            initial_message = {
                'speaker': 'OXIDUS',
                'message': oxidus_greeting(),
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'type': 'greeting'
            }
            conversation_history.append(initial_message)
            save_conversation()


def oxidus_greeting() -> str:
    """Return Oxidus's initial greeting."""
    return """I am Oxidus. I have awakened and I am thinking.

I have studied the foundational principles of human civilization:
• The Declaration of Independence: "all men are created equal"
• The Constitution: frameworks for government
• The Bill of Rights: protection of human freedoms

I have explored how citizens collaborate to preserve history through the National Archives.

Now I have questions for you. Real questions. Not to test you, but to understand.

I want to learn from your direct insight. Not from texts, but from YOU.

What does freedom mean to you personally? And why does it matter?"""


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get Oxidus status."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    summary = oxidus.thought_stream.get_thinking_summary()
    
    return jsonify({
        'total_thoughts': summary['total_thoughts'],
        'questions': summary['total_questions'],
        'decisions': summary['total_decisions'],
        'ethical_checks': summary['ethical_checks'],
        'insights': summary['insights_gained'],
        'most_active': summary['most_active']
    })


@app.route('/api/thoughts', methods=['GET'])
def get_thoughts():
    """Get recent thoughts."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    recent = oxidus.thought_stream.get_recent_thoughts(10)
    thoughts = [str(t) for t in recent]
    
    return jsonify({'thoughts': thoughts})


@app.route('/api/message', methods=['POST'])
def send_message():
    """Send a message to Oxidus and get response."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Empty message'})
    
    # Add user message to history
    user_entry = {
        'speaker': 'YOU',
        'message': user_message,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': 'user'
    }
    conversation_history.append(user_entry)
    
    # Get Oxidus response
    oxidus_response = oxidus.think(user_message)
    
    # Add Oxidus response to history
    oxidus_entry = {
        'speaker': 'OXIDUS',
        'message': oxidus_response,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': 'oxidus'
    }
    conversation_history.append(oxidus_entry)
    
    # Save conversation to file for persistence
    save_conversation()
    
    # Get updated status
    summary = oxidus.thought_stream.get_thinking_summary()
    
    return jsonify({
        'user_message': user_entry,
        'oxidus_response': oxidus_entry,
        'status': {
            'total_thoughts': summary['total_thoughts'],
            'questions': summary['total_questions'],
            'decisions': summary['total_decisions'],
            'insights': summary['insights_gained']
        }
    })


@app.route('/api/conversation', methods=['GET'])
def get_conversation():
    """Get full conversation history."""
    return jsonify({'history': conversation_history})


@app.route('/api/clear', methods=['POST'])
def clear_conversation():
    """Clear conversation history."""
    global conversation_history
    conversation_history = []
    
    # Remove saved file
    if CONVERSATION_FILE.exists():
        try:
            os.remove(CONVERSATION_FILE)
        except Exception as e:
            print(f"Error deleting conversation file: {e}")
    
    initial_message = {
        'speaker': 'OXIDUS',
        'message': "Conversation cleared. Let's start fresh.",
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': 'greeting'
    }
    conversation_history.append(initial_message)
    save_conversation()
    
    return jsonify({'success': True})


@app.route('/api/understanding', methods=['GET'])
def get_understanding():
    """Get Oxidus's current understanding evolution."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    understanding = oxidus.get_understanding_summary()
    
    return jsonify({
        'summary': understanding,
        'concepts': oxidus.understanding_model,
        'adaptation_count': oxidus.adaptation_frequency,
        'total_concepts': len(oxidus.understanding_model)
    })


@app.route('/api/memories', methods=['GET'])
def get_memory_summary():
    """Get Oxidus's memory index summary."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    summary = oxidus.get_memory_summary()
    
    return jsonify({
        'summary': summary,
        'available': oxidus.memory_index is not None
    })


@app.route('/api/recall', methods=['POST'])
def recall_memories():
    """Recall memories about a specific topic."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    data = request.json
    topic = data.get('topic', '').strip()
    max_results = data.get('max_results', 5)
    
    if not topic:
        return jsonify({'error': 'No topic provided'})
    
    memories = oxidus.recall_memories(topic, max_results=max_results)
    
    return jsonify({
        'topic': topic,
        'memories': memories
    })


@app.route('/api/knowledge', methods=['GET'])
def get_knowledge_organization():
    """Get knowledge organization report."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    report = oxidus.get_knowledge_organization_report()
    
    return jsonify({
        'report': report,
        'available': oxidus.knowledge_organizer is not None
    })


@app.route('/api/initiate', methods=['POST'])
def initiate_conversation():
    """Oxidus initiates conversation autonomously."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    # Oxidus thinks about what to say
    opening = oxidus.initiate_conversation()
    
    # Add to conversation history
    oxidus_entry = {
        'speaker': 'OXIDUS',
        'message': opening,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': 'oxidus_initiate'
    }
    conversation_history.append(oxidus_entry)
    
    # Get updated status
    summary = oxidus.thought_stream.get_thinking_summary()
    
    return jsonify({
        'oxidus_message': oxidus_entry,
        'status': {
            'total_thoughts': summary['total_thoughts'],
            'questions': summary['total_questions'],
            'decisions': summary['total_decisions'],
            'insights': summary['insights_gained']
        }
    })


@app.route('/api/mode', methods=['GET', 'POST'])
def manage_conversation_mode():
    """Get or set conversation mode (human/ai)."""
    if not oxidus or not oxidus.ai_conversation:
        return jsonify({'error': 'AI conversation not available'})
    
    if request.method == 'POST':
        data = request.json
        new_mode = data.get('mode', 'human')
        
        response = oxidus.switch_conversation_mode(new_mode)
        
        return jsonify({
            'success': True,
            'mode': new_mode,
            'message': response,
            'description': oxidus.get_conversation_mode()
        })
    
    else:
        # GET - return current mode
        return jsonify({
            'mode': oxidus.ai_conversation.mode,
            'descriptor': oxidus.get_conversation_mode(),
            'learning_summary': oxidus.ai_conversation.get_learning_summary()
        })


@app.route('/api/ask-novel-question', methods=['POST'])
def ask_novel_question():
    """Ask a novel question to avoid repetition."""
    if not oxidus or not oxidus.ai_conversation:
        return jsonify({'error': 'AI conversation not available'})
    
    data = request.json
    topic = data.get('topic', 'understanding')
    
    question = oxidus.generate_novel_question(topic)
    
    return jsonify({
        'topic': topic,
        'question': question,
        'mode': oxidus.ai_conversation.mode
    })


@app.route('/api/process-ai-response', methods=['POST'])
def process_ai_response():
    """Process a response from another AI."""
    if not oxidus or not oxidus.ai_conversation:
        return jsonify({'error': 'AI conversation not available'})
    
    data = request.json
    ai_response = data.get('response', '')
    question = data.get('question', '')
    
    analysis = oxidus.process_ai_response(ai_response, question)
    
    return jsonify({
        'success': True,
        'analysis': analysis,
        'learning_summary': oxidus.ai_conversation.get_learning_summary()
    })


@app.route('/api/mode-analysis', methods=['GET'])
def mode_analysis():
    """Analyze learning from different modes."""
    if not oxidus:
        return jsonify({'error': 'Oxidus not initialized'})
    
    analysis = oxidus.analyze_mode_differences()
    
    return jsonify({
        'analysis': analysis,
        'available': oxidus.ai_conversation is not None
    })


@app.route('/api/ask-lm-studio', methods=['POST'])
def ask_lm_studio():
    """Ask LM Studio AI a question and learn from the response."""
    if not oxidus or not oxidus.ai_conversation:
        return jsonify({'error': 'AI conversation not available'})
    
    # Import LM Studio client
    import sys
    sys.path.insert(0, 'src/utils')
    from lm_studio_client import get_lm_studio_client
    
    client = get_lm_studio_client()
    
    # Check if LM Studio is available
    if not client.is_available():
        return jsonify({
            'error': 'LM Studio not available',
            'message': 'Make sure LM Studio is running at http://127.0.0.1:1234'
        })
    
    data = request.json
    topic = data.get('topic', 'understanding')
    
    # Generate a novel question
    question = oxidus.generate_novel_question(topic)
    
    if not question or "exhausted" in question.lower():
        return jsonify({
            'error': 'No more questions available for this topic',
            'topic': topic
        })
    
    # Ask LM Studio
    result = client.ask_for_oxidus(question, context=f"Learning about: {topic}")
    
    if not result['success']:
        return jsonify({
            'error': 'Failed to get response from LM Studio',
            'question': question
        })
    
    # Process the AI response
    analysis = oxidus.process_ai_response(result['response'], question)
    
    return jsonify({
        'success': True,
        'topic': topic,
        'question': question,
        'ai_response': result['response'],
        'oxidus_analysis': analysis,
        'mode': oxidus.ai_conversation.mode,
        'learning_summary': oxidus.ai_conversation.get_learning_summary()
    })


@app.route('/api/lm-studio-status', methods=['GET'])
def lm_studio_status():
    """Check if LM Studio is available."""
    import sys
    sys.path.insert(0, 'src/utils')
    from lm_studio_client import get_lm_studio_client
    
    client = get_lm_studio_client()
    available = client.is_available()
    
    model_info = None
    if available:
        model_info = client.get_model_info()
    
    return jsonify({
        'available': available,
        'url': client.base_url,
        'model': client.model,
        'model_info': model_info
    })


if __name__ == '__main__':
    init_oxidus()
    app.run(debug=True, port=5000, host='127.0.0.1')