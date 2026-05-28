# Service Environment Configuration

Phase T adds per-service `.env.example` files for the active non-AI services. These files are
local/development templates only; production secrets and database URLs must come from the platform
secret manager or deployment manifests. The tracked templates also carry the monolith-era shared
application settings that active service settings still read, such as DB pool sizing, CORS, rate
limit, JWT, and app metadata knobs.

## Scope

Tracked templates:

- `Services/api-gateway/.env.example`
- `Services/identity-service/.env.example`
- `Services/customer-service/.env.example`
- `Services/product-service/.env.example`
- `Services/warehouse-service/.env.example`
- `Services/inventory-service/.env.example`
- `Services/documents-service/.env.example`
- `Services/audit-service/.env.example`
- `Services/reporting-service/.env.example`

Out of scope:

- `Services/wms-monolith/` because it is archived reference code.
- `Services/ai-service/.env.example` because AI remains opt-in and provider keys must never be
  committed. Local AI runs should use ignored `Services/ai-service/.env`.

## Rules

- Commit only `.env.example` templates, never real `.env` files.
- Use placeholder values for secrets such as `SECRET_KEY`.
- Keep provider API keys such as OpenAI, Google, and Groq only in ignored local `.env` files or in
  the production secret manager.
- Local templates may use SQLite URLs and `LOCAL_DB_BOOTSTRAP_ENABLED=1`.
- Production deployment must keep runtime table bootstrap disabled and source secrets from
  `deploy/kubernetes/examples/secret-manager-external-secrets.yaml` or the target platform.
- Service-owned datastore templates must match `docs/data_ownership.md` and root
  `docker-compose.yml`.

## Quick Check

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run --group dev pytest -q tests/contract/test_phase_t_env_contract.py
```
