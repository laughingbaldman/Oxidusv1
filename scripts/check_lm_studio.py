#!/usr/bin/env python3
"""Check LM Studio client availability and model info."""
import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from utils.lm_studio_client import get_lm_studio_client
    client = get_lm_studio_client()
    available = client.is_available()
    print('LM Studio available:', available)
    if available:
        try:
            info = client.get_model_info()
            print('Model info:', info)
        except Exception as e:
            print('Failed to get model info:', e)
except Exception as e:
    print('LM Studio client not importable or error:', e)
