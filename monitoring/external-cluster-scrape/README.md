# Getting Cluster Metrics into External Prometheus (WN-3)

Your Prometheus/Grafana/Alertmanager stack runs standalone on WN-3
(`192.168.1.96`), **outside** the Kubernetes cluster (CCCA `192.168.1.98`,
WN-1 `192.168.1.97`, WN-2 `192.168.1.95`). Prometheus can only scrape targets
it can reach over the network — so each metric source below needs to be
exposed on a port reachable from WN-3.

## What's being wired up

| Metric type | Source | How it's exposed |
|---|---|---|
| Node metrics (CPU/mem/disk per host) | `node_exporter` on each k8s node | Native binary + systemd, port `9100` |
| Pod/Deployment/Namespace metrics | `kube-state-metrics` (in-cluster) | NodePort `30080` |
| Argo CD app sync/health metrics | `argocd-metrics` service | NodePort `30082` |
| Argo CD API server metrics | `argocd-server-metrics` service | NodePort `30083` |

## Step 1 — Install node_exporter on CCCA, WN-1, WN-2

Copy `install-node-exporter.sh` to each node (via `git clone`/`scp` — not
copy/paste, same lesson as before), then on **each** node:

```bash
chmod +x install-node-exporter.sh
sudo bash install-node-exporter.sh
```

Verify locally on each node:

```bash
curl -s http://localhost:9100/metrics | head -5
```

## Step 2 — Confirm node_exporter is reachable from WN-3

From WN-3:

```bash
curl -s http://192.168.1.98:9100/metrics | head -3   # CCCA
curl -s http://192.168.1.97:9100/metrics | head -3   # WN-1
curl -s http://192.168.1.95:9100/metrics | head -3   # WN-2
```

**If these time out or connection-refuse**, it's almost certainly a firewall
blocking port 9100 between WN-3 and the cluster nodes. Check on each node:

```bash
sudo ufw status
# if active and 9100 isn't allowed:
sudo ufw allow from 192.168.1.96 to any port 9100
```

## Step 3 — Deploy kube-state-metrics in the cluster — (run from CCCA)

```bash
kubectl apply -f kube-state-metrics.yaml
```

Verify it's running:

```bash
kubectl -n monitoring-agents get pods
kubectl -n monitoring-agents get svc kube-state-metrics-external
```

Confirm from WN-3:

```bash
curl -s http://192.168.1.98:30080/metrics | head -5
```

(NodePort services are reachable via **any** cluster node's IP, not just
CCCA — `192.168.1.97:30080` or `192.168.1.95:30080` work identically.)

## Step 4 — Expose Argo CD's metrics via NodePort — (run from CCCA)

Only run this after Argo CD itself is installed (`03-argocd/install-and-sso.md`).

```bash
kubectl apply -f argocd-metrics-nodeport.yaml
```

Verify:

```bash
kubectl -n argocd get svc argocd-metrics-external argocd-server-metrics-external
```

Confirm from WN-3:

```bash
curl -s http://192.168.1.98:30082/metrics | head -5   # app controller metrics
curl -s http://192.168.1.98:30083/metrics | head -5   # API server metrics
```

## Step 5 — Update Prometheus's scrape config on WN-3

The `04-monitoring/standalone-core/prometheus/prometheus.yml` in this bundle
already has all 4 new scrape jobs added
(`k8s-node-exporter`, `kube-state-metrics`, `argocd-metrics`,
`argocd-server-metrics`). If you already have this file deployed with an
older version, replace it with the updated one, then reload:

```bash
cd 04-monitoring/standalone-core
docker compose up -d   # picks up the new prometheus.yml via the mounted volume
# or, without restarting the container:
curl -X POST http://localhost:9090/-/reload
```

## Step 6 — Verify every target is UP

Open `http://192.168.1.96:9090/targets` and confirm:

- `k8s-node-exporter` — 3 targets, all **UP**
- `kube-state-metrics` — 1 target, **UP**
- `argocd-metrics` — 1 target, **UP**
- `argocd-server-metrics` — 1 target, **UP**

If any show **DOWN**, click it to see the error — usually either a firewall
block (see Step 2) or the pod/service isn't actually running yet
(`kubectl get pods -A` to check).

## Step 7 — Import dashboards in Grafana

Open `http://192.168.1.96:3000` → **Dashboards → New → Import**, and use
these official dashboard IDs (Grafana pulls them straight from
grafana.com/dashboards):

| Dashboard | ID | Shows |
|---|---|---|
| Node Exporter Full | `1860` | Per-node CPU, memory, disk, network |
| Kubernetes Cluster (kube-state-metrics) | `13332` | Pod counts, deployment status, restarts, resource requests/limits |
| Argo CD | `14584` | App sync status, health, sync duration |

For each: paste the ID → **Load** → select **Prometheus** as the datasource →
**Import**.

## Step 8 — Confirm data is actually flowing

Each imported dashboard should populate with real data within ~30 seconds
(one scrape interval). If a panel stays empty:

1. Check the underlying query in that panel (usually uses a label like
   `instance` or `job` that must match your scrape config's job names above)
2. Re-check `/targets` in Prometheus — if the target shows UP but has 0
   samples, the exporter itself may not be exposing that particular metric

## Notes on scope/security

- **NodePorts (30080/30082/30083) are open on all 3 cluster nodes**, not just
  CCCA — anyone who can reach any cluster node on those ports can read your
  cluster's object metadata and Argo CD sync state. Fine for a home lab; for
  anything more exposed, put these behind a firewall rule restricting source
  IP to WN-3 only (`192.168.1.96`), similar to the `ufw allow from` pattern
  in Step 2.
- **Container-level resource metrics** (CPU/memory *per pod*, as opposed to
  per-node) come from the kubelet's cAdvisor endpoint, which requires a
  bearer-token + RBAC setup more involved than what's covered here. What
  you have now (node-level via node_exporter + object-level via
  kube-state-metrics) covers "is this pod running, how many replicas, is
  Argo CD synced" — ask if you also want true per-pod CPU/memory usage
  graphs; that's a separate, slightly more involved piece (kubelet
  `/metrics/cadvisor` scraping with a service account token).
