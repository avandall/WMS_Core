# Kubernetes Deployment Package

Phase 17 turns the release contract into a deployable baseline. The base manifests deploy
the gRPC-first stack without the retired monolith and without the opt-in AI service.

## Layout

- `base/`: deployable Kubernetes base for API Gateway, gRPC services, Redis Streams, and
  OpenTelemetry Collector.
- `examples/migration-jobs.yaml`: per-service migration job templates. Replace the command
  with each service-owned migration runner before production use.
- `examples/slo-alerts.yaml`: PrometheusRule examples for availability, latency, and
  error-rate alerts.
- `examples/load-chaos-checks.md`: release gate checklist for smoke, load, and chaos checks.

## Apply

Use the same immutable release id described in `docs/release_ops.md`:

```bash
export RELEASE_VERSION="$(git rev-parse --short=12 HEAD)"
kubectl apply -k deploy/kubernetes/base
```

Before applying to production, replace `base/secrets.example.yaml` with values from the
cluster secret manager or an ExternalSecret equivalent. Do not commit real secret values.

## Local k3s Validation

This repo can validate the deployment package against a local k3s API server without
creating application workloads:

```bash
systemctl status k3s
kubectl get nodes
kubectl kustomize deploy/kubernetes/base
kubectl create namespace wms
kubectl apply -k deploy/kubernetes/base --dry-run=server
kubectl delete namespace wms
```

The namespace create/delete pair is only for dry-run validation. Kubernetes server-side
dry-run does not persist the namespace resource rendered in the same kustomize batch, so
the namespace must exist before validating namespaced objects.

Useful k3s service commands:

```bash
sudo systemctl start k3s
sudo systemctl stop k3s
sudo systemctl restart k3s
sudo systemctl enable k3s
sudo systemctl disable k3s
```

## Images

The base uses `wms/<service>:RELEASE_VERSION` placeholders. Set real image tags with
Kustomize during release:

```bash
kubectl kustomize deploy/kubernetes/base \
  | sed "s/:RELEASE_VERSION/:${RELEASE_VERSION}/g" \
  | kubectl apply -f -
```

## Security

The base expects gRPC mTLS cert material in `wms-grpc-mtls`. Cert rotation should be handled
by the cluster secret manager or cert-manager and rolled through Kubernetes volume updates.

## AI

AI is intentionally absent from the base deployment. Add an explicit AI overlay when the AI
runtime is part of the release window, mirroring the local compose `ai` profile.
