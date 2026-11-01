# homelab-gitops

GitOps repository for a 5-node bare-metal Kubernetes homelab — built and operated by a Lead SRE with 15 years of production infrastructure experience. All cluster state is declared here; infrastructure, monitoring, AI workloads, and applications reconcile automatically on every commit via Flux CD.

This mirrors the GitOps and reliability patterns used in production at scale — Cilium eBPF networking, SOPS-encrypted secrets, default-deny NetworkPolicies, runtime threat detection, and a private AI inference platform running fully airgapped on local GPU.

## Stack

```
CLUSTER
├─ 3 control planes (HA etcd quorum)
└─ 2 workers: wk1 (physical Lenovo) + wk4 (physical XPS, GTX 1070)

NETWORKING
└─ Cilium 1.16 (eBPF CNI, VXLAN, L2 LoadBalancer — migrated from Flannel + MetalLB)

GITOPS
└─ Flux CD v2 — SOPS + age encrypted secrets, 3-layer kustomization

STORAGE
└─ Democratic CSI → TrueNAS iSCSI (dynamic PVC provisioning)

AI PLATFORM
├─ Ollama       — GPU inference on wk4 (GTX 1070, runtimeClassName: nvidia)
├─ LiteLLM      — OpenAI-compatible model router (mistral, llama3.2, qwen2.5-coder)
├─ Open-WebUI   — Chat interface (airgapped, no external API calls)
└─ Qdrant       — Vector database (RAG pipeline for Obsidian vault)

APPLICATIONS
├─ Nextcloud    — Self-hosted files + media (PostgreSQL, Redis, 250Gi iSCSI PVC)
├─ n8n          — Workflow automation (PostgreSQL, 1Gi iSCSI PVC)
└─ Vaultwarden  — Self-hosted password manager

MONITORING
├─ kube-prometheus-stack (Prometheus, Grafana, Alertmanager)
├─ Loki + Promtail
├─ ntfy (push notifications to mobile)
└─ nvidia_gpu_exporter (GTX 1070 metrics via runtimeClassName: nvidia)

SECURITY
├─ Falco (runtime threat detection, DaemonSet on all nodes)
├─ cert-manager (internal CA, TLS for all ingresses)
├─ Network policies per namespace (default-deny ingress)
├─ All container images pinned to SHA digest (no :latest)
└─ SSH hardening via Ansible (key-only auth)

DNS
├─ Technitium (internal zone: home.t12.io)
└─ Pi-hole (LAN ad-blocking + conditional forwarding)

BACKUP
└─ Velero → Backblaze B2 (daily schedule, 30d retention)

SRE TOOLING
└─ sre-cli — Prometheus alerts, cluster status, semantic runbook search via Qdrant
```

## Repository Structure

```
homelab-gitops/
├── clusters/prod/flux-system/     # Flux bootstrap — entry point
│   ├── gotk-components.yaml       # Flux controllers
│   ├── gotk-sync.yaml             # GitRepository + root Kustomization
│   ├── infrastructure.yaml        # Kustomization ref → infrastructure/prod
│   ├── monitoring.yaml            # Kustomization ref → monitoring/prod
│   └── apps.yaml                  # Kustomization ref → apps/prod
│
├── infrastructure/prod/           # CNI, ingress, DNS, storage, security
│   ├── cilium/                    # HelmRelease + L2 pool + announcement policy
│   ├── cert-manager/              # HelmRelease + ClusterIssuer
│   ├── nginx-ingress/             # HelmRelease
│   ├── technitium/                # Deployment + PVC + network policies
│   ├── pihole/                    # Deployment + ConfigMap + SOPS secret
│   ├── velero/                    # HelmRelease + daily backup schedule
│   ├── falco/                     # HelmRelease (DaemonSet, all nodes)
│   └── gpu-metrics/               # nvidia_gpu_exporter DaemonSet + ServiceMonitor
│
├── monitoring/prod/               # Prometheus stack, Loki, ntfy
│
├── apps/prod/                     # Applications and AI platform
│   ├── ai-platform/               # Ollama, LiteLLM, Open-WebUI, Qdrant, Dashy
│   ├── nextcloud/                 # Nextcloud + PostgreSQL + Redis
│   ├── n8n/                       # n8n + PostgreSQL
│   ├── vault-ingest/              # Qdrant ingestion pipeline (Redpanda + consumer)
│   └── vaultwarden/
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
     └── Cilium, cert-manager,        └── AI platform, Nextcloud,
         nginx-ingress, DNS,               n8n, Vaultwarden,
         storage, security                 vault-ingest
```

`apps` depends on `infrastructure` (ingress, TLS, storage must exist first). Race conditions on first bootstrap are eliminated.

## Secret Management

Secrets are encrypted in git with [SOPS](https://github.com/getsops/sops) + [age](https://age-encryption.org/). Flux decrypts at reconcile time using an age private key stored as a cluster secret.

`.sops.yaml` targets only `data`/`stringData` fields — metadata stays in plaintext and diffs remain readable.

## Cilium L2 LoadBalancer

Replaces MetalLB entirely. Services get stable LAN-routable IPs (`10.0.0.200-220`) via ARP announcements on physical interfaces. Key IPs: `10.0.0.200` (Technitium DNS), `10.0.0.201` (ingress-nginx), `10.0.0.202` (Grafana direct).

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
