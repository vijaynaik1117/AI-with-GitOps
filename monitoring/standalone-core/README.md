# Prometheus + Grafana + Alertmanager + Jaeger — Standalone Docker (WN-3)

Precise steps, run in order on WN-3. This assumes Docker is already installed
and working (`docker run --rm hello-world` succeeds).

## Step 1 — Get the files onto WN-3

```bash
cd ~
git clone <your-repo-with-this-bundle>   # or scp the standalone-core/ folder over
cd k8s-gitops/04-monitoring/standalone-core
```

Confirm the folder layout matches:

```bash
find . -type f
```

Expected:
```
./docker-compose.yml
./prometheus/prometheus.yml
./prometheus/alert.rules.yml
./alertmanager/alertmanager.yml
./grafana/provisioning/datasources/datasources.yaml
```

## Step 2 — Configure Alertmanager's Slack webhook

Create a Slack incoming webhook first (Slack → your workspace →
`api.slack.com/apps` → create app → Incoming Webhooks → add to channel), then:

```bash
nano alertmanager/alertmanager.yml
```

Replace this line's placeholder URL with your real webhook:

```yaml
api_url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

Save and exit.

## Step 3 — Start the stack

```bash
docker compose up -d
```

## Step 4 — Confirm all 4 containers are running

```bash
docker compose ps
```

Expected output: `prometheus`, `alertmanager`, `grafana`, `jaeger` all showing
state `running` (or `Up`).

If any show `Exited`, check its logs before continuing:

```bash
docker compose logs <service-name>
```

## Step 5 — Verify each UI is reachable

Replace `<WN-3-IP>` with WN-3's actual IP.

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9090       # Prometheus
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9093       # Alertmanager
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000       # Grafana
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:16686      # Jaeger
```

All four should return `200` (Grafana may return `302` on the bare `/` path —
that's normal, it's redirecting to the login page).

Then open each in a browser:

- Prometheus: `http://<WN-3-IP>:9090`
- Alertmanager: `http://<WN-3-IP>:9093`
- Grafana: `http://<WN-3-IP>:3000` — login `admin` / `changeMe123!` (change this — see Step 6)
- Jaeger: `http://<WN-3-IP>:16686`

## Step 6 — Change the Grafana default password

Don't skip this if WN-3 is reachable beyond localhost.

```bash
nano docker-compose.yml
```

Change:
```yaml
- GF_SECURITY_ADMIN_PASSWORD=changeMe123!
```
to a real password, then apply it:

```bash
docker compose up -d grafana
```

## Step 7 — Confirm Grafana's datasources auto-loaded

In Grafana UI: **Connections → Data sources**. You should already see
**Prometheus** and **Jaeger** listed — no manual setup needed, this was
provisioned automatically from `grafana/provisioning/datasources/datasources.yaml`.

Click **Prometheus → Save & Test** — should show "Successfully queried the
Prometheus API."

## Step 8 — Verify Prometheus is actually scraping itself

Open `http://<WN-3-IP>:9090/targets` — the `prometheus` job should show
**State: UP**.

## Step 9 — Test the alert pipeline end-to-end

Open `http://<WN-3-IP>:9090/alerts` — you should see 3 alert rules loaded
(`HighCPUUsage`, `HighMemoryUsage`, `InstanceDown`), all in state "Inactive"
(green) since nothing's actually firing yet.

To trigger a real alert without disrupting anything you care about, add a
temporary unreachable scrape target:

```bash
nano prometheus/prometheus.yml
```

Add under `scrape_configs`:
```yaml
  - job_name: 'fake-target-test'
    static_configs:
      - targets: ['10.255.255.1:9999']
```

Reload Prometheus config without restarting the container:

```bash
curl -X POST http://localhost:9090/-/reload
```

Within ~2 minutes, check `http://<WN-3-IP>:9090/alerts` — `InstanceDown`
should go to state "Firing" (red), and a message should land in your Slack
channel via Alertmanager.

**Clean up the test target afterward:**

```bash
nano prometheus/prometheus.yml   # remove the fake-target-test block
curl -X POST http://localhost:9090/-/reload
```

## Step 10 — Confirm it survives a reboot

```bash
sudo systemctl is-enabled docker    # should print: enabled
sudo reboot
```

After it comes back:

```bash
docker compose ps
```

All 4 should already be `Up` — no manual `docker compose up -d` needed, since
every service has `restart: unless-stopped` and Docker itself auto-starts.

## Step 11 — Send traces to Jaeger from an app

If you have an app that speaks Jaeger's legacy thrift protocol (like the
`service-a`/`service-b` Node examples built earlier), point it at:

```
JAEGER_AGENT_HOST=<WN-3-IP>
JAEGER_AGENT_PORT=6831
```

