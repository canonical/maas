MAAS environments often manage dozens or hundreds of machines. As more devices request provisioning, testing, or updates, system responsiveness depends on the ability to spread load across multiple controllers. High availability (HA) avoids slowdowns by distributing traffic and provides failover paths when hardware, software, or network faults occur.  HA ensures that MAAS continues to function even when individual components fail. Without it, a single downed region or rack controller can halt machine provisioning, block network boot workflows, or disconnect users from the API or UI.

This guide walks through setting up MAAS for high availability across four critical areas: the MAAS database (PostgreSQL), the API services, the DHCP server, and the Region + Rack controller topology. It's written to help you avoid fragile setups and get to a working state faster, even in complex deployments.

## Avoid single points of failure

If you're responsible for keeping bare-metal provisioning reliable under load, you'll eventually need high availability (HA). MAAS doesn't do it all for you — but with some planning, you can set up a resilient MAAS architecture that protects against common failure points:

* A single rack controller can get overloaded very quickly as provisioning scales.
* PostgreSQL is a single source of truth — if it fails, MAAS fails.
* Deploying multiple region controllers allows MAAS to handle a greater volume of concurrent API and UI traffic.
* API servers handle most user interaction; if these are overloaded or crash, provisioning halts.
* DHCP is critical to initial PXE booting. Misconfigurations or outages here can strand machines.

Each of these are addressed below.

## Scale rack controllers

Rack controllers coordinate PXE booting and local machine access. These are designed to be stateless and easy to duplicate, with built-in HA capability. You can run as many rack controllers as needed, and each will connect to one or more region controllers.

Install multiple rack controllers to automatically enable HA:

```shell
sudo snap install maas
sudo maas init rack --maas-url $MAAS_URL --secret $SECRET
```

For package installs:

```shell
sudo apt install maas-rack-controller
sudo maas-rack register --url $MAAS_URL --secret $SECRET
```

The $SECRET is stored at:
- `/var/snap/maas/common/maas/secret` (Snap)
- `/var/lib/maas/secret` (Package)

The UI also provides install instructions under *Controllers* > *Add rack controller*.

Assign each rack controller a unique name and make sure DNS allows MAAS-managed machines to resolve them. Note that adding a second rack controller also enables automatic BMC load balancing.

## Enable highly-available PostgreSQL

MAAS uses PostgreSQL as its backend, so database availability is your top priority. All region controllers must connect to the same PostgreSQL database.

