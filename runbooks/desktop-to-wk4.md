# Desktop → wk4 Migration Runbook

*Started: 2026-06-01 | Status: COMPLETE (2026-06-01)*

**Goal:** Join `py-xps-8930` (Ubuntu 24.04, i7 12t, 40Gi RAM, GTX 1070) as physical k8s worker `wk4`. Dissolve wk2/wk3 QEMU VMs. Move Ollama into k8s GPU pod.

---

## Discovery — Desktop Audit (2026-06-01)

### Hardware
- CPU: Intel Core i7 (6c/12t)
- RAM: 40Gi
- GPU: NVIDIA GTX 1070 (8Gi VRAM)
- Storage: 1TB NVMe + 256GB NVMe
- OS: Ubuntu 24.04
- IP: 10.0.0.113 (Ollama), Tailscale: 100.81.93.3

### QEMU VMs on desktop
| VM | k8s Node | IP | vCPU | RAM |
|---|---|---|---|---|
| wk2 | wk2 | 10.0.0.104 | 4 | 8Gi |
| wk3 | wk3 | 10.0.0.105 | 4 | 8Gi |

### Running services — disposition

| Service | What it does | Action |
|---|---|---|
| `ollama.service` | LLM inference — CPU only (GPU not working!) | → k8s GPU pod, fix GPU first |
| `vault-watcher.service` | Python (sre package) watches vault → publishes to Redpanda | → move to midir |
| `redpanda-portforward.service` | kubectl port-forward localhost:9092 → Redpanda in cluster | → stop (unnecessary once inside cluster) |
| `dns-forwarder.service` | dnsmasq → Pi-hole (10.0.0.203). Desktop DNS resolver | → stop (handled by pfSense/CoreDNS post-join) |
| `gitlab-runner.service` | CI runner for homelab-gitops | → keep as systemd service on wk4 node |
| `docker.service` | Docker daemon | → remove (conflicts with k8s containerd) |
| `node_exporter.service` | Prometheus metrics | → stop (k8s DaemonSet takes over) |
| `promtail.service` | Log shipping to Loki | → stop (k8s DaemonSet takes over) |
| `waydroid-container.service` | Android emulation — not used | → stop and remove |
| `lxc-monitord.service` / `lxcfs.service` | LXC container support | → stop and remove |
| `iperf3.service` | Network benchmarking server | → remove |
| `postfix` | Mail transfer agent | → remove |
| `clamav-daemon.service` | Antivirus | → remove |

### Docker containers (still running — must remove)
- `agency-infra-update-n8n-1` — stale, not used (was meant to be removed earlier)
- `agency-infra-update-postgres-1` — stale, not used

### Ollama GPU issue (CRITICAL)
Ollama is running on CPU, not GPU despite GTX 1070 being present:
```
offloaded 0/13 layers to GPU
```
`nvidia-cdi-refresh.service` is present suggesting nvidia-container-toolkit is installed. Root cause unknown — CUDA not being picked up by Ollama. Must diagnose before migration. Check:
```bash
nvidia-smi
ollama list
/usr/local/bin/ollama show --verbose <model>
```

### vault-watcher detail
```
ExecStart=/home/py/myenv/bin/python -m sre.scripts.vault_watcher
Environment=SRE_CONFIG_FILE=/home/py/.config/sre/config.toml
```
Watches local Obsidian vault path. After Syncthing removal, vault on desktop may be stale — verify path before migrating to midir.

### dns-forwarder detail
dnsmasq forwarding desktop DNS to Pi-hole at `10.0.0.203#53`. Set up to give the desktop Pi-hole DNS without relying on pfSense DHCP. Safe to stop — post k8s join, DNS will be handled by CoreDNS for pods and pfSense for host.

---

## Pre-conditions Before Joining

- [x] Remove agency Docker containers
- [x] Investigate and stop dns-forwarder
- [x] Move vault-watcher to wk4 (updated to use Redpanda pod IP directly, git-pull timer added)
- [x] Stop waydroid, lxc, iperf3, postfix, clamav
- [x] Remove Docker
- [x] Decide: gitlab-runner stays as systemd on wk4, CI pipeline rebuild needed
- [x] Fix Ollama GPU issue — reboot fixed driver mismatch (535.288 vs 535.309), now GPU-accelerated
- [x] Ensure wk1 + cp1-3 can handle workload during wk2/wk3 drain

## Migration Steps

### Phase 1 — Clean up desktop services ✅ DONE (2026-06-01)
1. ✅ Stop and remove agency Docker containers (n8n, postgres)
2. ✅ Stop non-essential services (waydroid, iperf3, clamav, lxc, dns-forwarder)
3. ✅ vault-watcher kept on wk4, updated to use Redpanda pod IP (10.244.5.230:9092), vault git-pull timer added
4. ✅ Stop redpanda-portforward (no longer needed — wk4 reaches pod IPs directly)
5. ✅ Remove Docker (docker.io)

### Phase 2 — Install k8s on desktop host ✅ DONE (2026-06-01)
1. ✅ Install containerd 2.2.1 (SystemdCgroup = true)
2. nvidia-container-toolkit already present (nvidia-cdi-refresh.service)
3. ✅ Install kubelet=1.31.3, kubeadm=1.31.3 via apt (removed snap kubeadm v1.35.5)
4. Configure nvidia runtime in containerd — PENDING (Phase 5)

