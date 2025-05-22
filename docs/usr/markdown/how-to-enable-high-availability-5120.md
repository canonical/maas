Region and rack controllers do the heavy lifting for MAAS, and automatically enable load-balancing and failover.

## Enable HA  

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

The **$SECRET** is stored at:  
- `/var/snap/maas/common/maas/secret` (Snap)  
- `/var/lib/maas/secret` (Package)  

The UI also provides install instructions under *Controllers* > *Add rack controller*.  

## Manage rack controllers

Rack controllers manage machines and their connected networks.

### List racks  

```shell
maas $PROFILE rack-controllers read | grep hostname | cut -d '"' -f 4
```

Multiple racks are required for HA. Ensure VM hosts can communicate with new rack controllers.  

### Delete a rack controller  

UI:  
*Controllers* > Select Controller > *Delete*  

CLI:  

```shell
maas $PROFILE rack-controller delete $SYSTEM_ID
```

Deleting a DHCP HA rack controller requires disabling DHCP HA first. If software is not removed, a reboot reinstates the rack controller.  

### Move a rack controller  

Moving a rack controller between MAAS instances or versions is unsupported and may cause data loss. Instead:  

1. **Delete** the rack controller:  

   ```shell
   maas $PROFILE rack-controller delete $SYSTEM_ID
   ```

2. **Register a new one:**  

   ```shell
   sudo maas-rack register --url $NEW_MAAS_URL --secret $NEW_SECRET
   ```

### Avoid rack controller mistakes

Avoid these mistakes:  

- **Rack + VM Host:** Resource contention may degrade performance.  
- **Version Mismatch:** A rack controller cannot be moved between MAAS versions.  
- **Multiple MAAS Connections:** One rack controller cannot serve multiple MAAS instances.  

## Manage region controllers  

Region controllers manage one or more racks (a data center), and interface with users.

### Add a region controller

On a secondary host, add the new region controller by installing maas-region-api:

```nohighlight
sudo apt install maas-region-api
```

You will need the ```/etc/maas/regiond.conf``` file from the primary API server. Below, we assume it can be copied (scp) from the ‘ubuntu’ account home directory using password authentication (adjust otherwise). The ```local_config_set``` command will edit that file by pointing to the host that contains the primary PostgreSQL database. Do not worry: MAAS will rationalize the DNS (```bind9```) configuration options so that they match those used within MAAS:

```nohighlight
sudo systemctl stop maas-regiond
sudo scp ubuntu@$PRIMARY_API_SERVER:regiond.conf /etc/maas/regiond.conf
sudo chown root:maas /etc/maas/regiond.conf
sudo chmod 640 /etc/maas/regiond.conf
sudo maas-region local_config_set --database-host $PRIMARY_PG_SERVER
sudo systemctl restart bind9
sudo systemctl start maas-regiond
```
Check log files for any errors.

### Enable highly-available PostgreSQL  

All region controllers must connect to the same PostgreSQL database.  

1. **Allow secondary API server:**  

   ```shell
   echo "host maasdb maas $SECONDARY_API_IP/32 md5" | sudo tee -a /etc/postgresql/9.5/main/pg_hba.conf
   sudo systemctl restart postgresql
   ```

2. **Add a region controller:**  

   ```shell
   sudo apt install maas-region-api
   ```

3. **Configure it:**  

   ```shell
   sudo scp ubuntu@$PRIMARY_API:/etc/maas/regiond.conf /etc/maas/
   sudo maas-region local_config_set --database-host $PRIMARY_PG_SERVER
   sudo systemctl restart bind9
   sudo systemctl start maas-regiond
   ```

### Boost region performance  

Increase `num_workers` in `/etc/maas/regiond.conf` for better performance:  

```yaml
num_workers: 8
```

Each worker requires **11 additional PostgreSQL connections**. Recommended: 1 worker per CPU, up to 8 total.  

### Enable BMC load-balancing

Adding a second rack controller enables automatic BMC load balancing.  

### Configure highly-available DHCP

Rack controllers replicate DHCP leases, improving failover. DHCP HA setup:  

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

Enable DHCP after adding a rack controller:  

**UI**  
*Subnets* > VLAN > *Reconfigure DHCP*  

**CLI**  
```shell
vid=$(maas maas subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24") | .vlan.vid')
fabric_id=$(maas maas fabrics read | jq -r '.[] | select(.name == "fabric-1") | .id')
maas maas vlan update $fabric_id $vid primary_rack=$(hostname) dhcp_on=true
```

### Define multiple region endpoints  

MAAS discovers and connects to available region controllers. You can manually define multiple endpoints in:  

- `/var/snap/maas/current/rackd.conf` (Snap)  
- `/etc/maas/rackd.conf` (Package)  

```yaml
maas_url:
  - http://<ip1>:<port>/MAAS/
  - http://<ip2>:<port>/MAAS/
```

### Enable highly-available region controllers  

Load balancing region controllers is recommended.  MAAS requires **PostgreSQL HA** for true region HA. Follow the [PostgreSQL HA guide](https://www.postgresql.org/docs/9.5/static/high-availability.html).  

Each region controller requires 40 database connections under high load. Increase `max_connections` accordingly.  

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

Use **port 80** instead of **5240** for API/UI access.