There are many ways to create an HA PostgreSQL configuration.  We recommend you check the [official PostgreSQL documentation](https://www.postgresql.org/docs/16/high-availability.html) for detailed and up-to-date instructions.  Whatever method you choose, ensure that you:

1. Install and configure HA PostgreSQL with:
   * Automatic failover
   * Synchronous replication (optional but helpful)
   * A virtual IP or service alias
2. Configure MAAS to connect to the VIP, not the actual PostgreSQL node.
3. Test failover to ensure MAAS reconnects cleanly.

## Add region controllers

<<<<<<< HEAD
UI**
*Controllers* > Select a rack controller > *Delete*

CLI**
```bash
maas $PROFILE rack-controller delete $SYSTEM_ID
```
=======
Region controllers can be load-balanced and failover-safe. Each region controller provides the API and connects to the same PostgreSQL backend. As long as your database is highly available, you can run multiple region controllers in parallel:

* Use HAProxy or another load balancer to expose a single virtual IP or DNS name to users.
* Route traffic round-robin or with health checks to two or more region controllers.
* All region controllers must point to the same PostgreSQL HA backend.

This protects you from:
>>>>>>> 4e2e21fd1 (fix(docs): improve HA and controller how-to and explanation documents)

* API server crashes
* OS-level instability
* Planned maintenance windows

To add a region controller:

   ```shell
   sudo apt install maas-region-api
   sudo scp ubuntu@$PRIMARY_API:/etc/maas/regiond.conf /etc/maas/
   sudo maas-region local_config_set --database-host $PRIMARY_PG_SERVER
   sudo systemctl start maas-regiond
   ```
   
MAAS discovers and connects to available region controllers. You can manually define multiple endpoints in:

- `/var/snap/maas/current/rackd.conf` (Snap)
- `/etc/maas/rackd.conf` (Package)

```yaml
maas_url:
  - http://<ip1>:<port>/MAAS/
  - http://<ip2>:<port>/MAAS/
```

You can also boost region performance by adding worker threads, that is, increasing `num_workers` in `/etc/maas/regiond.conf` for better performance:


```yaml
num_workers: 8
```

Note that each worker requires 11 additional PostgreSQL connections, so you'll also need to do some PostgreSQL configuration.  We recommended one worker per CPU, up to 8 total.

## Configure a highly-available API

Install and configure HAProxy to enable a highly-available MAAS API:

```shell
sudo apt install haproxy
```

Configure `/etc/haproxy/haproxy.cfg`:

```yaml
frontend maas
    bind    *:80
    default_backend maas

backend maas
    balance source
    server localhost localhost:5240 check
    server maas-api-1 $PRIMARY_API_SERVER_IP:5240 check
    server maas-api-2 $SECONDARY_API_SERVER_IP:5240 check
```

Restart HAProxy:

```shell
sudo systemctl restart haproxy
```

Use port 80 instead of 5240 for API/UI access.

## Configure highly-available DHCP

DHCP is easy to get wrong — but with the right approach, you can run multiple DHCP servers safely.

MAAS supports enabling DHCP on more than one rack controller, but does not handle DHCP failover automatically. You must:

* Enable DHCP on two rack controllers per subnet.
* Configure each to serve non-overlapping IP ranges.
* Ensure both are healthy via monitoring or automation.

MAAS will not stop a failed DHCP server automatically — so ensure you have alerts or fencing in place.  Here's an example setup:

```yaml
failover peer "failover-partner" {
     primary;
     address dhcp-primary.example.com;
     peer address dhcp-secondary.example.com;
     split 255;
}
failover peer "failover-partner" {
     secondary;
     address dhcp-secondary.example.com;
     peer address dhcp-primary.example.com;
}
```

To enable DHCP after adding a rack controller:

<<<<<<< HEAD
UI**
- *Subnets* > *VLAN* > *Reconfigure DHCP*

CLI**
```bash
vid=$(maas $PROFILE subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24") | .vlan.vid')
fabric_id=$(maas $PROFILE fabrics read | jq -r '.[] | select(.name == "fabric-1") | .id')
maas $PROFILE vlan update $fabric_id $vid primary_rack=$(hostname) dhcp_on=true
=======
UI
*Subnets* > VLAN > *Reconfigure DHCP*

CLI
```shell
<<<<<<< HEAD
vid=$(maas maas subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24") | .vlan.vid')
fabric_id=$(maas maas fabrics read | jq -r '.[] | select(.name == "fabric-1") | .id')
maas maas vlan update $fabric_id $vid primary_rack=$(hostname) dhcp_on=true
>>>>>>> 4e2e21fd1 (fix(docs): improve HA and controller how-to and explanation documents)
=======
VLAN_ID=$(maas maas subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24") | .vlan.vid')
FABRIC_ID=$(maas maas fabrics read | jq -r '.[] | select(.name == "fabric-1") | .id')
maas $PROFILE vlan update $FABRIC_ID $VLAN_ID \ primary_rack_controller=$RACK1_SYSTEM_ID \ secondary_rack_controller=$RACK2_SYSTEM_ID
>>>>>>> ab58b950a (fix(docs): respond to reviewer comments on documents)
```

Note that both rack controllers must be on the same VLAN.

## Monitoring MAAS HA behavior

MAAS uses Prometheus and Loki to monitor performance. You can configure Prometheus to alert you when critical MAAS HA components degrade or fail. Below are sample alerting rules using metrics exposed by MAAS via Prometheus endpoints. These alerts assume you’ve already scraped metrics using jobs targeting regiond, rackd, and /MAAS/metrics.

### Region controller unavailable

```bash
groups:
- name: maas-ha.rules
  rules:
  - alert: RegionControllerDown
    expr: up{job="maas", instance=~".*:5239"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Region controller is down"
      description: "No response from regiond at {{ $labels.instance }} for 2 minutes."
```

### Rack controller unavailable

```bash
- alert: RackControllerDown
    expr: up{job="maas", instance=~".*:5249"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Rack controller is down"
      description: "No response from rackd at {{ $labels.instance }} for 2 minutes."
```

### PostgreSQL saturated (connection pool exhausted)

```bash
- alert: PostgreSQLConnectionsExhausted
    expr: maas_rpc_pool_exhaustion_count > 0
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "PostgreSQL connection pool exhausted"
      description: "Region controller reports exhausted RPC pool connections."
```

### Slow DNS updates

```bash
- alert: SlowDNSUpdates
    expr: histogram_quantile(0.95, rate(maas_dns_update_latency_bucket[5m])) > 5
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "DNS updates taking too long"
      description: "Dynamic or full-zone DNS updates exceed 5s at the 95th percentile."
```

### How to load these rules

To enable these alerts:

1. Clone Canonical’s Prometheus alert rules repo:

```bash
git clone https://github.com/canonical/maas-prometheus-alert-rules.git
cd maas-prometheus-alert-rules
make groups
```

2. Copy your alert group(s) to Prometheus:

```bash
cp group.yml /var/lib/prometheus/rules/maas/
```
3. Ensure your prometheus.yml is loading them:

```bash
rule_files:
  - /var/lib/prometheus/rules/maas/*.yml
```

4. Restart Prometheus:

```bash
systemctl restart prometheus
```

You can also use Loki for alerting.

## Supporting documents

Here are a few supporting documents that may be helpful:

- [About controllers](https://maas.io/docs/about-controllers) gives a deeper explanation of how controllers work: separately, together, and in HA configurations.
- The [official PostgreSQL documentation](https://www.postgresql.org/docs/16/high-availability.html) explains the available options to run PostgreSQL in a highly-available mode.
- [How to monitor MAAS](https://maas.io/docs/how-to-monitor-maas) explains how to use Prometheus and Loki to set up monitoring and alerts.
- The [MAAS metrics reference](https://maas.io/docs/reference-maas-metrics) lists various parameters you may find useful in monitoring HA configurations.
