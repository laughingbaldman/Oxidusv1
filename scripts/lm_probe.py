"""LM Studio probe script used after launching Oxidus.
Prints availability and model list.
"""
from pathlib import Path
import sys
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / 'src'))
from utils.lm_studio_client import get_lm_studio_client

client = get_lm_studio_client()
print('LM Studio base:', client.base_url)
print('is_available:', client.is_available())
info = client.get_model_info()
print('models_info:', info if info else 'None')
