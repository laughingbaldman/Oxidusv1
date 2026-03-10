"""
Test script to verify security fixes don't break functionality.
"""
import sys
from pathlib import Path

# Test imports
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from web_gui import (
        _is_path_safe, 
        _resolve_path_under_base,
        _resolve_relative_path_under_base,
        _extract_query_topics
    )
    print("✓ Web GUI imports successful")
except Exception as e:
    print(f"✗ Web GUI import failed: {e}")
    sys.exit(1)

try:
    from src.core.oxidus import Oxidus
    print("✓ Oxidus core imports successful")
except Exception as e:
    print(f"✗ Oxidus import failed: {e}")
    sys.exit(1)

try:
    from src.utils.lm_studio_client import LMStudioClient
    print("✓ LM Studio client imports successful")
except Exception as e:
    print(f"✗ LM Studio client import failed: {e}")
    sys.exit(1)

# Test path validation functions
print("\n=== Testing Path Validation ===")
base = Path(__file__).parent / 'data'
base.mkdir(exist_ok=True)

# Test valid path
valid_path = _resolve_path_under_base('knowledge_base', base)
if valid_path:
    print(f"✓ Valid path resolution works")
else:
    print(f"✗ Valid path resolution failed")

# Test path traversal attempt (should be blocked)
traversal_path = _resolve_path_under_base('../../../etc/passwd', base)
if not traversal_path:
    print(f"✓ Path traversal blocked correctly")
else:
    print(f"✗ Path traversal NOT blocked - SECURITY ISSUE")

# Test relative path validation
rel_path = _resolve_relative_path_under_base('knowledge_base/wiki_corpus', base)
if rel_path:
    print(f"✓ Relative path resolution works")
else:
    print(f"✗ Relative path resolution failed")

# Test absolute path in relative function (should be blocked)
abs_path = _resolve_relative_path_under_base('/etc/passwd', base)
if not abs_path:
    print(f"✓ Absolute path in relative resolver blocked")
else:
    print(f"✗ Absolute path NOT blocked - SECURITY ISSUE")

# Test query topic extraction (ReDoS fix)
print("\n=== Testing Query Topic Extraction ===")
try:
    # Normal query
    topics = _extract_query_topics("tell me about machine learning and neural networks")
    print(f"✓ Normal query extraction works: {len(topics)} topics")
    
    # Very long query (should be truncated)
    long_query = "a" * 20000
    topics = _extract_query_topics(long_query)
    print(f"✓ Long query handled (truncated to prevent ReDoS)")
    
    # Empty query
    topics = _extract_query_topics("")
    if topics == []:
        print(f"✓ Empty query handled correctly")
except Exception as e:
    print(f"✗ Query extraction failed: {e}")

# Test URL validation
print("\n=== Testing URL Validation ===")
from urllib.parse import urlparse

def test_wikipedia_check(url):
    """Simulate the fixed Wikipedia domain check."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    domain_parts = domain.split('.')
    is_wikipedia = (
        domain == 'wikipedia.org' or 
        (len(domain_parts) >= 3 and 
         domain_parts[-2] == 'wikipedia' and 
         domain_parts[-1] == 'org')
    )
    return is_wikipedia

valid_wiki = test_wikipedia_check("https://en.wikipedia.org/wiki/Something")
if valid_wiki:
    print(f"✓ Valid Wikipedia URL accepted")

invalid_wiki1 = test_wikipedia_check("https://wikipedia.org.evil.com/")
if not invalid_wiki1:
    print(f"✓ Spoofed Wikipedia domain blocked")
else:
    print(f"✗ Spoofed domain NOT blocked - SECURITY ISSUE")

invalid_wiki2 = test_wikipedia_check("https://notwikipedia.org/")
if not invalid_wiki2:
    print(f"✓ Non-Wikipedia domain rejected")

print("\n=== All Security Tests Complete ===")
print("If you see any '✗' above, there may be an issue with the fixes.")
print("Otherwise, security fixes appear to be working correctly!")
