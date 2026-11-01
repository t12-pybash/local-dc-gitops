# local-dc-gitops

GitOps repository for a 5-node bare-metal Kubernetes cluster — built and operated by a Lead SRE. All cluster state is declared here; infrastructure, monitoring, and AI workloads reconcile automatically on every commit via Flux CD.

## Stack

```
CLUSTER
├─ 3 control planes (HA etcd quorum)
└─ 2 workers: wk1 (general workloads) + wk4 (GPU worker, runtimeClassName: nvidia)

NETWORKING
└─ Cilium 1.16 (eBPF CNI, VXLAN, L2 LoadBalancer — migrated from Flannel + MetalLB)

GITOPS
└─ Flux CD v2 — SOPS + age encrypted secrets, 3-layer kustomization

STORAGE
└─ Democratic CSI → TrueNAS iSCSI (dynamic PVC provisioning)

AI PLATFORM
├─ Ollama       — GPU inference on wk4 (runtimeClassName: nvidia)
├─ LiteLLM      — OpenAI-compatible model router (mistral, llama3.2, qwen2.5-coder)
├─ Open-WebUI   — Chat interface (airgapped, no external API calls)
└─ Qdrant       — Vector database (RAG pipeline)

MONITORING
├─ kube-prometheus-stack (Prometheus, Grafana, Alertmanager)
├─ Loki + Promtail
├─ ntfy (push notifications to mobile)
└─ nvidia_gpu_exporter (GPU metrics via runtimeClassName: nvidia)

SECURITY
├─ Falco (runtime threat detection, DaemonSet on all nodes)
├─ cert-manager (internal CA, TLS for all ingresses)
├─ Network policies per namespace (default-deny ingress)
├─ All container images pinned to SHA digest (no :latest)
└─ SSH hardening via Ansible (key-only auth)

BACKUP
└─ Velero → Backblaze B2 (daily schedule, 30d retention)

SRE TOOLING
└─ sre-cli — Prometheus alerts, cluster status, semantic runbook search via Qdrant
```

## Repository Structure

```
local-dc-gitops/
├── clusters/prod/flux-system/     # Flux bootstrap — entry point
│   ├── gotk-components.yaml       # Flux controllers
│   ├── gotk-sync.yaml             # GitRepository + root Kustomization
│   ├── infrastructure.yaml        # Kustomization ref → infrastructure/prod
│   ├── monitoring.yaml            # Kustomization ref → monitoring/prod
│   └── apps.yaml                  # Kustomization ref → apps/prod
│
├── infrastructure/prod/           # CNI, ingress, storage, security
│   ├── cilium/                    # HelmRelease + L2 pool + announcement policy
│   ├── cert-manager/              # HelmRelease + ClusterIssuer
│   ├── nginx-ingress/             # HelmRelease
│   ├── velero/                    # HelmRelease + daily backup schedule
│   ├── falco/                     # HelmRelease (DaemonSet, all nodes)
│   └── gpu-metrics/               # nvidia_gpu_exporter DaemonSet + ServiceMonitor
│
├── monitoring/prod/               # Prometheus stack, Loki, ntfy
│
├── apps/prod/                     # AI platform
│   ├── ai-platform/               # Ollama, LiteLLM, Open-WebUI, Qdrant, Dashy
│   └── vault-ingest/              # Qdrant ingestion pipeline (Redpanda + consumer)
│
├── helm/                          # Local Helm charts
│   ├── litellm/
│   ├── open-webui/
│   └── qdrant/
│
└── ansible/                       # Node bootstrap and maintenance playbooks
    ├── inventory.yaml
    └── playbooks/
        ├── cni-cleanup.yaml       # Serial Flannel → Cilium migration
        ├── ssh-hardening.yaml
        └── etcd-metrics-expose.yaml
```

## Flux Dependency Order

```
infrastructure  ──▶  monitoring  ──▶  apps
     └── Cilium, cert-manager,        └── AI platform,
         nginx-ingress,                   vault-ingest
         storage, security
```

`apps` depends on `infrastructure` (ingress, TLS, storage must exist first). Race conditions on first bootstrap are eliminated.

## Secret Management

Secrets are encrypted in git with [SOPS](https://github.com/getsops/sops) + [age](https://age-encryption.org/). Flux decrypts at reconcile time using an age private key stored as a cluster secret.

`.sops.yaml` targets only `data`/`stringData` fields — metadata stays in plaintext and diffs remain readable.

## Cilium L2 LoadBalancer

Replaces MetalLB entirely. Services get stable LAN-routable IPs via ARP announcements on physical interfaces — ingress-nginx, Grafana, and the AI platform are directly reachable on the LAN without a cloud load balancer.

## CNI Migration (Flannel → Cilium)

`ansible/playbooks/cni-cleanup.yaml` migrates nodes one at a time (`serial: 1`). For each node: drain, remove Flannel CNI config + `flannel.1` interface + `cni0` bridge, uncordon so Cilium takes over. Parallel migration causes routing loops — serial is required.

## Related Posts

- [HA Kubernetes on Ubuntu — cluster bootstrap](https://t-12.io/solutions/01-ubuntu-ha-kubernetes-gpu-ai/)
- [Cilium, Flux CD, and Democratic CSI](https://t-12.io/solutions/multi-cluster-setup-guide/)
- [Private AI Platform](https://t-12.io/solutions/private-ai-platform/)

## Related Repos

- [sre-cli](https://github.com/t12-pybash/sre-cli) — SRE CLI and MCP server for operating this cluster
- [fullnode-infrastructure](https://github.com/t12-pybash/fullnode-infrastructure) — Production blockchain node infrastructure (OP Stack, Kubernetes, Terraform)

---

*[LinkedIn](https://www.linkedin.com/in/cdonegan7/) | [t-12.io](https://t-12.io)*
