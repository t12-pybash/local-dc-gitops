# Backstage IDP — Runbook

*Deployed: 2026-06-09 | Chart: backstage/backstage 1.11.0 | Image: ghcr.io/backstage/backstage:1.30.2*

---

## Architecture

| Component | Namespace | Storage |
|---|---|---|
| Backstage 1.30.2 | backstage | SQLite in-memory (`/tmp/backstage-sqlite`) |

**Ingress:** `https://backstage.home.t12.io` → 10.0.0.201 (nginx-ingress)  
**TLS:** homelab-ca-issuer (cert-manager)  
**Auth:** Guest provider (`dangerouslyAllowOutsideDevelopment: true`)  
**Kubernetes integration:** in-cluster service account, cluster name `homelab`  
**Catalogue source:** https://github.com/t12-pybash/clever-cloud-3tier/blob/main/catalog-info.yaml

---

## GitOps Files

```
homelab-gitops/apps/prod/backstage/
├── kustomization.yaml
├── namespace.yaml
├── sources.yaml        # HelmRepository
├── helmrelease.yaml    # Chart values — app config, auth, k8s integration
└── ingress.yaml        # Certificate + Ingress (homelab-ca-issuer)
```

---

## Common Operations

### Check status
```bash
kubectl get pods -n backstage
kubectl get helmrelease -n backstage
kubectl get certificate -n backstage
```

### Logs
```bash
kubectl logs -n backstage deployment/backstage --tail=50
```

### Force Flux reconcile
```bash
flux reconcile helmrelease backstage -n backstage
```

---

## Configuration Notes

- **SQLite**: data lives at `/tmp/backstage-sqlite` — not persisted across pod restarts. Catalogue re-syncs from Git on startup. Acceptable for homelab; swap to PostgreSQL for production.
- **baseUrl**: must match the external URL (`https://backstage.home.t12.io`). If you change the hostname, update `app.baseUrl`, `backend.baseUrl`, and `backend.cors.origin` in the HelmRelease values.
- **Ingress**: chart-managed ingress is disabled (`ingress.enabled: false`). The ingress is defined separately in `ingress.yaml` following the homelab pattern (Certificate + Ingress, homelab-ca-issuer).
- **DNS**: `backstage.home.t12.io` A record → 10.0.0.201 in Technitium. Added via API: `POST /api/zones/records/add`.

---

## Known Issues

### TechDocs search index empty
```
warn: Index for techdocs was not created: indexer received 0 documents
404 /api/techdocs/static/docs/default/component/ai-platform/search/search_index.json
```
TechDocs requires pre-built static docs. Not a blocker — catalogue and software templates work fine. Fix: run `techdocs-cli generate` and publish docs, or configure an external storage backend.

---

## Reinstall / Recovery

If the pod is crashlooping, force a fresh rollout:
```bash
kubectl rollout restart deployment/backstage -n backstage
```

If the HelmRelease is stuck:
```bash
flux suspend helmrelease backstage -n backstage
kubectl delete helmrelease backstage -n backstage
flux resume helmrelease backstage -n backstage
```

To wipe and redeploy from scratch:
```bash
kubectl delete namespace backstage
# Flux will recreate on next reconcile (up to 10 min), or force it:
flux reconcile kustomization apps --with-source
```
