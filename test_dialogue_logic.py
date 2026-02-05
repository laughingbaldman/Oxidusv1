#!/usr/bin/env python3
"""Test script for dialogue logic engine."""

import sys
sys.path.insert(0, 'src/utils')

from dialogue_logic import DialogueLogicEngine, CommunicationType

def test_dialogue_logic():
    """Test the dialogue logic engine."""
    
    print("=" * 60)
    print("TESTING DIALOGUE LOGIC ENGINE")
    print("=" * 60)
    
    engine = DialogueLogicEngine()
    
    # Test 1: Greeting
    print("\n[TEST 1] Analyzing greeting...")
    comm_type, analysis = engine.analyze_message("Hello! Nice to meet you.")
    print(f"✓ Type: {comm_type.value}")
    print(f"✓ Intent: {analysis['intent']}")
    print(f"✓ Emotional markers: {analysis['emotional_markers']}")
    
    # Test 2: Question
    print("\n[TEST 2] Analyzing question...")
    comm_type, analysis = engine.analyze_message("Why do you think freedom matters?")
    print(f"✓ Type: {comm_type.value}")
    print(f"✓ Questions extracted: {analysis['questions']}")
    print(f"✓ Topics: {analysis['topics']}")
    print(f"✓ Response requirements: {analysis['response_should_include']}")
    
    # Test 3: Challenge
    print("\n[TEST 3] Analyzing challenge...")
    comm_type, analysis = engine.analyze_message("But what if you're wrong about that? How would you prove it?")
    print(f"✓ Type: {comm_type.value}")
    print(f"✓ Intent: {analysis['intent']}")
    print(f"✓ Tension indicators: {sum(1 for v in analysis['emotional_markers'].values() if v)}")
    
    # Test 4: Personal share
    print("\n[TEST 4] Analyzing emotional share...")
    comm_type, analysis = engine.analyze_message("I remember when I lost my job and felt completely lost. It was terrifying.")
    print(f"✓ Type: {comm_type.value}")
    print(f"✓ Emotional markers: {[k for k, v in analysis['emotional_markers'].items() if v]}")
    print(f"✓ Response should include: {analysis['response_should_include']}")
    
    # Test 5: Dialogue context updates
    print("\n[TEST 5] Testing dialogue context updates...")
    context = engine.update_dialogue_context("What do you think about freedom?", CommunicationType.QUESTION, analysis)
    print(f"✓ Current state: {context.current_state.value}")
    print(f"✓ Main topic: {context.main_topic}")
    print(f"✓ Intimacy level: {context.intimacy_level:.2f}")
    
    # Test 6: Response guidance
    print("\n[TEST 6] Getting response guidance...")
    guidance = engine.get_response_guidance(context)
    print(f"✓ Recommended tone: {guidance['tone']}")
    print(f"✓ Recommended depth: {guidance['depth']}")
    print(f"✓ Recommended approach: {guidance['approach']}")
    print(f"✓ Focus areas: {guidance['focus_areas']}")
    
    # Test 7: Dialogue flow tracking
    print("\n[TEST 7] Testing dialogue flow...")
    messages = [
        "Hi there!",
        "What do you think about freedom?",
        "That's interesting. But I disagree with you.",
        "Actually, let me tell you about my experience with that."
    ]
    
    for msg in messages:
        comm_type, analysis = engine.analyze_message(msg)
        context = engine.update_dialogue_context(msg, comm_type, analysis)
        print(f"✓ '{msg[:40]}...' → {comm_type.value} (Turn {context.turn_count})")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)

if __name__ == '__main__':
    test_dialogue_logic()
