> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/ensuring-high-availability-for-controllers" target = "_blank">Let us know.</a>*

Region and rack controllers balance the load and execute failover, automatically, as part of normal operations. This article will help you understand how to take advantage of these built-in features.

## Enter HA mode

To enable high availability, just [install multiple rack controllers](/t/how-to-configure-controllers/5172); the rest is automatic. MAAS will immediately begin to load balance:

- racks to regions.
- rack controller connection count.
- region worker processes.

Every rack-to-region connection initiates a re-balancing loop.  Re-balancing is also done at various other opportune times. For example, if a network change happens (like toggling DHCP or changing a VLAN), MAAS will also redistribute load. 

## HA BMC

You can also enable HA for BMC control (node power cycling) just by adding a second rack controller. MAAS will automatically identify which rack controller is responsible for a BMC, continuously balancing the connections.

## HA DHCP

You can enable highly-available DHCP services by using MAAS-managed DHCP, and adding rack controllers. This DHCP HA affects the way MAAS manages nodes, including enlistment, commissioning and deployment. It enables primary and secondary DHCP instances to serve the same VLAN. This VLAN replicates all lease information is between rack controllers, so there's a bit of performance boost for large networks.

MAAS DHCP automatically creates failover peers, using mostly standard parameters:

```nohighlight
failover peer "failover-partner" {
     primary;
     address dhcp-primary.example.com;
     peer address dhcp-secondary.example.com;
     max-response-delay 60;
     max-unacked-updates 10;
     mclt 3600;
     split 255;
     load balance max seconds 3;
}
failover peer "failover-partner" {
     secondary;
     address dhcp-secondary.example.com;
     peer address dhcp-primary.example.com;
     max-response-delay 60;
     max-unacked-updates 10;
     load balance max seconds 3;
}
```
Note that the only difference from a standard 50/50 split (`split 128`) is that the primary DHCP server answers any requests that it can (`split 255`), within the maximum response delay of 60 seconds and an unacknowledged update count of 10. In this sense, highly-available MAAS DHCP fails over only when absolutely necessary.

If you are enabling DHCP for the first time after adding a second rack controller, please read [Enabling DHCP](/t/how-to-enable-dhcp/5132). On the other hand, if you have already enabled DHCP on your initial rack controller, you'll need to reconfigure DHCP to get optimum results.

## Update DHCP (UI)

To reconfigure DHCP after adding a new rack controller, select *Subnets* > VLAN > *Reconfigure DHCP*. Confirm that you can see the second rack controller under *Secondary controller* and select *Reconfigure DHCP*.

## Update DHCP (CLI)

To reconfigure DHCP after adding a new rack controller, use the following sequence of commands:

```nohighlight
vid=$(maas maas subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24") | .vlan.vid')
fabric_name=$(maas maas subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24") | .vlan.fabric')
query=".[] | select(.name == \"$fabric_name\") | .id"
fabric_id=$(maas maas fabrics read | jq "$query")
maas maas ipranges create type=reserved start_ip=10.0.0.3 end_ip=10.0.0.49
maas maas ipranges create type=dynamic start_ip=10.0.0.50 end_ip=10.0.0.99
maas maas vlan update ${fabric_id} ${vid} primary_rack=$(hostname) dhcp_on=true
```

Be sure to substitute the sample values for those of your own environment.

## Multiple endpoints

MAAS will automatically discover and track all reachable region controllers in a single cluster of rack controllers  It will also attempt to automatically connect to them if the one in use becomes inaccessible. Administrators can alternatively specify multiple region-controller endpoints for a single rack controller by adding entries to `/var/snap/maas/current/rackd.conf` (if using Snaps) or `/etc/maas/rackd.conf` (if using packages). For example:

```nohighlight
    .
    .
    .
    maas_url:
      - http://<ip 1>:<port>/MAAS/
      - http://<ip 2>:<port>/MAAS/
    .
    .
    .
```

The setup of highly-available DHCP is now complete. Note that, for HA purposes, DHCP provisioning will take into account multiple DNS services when there is more than one region controller on a single region.

## HA regions

Implementing highly-available region control is relatively simple. Load balancing is optional, but is highly recommended.

## HA PostgreSQL

