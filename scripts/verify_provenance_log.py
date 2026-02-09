import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.metadata_governance import verify_provenance_log


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify provenance log hash chain")
    parser.add_argument(
        "--metadata-dir",
        default="data/knowledge_base/metadata",
        help="Path to metadata directory"
    )
    args = parser.parse_args()

    log_path = Path(args.metadata_dir) / "provenance_log.jsonl"
    report = verify_provenance_log(log_path)

    if report.get("ok"):
        print(f"OK: {report.get('entries', 0)} entries verified")
        return 0

    print("FAIL: provenance log verification failed")
    print(f"Path: {report.get('path')}")
    print(f"Entries: {report.get('entries', 0)}")
    for issue in report.get("issues", [])[:20]:
        print(f"- Line {issue.get('line')}: {issue.get('error')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
