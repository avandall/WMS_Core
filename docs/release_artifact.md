# Release Artifact

Phase Q requires every release candidate to publish a machine-readable artifact with enough
information to redeploy or roll back without local notes.

Generate the artifact:

```bash
python3 scripts/release_artifact.py --release-version "$RELEASE_VERSION" --output release-artifact.json
```

The artifact records:

- immutable release version and git SHA
- non-AI runtime image tags
- opt-in AI image tag
- service-owned migration commands
- required release gates
- deployment artifact paths
- rollback rule and required rollback evidence

The release workflow uploads `release-artifact.json` together with SBOM output. Store the artifact
with the release record and keep it alongside cutover reconciliation output.
