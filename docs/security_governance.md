# Security Governance and Authorization

Phase S turns the baseline security wiring into an enforceable governance policy for production.

## Authorization Boundary

Fine-grained authorization belongs at the API Gateway boundary. Downstream domain services keep
their business rules and data ownership, but they do not duplicate REST role/scope policy.

The policy source is `deploy/kubernetes/examples/security-governance-policy.json`.

Validate it with:

```bash
python3 scripts/security_governance_check.py \
  --policy deploy/kubernetes/examples/security-governance-policy.json
```

## Role Matrix

| Role | Scope |
| --- | --- |
| `admin` | all permissions |
| `user` | customer/product/inventory/report read |
| `sales` | customer management, product/inventory/report read, import document creation |
| `warehouse` | transfer document creation, document posting, inventory/report read |
| `warehouse_manager` | warehouse, inventory, document, product, and report operations |
| `accountant` | read workflows plus price editing |

Admin-only workflows include user management and audit-event reads. Warehouse, inventory, and
document workflows must use `require_permissions(...)` in API Gateway routes.

## Token and Rotation Policy

- Identity issues JWTs and validates token expiry/signature.
- API Gateway calls Identity over gRPC for token validation.
- Access tokens expire after 60 minutes.
- Refresh tokens expire after 7 days.
- Rotate JWT `SECRET_KEY` by rolling `identity-service` and API Gateway together.
- Rotate gRPC mTLS certificates through `wms-grpc-mtls`, then roll gateway/backends.
- Rotate database credentials one service-owned datastore at a time.
- Rotate external provider keys per integrating service.

Each rotation rehearsal must record the old secret version, new secret version, rollout order,
health checks, and rollback command.

## Audit Requirements

Audit records must be sufficient to investigate privileged or destructive operations.

Required fields:

- `event_id`
- `request_id`
- `user_id`
- `action`
- `entity_type`
- `entity_id`
- `warehouse_id`
- `payload`
- `created_at`

Required audit categories:

- privileged operations: user, product, warehouse, document, and document-post actions
- failed auth attempts: invalid token, inactive user, permission denied
- data export: reports and audit-event reads
- manual inventory adjustments and reservation release

## Dependency and License Scanning

Release candidates run SBOM and vulnerability scanning in `.github/workflows/release-gates.yml`.
Pull requests also run dependency review when GitHub dependency metadata is available.

Remediation targets:

| Severity | SLA |
| --- | --- |
| critical | 24h |
| high | 7d |
| medium | 30d |

Ownership:

- shared utilities and API Gateway: platform owner
- runtime services: service owners
- AI service: AI owner
