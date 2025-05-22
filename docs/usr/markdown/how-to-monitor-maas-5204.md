To keep your MAAS setup transparent, we've engineered it for observability — you can gauge its internal state purely through telemetry data. Depending on your MAAS version, your monitoring toolkit will differ.

Make sure to navigate to the section that matches your MAAS version.

## Monitoring (3.2++)

From version 3.2 onward, MAAS simplifies the integration process with key Grafana stack components like Prometheus and Loki. Use this data seamlessly with an open-source stack, whether it's orchestrated by Juju—like the Canonical Observability Stack—or a third-party solution, be it SaaS or self-managed.

Below is a reference observability stack featuring Prometheus for metric collection and alerting, Loki for log aggregation and alerts, Grafana for visualization, Alertmanager for handling notifications, and Grafana Agent as the telemetry collector.

<a href="https://discourse.maas.io/uploads/default/optimized/2X/d/d6f66cbb3ea314818894b4f07ca8037628993ae2_2_690x437.png" target = "_blank">![](upload://eGnGAB4W9qzA8wgGzGaWozgmMTl.png)</a>

This section walks you through setting up the stack to ingest telemetry data and trigger alerts for failures.

## O11y requirements

- an Ubuntu host with MAAS 3.2+ running
- an Ubuntu host with enough storage capacity to hold logs and metrics' time-series

Both hosts need internet access for installation. While we employ LXD for a single-host setup, it's not mandatory. For production use, consult the [Prometheus](https://prometheus.io/docs/) and [Loki](https://grafana.com/docs/loki/latest/) docs to enhance security and performance.

## Configuring O11y

In monitoring MAAS, you'll need to follow three key steps: set up your tool stack, export telemetry data, and validate that it's all running smoothly. 

## Configure the stack

Create a VM with the following script to install all required software.

```nohighlight
export LXD_NET=virbr0
export GRAFANA_REPOS=https://packages.grafana.com/oss/deb
export GRAFANA_KEY=https://packages.grafana.com/gpg.key
export LOKI_PKG=https://GitHub.com/grafana/loki/releases/download/v2.4.2/loki-linux-amd64.zip
export PROM_PKG=https://GitHub.com/prometheus/prometheus/releases/download/v2.31.1/prometheus-2.31.1.linux-amd64.tar.gz
export PROM_ALERT_PKG=https://GitHub.com/prometheus/alertmanager/releases/download/v0.23.0/alertmanager-0.23.0.linux-amd64.tar.gz

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

Next, you have to configure and start four services, include Prometheus, Loki, AlertManager, and Grafana. Once these services are started, you can proceed to export telemetry data and see how your observability tools are working.

## Configure Prometheus

Create the Prometheus configuration.

```nohighlight
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

MAAS has a git repository of curated alert rules for Prometheus. Checkout this repository, compile the rules and copy them to prometheus directory.

```nohighlight
git clone https://GitHub.com/canonical/maas-prometheus-alert-rules.git
cd maas-prometheus-alert-rules
make python-deps groups

mkdir -p /var/lib/prometheus/rules/maas
cp group.yml /var/lib/prometheus/rules/maas/
```

Start the Prometheus service. You should enable the *Remote-Write Receiver* function.

```nohighlight
systemd-run -u prometheus /opt/prometheus/prometheus \
    --config.file=/opt/prometheus/prometheus.yaml \
    --enable-feature=remote-write-receiver
```

## Configure Loki

Create the Loki configuration.

```nohighlight
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

MAAS has a git repository of curated alert rules for Loki. Checkout this repository, compile the rules and copy them to Loki directory.

```nohighlight
git clone https://GitHub.com/canonical/maas-loki-alert-rules.git
cd maas-loki-alert-rules
make groups

mkdir -p /var/lib/loki/rules/fake
cp rules/bundle.yml /var/lib/loki/rules/fake/
```

Start the Loki service.

```nohighlight
systemd-run -u loki /opt/loki/loki-linux-amd64 \
    --config.file=/opt/loki/loki.yaml
```

## Start AlertManager

The default configuration is enough for receiving alerts from Prometheus and Loki. You should read the project documentation to change it to forward notifications to somewhere useful.

```nohighlight
systemd-run -u alertmanager /opt/alertmanager/alertmanager \
    --config.file=/opt/alertmanager/alertmanager.yml
```

You can access the AlertManager dashboard at `http://<VM_IP>:9093`

## Start Grafana

Grafana works out-of-the-box with the default configuration.

```nohighlight
systemctl enable grafana-server
systemctl start grafana-server
```

You can access the dashboard at `http://<VM_IP>:3000`, the default user/password is "admin".

## Export telemetry

The Grafana Agent should be installed in the same host as MAAS.

```nohighlight
# Set this to the address of the VM running Loki and Prometheus
export O11y_IP=<VM_IP>
export GRAFANA_AGENT_PKG=https://GitHub.com/grafana/agent/releases/download/v0.22.0/agent-linux-amd64.zip

wget -q "${GRAFANA_AGENT_PKG}" -O /tmp/agent.zip
unzip /tmp/agent.zip -d /opt/agent
chmod a+x /opt/agent/agent-linux-amd64
```

Copy the agent example configuration from MAAS and start the agent. Adapt the environment variable values to your setup. For example, if you're using a snap, the `MAAS_LOGS` variable would be as shown (`/var/snap/maas/common/log`):

```nohighlight
mkdir -p /var/lib/grafana-agent/positions \
         /var/lib/grafana-agent/wal
cp /snap/maas/current/usr/share/maas/grafana_agent/agent.yaml.example /opt/agent/agent.yml

systemd-run -u telemetry \
    -E HOSTNAME="$(hostname)" \
    -E AGENT_WAL_DIR="/var/lib/grafana-agent/wal" \
    -E AGENT_POS_DIR="/var/lib/grafana-agent/positions" \
    -E PROMETHEUS_REMOTE_WRITE_URL="http://${O11y_IP}:9090/api/v1/write" \
    -E LOKI_API_URL="http://${O11y_IP}:3100/loki/api/v1/push" \
    -E MAAS_LOGS="/var/snap/maas/common/log/" \
    -E MAAS_IS_REGION="true" \
    -E MAAS_IS_RACK="true" \
    -E MAAS_AZ="default" \
    /opt/agent/agent-linux-amd64 \
        -config.expand-env \
        -config.file=/opt/agent/agent.yml
```

On the other hand, if you're using packages, the `MAAS_LOGS` would be `/var/log/maas`, as shown below:

```nohighlight
    ...
    -E MAAS_LOGS="/var/log/maas" \
    ...
```

Be sure to adjust the values of the other environment variables to suit your situation, where applicable.

Next, enable log forwarding in MAAS.

```nohighlight
# set the TCP port the Grafana Agent is listening for syslog messages
# this port must match the one in /opt/agent/agent.yml
maas $ADMIN maas set-config name=promtail_port value=5238

# enable syslog forwarding
maas $ADMIN maas set-config name=promtail_enabled value=true
```

## Verify operation

Once your stack is set up, verifying its operation becomes crucial. You should be able to add both Loki and Prometheus as data sources in Grafana. This enables you to craft dashboards that bring MAAS metrics to life. Beyond that, you'll want to fine-tune Alertmanager to ensure that you're receiving timely and relevant alerts.

## Basic O11y (3.1--)

MAAS services can provide [Prometheus](https://prometheus.io/) endpoints for collecting performance metrics.

## Prometheus for MAAS

MAAS can provide five endpoints of particular interest to MAAS users:

1.  TFTP server file transfer latency
2.  HTTP requests latency
3.  Websocket requests latency
4.  RPC calls (between MAAS services) latency
5.  Per request DB queries counts

All available metrics are prefixed with `maas_`, to make it easier to look them up in Prometheus and Grafana UIs.

## Prometheus endpoints

Whenever you install the `python3-prometheus-client` library, Prometheus endpoints are exposed over HTTP by the `rackd` and `regiond` processes under the default `/metrics` path.

>Pro tip: Currently, prometheus metrics are shared when rack and region controllers are running on the same machine, even though each service provides its own port. You can safely only query one of the two ports if you're running both controllers.

For a Snap-based MAAS setup, you're in luck: the necessary libraries are bundled right in, making metrics immediately available. For those on a Debian-based MAAS installation, you'll need to install the library and give your MAAS services a quick restart. Here's how:

    sudo apt install python3-prometheus-client
    sudo systemctl restart maas-rackd
    sudo systemctl restart maas-regiond

MAAS also provides optional stats about resources registered with the MAAS server itself. These include four broad categories of information:

1.  The number of nodes by type, arch, ...
2.  Number of networks, spaces, fabrics, VLANs and subnets
3.  Total counts for machines CPU cores, memory and storage
4.  Counters for VM host resources

After installing the `python3-prometheus-client` library as describe above, run the following to enable stats:

    maas $PROFILE maas set-config name=prometheus_enabled value=true

## Configure Prometheus

Once the `/metrics` endpoint is available in MAAS services, Prometheus can be configured to scrape metric values from these. You can configure this by adding a stanza like the following to the [prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/):

```yaml
    - job_name: maas
      static_configs:
        - targets:
          - <maas-host1-IP>:5239  # for regiond
          - <maas-host1-IP>:5249  # for rackd
          - <maas-host2-IP>:5239  # regiond-only
          - <maas-host3-IP>:5249  # rackd-only
```

If the MAAS installation includes multiple nodes, the `targets` entries must be adjusted accordingly, to match services deployed on each node.

If  you have enabled MAAS stats,  you must add an additional Prometheus job to the config:

```yaml
    - job_name: maas
      metrics_path: /MAAS/metrics
      static_configs:
        - targets:
          - <maas-host-IP>:5240
```

In case of a multi-host deploy, adding a single IP for any of the MAAS hosts running `regiond` will suffice.

## Deploy Prometheus

[Grafana](https://grafana.com/) and Prometheus can be easily deployed using Juju.

The [MAAS performance repo](https://git.launchpad.net/~maas-committers/maas/+git/maas-performance) repository provides a sample `deploy-stack` script that will deploy and configure the stack on LXD containers.

First, you must install juju via:

    sudo snap install --classic juju

Then you can run the script from the repo:

    grafana/deploy-stack <MAAS-IP>

To follow the progress of the deployment, run the following:

    watch -c juju status --color

Once you deploy everything, the Grafana UI is accessible on port `3000` with the credentials `admin`/`grafana`. The Prometheus UI will be available on port `9090`.

The repository also provides some sample dashboard covering the most common use cases for graphs. These are available under `grafana/dashboards`. You can import them from the Grafana UI or API.

