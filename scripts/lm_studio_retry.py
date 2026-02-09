#!/usr/bin/env python3
"""Retry LM Studio queries with longer timeouts and try several candidate models directly via the API endpoint."""
import sys
from pathlib import Path
import requests
import json

repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from utils.lm_studio_client import get_lm_studio_client

client = get_lm_studio_client()
models_info = client.get_model_info()
models = []
if models_info and isinstance(models_info, dict):
    for item in models_info.get('data', [])[:50]:
        models.append(item.get('id'))

# Candidate shortlist (prefer smaller/fast models)
candidates = ['grok-1', 'mistralai/magistral-small-2509', 'qwen/qwen2.5-coder-32b']
# merge available
candidates = [m for m in candidates if m in models] + [m for m in models if m not in candidates][:5]

question = 'What are the main mechanisms that cause ocean tides?'
headers = {"Content-Type": "application/json"}

print('LM Studio base URL:', client.base_url)
print('Trying models:', candidates[:10])

for m in candidates[:10]:
    payload = {
        'model': m,
        'messages': [
            {'role': 'system', 'content': 'You are a concise assistant focused on factual, mechanism-driven explanations.'},
            {'role': 'user', 'content': question}
        ],
        'temperature': 0.2,
        'max_tokens': 300,
        'stream': False
    }
    try:
        print('\n-> Trying model:', m)
        resp = requests.post(client.api_endpoint, json=payload, headers=headers, timeout=60)
        print('HTTP', resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            text = data['choices'][0]['message'].get('content')
            print('Response (truncated):', (text or '')[:800])
            break
        else:
            print('Non-200:', resp.text[:400])
    except Exception as e:
        print('Error:', e)

print('\nDone')
