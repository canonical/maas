Confirm that your system has adequate resources for your use-case, prior to installation. Proof-of-concept and production setups are available.

## LXD

LXD versions older than 5.21 will not work correctly with MAAS.

## PostgreSQL

From version 3.5, MAAS [requires PostgreSQL 14](https://discourse.maas.io/t/postgresql-deprecation-notices/8089) and a different PostgreSQL default user.

> **Warning**: PostgreSQL defaults may not support HA deployments.  Consider using 20-50 extra connections per additional region controller.  Check settings using `psql` or by inspecting the configuration file. 

### Getting information using psql

You can count PostgreSQL connections with this SQL query:

```nohighlight
SELECT 
  max_conn, 
  used
FROM 
  (SELECT count(*) used FROM pg_stat_activity) t1,
  (SELECT setting::int res_for_super FROM pg_settings WHERE name=$$superuser_reserved_connections$$) t2,
  (SELECT setting::int max_conn FROM pg_settings WHERE name=$$max_connections$$) t3;
```

`max_conn` is the number of available connections; `used` is the number of active connections.

### Getting information via configuration file

```nohighlight
grep 'max_connections' /var/lib/pgsql/{version_number}/data/postgresql.conf
```

### Increasing maximum connections

If `max_connections` is `100`, you need to increase that number. Refer to [these best practices](https://www.postgresql.org/docs/14/runtime-config-connection.html) for details.

### Symptoms of an issue

Too few database connections tend do produce errors:

```nohighlight
> FATAL: sorry, too many clients already
> FATAL:  remaining connection slots are reserved for non-replication superuser connections
> pq: remaining connection slots are reserved for non-replication superuser connections
```

## MAAS, NTP, and chrony

Conflicts can arise between Ubuntu's default `systemd-timesyncd` and MAAS `chrony`. Consult the MAAS [installation guide](https://maas.io/docs/how-to-install-maas) for solutions.

## Test environment

Requirements for a single-host test setup include the latest two Ubuntu LTS releases and the following component settings:

| Component | Memory (MB) | CPU (GHz) | Disk (GB) |
|:---|----:|----:|----:|
| [Region controller](https://maas.io/docs/cli-region-controller) | 512 | 0.5 | 5 |
| PostgreSQL | 512 | 0.5 | 5 |
| [Rack controller](https://maas.io/docs/cli-rack-controller) | 512 | 0.5 | 5 |
| Ubuntu Server | 512 | 0.5 | 5 |

Total: 2 GB RAM, 2 GHz CPU, 20 GB disk.

## Production environment

For large-scale, continuous client handling, plan as follows:

| Component | Memory (MB) | CPU (GHz) | Disk (GB) |
|:---|----:|----:|----:|
| [Region controller](https://maas.io/docs/cli-region-controller) | 2048 | 2.0 | 5 |
| PostgreSQL | 2048 | 2.0 | 20 |
| [Rack controller](https://maas.io/docs/cli-rack-controller) | 2048 | 2.0 | 20 |
| Ubuntu Server | 512 | 0.5 | 5 |

Plan for 4.5 GB RAM, 4.5 GHz CPU, and 45 GB disk per host for region controllers, and slightly less for rack controllers.

Additional notes:

- These specs are MAAS-specific and don't cover extra nodes.
- IPMI-based BMC controllers are recommended for power management.
  
Factors affecting these numbers:

- Client activity
- Service distribution
- Use of [high availability/load balancing](https://maas.io/docs/how-to-manage-controllers#p-9026-enable-ha).
- Number and type of stored images
- A local image mirror will increase disk requirements. 
- Rack controllers have a 1000-machine cap per subnet
