#!/usr/bin/env python3
"""Test script for the knowledge organizer system."""

import sys
sys.path.insert(0, 'src')

from utils.knowledge_organizer import KnowledgeOrganizer

def test_knowledge_organizer():
    """Test the knowledge organizer with sample content."""
    
    print("=" * 60)
    print("TESTING KNOWLEDGE ORGANIZER")
    print("=" * 60)
    
    organizer = KnowledgeOrganizer()
    
    # Test 1: Add a sample source
    print("\n[TEST 1] Adding sample source...")
    sample_content = """
    # Philosophy of Mind
    
    The philosophy of mind is concerned with basic questions about the nature of consciousness.
    **Consciousness** is often described as the subjective experience of the world.
    
    ## Key Concepts
    
    - Dualism: The view that mind and body are separate substances
    - Physicalism: The view that everything is ultimately physical
    - Qualia: The subjective qualities of conscious experience
    - Intentionality: The property of mental states being about things
    
    The problem of other minds asks how we can know that other beings have consciousness.
    This raises questions about **empathy** and **understanding**.
    
    Many philosophers discuss the relationship between consciousness and **freedom** of choice.
    Some argue that consciousness requires ethical **responsibility**.
    """
    
    result = organizer.add_source(
        "https://en.wikipedia.org/wiki/Philosophy_of_mind",
        "Philosophy of Mind",
        sample_content
    )
    
    print(f"✓ Concepts found: {result['concepts_found']}")
    print(f"✓ Key concepts: {', '.join(result['key_concepts'][:5])}")
    print(f"✓ Value connections: {dict(list(result['value_connections'].items())[:3])}")
    
    # Test 2: Add another source
    print("\n[TEST 2] Adding second source...")
    sample_content_2 = """
    # Ethics and Morality
    
    Ethics is the study of right and wrong. Morality concerns **freedom**, **duty**, and **sacrifice**.
    
    ## Ethical Frameworks
    
    - Consequentialism: Evaluates actions by outcomes
    - Deontology: Focuses on duties and principles
    - Virtue Ethics: Emphasizes character and wisdom
    
    **Responsibility** and **learning** are central to ethical development.
    The capacity for **empathy** enables moral understanding.
    """
    
    result = organizer.add_source(
        "https://en.wikipedia.org/wiki/Ethics",
        "Ethics and Morality",
        sample_content_2
    )
    
    print(f"✓ Concepts found: {result['concepts_found']}")
    print(f"✓ Key concepts: {', '.join(result['key_concepts'][:5])}")
    
    # Test 3: Get knowledge report
    print("\n[TEST 3] Generating knowledge report...")
    report = organizer.get_knowledge_report()
    
    print(f"\n📚 Knowledge Report:")
    if isinstance(report, dict):
        print(f"  Total sources: {report.get('total_sources', 0)}")
        print(f"  Total concepts: {report.get('total_concepts', 0)}")
        if report.get('top_concepts'):
            print(f"  Top 5 concepts: {', '.join(report['top_concepts'][:5])}")
        if report.get('value_connections'):
            values = report['value_connections']
            print(f"  Detected values: {', '.join(list(values.keys())[:5])}")
    else:
        # String report - print first 800 chars
        report_lines = report.split('\n')[:15]  # First 15 lines
        print('\n'.join(report_lines))
    
    # Test 4: Search concepts
    print("\n[TEST 4] Searching concepts...")
    search_results = organizer.search_concepts("consciousness")
    print(f"✓ Search results for 'consciousness':")
    if isinstance(search_results, dict):
        print(f"  Direct matches: {search_results.get('direct_matches', [])}")
        print(f"  Related matches: {search_results.get('related_matches', [])}")
        print(f"  Sources: {search_results.get('sources', [])}")
    
    # Test 5: Connect to human context
    print("\n[TEST 5] Connecting to human context...")
    human_statement = "I'm trying to understand what makes us free as conscious beings"
    context = organizer.connect_to_human_context(human_statement)
    
    if isinstance(context, dict):
        print(f"✓ Detected values: {context.get('values_detected', [])}")
        print(f"✓ Relevant sources: {context.get('relevant_sources', [])}")
        if context.get('knowledge_connections'):
            print(f"✓ Knowledge connections: {len(context['knowledge_connections'])} found")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 60)

if __name__ == '__main__':
    test_knowledge_organizer()
