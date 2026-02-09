# Ops Metrics Schema

This document defines the operational metrics schema exposed by Oxidus admin APIs. It is intended for dashboards, alerting, and audits.

## Sources
- /api/admin/health
- /api/admin/ops/summary
- /api/admin/status
- /api/admin/indexing/status
- /api/admin/search/overview

## Core Sections

### Reliability
- slo
  - uptime_slo_pct
  - api_latency_p95_ms
  - ingestion_throughput_eps_min
  - crawler_pages_per_min_min
  - index_staleness_hours
  - storage_free_gb_min
  - alert_dedupe_seconds
- latency
  - p50_ms
  - p95_ms
  - count
- safe_mode
  - active
  - reason
  - since
  - triggered_by
- alerts[]
  - code
  - level (warning|critical)
  - message
  - meta (optional)
- storage
  - path
  - free_gb
  - total_gb
  - used_pct

### Indexing
- running
- last_error
- last_result
- processed_batches
- total_batches
- throughput_eps
- started_at
- avg_batch_ms
- device_ids
- index_meta
  - model_id
  - indexed_at
  - documents
  - vectors
  - dimensions
  - file_mtime (seconds epoch)
- indexed_at_utc (derived)
- staleness_hours (derived)

### Knowledge
- metrics
  - total_sources
  - total_concepts
- coverage
  - domains (list of [domain, count])
  - coverage_targets (dict)
  - coverage_gaps (list of [domain, gap, count, target])
  - quality_buckets
  - domain_quality
  - quality_thresholds
- freshness
  - global
    - last_ingest_at (UTC ISO)
    - age_hours
  - domains
    - <domain>
      - last_ingest_at (UTC ISO)
      - age_hours
      - source_count
- pipeline
  - total_sources
  - concepts_extracted
  - values_mapped
  - summaries_generated
  - indexed
- pipeline_health
  - concepts_extracted_pct
  - values_mapped_pct
  - summaries_generated_pct
  - indexed_pct
- notes
  - total
  - open
- loose_ends
  - open_threads
  - underexplored_values
  - review_queue

### Crawler
- running
- pages_crawled
- started_at
- strategy
- seed_strategy
- health
  - stalled
  - last_error
  - rate_limit_seconds
  - save_every_pages
  - save_every_seconds
  - round_robin_domains
  - last_watchdog_restart_at
  - watchdog_restart_count
- resume
  - state_exists
  - queue_size

### Search Overview
- index_entries
- index_meta (see Indexing)
- index_last_built_utc
- index_staleness_hours
- weights
- tuning_cases
- tuning_updated_utc

## Telemetry Events
- reliability_alert
  - code, level, message, meta
- freshness_snapshot
  - global_age_hours
  - global_last_ingest_at
  - stale_domains (list of {domain, age_hours})
  - domain_count
- index_staleness_snapshot
  - staleness_hours
  - indexed_at_utc

## Notes
- All timestamps are UTC ISO strings unless explicitly marked as epoch seconds.
- Derived fields can be recomputed if index_meta is available.
