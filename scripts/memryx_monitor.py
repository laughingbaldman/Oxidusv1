"""
MemryX monitor loop for Oxidus.
Prints MX3 device IDs and indexing status on an interval.
"""

import argparse
import os
import time
from pathlib import Path

import requests


def load_token() -> str:
    token = os.environ.get('OXIDUS_ADMIN_TOKEN', '').strip()
    if token:
        return token
    token_path = Path(__file__).parent.parent / 'config' / 'admin_token.txt'
    try:
        if token_path.exists():
            return token_path.read_text(encoding='utf-8').strip()
    except Exception:
        return ''
    return ''


def fetch_json(url: str, token: str):
    headers = {'X-Oxidus-Admin-Token': token} if token else {}
    return requests.get(url, headers=headers, timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=int, default=15)
    parser.add_argument('--base-url', default=os.environ.get('OXIDUS_BASE_URL', 'http://127.0.0.1:5000'))
    args = parser.parse_args()

    token = load_token()
    base_url = args.base_url.rstrip('/')

    print('Oxidus MemryX monitor running...')
    print(f'Base URL: {base_url}')
    print(f'Interval: {args.interval}s')
    if not token:
        print('Admin token missing. Set OXIDUS_ADMIN_TOKEN or config/admin_token.txt.')

    # Wait for Oxidus API to come up
    for _ in range(12):
        try:
            health = requests.get(f'{base_url}/api/status', timeout=2)
            if health.ok:
                break
        except requests.exceptions.RequestException:
            pass
        print(f"[{time.strftime('%H:%M:%S')}] Waiting for Oxidus API...")
        time.sleep(5)

    while True:
        try:
            devices = fetch_json(f'{base_url}/api/admin/memryx/devices', token)
            indexing = fetch_json(f'{base_url}/api/admin/indexing/status', token)

            timestamp = time.strftime('%H:%M:%S')
            if devices.status_code == 401:
                print(f'[{timestamp}] Unauthorized. Check admin token.')
            elif devices.ok:
                data = devices.json()
                ids = data.get('device_ids', [])
                source = data.get('source', 'unknown')
                errors = data.get('errors') or []
                if errors:
                    print(f'[{timestamp}] Devices ({source}): {ids or "none"} | errors: {"; ".join(errors)}')
                else:
                    print(f'[{timestamp}] Devices ({source}): {ids or "none"}')
            else:
                print(f'[{timestamp}] Devices request failed: {devices.status_code}')

            if indexing.ok:
                idx = indexing.json()
                running = idx.get('running')
                last_error = idx.get('last_error')
                last_result = idx.get('last_result') or {}
                throughput = idx.get('throughput_eps', 0.0)
                avg_batch_ms = idx.get('avg_batch_ms', 0.0)
                device_ids = idx.get('device_ids', [])
                processed = idx.get('processed_batches', 0)
                total = idx.get('total_batches', 0)
                if running:
                    progress = f"{processed}/{total} batches" if total else "progress n/a"
                    device_text = f"devices {device_ids}" if device_ids else "devices n/a"
                    print(
                        f'[{timestamp}] Indexing: running | {progress} | {throughput} embeddings/s | '
                        f'{avg_batch_ms} ms/batch | {device_text}'
                    )
                elif last_error:
                    print(f'[{timestamp}] Indexing error: {last_error}')
                elif last_result:
                    print(
                        f"[{timestamp}] Indexing done: {last_result.get('vectors', 0)} vectors | "
                        f"{last_result.get('dimensions', 0)} dim"
                    )
                else:
                    print(f'[{timestamp}] Indexing: idle')
            else:
                print(f'[{timestamp}] Indexing request failed: {indexing.status_code}')

        except requests.exceptions.RequestException:
            timestamp = time.strftime('%H:%M:%S')
            print(f'[{timestamp}] Waiting for Oxidus API...')

        time.sleep(args.interval)


if __name__ == '__main__':
    raise SystemExit(main())
