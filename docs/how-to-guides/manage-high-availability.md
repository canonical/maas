# Manage high-availability

Region and rack controllers are the backbone of MAAS. By deploying multiple controllers, you automatically gain load-balancing and failover. This ensures that machine provisioning and API access continue even if one controller goes offline.

This page explains how to enable and manage HA for both rack and region controllers, as well as supporting services like PostgreSQL, DHCP, and the MAAS API.

## Enable HA for rack controllers

Adding a second rack controller automatically enables HA.

```shell
sudo snap install maas
sudo maas init rack --maas-url $MAAS_URL --secret $SECRET
```

The `$SECRET` is stored at `/var/snap/maas/common/maas/secret`.

You can also follow the UI path: *Controllers* > *Add rack controller*.

## Manage rack controllers

Rack controllers manage networks and connected machines.

### List racks

```shell
maas $PROFILE rack-controllers read | grep hostname | cut -d '"' -f 4
```

Multiple racks are required for HA.

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
   sudo maas init rack --maas-url $NEW_MAAS_URL --secret $NEW_SECRET
   ```

### Common pitfalls

- Don’t move rack controllers between MAAS versions.
- Don’t connect a rack controller to multiple MAAS instances.

## Manage region controllers

Region controllers coordinate racks and present the API/UI.

To add a region controller, follow the [installation guide](/how-to-guides/get-started/install-maas.md) on a secondary host. Then configure it to use the primary PostgreSQL database.

### Enable HA PostgreSQL

All region controllers share the same PostgreSQL DB.

1. Allow the secondary API server:

   ```shell
   echo "host maasdb maas $SECONDARY_API_IP/32 md5" | sudo tee -a /etc/postgresql/9.5/main/pg_hba.conf
   sudo systemctl restart postgresql
   ```

2. Configure the secondary region controller to point to the primary PostgreSQL database by modifying its configuration.

### Boost region performance

Increase workers in `/var/snap/maas/current/regiond.conf`:

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

Define endpoints manually in `/var/snap/maas/current/rackd.conf`:

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

### Boot resource uploads behind a load balancer

The MAAS CLI uploads custom images (`maas <profile> boot-resources create ... content@=<file>`) as a series of 4 MiB chunks, each sent as a separate `PUT` request to the same upload URL:

```text
/MAAS/api/2.0/boot-resources/<resource-id>/upload/<file-id>/
```

Each region controller tracks the upload offset locally. All chunks of one file must therefore reach the same region controller. If a load balancer spreads the chunks across regions, no region receives the complete file. Every region keeps a partial `<filename>.incomplete` file in its image storage, the image never finishes syncing, and the CLI still exits with status 0.

Configure the load balancer to route all requests for a given upload URL to the same region controller. Because the URL is identical for every chunk of a file, hashing on the URI is enough.

With HAProxy, send upload requests to a dedicated backend that balances on the URI. Edit `/etc/haproxy/haproxy.cfg` on the load balancer host. This replaces the `frontend maas` and `backend maas` sections from [Highly-available API with HAProxy](#highly-available-api-with-haproxy) and adds a `backend maas_uploads` section:

```text
frontend maas
    bind    *:80
    acl is_boot_resource_upload path_reg ^/MAAS/api/2\.0/boot-resources/[^/]+/upload/[^/]+/?$
    use_backend maas_uploads if is_boot_resource_upload
    default_backend maas

backend maas
    balance source
    server maas-api-1 $PRIMARY_API_SERVER_IP:5240 check
    server maas-api-2 $SECONDARY_API_SERVER_IP:5240 check

backend maas_uploads
    balance uri whole
    hash-type consistent
    server maas-api-1 $PRIMARY_API_SERVER_IP:5240 check
    server maas-api-2 $SECONDARY_API_SERVER_IP:5240 check
```

The example uses two regions. Add one `server` line to both backends for each additional region controller. `hash-type consistent` limits how many upload URLs move to a different region when you add or remove one.

The `balance source` setting in the default backend, shown in [Highly-available API with HAProxy](#highly-available-api-with-haproxy), also keeps uploads on one region as long as the client IP address doesn't change. Other load balancers need an equivalent rule: hash on the request path, or on the client IP address.

If a server in the pool goes down during an upload, the remaining chunks are routed to a different region and the upload is corrupted. Restart the upload after the region recovers.

To verify an upload after it finishes, read the resource and check that its file reports `"complete": true`:

```shell
maas $PROFILE boot-resource read $RESOURCE_ID
```

The CLI exits with status 0 even when an upload was split across regions. In that case the file reports `"complete": false` and a `progress` value below 100.

To recover, first note the `filename_on_disk` value from `boot-resource read`, because you can't read it after the resource is deleted. Then delete the resource and wait for the deletion to finish. Next, on every region controller, remove the leftover files for that image from the image storage directory and upload again. The leftover file is named by that `filename_on_disk` value (or ends in `.incomplete`, depending on the MAAS version). The image storage directory is:

- Snap: `/var/snap/maas/common/maas/image-storage/`
- Debian package: `/var/lib/maas/image-storage/`

For example, for a file with `filename_on_disk` set to `99aec68`:

```shell
sudo rm -f /var/snap/maas/common/maas/image-storage/99aec68*
```

If partial files remain, the new upload appends to them and fails with a 400 error or a SHA256 mismatch. Alternatively, upload directly to a single region controller, bypassing the load balancer.

## Safety nets

- Always back up PostgreSQL before modifying configs.
- Never mix controller versions between instances.
- Plan database connection limits when scaling workers or regions.

## Next steps

- [About controllers](/explanation/controllers.md)
