# Archive Rules

Purpose: keep legacy files organized and retrievable without cluttering the active workspace.

Rules
- Archive only files that are not referenced by the current app runtime.
- Use a dated subfolder per batch: retired/archives/YYYY-MM-DD/.
- Add an entry to archive_manifest.json for every moved file.
- Include: original path, new path, reason, and timestamp.
- Do not modify archived file contents unless explicitly requested.
- Review archives monthly; delete only with explicit approval.
