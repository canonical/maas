# Manage high-availability

Region and rack controllers are the backbone of MAAS. By deploying multiple controllers, you automatically gain load-balancing and failover. This ensures that machine provisioning and API access continue even if one controller goes offline.

This page explains how to enable and manage HA for both rack and region controllers, as well as supporting services like PostgreSQL, DHCP, and the MAAS API.

## Enable HA for rack controllers

Adding a second rack controller automatically enables HA.

### Snap install

```shell
sudo snap install maas
sudo maas init rack --maas-url $MAAS_URL --secret $SECRET
```

### Package install

```shell
sudo apt install maas-rack-controller
sudo maas-rack register --url $MAAS_URL --secret $SECRET
```

The `$SECRET` is stored at:

- Snap: `/var/snap/maas/common/maas/secret`
- Package: `/var/lib/maas/secret`

You can also follow the UI path: *Controllers* > *Add rack controller*.

## Manage rack controllers

Rack controllers manage networks and connected machines.

### List racks

```shell
maas $PROFILE rack-controllers read | grep hostname | cut -d '"' -f 4
```

Multiple racks are required for HA. Ensure VM hosts can reach each rack controller.

### Delete a rack controller

- UI: *Controllers* > select controller > *Delete*
- CLI:

  ```shell
  maas $PROFILE rack-controller delete $SYSTEM_ID
  ```

⚠️ If the controller participates in DHCP HA, disable DHCP HA first. If you don’t remove the software, a reboot will reinstate it.

### Move a rack controller

Moving between MAAS instances or versions is not supported and risks data loss. Instead:

1. Delete the old controller.

   ```shell
   maas $PROFILE rack-controller delete $SYSTEM_ID
   ```

2. Register a new one.

   ```shell
   sudo maas-rack register --url $NEW_MAAS_URL --secret $NEW_SECRET
   ```

### Common pitfalls

- Don’t run a rack and VM host on the same machine (resource contention).
- Don’t move rack controllers between MAAS versions.
- Don’t connect a rack controller to multiple MAAS instances.

## Manage region controllers

Region controllers coordinate racks and present the API/UI.

### Add a region controller

On a secondary host:

```text
sudo apt install maas-region-api
```

Copy `regiond.conf` from the primary API server, set ownership, and point it to the primary PostgreSQL database:

```text
sudo systemctl stop maas-regiond
sudo scp ubuntu@$PRIMARY_API_SERVER:regiond.conf /etc/maas/regiond.conf
sudo chown root:maas /etc/maas/regiond.conf
sudo chmod 640 /etc/maas/regiond.conf
sudo maas-region local_config_set --database-host $PRIMARY_PG_SERVER
sudo systemctl restart bind9
sudo systemctl start maas-regiond
```

Check logs for errors.

### Enable HA PostgreSQL

All region controllers share the same PostgreSQL DB.

1. Allow the secondary API server:

   ```shell
   echo "host maasdb maas $SECONDARY_API_IP/32 md5" | sudo tee -a /etc/postgresql/9.5/main/pg_hba.conf
   sudo systemctl restart postgresql
   ```

2. Add the region controller:

   ```shell
   sudo apt install maas-region-api
   ```

3. Configure it:

   ```shell
   sudo scp ubuntu@$PRIMARY_API:/etc/maas/regiond.conf /etc/maas/
   sudo maas-region local_config_set --database-host $PRIMARY_PG_SERVER
   sudo systemctl restart bind9
   sudo systemctl start maas-regiond
   ```

### Boost region performance

Increase workers in `/etc/maas/regiond.conf`:

```yaml
num_workers: 8
```

Each worker requires 11 PostgreSQL connections. Recommended: one per CPU, max 8.

## Load balancing and HA for services

### BMC load balancing

Adding a second rack controller automatically balances BMC duties.

### DHCP HA

Rack controllers replicate DHCP leases. Example configuration:

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

Enable via:

- UI: *Subnets* > VLAN > *Reconfigure DHCP*
- CLI:

  ```shell
  vid=$(maas maas subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24") | .vlan.vid')
  fabric_id=$(maas maas fabrics read | jq -r '.[] | select(.name == "fabric-1") | .id')
  maas maas vlan update $fabric_id $vid primary_rack=$(hostname) dhcp_on=true
  ```

### Multiple region endpoints

Define endpoints manually:

- Snap: `/var/snap/maas/current/rackd.conf`
- Package: `/etc/maas/rackd.conf`

```yaml
maas_url:
  - http://<ip1>:<port>/MAAS/
  - http://<ip2>:<port>/MAAS/
```

### Region controller HA

- Requires PostgreSQL HA.
- Each region controller may need 40 DB connections under load. Increase `max_connections` in PostgreSQL.

### Highly-available API with HAProxy

Install HAProxy:

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

## Safety nets

- Always back up PostgreSQL before modifying configs.
- Never mix controller versions between instances.
- Plan database connection limits when scaling workers or regions.

## Next steps

- [About controllers](explanation/controllers.md)