For apps using OpenTelemetry SDKs directly (OTLP), point them at:

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://<WN-3-IP>:4317   # gRPC
# or :4318 for HTTP
```

Traces will appear in Jaeger's UI under **Search → Service** within seconds
of the app making a request.

## Done

You now have Prometheus scraping + alerting, Alertmanager routing to Slack,
Grafana visualizing both metrics and traces, and Jaeger collecting distributed
traces — all as standalone Docker containers on WN-3, fully independent of
the Kubernetes cluster.

---

## Adding OTel Collector + Loki (log aggregation) to this same stack

This stack now also includes an **OpenTelemetry Collector** (central place for
apps to send traces/metrics, which fans out to Jaeger + Prometheus) and
**Loki + Promtail** (log aggregation — Promtail auto-discovers every Docker
container's logs and ships them to Loki, no per-container config needed).

### Step 12 — Pull the new config files

If you already ran `docker compose up -d` from Step 3, you just need the
updated `docker-compose.yml` plus the new folders:

```
otel-collector/otel-collector-config.yaml
loki/loki-config.yaml
promtail/promtail-config.yaml
```

Confirm they're present:

```bash
find . -type f | sort
```

### Step 13 — Apply the changes

```bash
docker compose up -d
```

This only creates/starts the **new** services (`otel-collector`, `loki`,
`promtail`) — your existing Prometheus/Grafana/Alertmanager/Jaeger containers
are untouched since their config didn't change.

### Step 14 — Confirm all 7 containers are running

```bash
docker compose ps
```

Expected: `prometheus`, `alertmanager`, `grafana`, `jaeger`, `otel-collector`,
`loki`, `promtail` — all `Up`.

### Step 15 — Verify Loki is reachable

```bash
curl -s http://localhost:3100/ready
```

Should print `ready`.

### Step 16 — Verify Promtail is shipping logs

```bash
curl -s http://localhost:9080/targets | grep -i docker
```

Should show the `docker-containers` job with active targets (one per running
container).

### Step 17 — Confirm Loki shows up in Grafana

**Connections → Data sources** — you should now see **Loki** listed alongside
Prometheus and Jaeger (auto-provisioned, no manual setup).

Then go to **Explore** (compass icon in the left sidebar), select **Loki** as
the datasource, and run this query to see all container logs:

```
{compose_service=~".+"}
```

Or filter to one container, e.g.:

```
{container="jaeger"}
```

You should see live log lines streaming in from every container in this
stack within a few seconds.

### Step 18 — Verify OTel Collector is reachable and scraped

```bash
curl -s http://localhost:8888/metrics | head -5
```

Should print Prometheus-format metrics. Then confirm Prometheus is scraping
it: open `http://<WN-3-IP>:9090/targets` — `otel-collector` and
`otel-collector-forwarded-app-metrics` jobs should both show **State: UP**.

### Step 19 — Point an app at the OTel Collector

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://<WN-3-IP>:4319   # gRPC
# or :4320 for HTTP
```

Traces sent here get forwarded to Jaeger automatically; metrics get exposed
on `:8889` for Prometheus to pick up on its next scrape (~15s).

### Notes

- **Loki retention** is set to 7 days (`retention_period: 168h` in
  `loki/loki-config.yaml`) — raise this if you have disk to spare and want
  longer log history.
- **Promtail needs the Docker socket** (`/var/run/docker.sock`, read-only) to
  auto-discover containers, and reads raw log files from
  `/var/lib/docker/containers` — both are mounted read-only, Promtail never
  writes to either.
- If you add more containers to WN-3 later (outside this compose file),
  Promtail picks them up automatically — no config change needed, it
  discovers via the Docker socket continuously.

---

## Extension: Loki (logs) + OTel Collector

Three more services are now included: **Loki** (log storage), **Promtail**
(ships every Docker container's logs on WN-3 into Loki automatically), and
**OTel Collector** (a single OTLP endpoint apps can send traces/metrics/logs
to, which fans them out to Jaeger/Prometheus/Loki respectively).

### Step 12 — Restart the stack to pick up the new services

```bash
docker compose up -d
```

Compose only creates/updates what changed — your existing Prometheus,
Grafana, Alertmanager, Jaeger data isn't touched.

### Step 13 — Confirm the new containers are running

```bash
docker compose ps
```

Expect 7 services now: `prometheus`, `alertmanager`, `grafana`, `jaeger`,
`loki`, `promtail`, `otel-collector` — all `running`.

### Step 14 — Verify Loki is receiving logs

```bash
curl -s http://localhost:3100/ready
```

Should return `ready`.

Check Promtail is actually shipping logs:

```bash
docker compose logs promtail | tail -20
```

You should see it discovering containers, no repeated errors connecting to
Loki.

### Step 15 — Confirm Loki shows up in Grafana

Grafana → **Connections → Data sources** → you should now see **Loki**
alongside Prometheus and Jaeger, auto-provisioned.

Go to **Explore**, select the **Loki** datasource, and run:

```logql
{compose_service=~".+"}
```

You should see live log lines from every container in this stack (Prometheus,
Grafana, Jaeger, etc. all logging to stdout, which Promtail picked up
automatically via the Docker socket).

### Step 16 — Send data to the OTel Collector from an app

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://<WN-3-IP>:4319   # gRPC
# or http://<WN-3-IP>:4320 for OTLP/HTTP
```

Anything the app sends via OTLP — traces, metrics, or logs — gets routed
automatically: traces → Jaeger, metrics → Prometheus (scraped from
`otel-collector:8889`), logs → Loki.

### Step 17 — Confirm the collector's own health

```bash
curl -s http://localhost:8888/metrics | head -5
```

Should return Prometheus-format metrics text (the collector's internal
telemetry) — confirms it's alive and Prometheus can scrape it.

