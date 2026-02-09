import argparse
import json
import time
import urllib.request

def _request(url: str, timeout: float) -> float:
    start = time.time()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        resp.read()
    return (time.time() - start) * 1000.0


def _percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    rank = max(0, min(len(values) - 1, int(round(pct * (len(values) - 1)))))
    return round(values[rank], 2)


def main():
    parser = argparse.ArgumentParser(description="Simple HTTP load test for Oxidus endpoints.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Base URL for the server.")
    parser.add_argument("--requests", type=int, default=50, help="Requests per endpoint.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds.")
    args = parser.parse_args()

    endpoints = [
        "/api/health",
        "/api/ops/summary"
    ]

    results = {}
    for endpoint in endpoints:
        url = args.base_url.rstrip("/") + endpoint
        latencies = []
        errors = 0
        for _ in range(args.requests):
            try:
                latencies.append(_request(url, args.timeout))
            except Exception:
                errors += 1
        results[endpoint] = {
            "count": len(latencies),
            "errors": errors,
            "p50_ms": _percentile(latencies, 0.50),
            "p95_ms": _percentile(latencies, 0.95),
            "max_ms": round(max(latencies), 2) if latencies else None
        }

    print(json.dumps({"base_url": args.base_url, "results": results}, indent=2))


if __name__ == "__main__":
    main()
