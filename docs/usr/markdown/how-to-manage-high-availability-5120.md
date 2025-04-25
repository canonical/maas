Region and rack controllers do the heavy lifting in MAAS. To ensure resilience, MAAS supports high availability (HA) via load balancing and failover — both for API access and provisioning infrastructure.

This guide walks through enabling and managing HA in MAAS using multiple controllers, shared databases, and optional HAProxy support.

## Enable rack controller HA

Rack controllers manage machine communication and network services. To enable HA:

### Add additional rack controllers

MAAS automatically enables rack controller HA when multiple rack controllers are registered to the same region.

#### Snap-based install:

```bash
sudo snap install maas
sudo maas init rack --maas-url $MAAS_URL --secret $SECRET
```

#### Package-based install:

```bash
sudo apt install maas-rack-controller
sudo maas-rack register --url $MAAS_URL --secret $SECRET
```

- The `$SECRET` is stored at:
  - `/var/snap/maas/common/maas/secret` (Snap)
  - `/var/lib/maas/secret` (Package)

You can also find install instructions in the MAAS UI under *Controllers > Add rack controller*. 

## Manage rack controllers

### List registered rack controllers

```bash
maas $PROFILE rack-controllers read | grep hostname | cut -d '"' -f 4
```

Make sure all VM hosts can reach the new rack controllers, by pinging their IPs from relevant nodes.

### Remove a rack controller

**UI**
*Controllers* > Select a rack controller > *Delete*

**CLI**
```bash
maas $PROFILE rack-controller delete $SYSTEM_ID
```

If DHCP HA is enabled, you must disable it first. If the MAAS software is still installed, the controller may re-register on reboot.

### Don’t move rack controllers between instances

Rack controllers can’t be transferred across MAAS versions or instances — doing so risks data loss. Instead:

1. Delete the old one:
   ```bash
   maas $PROFILE rack-controller delete $SYSTEM_ID
   ```

2. Register a new one:
   ```bash
   sudo maas-rack register --url $NEW_MAAS_URL --secret $NEW_SECRET
   ```

### Common rack HA pitfalls

Avoid these mistakes:

- Running rack + VM host on the same machine: Can cause resource contention
- Version mismatches: Rack controllers must match MAAS version
- Connecting one rack to multiple MAAS instances: Not supported

## Enable region controller HA

Region controllers handle the API, UI, and database logic. You can add more region controllers for redundancy and performance — but all must point to the same PostgreSQL backend.

### Add a region controller

On the new host:

```bash
sudo apt install maas-region-api
```

Then copy the `regiond.conf` from the primary region controller:

```bash
sudo systemctl stop maas-regiond
scp ubuntu@$PRIMARY_API:/etc/maas/regiond.conf /etc/maas/regiond.conf
sudo chown root:maas /etc/maas/regiond.conf
sudo chmod 640 /etc/maas/regiond.conf
sudo maas-region local_config_set --database-host $PRIMARY_PG_SERVER
sudo systemctl restart bind9
sudo systemctl start maas-regiond
```

Check the logs for errors before proceeding.

### Boost performance with more workers

Edit `/etc/maas/regiond.conf`:

```yaml
num_workers: 8
```

- Recommend 1 worker per CPU (up to 8)
- Each worker needs ~11 PostgreSQL connections

### Connect all region controllers to PostgreSQL

Before connecting the new region controller:

```bash
echo "host maasdb maas $SECONDARY_API_IP/32 md5" | sudo tee -a /etc/postgresql/9.5/main/pg_hba.conf
sudo systemctl restart postgresql
```

## Define multiple region endpoints (optional)

Rack controllers automatically discover region controllers, but you can also define them manually:

- `/var/snap/maas/current/rackd.conf` (Snap)
- `/etc/maas/rackd.conf` (Package)

```yaml
maas_url:
  - http://10.0.0.1:5240/MAAS/
  - http://10.0.0.2:5240/MAAS/
```

## Enable highly available DHCP and BMC services

When you add a second rack controller:

- BMC load balancing is enabled automatically
- DHCP leases are replicated to improve failover

To configure DHCP HA:

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

### 🔄 Enable DHCP via UI or CLI

**UI**
- *Subnets* > *VLAN* > *Reconfigure DHCP*

**CLI**
```bash
vid=$(maas $PROFILE subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24") | .vlan.vid')
fabric_id=$(maas $PROFILE fabrics read | jq -r '.[] | select(.name == "fabric-1") | .id')
maas $PROFILE vlan update $fabric_id $vid primary_rack=$(hostname) dhcp_on=true
```

## Enable HA for the API with HAProxy (optional)

To load balance API and UI access across region controllers, install HAProxy:

```bash
sudo apt install haproxy
```

Edit `/etc/haproxy/haproxy.cfg`:

```haproxy
frontend maas
    bind *:80
    default_backend maas

backend maas
    balance source
    server localhost localhost:5240 check
    server maas-api-1 10.0.0.1:5240 check
    server maas-api-2 10.0.0.2:5240 check
```

Restart HAProxy:

```bash
sudo systemctl restart haproxy
```

MAAS will now serve the API and UI via port 80, and distribute requests across available region controllers.
