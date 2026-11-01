# Nextcloud on Kubernetes — Runbook

*Migrated: 2026-05-31 | Stack: Nextcloud 28-apache + PostgreSQL 16 + Redis 7*

---

## Architecture

| Component | Namespace | Storage |
|---|---|---|
| Nextcloud 28-apache | nextcloud | 250Gi TrueNAS iSCSI PVC (`/var/www/html`) |
| PostgreSQL 16 | nextcloud | 10Gi TrueNAS iSCSI PVC |
| Redis 7-alpine | nextcloud | None (in-memory only) |
| go-vod (sidecar) | nextcloud | Shared Nextcloud PVC |

**Ingress:** `nextcloud.home.t12.io` → 10.0.0.201 (nginx-ingress)  
**TLS:** homelab-ca-issuer (cert-manager)  
**Secrets:** `apps/prod/nextcloud/nextcloud-secret.sops.yaml` (SOPS encrypted)  
**Admin user:** `<your-admin-user>`

---

## GitOps Files

```
homelab-gitops/apps/prod/nextcloud/
├── kustomization.yaml
├── namespace.yaml
├── nextcloud-secret.sops.yaml
├── nextcloud.yaml          # Deployment + PVC + Service (includes go-vod sidecar)
├── postgres.yaml           # StatefulSet + PVC + Service
├── redis.yaml              # Deployment + Service
├── ingress.yaml            # Certificate + Ingress
└── network-policies/
```

---

## Common Operations

### Check pod status
```bash
kubectl get pods -n nextcloud
kubectl logs -n nextcloud deployment/nextcloud -c nextcloud --tail=50
kubectl logs -n nextcloud deployment/nextcloud -c go-vod --tail=20
```

### Run occ commands
```bash
kubectl exec -n nextcloud deployment/nextcloud -c nextcloud -- su -s /bin/bash www-data -c "php occ <command>"
```

### Enable maintenance mode
```bash
kubectl exec -n nextcloud deployment/nextcloud -c nextcloud -- su -s /bin/bash www-data -c "php occ maintenance:mode --on"
```

### Scan files after manual upload
```bash
kubectl exec -n nextcloud deployment/nextcloud -c nextcloud -- su -s /bin/bash www-data -c "php occ files:scan --all"
```

### Generate previews (skips videos)
```bash
kubectl exec -n nextcloud deployment/nextcloud -c nextcloud -- su -s /bin/bash www-data -c "nohup php occ preview:generate-all --verbose > /tmp/preview.log 2>&1 &"
# Monitor:
kubectl exec -n nextcloud deployment/nextcloud -c nextcloud -- tail -f /tmp/preview.log
```

---

## go-vod (Video Transcoding)

go-vod runs as a sidecar container in the Nextcloud pod. It handles HLS transcoding for the Memories app.

- **Port:** 47788 (localhost only, within pod)
- **Config:** Set via `occ config:app:set memories vod_host --value='http://localhost:47788'`
- **Logs:** `kubectl logs -n nextcloud deployment/nextcloud -c go-vod`

If go-vod is crashlooping, check `NEXTCLOUD_HOST` env var is set to `http://localhost`.

---

## Migration Notes (Desktop Docker → k8s)

Original stack: Nextcloud (Docker) + MariaDB 10.6 on py-xps-8930 desktop.

**Migration steps taken:**
1. Deploy k8s stack (PostgreSQL — not MariaDB, fresh DB)
2. Start Nextcloud — let it initialise fresh
3. Transfer files via tar pipe:
   ```bash
   # On desktop
   tar -C /mnt/nvme/nextcloud-data/html/data/pybash -cf - . | \
     kubectl exec -n nextcloud deployment/nextcloud -c nextcloud -i -- \
     tar -C /var/www/html/data/<your-admin-user> -xf -
   ```
4. Set correct ownership: `chown -R www-data:www-data /var/www/html/data/`
5. Scan files: `php occ files:scan --all`
6. Disable maintenance mode

**Known issues post-migration:**
- MP4/HEVC files (.TS.mp4 from Pixel phones) show black screen in Chromium — use Firefox or Zen Browser
- Preview generation crashes on large HEVC videos — video preview providers disabled in config

---

## PVC Resize (if needed)

```bash
kubectl patch pvc nextcloud-data -n nextcloud -p '{"spec":{"resources":{"requests":{"storage":"300Gi"}}}}'
# Restart pod to trigger filesystem resize
kubectl rollout restart deployment/nextcloud -n nextcloud
```

---

## Backup

Covered by Velero daily backup to Backblaze B2 (30d retention).  
Velero backs up the `nextcloud` namespace including PVC snapshots.
