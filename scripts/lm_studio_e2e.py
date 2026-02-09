#!/usr/bin/env python3
"""Run an end-to-end LM Studio question -> Oxidus processing -> secondary judgment."""
import sys
from pathlib import Path
import json
repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.oxidus import Oxidus
from utils.lm_studio_client import get_lm_studio_client

def main():
    ox = Oxidus()
    client = get_lm_studio_client()
    if not client.is_available():
        print('LM Studio not available')
        return

    question = 'What are the main mechanisms that cause ocean tides?'
    print('Asking primary model...')
    primary = client.ask_for_oxidus(question, context='Geophysical phenomena')
    print('Primary success:', primary['success'])
    print('Primary response sample:', (primary['response'] or '')[:500])

    # If primary failed (likely due to model timeout), try a smaller/faster model as fallback
    if not primary['success']:
        print('\nPrimary failed; trying fallback small models')
        fallback_models = ['grok-1', 'mistralai/magistral-small-2509', 'qwen/qwen2.5-coder-32b']
        fallback = None
        for m in fallback_models:
            try:
                print('Trying model:', m)
                fallback = client.ask_question(question, system_prompt='You are a concise assistant.', model=m, max_tokens=200)
            except Exception as e:
                print('Model request error:', e)
                fallback = None
            if fallback:
                print('Got response from', m)
                break
        print('Fallback response sample:', (fallback or '')[:500])
        if fallback:
            primary = {'success': True, 'question': question, 'response': fallback}

    if primary.get('success'):
        analysis = ox.process_ai_response(primary['response'], primary.get('question'))
        print('\nOxidus processed primary response:')
        print(analysis)

        print('\nAsking secondary judgment model...')
        secondary = client.ask_secondary_judgment(primary['response'], primary['question'], context='Check for unknowns and critique')
        print('Secondary response sample:', (secondary or '')[:500])
        if secondary:
            sec_analysis = ox.process_secondary_judgment(secondary, primary['question'])
            print('\nOxidus processed secondary judgment:')
            print(sec_analysis)

if __name__ == '__main__':
    main()
