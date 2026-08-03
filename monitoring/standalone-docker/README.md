# Standalone Observability Stack (Docker, WN-3)

This runs **independently of the Kubernetes cluster** — plain Docker
containers on WN-3, wired together with docker compose. Use this if you want
observability tooling on a box that isn't part of the k8s cluster (e.g. for
monitoring the VM itself, or apps running outside k8s).

## Stack

| Service | Port | Purpose |
|---|---|---|
| Prometheus | 9090 | Metrics scraping + storage |
| Alertmanager | 9093 | Routes alerts → Slack |
| node-exporter | 9100 | Host-level metrics (CPU, memory, disk) for Prometheus |
| Grafana | 3000 | Dashboards (Prometheus + Jaeger pre-provisioned as datasources) |
| Jaeger | 16686 (UI), 4317/4318 (OTLP) | Distributed tracing |
| OTel Collector | 4319/4320 (OTLP in), 8888/8889 (metrics out) | Central place apps send traces/metrics; fans out to Jaeger + Prometheus |
| Datadog Agent | — (no exposed UI, ships to Datadog SaaS) | Host + container monitoring, APM |

## 1. Configure secrets

```bash
cd 04-monitoring/standalone-docker
cp .env.example .env
```

Edit `.env` and set your real `DD_API_KEY` (from Datadog → Organization
Settings → API Keys) and `DD_SITE` (`datadoghq.com` for US1, `datadoghq.eu`
for EU, etc — check which region your Datadog org is on).

Edit `alertmanager/alertmanager.yml` and replace the placeholder `api_url`
with your real Slack incoming webhook URL.

## 2. Start everything

```bash
docker compose up -d
```

Check everything came up healthy:

```bash
docker compose ps
```

## 3. Access each UI

- Prometheus: `http://<WN-3-IP>:9090`
- Alertmanager: `http://<WN-3-IP>:9093`
- Grafana: `http://<WN-3-IP>:3000` (login: `admin` / the password set in `docker-compose.yml`'s `GF_SECURITY_ADMIN_PASSWORD` — change it before exposing this beyond localhost)
- Jaeger: `http://<WN-3-IP>:16686`

Datadog has no local UI — check `https://app.datadoghq.com` (or your region's
URL) once the agent's been running a minute or two; WN-3 should appear under
**Infrastructure → Host Map**.

## 4. Point your own apps at this stack

If you have apps on WN-3 (or reachable from it) that emit OTLP traces/metrics,
send them to:

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://<WN-3-IP>:4320   # OTLP HTTP
# or gRPC on 4319
```

The collector fans traces out to Jaeger and metrics out to a Prometheus-scrapable
endpoint automatically — no per-app config needed beyond the OTLP endpoint.

If an app already speaks legacy Jaeger-thrift (like the `service-a`/`service-b`
Node apps built earlier in this project), point it directly at Jaeger instead:

```
JAEGER_AGENT_HOST=<WN-3-IP>
JAEGER_AGENT_PORT=6831
```

## 5. Verify alerting end-to-end

Force a test alert by stopping a scrape target temporarily:

```bash
docker stop node-exporter
```

Within ~2 minutes, `InstanceDown` should fire in Prometheus (`http://<WN-3-IP>:9090/alerts`),
route through Alertmanager, and land in your Slack channel. Then:

```bash
docker start node-exporter
```

The alert should auto-resolve and post a resolved message to Slack too
(`send_resolved: true` is already set).

## 6. Auto-start on reboot

Every service already has `restart: unless-stopped` set, and as long as
Docker itself is enabled (`sudo systemctl enable docker`), the whole stack
comes back up automatically after a VM reboot — same pattern as the Jenkins
container.

## Notes

- **This stack is separate from `04-monitoring/install-monitoring.md`**, which
  is the in-cluster kube-prometheus-stack Helm install for the Kubernetes
  cluster itself. Run both if you want cluster-internal monitoring (via Helm)
  *and* a standalone box monitoring WN-3/host-level/non-k8s apps (this one).
- Prometheus retains data in a Docker named volume (`prometheus_data`) — not
  ideal for long-term retention on a single VM; consider mounting a larger
  disk or adding `--storage.tsdb.retention.time=15d` to Prometheus's command
  args if disk space is limited.
- Datadog and the Prometheus/Grafana/Jaeger stack overlap significantly in
  purpose (both do metrics + APM). Running both isn't wrong, but worth
  knowing you likely don't need both long-term — this setup gives you room to
  compare and pick one.