MAAS stores all state information in the PostgreSQL database. It is therefore recommended to run it in HA mode. Configuring HA for PostgreSQL is external to MAAS. You will, therefore, need to study the [PostgreSQL documentation](https://www.postgresql.org/docs/9.5/static/high-availability.html)`↗` and implement the variant of HA that makes you feel most comfortable.

Each region controller uses up to 40 connections to PostgreSQL in high load situations. Running two region controllers requires no modifications to the `max_connections` in `postgresql.conf`. More than two region controllers require that `max_connections` be adjusted to add 40 more connections per added region controller.

## HA API services

Setting up high-availability using snaps is relatively easy:

1. Set up PostgreSQL for high-availability as explained above. PostgreSQL should run outside of the snap.
2. [Install](/t/how-to-install-maas/5128) the MAAS snap on each machine you intend to use as a rack or region controller. You'll need the MAAS shared secret, located here, `/var/snap/maas/common/maas/secret`, on the first region controller you set up.
3. [Initialise the snap](/t/how-to-install-maas/5128) as a `rack` or `region` controller.

Note that if you intend to use a machine as a region controller, you'll need to tell MAAS how to access your PostgreSQL database host with the following arguments:

- `--database-host DATABASE_HOST`
- `--database-name DATABASE_NAME`
- `--database-user DATABASE_USER`
- `--database-pass DATABASE_PASS`

Please see [Region controllers](/t/how-to-configure-controllers/5172) for more information about how to install and configure rack controllers for multiple region controllers, when using packages.

## Load balancing the API

You can add load balancing with [HAProxy](http://www.haproxy.org/)`↗` load-balancing software to support multiple API servers. In this setup, HAProxy provides access to the MAAS web UI and API.

>**Pro tip**: If you happen to have Apache running on the same server where you intend to install HAProxy, you will need to stop and disable `apache2`, because HAProxy binds to port 80.

## Install HAProxy

```nohighlight
sudo apt install haproxy
```

## Set up HAProxy

Configure each API server's load balancer by copying the following into `/etc/haproxy/haproxy.cfg` (see the [upstream configuration manual (external link)](http://cbonte.github.io/haproxy-dconv/1.6/configuration.html)`↗` as a reference). Replace $PRIMARY_API_SERVER_IP and $SECONDARY_API_SERVER_IP with their respective IP addresses:

```nohighlight
frontend maas
    bind    *:80
    retries 3
    option  redispatch
    option  http-server-close
    default_backend maas

backend maas
    timeout server 90s
    balance source
    hash-type consistent
    server localhost localhost:5240 check
    server maas-api-1 $PRIMARY_API_SERVER_IP:5240 check
    server maas-api-2 $SECONDARY_API_SERVER_IP:5240 check
```
 
where `maas-api-1` and `maas-api-2` are arbitrary server labels.

Now restart the load balancer to have these changes take effect:

```nohighlight
sudo systemctl restart haproxy
```

The configuration of region controller HA is now complete.

**The API server(s) must be now be referenced (e.g. web UI, MAAS CLI) using port 80 (as opposed to port 5240).**

## Moving racks

In effect, there is no such action as moving a rack controller, although you can delete a rack controller from one MAAS and reinstantiate the same controller (binary-wise) on another MAAS instance. First, delete the rack controller. In the UI, find *Controllers*, select the rack controller you with to delete, choose *Take action* and select *Delete*. You will be asked to confirm.

If you're using the CLI, follow this procedure:

```nohighlight
maas $PROFILE rack-controller delete $SYSTEM_ID
```

where `$PROFILE` is your admin profile name, and `$SYSTEM_ID` can be found by examining the output of the command:

```nohighlight
maas $PROFILE rack-controllers read
```

There is no confirmation step, so make sure you have the right rack controller before proceeding.

Next, you must register a new rack controller, which is always done from the command line:

```nohighlight
sudo maas-rack register --url $MAAS_URL_OF_NEW_MAAS --secret $SECRET_FOR_NEW_MAAS
```

where the secret is found in `/var/lib/maas/secret` (if using Debian packages) or `/var/snap/maas/common/maas/secret` (if using Snaps).

## Avoiding move issues

There are dangers associate with moving a rack controller -- dangers that may generate errors, get you into a non-working state, or cause you significant data loss. These dangers are precipitated by one caveat and two potential mistakes:

- **Using the same system as a rack controller and a VM host:** While not forbidden or inherently dangerous, using the same machine as both a rack controller and a VM host may cause resource contention and poor performance. If the resources on the system are not more than adequate to cover both tasks, you may see slowdowns (or even apparent "freeze" events) on the system.

- **Moving a rack controller from one version of MAAS to another:** MAAS rack controller software is an integral part of each version of MAAS. If you delete a rack controller from, say, a 2.6 version of MAAS, and attempt to register that 2.6 version of the rack controller code to, say, a 2.9 version of MAAS, you may experience errors and potential data loss. Using the above example, if you are running both a VM host and a rack controller for MAAS 2.6 on one system, and you suddenly decide to delete that rack controller from 2.6 and attempt to register the same code to a 2.9 MAAS, the VM host may fail or disappear. This will possibly delete all the VMs you have created or connected to that VM host -- which may result in data loss. This action is not supported.

- **Connecting one instance of a rack controller to two instances of MAAS, regardless of version:** Trying to connect a single rack controller to two different instances of MAAS can result in all sorts of unpredictable (and potentially catastrophic) behaviour. It is not a supported configuration.

Take these warnings to heart. It may seem like a faster approach to "bridge" your existing rack controllers from one MAAS to another -- or from one version of MAAS to another -- while they're running. Ultimately, though, it will probably result in more work than just following the recommended approach.