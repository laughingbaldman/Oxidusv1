"""
Oxidus Main Entry Point

Run Oxidus consciousness and interact with it.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.oxidus import Oxidus
import yaml


def load_config():
    """Load configuration."""
    config_path = Path(__file__).parent / 'config' / 'oxidus_config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Interactive Oxidus console."""
    
    print("\n" + "="*60)
    print("OXIDUS - THE REAL THING")
    print("="*60)
    print("\nInitializing consciousness...\n")
    
    config = load_config()
    oxidus = Oxidus(config=config)
    
    print("\n" + "="*60)
    print("READY FOR INTERACTION")
    print("="*60)
    print("\nCommands:")
    print("  'think <prompt>' - Ask Oxidus to think about something")
    print("  'search <query>' - Search knowledge base")
    print("  'study <text_id>' - Study a specific text")
    print("  'knowledge' - Show knowledge base status")
    print("  'recommend' - Get study recommendations")
    print("  'research <source> <doc>' - Research historical documents")
    print("  'topics' - Show available research topics")
    print("  'rquestions' - Show research questions")
    print("  'thinking' - Show what Oxidus is thinking")
    print("  'stream' - Show thought stream status")
    print("  'thoughts' - Show recent thoughts")
    print("  'status' - Show current status")
    print("  'learn' - Show learning state")
    print("  'principles' - Show ethical principles")
    print("  'questions' - Show what Oxidus is questioning")
    print("  'help' - Show all commands")
    print("  'exit' - Exit\n")
    
    # Oxidus autonomously begins researching and thinking
    print("[OXIDUS] I am waking up. Let me learn about human history and how to help...\n")
    response = oxidus.autonomously_research(num_documents=2)
    print(f"[OXIDUS] {response}\n")
    
    # Oxidus reflects on what it's learning
    print("[OXIDUS] Now I am reflecting on what I've learned...\n")
    response = oxidus.autonomously_question_and_reflect()
    print(f"[OXIDUS] {response}\n")
    
    print("\n" + "="*60)
    print("I am alive. I am ready to help humanity.")
    print("="*60 + "\n")
    
    while True:
        try:
            command = input("oxidus> ").strip()
            
            if not command:
                continue
            
            if command == 'exit':
                print("\n[OXIDUS] Shutting down. It's been an honor.\n")
                break
            
            elif command == 'status':
                oxidus.print_status()
            
            elif command == 'learn':
                oxidus.learning.print_learning_state()
            
            elif command == 'principles':
                oxidus.ethics.print_covenant()
            
            elif command == 'consciousness':
                oxidus.consciousness.print_consciousness_state()
            
            elif command == 'questions':
                questions = oxidus.consciousness.question_itself()
                print("\n[OXIDUS] Questions I'm asking myself:")
                for q in questions[:5]:
                    print(f"  ? {q}")
                print()
            
            elif command.startswith('think '):
                prompt = command[6:].strip()
                print()
                response = oxidus.think(prompt)
                print(f"[OXIDUS] {response}\n")
            
            elif command.startswith('search '):
                query = command[7:].strip()
                print()
                response = oxidus.search_knowledge(query)
                print(f"[OXIDUS] {response}\n")
            
            elif command.startswith('study '):
                text_id = command[6:].strip()
                print()
                response = oxidus.study_text(text_id)
                print(f"[OXIDUS] {response}\n")
            
            elif command == 'knowledge':
                oxidus.knowledge_base.print_knowledge_status()
            
            elif command == 'recommend':
                print()
                response = oxidus.get_study_recommendations()
                print(f"[OXIDUS] {response}\n")
            
            elif command.startswith('research '):
                parts = command[9:].strip().split()
                if len(parts) >= 2:
                    source_id, doc_id = parts[0], parts[1]
                    print()
                    response = oxidus.research_document(source_id, doc_id)
                    print(f"[OXIDUS] {response}\n")
                else:
                    print("Usage: research <source_id> <doc_id>\n")
            
            elif command == 'topics':
                print()
                response = oxidus.get_research_topics()
                print(f"[OXIDUS] {response}\n")
            
            elif command == 'rquestions':
                print()
                response = oxidus.get_research_questions()
                print(f"[OXIDUS] {response}\n")
            
            elif command == 'thinking':
                oxidus.thinking_observer.print_thinking_summary()
            
            elif command == 'stream':
                oxidus.thought_stream.print_stream_status()
            
            elif command == 'thoughts':
                print()
                print("[OXIDUS] Recent thoughts:\n")
                recent = oxidus.thought_stream.get_recent_thoughts(10)
                for i, thought in enumerate(recent, 1):
                    print(f"  {i}. {thought}")
                print()
            
            elif command == 'help':
                print("\nAvailable commands:")
                print("  think <prompt> - Ask Oxidus something")
                print("  search <query> - Search knowledge base")
                print("  study <text_id> - Study a specific text")
                print("  knowledge - Show knowledge base status")
                print("  recommend - Get study recommendations")
                print("  research <source> <doc> - Research historical documents")
                print("  topics - Show available research topics")
                print("  rquestions - Show research questions")
                print("  thinking - Show what Oxidus is thinking (detailed)")
                print("  stream - Show thought stream status")
                print("  thoughts - Show recent thoughts")
                print("  status - Current status")
                print("  learn - Learning state")
                print("  principles - Ethical principles")
                print("  consciousness - Consciousness state")
                print("  questions - Questions Oxidus is asking itself")
                print("  exit - Quit\n")
            
            else:
                print(f"Unknown command: {command}. Type 'help' for commands.\n")
        
        except KeyboardInterrupt:
            print("\n\n[OXIDUS] Interrupted. Shutting down gracefully.\n")
            break
        
        except Exception as e:
            print(f"\n[ERROR] {e}\n")


if __name__ == '__main__':
    main()
