import argparse
import json
import os
import time
from datetime import datetime


def _utc_iso(ts):
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_root():
    return os.path.join("data", "knowledge_base")


def _load_config(config_path):
    if not config_path:
        return None
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _iter_files(root, include_dirs):
    for dirname in include_dirs:
        abs_dir = os.path.join(root, dirname)
        if not os.path.isdir(abs_dir):
            continue
        for base, _, files in os.walk(abs_dir):
            for name in files:
                yield os.path.join(base, name)


def _topic_type(rel_path):
    parts = rel_path.replace("\\", "/").split("/")
    if "wiki_corpus" in parts:
        return "wiki_corpus"
    if "wiki" in parts:
        return "wiki_article"
    return "unknown"


def build_index(root, include_dirs, index_file):
    files = []
    for path in _iter_files(root, include_dirs):
        rel_path = os.path.relpath(path, start=root).replace("\\", "/")
        topic_type = _topic_type(rel_path)
        source_type = "wiki_corpus" if topic_type == "wiki_corpus" else "wiki"
        stat = os.stat(path)
        files.append(
            {
                "file_name": os.path.basename(path),
                "relative_path": rel_path,
                "topic_type": topic_type,
                "source_type": source_type,
                "size_bytes": stat.st_size,
                "modified_utc": _utc_iso(stat.st_mtime),
            }
        )

    index = {
        "schema_version": "1.0",
        "updated_utc": _utc_iso(time.time()),
        "root": root.replace("\\", "/"),
        "files": sorted(files, key=lambda item: item["relative_path"]),
    }

    os.makedirs(os.path.dirname(index_file), exist_ok=True)
    with open(index_file, "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Build wiki file index by topic type")
    parser.add_argument("--root", default=_default_root(), help="Knowledge base root")
    parser.add_argument("--index", default=None, help="Index file path")
    parser.add_argument("--watch", action="store_true", help="Rebuild index on interval")
    parser.add_argument("--interval", type=int, default=None, help="Watch interval in seconds")
    parser.add_argument("--config", default=None, help="Path to config JSON")
    args = parser.parse_args()

    config = _load_config(args.config) if args.config else None
    root = args.root
    include_dirs = ["wiki", "wiki_corpus"]
    index_file = args.index
    interval = args.interval or 60

    if config:
        root = config.get("root", root)
        include_dirs = config.get("include_dirs", include_dirs)
        index_file = config.get("index_file", index_file)
        interval = config.get("interval_seconds", interval)

    if not index_file:
        index_file = os.path.join(root, "metadata", "indexes", "wiki_file_topic_index.json")

    if args.watch:
        while True:
            build_index(root, include_dirs, index_file)
            time.sleep(interval)
    else:
        build_index(root, include_dirs, index_file)


if __name__ == "__main__":
    main()
