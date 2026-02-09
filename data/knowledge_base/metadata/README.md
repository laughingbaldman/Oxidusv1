# Metadata

This folder stores registries, manifests, migration plans, and indexes that describe the knowledge base structure and ingestion state.

## Governance

- Metadata writes should include the required fields in `metadata_schema.json`.
- Curation requires a minimum source trust tier (default `secondary`). Override with `OXIDUS_MIN_TRUST_TIER`.
- Provenance is append-only in `provenance_log.jsonl` with hash chaining.

### Verify provenance

Run the verifier:

```bash
python scripts/verify_provenance_log.py --metadata-dir data/knowledge_base/metadata
```
