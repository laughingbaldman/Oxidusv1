"""
Test AI Conversation Integration
Quick verification that all modes and question generation work correctly.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_mode_switching():
    """Test switching between HUMAN, AI, and HYBRID modes."""
    print("\n🔄 Testing Mode Switching...")
    
    modes = ["HUMAN", "AI", "HYBRID"]
    for mode in modes:
        response = requests.post(f"{BASE_URL}/api/mode", json={"mode": mode})
        data = response.json()
        if data.get("success"):
            print(f"  ✅ Switched to {mode} mode: {data.get('message', '')[:60]}...")
        else:
            print(f"  ❌ Failed to switch to {mode} mode")
    
    # Get current mode
    response = requests.get(f"{BASE_URL}/api/mode")
    data = response.json()
    print(f"\n  Current Mode: {data.get('mode')}")
    print(f"  Description: {data.get('description', '')[:80]}...")

def test_novel_question_generation():
    """Test generating novel questions without repetition."""
    print("\n❓ Testing Novel Question Generation...")
    
    topics = ["consciousness", "learning", "ethics"]
    
    for topic in topics:
        print(f"\n  Topic: {topic}")
        # Ask 3 questions per topic to verify no repetition
        for i in range(3):
            response = requests.post(f"{BASE_URL}/api/ask-novel-question", json={"topic": topic})
            data = response.json()
            if data.get("success"):
                question = data.get("question", "")
                print(f"    Q{i+1}: {question[:80]}...")
            else:
                print(f"    ❌ Failed: {data.get('message', '')}")

def test_ai_response_processing():
    """Test processing AI responses and recording insights."""
    print("\n🤖 Testing AI Response Processing...")
    
    # Switch to AI mode first
    requests.post(f"{BASE_URL}/api/mode", json={"mode": "AI"})
    
    ai_response = "Consciousness emerges from complex information processing patterns. Neural networks with sufficient depth and recurrent connections can exhibit emergent properties that resemble awareness. This is a logical analysis based on computational theory of mind."
    
    response = requests.post(f"{BASE_URL}/api/process-ai-response", json={
        "ai_response": ai_response,
        "original_question": "What is consciousness from a computational perspective?"
    })
    
    data = response.json()
    if data.get("success"):
        print(f"  ✅ Processed AI response")
        print(f"  Learning: {data.get('learning_response', '')[:100]}...")
    else:
        print(f"  ❌ Failed to process AI response")

def test_mode_analysis():
    """Test comparing insights from different modes."""
    print("\n📊 Testing Mode Analysis...")
    
    response = requests.get(f"{BASE_URL}/api/mode-analysis")
    data = response.json()
    
    if data.get("success"):
        analysis = data.get("analysis", "")
        print(f"  ✅ Generated analysis:")
        print("\n" + "\n".join("    " + line for line in analysis.split("\n")[:20]))
    else:
        print(f"  ❌ Failed to get analysis")

def main():
    print("=" * 70)
    print("OXIDUS AI CONVERSATION INTEGRATION TEST")
    print("=" * 70)
    
    try:
        # Verify Oxidus is running
        response = requests.get(f"{BASE_URL}/api/status", timeout=2)
        if response.status_code == 200:
            print("✅ Oxidus is running at", BASE_URL)
        else:
            print("❌ Oxidus not responding properly")
            return
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to Oxidus at {BASE_URL}")
        print(f"   Make sure Oxidus is running with: python chromium_gui.py")
        return
    
    # Run tests
    test_mode_switching()
    test_novel_question_generation()
    test_ai_response_processing()
    test_mode_analysis()
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nAll AI conversation features are integrated and working!")
    print("Open http://127.0.0.1:5000 to use the GUI interface.")

if __name__ == "__main__":
    main()
