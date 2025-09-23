
Observability makes MAAS transparent. With metrics, logs, and alerts, you can see the system’s internal state, detect failures quickly, and tune performance. MAAS integrates with Prometheus, Loki, Grafana, and Alertmanager, either via Canonical Observability Stack (COS) or your own deployment.

This guide shows how to:

- Deploy an observability stack with Prometheus, Loki, Alertmanager, and Grafana.
- Export telemetry from MAAS using Grafana Agent.
- Verify dashboards and alerts.

Use the section that matches your MAAS version.


## Monitoring with MAAS 3.5+

From MAAS 3.5 onward, integration with Prometheus and Loki is simplified.

### Requirements
- Ubuntu host with MAAS 3.5+ running.
- Separate Ubuntu host (or VM) with enough storage for logs and metrics.
- Internet access for package downloads.
- Optional: LXD for single-host testing.

### Step 1: Configure the stack

Launch an Ubuntu VM and install Prometheus, Loki, Alertmanager, and Grafana:

```bash
export LXD_NET=virbr0
export GRAFANA_REPOS=https://packages.grafana.com/oss/deb
export GRAFANA_KEY=https://packages.grafana.com/gpg.key
export LOKI_PKG=https://github.com/grafana/loki/releases/download/v3.4.2/loki-linux-amd64.zip
export PROM_PKG=https://github.com/prometheus/prometheus/releases/download/v3.2.1/prometheus-3.2.1.linux-amd64.tar.gz
export PROM_ALERT_PKG=https://github.com/prometheus/alertmanager/releases/download/v0.28.1/alertmanager-0.28.1.illumos-amd64.tar.gz

cat <<EOF | lxc launch ubuntu: o11y
config:
    user.user-data: |
        #cloud-config
        apt:
            sources:
                grafana:
                    source: 'deb ${GRAFANA_REPOS} stable main'
                    key: |
$(wget -qO- ${GRAFANA_KEY} | sed 's/^/                        /')
        packages:
        - unzip
        - grafana
        - make
        - git
        - python3-pip
        runcmd:
        - mkdir -p /opt/prometheus /opt/loki /opt/alertmanager
        - wget -q "${LOKI_PKG}" -O /tmp/loki-linux-amd64.zip
        - unzip /tmp/loki-linux-amd64.zip -d /opt/loki
        - chmod a+x /opt/loki/loki-linux-amd64
        - wget -qO- "${PROM_PKG}" | tar xz --strip-components=1 -C /opt/prometheus
        - wget -qO- "${PROM_ALERT_PKG}" | tar xz --strip-components=1 -C /opt/alertmanager
        - cat /dev/zero | sudo -u ubuntu -- ssh-keygen -q -N "
        ssh_authorized_keys:
        - $(cat ${HOME}/.ssh/id_rsa.pub | cut -d' ' -f1-2)
description: O11y stack
devices:
    eth0:
        type: nic
        name: eth0
        network: ${LXD_NET}
EOF

# log into the VM
lxc shell o11y
```

### Step 2: Configure Prometheus

Create the Prometheus config:

```bash
cat > /opt/prometheus/prometheus.yaml <<EOF
global:
  evaluation_interval: 1m
rule_files:
  - /var/lib/prometheus/rules/maas/*.yml
alerting:
  alertmanagers:
    - static_configs:
      - targets:
        - localhost:9093
EOF
```

Install curated MAAS alert rules:

```bash
git clone https://github.com/canonical/maas-prometheus-alert-rules.git
cd maas-prometheus-alert-rules
make python-deps groups

mkdir -p /var/lib/prometheus/rules/maas
cp group.yml /var/lib/prometheus/rules/maas/
```

Start Prometheus with remote write enabled:

```bash
systemd-run -u prometheus /opt/prometheus/prometheus     --config.file=/opt/prometheus/prometheus.yaml     --web.enable-remote-write-receiver
```

### Step 3: Configure Loki

Create the Loki config:

```bash
cat > /opt/loki/loki.yaml <<EOF
auth_enabled: false
server:
  http_listen_port: 3100
  grpc_listen_port: 9096
common:
  path_prefix: /var/lib/loki/
  storage:
    filesystem:
      chunks_directory: /var/lib/loki/chunks
      rules_directory: /var/lib/loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h
ruler:
  alertmanager_url: http://localhost:9093
  evaluation_interval: 15s
  poll_interval: 1m
  storage:
    type: local
    local:
      directory: /var/lib/loki/rules
  enable_api: true
EOF
```

Install curated Loki rules:

```bash
git clone https://github.com/canonical/maas-loki-alert-rules.git
cd maas-loki-alert-rules
make groups

mkdir -p /var/lib/loki/rules/fake
cp rules/bundle.yml /var/lib/loki/rules/fake/
```

Start Loki:

```bash
systemd-run -u loki /opt/loki/loki-linux-amd64     --config.file=/opt/loki/loki.yaml     -validation.allow-structured-metadata=false
```

