# Reliability Runbook and Verification

## Scope
This runbook covers reliability SLOs, health checks, alerting, and safe-mode operations.

Ops metrics reference:
- OPS_METRICS_SCHEMA.md

## SLO Configuration
Edit thresholds in:
- config/reliability_slo.yaml

Key fields:
- uptime_slo_pct
- api_latency_p95_ms
- ingestion_throughput_eps_min
- crawler_pages_per_min_min
- index_staleness_hours
- storage_free_gb_min
- alert_dedupe_seconds

## Health Checks
Endpoints:
- GET /api/health
- GET /api/admin/health (requires admin token)

What they include:
- Uptime, latency p50/p95
- Crawler status and health
- Indexing status and throughput
- LM Studio availability
- LM Studio model selection and match
- MemryX status/devices (admin)
- Storage free space
- Safe mode state and alerts

## Alerting
Alerts are emitted to:
- logs/admin_telemetry.jsonl

Event type:
- reliability_alert

Common alert codes:
- latency_p95
- indexing_throughput
- index_staleness
- crawler_throughput
- crawler_stalled
- indexing_error
- storage_low
- lm_offline
- lm_model_mismatch
- memryx_devices

Freshness/staleness snapshots:
- freshness_snapshot
- index_staleness_snapshot

## Safe Mode
Safe mode blocks ingestion and indexing actions.

Triggers:
- Indexing errors
- Crawler stall
- Storage free space below SLO
- Moltbook ingest errors

Clear safe mode:
- POST /api/admin/safe-mode/clear
- Admin UI button: "Clear Safe Mode"

## Verification Checklist
Run these after changes or incidents:

1) Health endpoint responds
- GET /api/health returns JSON and no errors.
- GET /api/admin/health returns JSON (admin token required).

1b) LM Studio model match
- Confirm lm_studio.model is openai/gpt-oss-20b.
- Confirm lm_studio.model_match is true.

2) Safe mode guards
- Enable safe mode by simulating a failure (or set storage_free_gb_min above current free space).
- Verify indexing start is blocked (HTTP 423).
- Clear safe mode and verify indexing can start.

3) Alert generation
- Lower ingestion_throughput_eps_min to a high value and run indexing.
- Confirm reliability_alert entries in logs/admin_telemetry.jsonl.

3b) Index staleness alert
- Set index_staleness_hours to a very low value (ex: 0.01).
- Refresh /api/admin/health or /api/admin/ops/summary.
- Confirm index_staleness appears in alerts and telemetry.

3c) Freshness snapshot
- Refresh /api/admin/ops/summary (admin token required).
- Confirm freshness_snapshot entries in logs/admin_telemetry.jsonl.

4) Crawler health
- Start a crawl and verify /api/admin/status shows crawler details.
- Confirm crawler throughput alerts only when below SLO.

5) UI visibility
- Admin panel shows Safe Mode status and Alerts count.
- Ops Summary includes SLO and latency lines.
- Ops Summary shows freshness and top stale domains.

## Hybrid Search Rollout + Monitoring
Use this when deploying or tuning hybrid search.

Rollout steps:
1) Build or refresh the embedding index (Admin panel or POST /api/admin/indexing/start).
2) Confirm index metadata is populated (GET /api/admin/indexing/status).
3) Confirm search overview snapshot (GET /api/admin/search/overview).
4) Run tuning set checks (see data/knowledge_base/metadata/search_tuning_set.json).
5) Run local tests: python test_hybrid_search.py.

Monitoring signals:
- Search index meta (index_meta.json) and entry count (metadata.json).
- Search weights (data/knowledge_base/metadata/search_weights.json).
- Tuning set status (data/knowledge_base/metadata/search_tuning_set.json).
- Telemetry event: search_overview in logs/admin_telemetry.jsonl.

Health checks for search:
- GET /api/admin/search/overview
- GET /api/admin/indexing/status

## Tiering + Indexing Controls
New controls that impact performance and storage reliability.

Tiering signals:
- GET /api/admin/access-heat
- GET /api/admin/tiering/overview

Indexing controls:
- /api/admin/indexing/start supports batch_delay_ms (backpressure)
- GET /api/admin/indexing/metrics for throughput and batch timing

Operational guidance:
- If indexing competes with inference, raise batch_delay_ms in the indexing payload.
- If storage pressure rises, review tiering candidates and run archive preview.
- After archival, refresh ops summary to confirm storage relief.

## Troubleshooting
- If alerts are too frequent: raise alert_dedupe_seconds in config/reliability_slo.yaml.
- If throughput alerts are noisy: lower ingestion_throughput_eps_min or crawler_pages_per_min_min.
- If safe mode is stuck: clear via /api/admin/safe-mode/clear and check admin_telemetry.jsonl for root cause.

## Taxonomy and Knowledge Graph Operations
Use this section to expand taxonomy coverage, maintain stable topic IDs, and grow evidence-backed graph edges.

### Coverage Expansion Checklist
1) Audit coverage gaps across world-scale domains:
	- humanities
	- law
	- medicine
	- engineering
2) Record missing domain areas and prioritize by usage or ingestion volume.
3) Add new domain nodes and subdomains in the taxonomy files.

### Topic ID Registry
Maintain stable topic IDs so references remain durable over time.

Rules:
- Never reuse an ID after deletion.
- Prefer explicit merges over silent replacements.
- Track redirects for renamed or merged topics.

Suggested registry fields:
- topic_id
- canonical_name
- status (active, merged, redirected, deprecated)
- merge_target_id (if merged)
- redirect_to_id (if renamed)
- updated_at

### Merge and Redirect Procedure
1) Mark source topic as merged or redirected in the registry.
2) Update any references to point to the target ID.
3) Keep a redirect record for lookups and legacy data.

### Evidence-Backed Edge Model
Edges should be grounded in evidence and traceable to sources.

Edge fields (recommended):
- source_topic_id
- target_topic_id
- relation_type
- evidence_refs (source document IDs or URLs)
- confidence (low, medium, high)
- created_at

### Graph Seeding and QA
1) Seed edges for high-confidence relationships first.
2) Run validation checks for:
	- orphaned topics
	- broken redirects
	- edges without evidence
3) Spot-check sample edges in each domain.
4) Validate metadata alignment:
	- python scripts/validate_taxonomy_graph.py

### Governance Notes
- Use consistent naming conventions and avoid near-duplicate topics.
- Record decisions for merges, redirects, and edge changes.
- Keep changes auditable for future governance reviews.
