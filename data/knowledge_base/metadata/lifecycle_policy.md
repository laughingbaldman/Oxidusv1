# Knowledge Base Lifecycle Policy

## States
- raw: unprocessed source material
- draft: partially processed notes
- curated: validated, cleaned knowledge
- archived: deprecated or superseded material

## Rules
- Content must move in order: raw -> draft -> curated -> archived
- Each move requires updated metadata (created_utc, updated_utc, curator)
- Archived content remains searchable but is excluded from default results

## Required Fields (per item)
- source_url
- source_title
- source_type
- topic_type
- created_utc
- updated_utc
- lifecycle_state

## Retention and archival
- Retention thresholds live in metadata/retention_policy.json
- Archival targets live in metadata/archival_policy.json
- Tiering criteria live in metadata/tiering_policy.json