### Step 4: Start Alertmanager

```bash
systemd-run -u alertmanager /opt/alertmanager/alertmanager     --config.file=/opt/alertmanager/alertmanager.yml
```

Access at `http://<VM_IP>:9093`.

### Step 5: Start Grafana

```bash
systemctl enable grafana-server
systemctl start grafana-server
```

Access at `http://<VM_IP>:3000` (`admin`/`admin`).

### Step 6: Export telemetry from MAAS

Install Grafana Agent on the MAAS host:

```bash
export O11y_IP=<O11y_IP>
export GRAFANA_AGENT_PKG=https://github.com/grafana/agent/releases/download/v0.44.2/grafana-agent-linux-amd64.zip
wget -q "${GRAFANA_AGENT_PKG}" -O /tmp/agent.zip
unzip /tmp/agent.zip -d /opt/agent
chmod a+x /opt/agent/grafana-agent-linux-amd64
```

Copy the agent config (depends on snap vs deb):

```bash
mkdir -p /var/lib/grafana-agent/positions          /var/lib/grafana-agent/wal

# for snap
cp /snap/maas/current/usr/share/maas/grafana_agent/agent-example-snap.yaml /opt/agent/agent.yaml

# for deb
cp /usr/share/maas/grafana_agent/agent-example-deb.yaml /opt/agent/agent.yaml
```

Start the agent:

```bash
systemd-run -u telemetry     -E HOSTNAME="$(hostname)"     -E AGENT_WAL_DIR="/var/lib/grafana-agent/wal"     -E AGENT_POS_DIR="/var/lib/grafana-agent/positions"     -E PROMETHEUS_REMOTE_WRITE_URL="http://${O11y_IP}:9090/api/v1/write"     -E LOKI_API_URL="http://${O11y_IP}:3100/loki/api/v1/push"     -E MAAS_IS_REGION="true"     -E MAAS_IS_RACK="true"     -E MAAS_AZ="default"     /opt/agent/grafana-agent-linux-amd64      -config.expand-env      -config.file=/opt/agent/agent.yaml
```

Enable syslog forwarding:

```bash
maas $ADMIN maas set-config name=promtail_port value=5238
maas $ADMIN maas set-config name=promtail_enabled value=true
```

### Step 7: Verify

- Add Prometheus and Loki as data sources in Grafana.
- Import curated dashboards.
- Confirm alerts fire through Alertmanager.


## Monitoring with MAAS 3.4–3.2

The process is similar, but with older versions of Prometheus, Loki, and Grafana Agent.

Key differences:
- Loki v2.4.2
- Prometheus v2.31.1
- Alertmanager v0.23.0
- Grafana Agent v0.22.0

Prometheus uses `--enable-feature=remote-write-receiver` instead of `--web.enable-remote-write-receiver`.

All other steps (VM launch, config creation, starting services, exporting telemetry, enabling syslog) follow the same structure.


## Basic O11y (MAAS 3.1 and earlier)

Older versions expose Prometheus endpoints directly (`/metrics`). Install `python3-prometheus-client` (Deb only) and restart `maas-rackd` / `maas-regiond`.

Enable optional stats:
```bash
maas $PROFILE maas set-config name=prometheus_enabled value=true
```

### Prometheus endpoints
- TFTP server file transfer latency
- HTTP request latency
- WebSocket request latency
- RPC call latency
- DB query counts

### Configure Prometheus scrape jobs
```yaml
- job_name: maas
  static_configs:
    - targets:
      - <maas-host1-IP>:5239  # regiond
      - <maas-host1-IP>:5249  # rackd
      - <maas-host2-IP>:5239  # regiond-only
      - <maas-host3-IP>:5249  # rackd-only
```

If MAAS stats are enabled:
```yaml
- job_name: maas
  metrics_path: /MAAS/metrics
  static_configs:
    - targets:
      - <maas-host-IP>:5240
```


## Deploy Prometheus with Juju (optional)

The [MAAS performance repo](https://git.launchpad.net/~maas-committers/maas/+git/maas-performance) provides a `deploy-stack` script to spin up Prometheus + Grafana on LXD containers.

1. Install Juju:
   ```bash
   sudo snap install --classic juju
   ```
2. Run the deploy script:
   ```bash
   grafana/deploy-stack <MAAS-IP>
   ```
3. Monitor deployment:
   ```bash
   watch -c juju status --color
   ```

Grafana: port 3000 (`admin`/`grafana`)
Prometheus: port 9090


## Safety nets

- Always test telemetry with `systemd-run` and verify logs/metrics in Grafana.
- Confirm Prometheus scrape jobs are targeting the right host/port.
- Adjust Alertmanager config to send notifications somewhere useful.
- Use the curated MAAS alert rule repositories for Prometheus and Loki.


## Next steps
- Read about our [MAAS performance work](https://canonical.com/maas/docs/about-maas-performance)
- Peruse our [MAAS metrics catalog](https://canonical.com/maas/docs/reference-maas-metrics)
