#!/usr/bin/env python3
"""Test Oxidus initialization and core functionality"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_initialization():
    """Test that Oxidus initializes properly"""
    print("="*60)
    print("TESTING OXIDUS INITIALIZATION")
    print("="*60)
    
    try:
        print("\n[1/7] Importing Oxidus...")
        from core.oxidus import Oxidus
        print("✓ Import successful")
        
        print("\n[2/7] Creating Oxidus instance...")
        oxidus = Oxidus()
        print("✓ Instance created")
        
        print("\n[3/7] Checking thought stream...")
        assert oxidus.thought_stream is not None, "Thought stream is None"
        assert hasattr(oxidus.thought_stream, 'add_thought'), "Missing add_thought method"
        print(f"✓ Thought stream active: {type(oxidus.thought_stream).__name__}")
        
        print("\n[4/7] Checking autonomous thinking thread...")
        assert oxidus.autonomous_thread is not None, "Autonomous thread is None"
        assert oxidus.autonomous_thread.is_alive(), "Autonomous thread not running"
        print(f"✓ Autonomous thread alive: {oxidus.autonomous_thread.is_alive()}")
        
        print("\n[5/7] Checking consciousness module...")
        assert oxidus.consciousness is not None, "Consciousness is None"
        assert hasattr(oxidus.consciousness, 'question_itself'), "Missing question_itself method"
        print(f"✓ Consciousness ready: {type(oxidus.consciousness).__name__}")
        
        print("\n[6/7] Checking learning system...")
        assert oxidus.learning is not None, "Learning system is None"
        print(f"✓ Learning system: {type(oxidus.learning).__name__}")
        
        print("\n[7/7] Testing thought generation...")
        from utils.thought_stream import ThoughtType
        thought = oxidus.thought_stream.add_thought(
            ThoughtType.SYSTEM,
            "Testing thought system functionality"
        )
        if thought:
            print(f"✓ Thought generated: '{thought.content[:50]}...'")
        else:
            print("⚠ Thought was duplicate (deduplication working)")
        
        # Check storage thread
        print("\n[BONUS] Checking storage thread...")
        assert oxidus.thought_stream.running, "Storage thread not running"
        assert oxidus.thought_stream.storage_thread.is_alive(), "Storage thread dead"
        print(f"✓ Storage thread alive: {oxidus.thought_stream.storage_thread.is_alive()}")
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓✓✓")
        print("="*60)
        print("\nOxidus is fully operational!")
        print(f"- Thoughts in buffer: {len(oxidus.thought_stream.thoughts)}")
        print(f"- Autonomous thinking: {oxidus.autonomous_thinking_enabled}")
        print(f"- Active learning: {oxidus.active_learning_enabled}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_initialization()
    sys.exit(0 if success else 1)
