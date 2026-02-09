#!/usr/bin/env python3
"""Run a rebuild of Oxidus knowledge index and perform quick smoke checks.
"""
import sys
from pathlib import Path
import json

repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.oxidus import Oxidus


def main():
    print('Initializing Oxidus...')
    ox = Oxidus()
    print('Running rebuild_knowledge_index()...')
    result = ox.rebuild_knowledge_index()
    print('\nREBUILD RESULT:')
    print(json.dumps(result, indent=2))

    print('\nRunning smoke checks...')
    checks = {}
    try:
        if hasattr(ox, 'get_memory_summary'):
            checks['memory_summary'] = ox.get_memory_summary()
        else:
            checks['memory_summary'] = None
    except Exception as e:
        checks['memory_summary_error'] = str(e)

    try:
        if hasattr(ox, 'get_knowledge_organization_report'):
            report = ox.get_knowledge_organization_report()
            checks['knowledge_report_sample'] = report if isinstance(report, dict) else str(report)[:1000]
        else:
            checks['knowledge_report_sample'] = None
    except Exception as e:
        checks['knowledge_report_error'] = str(e)

    try:
        # Basic think() smoke test (non-destructive) - call as owner to avoid access restrictions
        # Prefer safe_think which guarantees a string result
        if hasattr(ox, 'safe_think'):
            resp = ox.safe_think('Hello, how are you?', user_id=ox.owner_id)
        else:
            resp = ox.think('Hello, how are you?', user_id=ox.owner_id)
        checks['think_response'] = resp[:400]
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        checks['think_error'] = str(e)
        checks['think_traceback'] = tb

    print('\nSMOKE CHECKS:')
    print(json.dumps(checks, indent=2, default=str))


if __name__ == '__main__':
    main()
