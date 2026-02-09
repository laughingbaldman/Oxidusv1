#!/usr/bin/env python3
"""
End-to-End Test Suite for Oxidus API
Tests all major endpoints and functionality
"""

import requests
import json
import time
from datetime import datetime
import pytest

BASE_URL = "http://127.0.0.1:5000"


def _require_server() -> None:
    try:
        response = requests.get(f"{BASE_URL}/api/status", timeout=2)
        if response.status_code != 200:
            pytest.skip("Oxidus API not ready")
    except requests.exceptions.RequestException:
        pytest.skip("Oxidus API not running")

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_test(test_name):
    print(f"\n{Colors.BLUE}{Colors.BOLD}[TEST] {test_name}{Colors.END}")

def print_pass(message):
    print(f"{Colors.GREEN}✓ PASS{Colors.END}: {message}")

def print_fail(message):
    print(f"{Colors.RED}✗ FAIL{Colors.END}: {message}")

def print_info(message):
    print(f"{Colors.YELLOW}ℹ INFO{Colors.END}: {message}")

def test_status_endpoint():
    """Test the status endpoint"""
    print_test("Status Endpoint")
    _require_server()
    try:
        response = requests.get(f"{BASE_URL}/api/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'total_thoughts' in data, "Missing total_thoughts"
        assert 'questions' in data, "Missing questions"
        assert 'decisions' in data, "Missing decisions"
        assert 'insights' in data, "Missing insights"
        
        print_pass(f"Status retrieved: {data['total_thoughts']} thoughts, {data['questions']} questions")
        return True
    except Exception as e:
        print_fail(f"Status test failed: {e}")
        raise

def test_thoughts_endpoint():
    """Test the thoughts endpoint"""
    print_test("Thoughts Endpoint")
    _require_server()
    try:
        response = requests.get(f"{BASE_URL}/api/thoughts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of thoughts"
        
        if len(data) > 0:
            thought = data[0]
            assert 'type' in thought, "Thought missing type"
            assert 'content' in thought, "Thought missing content"
            assert 'timestamp' in thought, "Thought missing timestamp"
            print_pass(f"Retrieved {len(data)} recent thoughts")
            print_info(f"Latest: [{thought['type']}] {thought['content'][:80]}...")
        else:
            print_pass("No thoughts yet (system just started)")
        return True
        
    except Exception as e:
        print_fail(f"Thoughts test failed: {e}")
        raise

def test_conversation_endpoint():
    """Test the conversation history endpoint"""
    print_test("Conversation History Endpoint")
    _require_server()
    try:
        response = requests.get(f"{BASE_URL}/api/conversation")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of messages"
        
        print_pass(f"Retrieved {len(data)} conversation messages")
        if len(data) > 0:
            latest = data[-1]
            print_info(f"Latest from {latest['speaker']}: {latest['message'][:80]}...")
        return True
        
    except Exception as e:
        print_fail(f"Conversation test failed: {e}")
        raise

def test_send_message():
    """Test sending a message to Oxidus"""
    print_test("Send Message to Oxidus")
    _require_server()
    try:
        test_message = "Hello Oxidus, this is an automated test. Can you acknowledge this message?"
        
        print_info(f"Sending: '{test_message}'")
        response = requests.post(
            f"{BASE_URL}/api/message",
            json={'message': test_message}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'oxidus_response' in data, "Missing oxidus_response"
        assert 'user_message' in data, "Missing user_message"
        
        oxidus_reply = data['oxidus_response']['message']
        print_pass(f"Message sent and response received")
        print_info(f"Oxidus replied: {oxidus_reply[:150]}...")
        return True
        
    except Exception as e:
        print_fail(f"Send message test failed: {e}")
        raise

def test_understanding_endpoint():
    """Test the understanding endpoint"""
    print_test("Understanding Summary Endpoint")
    _require_server()
    try:
        response = requests.get(f"{BASE_URL}/api/understanding")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'summary' in data, "Missing summary"
        assert 'concepts' in data, "Missing concepts"
        assert 'total_concepts' in data, "Missing total_concepts"
        
        print_pass(f"Understanding retrieved: {data['total_concepts']} concepts tracked")
        if data['total_concepts'] > 0:
            sample_concepts = list(data['concepts'].keys())[:3]
            print_info(f"Sample concepts: {', '.join(sample_concepts)}")
        return True
        
    except Exception as e:
        print_fail(f"Understanding test failed: {e}")
        raise

def test_memories_endpoint():
    """Test the memories endpoint"""
    print_test("Memories Endpoint")
    _require_server()
    try:
        response = requests.get(f"{BASE_URL}/api/memories")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'memories' in data, "Missing memories"
        assert 'available' in data, "Missing available flag"
        
        if data['available']:
            print_pass("Memory indexing is available")
            print_info(f"Total memories: {len(data['memories'])}")
        else:
            print_pass("Memory indexing not yet initialized (expected)")
        return True
        
    except Exception as e:
        print_fail(f"Memories test failed: {e}")
        raise

def test_knowledge_organization():
    """Test the knowledge organization endpoint"""
    print_test("Knowledge Organization Endpoint")
    _require_server()
    try:
        response = requests.get(f"{BASE_URL}/api/knowledge")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'report' in data, "Missing report"
        assert 'available' in data, "Missing available flag"
        
        if data['available']:
            print_pass("Knowledge organizer is available")
            # Check if report has content
            if len(data['report']) > 50:
                print_info(data['report'][:200])
            else:
                print_info("No knowledge organized yet (expected for new system)")
        else:
            print_pass("Knowledge organizer not initialized")
        return True
        
    except Exception as e:
        print_fail(f"Knowledge organization test failed: {e}")
        raise

def test_conversation_mode():
    """Test conversation mode endpoint"""
    print_test("Conversation Mode Endpoint")
    _require_server()
    try:
        # Get current mode
        response = requests.get(f"{BASE_URL}/api/mode")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'mode' in data, "Missing mode"
        assert 'descriptor' in data, "Missing descriptor"
        
        current_mode = data['mode']
        print_pass(f"Current mode: {current_mode}")
        print_info(data['descriptor'])
        return True
        
    except Exception as e:
        print_fail(f"Conversation mode test failed: {e}")
        raise

def test_initiate_conversation():
    """Test autonomous conversation initiation"""
    print_test("Autonomous Conversation Initiation")
    _require_server()
    try:
        print_info("Asking Oxidus to initiate conversation...")
        response = requests.post(f"{BASE_URL}/api/initiate")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'oxidus_message' in data, "Missing oxidus_message"
        
        message = data['oxidus_message']['message']
        print_pass("Oxidus initiated conversation")
        print_info(f"Oxidus says: {message[:150]}...")
        return True
        
    except Exception as e:
        print_fail(f"Initiate conversation test failed: {e}")
        raise

def test_lm_studio_status():
    """Test LM Studio connection status"""
    print_test("LM Studio Connection Status")
    _require_server()
    try:
        response = requests.get(f"{BASE_URL}/api/lm-studio-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'available' in data, "Missing available flag"
        
        if data['available']:
            print_pass("LM Studio is connected and available")
            if 'model' in data:
                print_info(f"Active model: {data['model']}")
        else:
            print_info("LM Studio not connected (expected if not configured)")
        return True
        
    except Exception as e:
        print_fail(f"LM Studio status test failed: {e}")
        raise

def run_all_tests():
    """Run all end-to-end tests"""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}OXIDUS END-TO-END API TEST SUITE{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"Testing against: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Status Endpoint", test_status_endpoint),
        ("Thoughts Endpoint", test_thoughts_endpoint),
        ("Conversation History", test_conversation_endpoint),
        ("Send Message", test_send_message),
        ("Understanding Summary", test_understanding_endpoint),
        ("Memories Index", test_memories_endpoint),
        ("Knowledge Organization", test_knowledge_organization),
        ("Conversation Mode", test_conversation_mode),
        ("Autonomous Initiation", test_initiate_conversation),
        ("LM Studio Status", test_lm_studio_status),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            time.sleep(0.5)  # Brief pause between tests
        except Exception as e:
            print_fail(f"Test crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for test_name, result in results:
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"  {status} - {test_name}")
    
    print(f"\n{Colors.BOLD}Total: {len(results)} tests{Colors.END}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
    print(f"{Colors.RED}Failed: {failed}{Colors.END}")
    
    success_rate = (passed / len(results) * 100) if results else 0
    print(f"\n{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.END}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! Oxidus is fully operational.{Colors.END}")
    else:
        print(f"\n{Colors.YELLOW}⚠ Some tests failed. Review output above for details.{Colors.END}")
    
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")
    
    return failed == 0

if __name__ == '__main__':
    try:
        success = run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Test suite crashed: {e}{Colors.END}")
        exit(1)
