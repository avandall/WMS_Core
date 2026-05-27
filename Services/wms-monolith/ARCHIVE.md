# Monolith Archive Policy

Status: frozen read-only reference.

`Services/wms-monolith/` remains in the repository only as a historical rollback and parity
reference. It must not be used by default development, CI, deployment, migration, fixture,
observability, or release workflows.

## Decision

- Keep the archive in this repository until the next tagged service release has been accepted.
- Do not add new runtime features, migrations, fixtures, generated protos, CI jobs, or deployment
  scripts under this tree.
- Allow changes only for archive documentation, security disclosure notes, or a deliberate
  rollback/parity investigation.
- After the next accepted release, the team may delete this directory in a dedicated commit.

## Rollback Reference

Rollback reference tag: `phase-o-monolith-archive-exit`.

If this directory is deleted later and a rollback needs the archive, recover it from that tag:

```bash
git checkout phase-o-monolith-archive-exit -- Services/wms-monolith
```

## Active Entry Points

Use these paths for current work:

- `Services/api-gateway/`
- `Services/*-service/`
- `Libraries/shared-utils/`
- `proto/`
- `docker-compose.yml`
- `deploy/kubernetes/`
- `tests/contract/`
- `tests/e2e/`
