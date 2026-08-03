#!/usr/bin/env bash
# Run on CCCA, WN-1, WN-2 — installs node_exporter as a native binary +
# systemd service. Deliberately NOT using Docker here since these nodes only
# run containerd for Kubernetes; adding Docker just for this would risk the
# same containerd conflicts hit earlier on WN-3.
set -euo pipefail

NODE_EXPORTER_VERSION="1.8.2"
ARCH="amd64"

echo "== Downloading node_exporter v${NODE_EXPORTER_VERSION} =="
cd /tmp
curl -fsSL -o node_exporter.tar.gz \
  "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-${ARCH}.tar.gz"

tar xzf node_exporter.tar.gz
sudo mv "node_exporter-${NODE_EXPORTER_VERSION}.linux-${ARCH}/node_exporter" /usr/local/bin/node_exporter
rm -rf node_exporter.tar.gz "node_exporter-${NODE_EXPORTER_VERSION}.linux-${ARCH}"

echo "== Creating dedicated system user =="
if ! id -u node_exporter &>/dev/null; then
  sudo useradd --no-create-home --shell /usr/sbin/nologin node_exporter
fi
sudo chown node_exporter:node_exporter /usr/local/bin/node_exporter

echo "== Creating systemd unit =="
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<'UNIT_END'
[Unit]
Description=Prometheus Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter --collector.systemd --collector.processes

[Install]
WantedBy=multi-user.target
UNIT_END

echo "== Enabling and starting =="
sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter

echo "== Verifying =="
sleep 2
sudo systemctl status node_exporter --no-pager || true
curl -s http://localhost:9100/metrics | head -5

echo "Done. node_exporter is now listening on :9100 on this node."
