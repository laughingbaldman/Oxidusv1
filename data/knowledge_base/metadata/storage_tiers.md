# Storage tiers (hot/cold)

This document defines the initial hot/cold storage layout and signals used for tiering.
The intent is additive: promote high-value content to hot storage and preserve cold content
in a searchable, reversible archive.

## Hot tier (fast access)
- data/knowledge_base/normalized_deeper/sorted
- data/knowledge_base/wiki_corpus
- data/knowledge_base/notes
- data/knowledge_base/metadata
- data/knowledge_base/index

## Cold tier (lower access, preserved)
- retired/data/knowledge_base/wiki
- retired/data/knowledge_base/wiki_corpus
- retired/data/knowledge_base/normalized_deeper
- retired/data/knowledge_base/cache
- data/knowledge_base/archives

## Access heat signals
- data/knowledge_base/metadata/access_heat.json
  - topics: normalized topic keys with counts and last access time
  - paths: knowledge base relative paths with counts and last access time
  - events: event counts (user_message, wiki_search, wiki_page, memory_recall, file_open)

## Tiering criteria (initial)
- Promote to hot tier when:
  - access count >= 5 in the last 30 days, or
  - referenced by high-value domains (curated/curricula) and accessed >= 2
- Demote to cold tier when:
  - access count == 0 in the last 180 days, and
  - age since last content update >= 180 days

Policy settings are tracked in metadata/tiering_policy.json, metadata/retention_policy.json,
and metadata/archival_policy.json.

## Batch indexing priority
1) Hot tier content
2) Recently promoted content (last 7 days)
3) Cold tier content (background only)

## Notes
- Cold tier is not deletion. Content remains searchable and can be restored.
- Retention and archival rules should use this layout as the default target structure.
