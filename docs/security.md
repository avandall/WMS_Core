# Security Hardening Baseline

Phase 13 adds a production-ready security baseline while keeping local dev/test lightweight.

## Internal gRPC Transport

Local compose defaults to plaintext gRPC:

```bash
GRPC_TLS_ENABLED=0
GRPC_CLIENT_TLS_ENABLED=0
```

Production can opt in to TLS for service-to-service traffic:

```bash
GRPC_TLS_ENABLED=1
GRPC_TLS_CERT_FILE=/run/secrets/grpc/tls.crt
GRPC_TLS_KEY_FILE=/run/secrets/grpc/tls.key
GRPC_TLS_CLIENT_CA_FILE=/run/secrets/grpc/client-ca.crt
GRPC_CLIENT_TLS_ENABLED=1
GRPC_CLIENT_ROOT_CERT_FILE=/run/secrets/grpc/ca.crt
GRPC_CLIENT_CERT_FILE=/run/secrets/grpc/client.crt
GRPC_CLIENT_KEY_FILE=/run/secrets/grpc/client.key
```

`GRPC_TLS_ENABLED=1` switches each gRPC service to `add_secure_port`. Gateway and
service-to-identity clients use `GRPC_CLIENT_TLS_ENABLED=1` to create secure channels.
When `GRPC_TLS_CLIENT_CA_FILE` and the matching client cert/key are provided, the channel
is mutual TLS.

## Gateway Request Hardening

Gateway CORS is no longer wildcard-by-default with credentials. Configure explicit origins:

```bash
CORS_ORIGINS=https://app.example.com,https://ops.example.com
CORS_ALLOW_CREDENTIALS=1
```

The gateway also adds baseline response hardening headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: camera=(), geolocation=(), microphone=()`
- `Cross-Origin-Opener-Policy: same-origin`

Request bodies are limited by `MAX_REQUEST_BODY_BYTES` and rate limiting is keyed by
authorization token hash when present, otherwise by client IP and route:

```bash
MAX_REQUEST_BODY_BYTES=1048576
RATE_LIMIT_RPS=10
```

## Secrets

Root compose uses a local `SECRET_KEY` default for dev convenience. Production must set
`SECRET_KEY` through the platform secret manager and should avoid committing `.env` secrets.

## Remaining Production Work

- Certificate provisioning/rotation belongs in deployment automation.
- Fine-grained authz scopes should keep living at the API Gateway boundary.
- Kubernetes network policies or service mesh policy can be added in Phase 17 deployment work.