### Phase 3 — Join cluster as wk4 ✅ DONE (2026-06-01)
1. ✅ Token from cp1 via `ssh 10.0.0.102`
2. ✅ `kubeadm join 10.0.0.102:6443 --node-name wk4`
3. ✅ Labels: `node-role.kubernetes.io/worker=worker gpu=true`
4. ✅ Node Ready — Cilium fix required: added `br0` to devices (desktop uses bridge network)
   Note: VIP 10.0.0.100 unreachable from desktop — use cp1 direct IP for join

### Phase 4 — Drain wk2/wk3 ✅ DONE (2026-06-01)
1. ✅ `kubectl drain wk2/wk3 --ignore-daemonsets --delete-emptydir-data`
2. ✅ All pods rescheduled onto wk1/wk4
3. ✅ `kubectl delete node wk2 wk3`
4. ✅ `virsh destroy wk2 && virsh destroy wk3` (graceful shutdown succeeded first)

### Phase 5 — Move Ollama to k8s GPU pod ✅ DONE (2026-06-01)
1. ✅ `apps/prod/ai-platform/ollama.yaml` — Deployment + PVC (50Gi iSCSI), runtimeClassName: nvidia, nodeSelector: gpu=true
2. ✅ nodeSelector: gpu=true, nvidia.com/gpu: 1 request+limit
3. ✅ NVIDIA device plugin DaemonSet + RuntimeClass deployed (`infrastructure/prod/nvidia-device-plugin/`)
4. ✅ CDI spec generated on wk4 (`nvidia-ctk cdi generate`), nvidia set as default containerd runtime
5. ✅ iscsid (open-iscsi) installed on wk4 for iSCSI PVC mount
6. ✅ Models pulled: mistral, nomic-embed-text, llama3.2:3b
7. ✅ LiteLLM updated to `ollama.ai-platform.svc.cluster.local:11434`
8. ✅ ollama.home.t12.io ingress added (600s timeout, proxy-body-size: 0)
9. ✅ ollama.service disabled on wk4
10. ✅ GPU confirmed: GTX 1070, 4842MiB VRAM, Ollama using GPU

### Phase 6 — Taint control planes (optional)
1. `kubectl taint nodes cp1 cp2 cp3 node-role.kubernetes.io/control-plane:NoSchedule`
2. Verify workloads reschedule to wk1/wk4

---

## Workloads Currently on wk2/wk3

Critical — must have landing zone before draining:

| Workload | Node | Notes |
|---|---|---|
| ingress-nginx | wk2 | CRITICAL — all traffic routes through this |
| technitium DNS | wk3 | CRITICAL — DNS for entire network |
| qdrant | wk2 | Vector DB, has iSCSI PVC |
| nextcloud | wk3 | Has PVC on TrueNAS |
| postgres-0 (nextcloud) | wk2 | StatefulSet, has PVC |
| vaultwarden | wk2 | Password manager |
| grafana | wk3 | Monitoring UI |
| cert-manager (all 3) | wk3 | TLS certificates |
| litellm | wk2 | LLM proxy |
| open-webui | wk3 | Chat UI |
| vault-ingest-consumer | wk3 | RAG pipeline |
| redpanda-console | wk2 | Kafka UI |

---

## Rollback Plan

If drain causes issues:
```bash
kubectl uncordon wk2
kubectl uncordon wk3
```

VMs remain running throughout until Phase 4 is confirmed stable.

---

## Post-Migration Validation

- [x] All pods Running on wk1/wk4
- [x] `nextcloud.home.t12.io` accessible
- [x] `qdrant.home.t12.io` accessible
- [x] DNS resolving (Technitium) — password reset via API, ollama.home.t12.io added
- [x] Ingress routing (ingress-nginx)
- [x] Grafana accessible
- [x] Ollama responding (GPU inference — GTX 1070, 4842MiB VRAM)
- [x] LiteLLM → Ollama → Open-WebUI working end to end
- [x] Vault RAG pipeline ingesting (vault-ingest-consumer using svc.cluster.local)

## Post-Migration Open Items

- [ ] CoreDNS home.t12.io forwarding live — monitor Alertmanager DNS errors clear
- [ ] gitlab-runner CI pipeline rebuild (runner configured for Docker executor, now removed)
- [ ] nvidia-smi exporter on wk4 — GPU metrics in Prometheus/Grafana
- [ ] Phase 2 gap: pfSense syslog → Loki
- [ ] Phase 3 gap: Restic not running on wk4
- [ ] sre-cli: add `sre search` command (Qdrant semantic search over vault)
- [ ] LiteLLM ConfigMap not updated by Helm — investigate why (manually patched as workaround)
- [ ] Technitium password stored in vault (new password set via API: Gl4sh33n*)

## Key Notes

- **VIP unreachable from desktop**: Use cp1 direct IP `10.0.0.102` for kubeadm join, not `10.0.0.100`
- **Cilium on wk4**: Must include `br0` in devices — desktop uses Linux bridge for QEMU
- **containerd autoremove risk**: `apt remove docker.io` + autoremove can remove containerd. Reinstall + regenerate config if this happens
- **iSCSI on wk4**: requires `open-iscsi` package + `iscsid` running before iSCSI PVC pods will start
- **Technitium reset**: delete `/etc/dns/auth.config` via busybox pod on PVC, restart deployment, login admin/admin, change password immediately
- **LiteLLM ConfigMap drift**: Helm upgrades don't reliably update the ConfigMap — patch manually after config changes
