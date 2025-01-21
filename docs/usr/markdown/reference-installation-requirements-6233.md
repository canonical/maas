> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/installation-requirements" target = "_blank">Let us know.</a>*

Before installing MAAS, confirm that your system has adequate resources. These vary by use-case.  This page offers a guide based on using Ubuntu Server for test and production setups.

## LXD

If you plan to use LXD to create virtual machines with MAAS, you need to use LXD version 5.21 or higher.  Older versions will not work correctly with MAAS.

## PostgreSQL

From version 3.5, MAAS [requires PostgreSQL 14 or higher](/t/postgresql-deprecation-notices/8089), as well as a change in the allowed PostgreSQL default user.

> **Warning**: Default configuration of PostgreSQL may not be enough for MAAS 3.5 HA deployments, as MAAS now requires more connections towards your database.  For every Region Controller you need to consider at least an additional 20 connections. A safer move would be to have +50 for every Region Controller.  You can check your current settings using `psql` or by getting information from the configuration file.  Both methods are demonstrated below.

### Getting information using psql

You can check existing connection settings and utilisation using the following SQL query.

```nohighlight
SELECT 
  max_conn, 
  used
FROM 
  (SELECT count(*) used FROM pg_stat_activity) t1,
  (SELECT setting::int res_for_super FROM pg_settings WHERE name=$$superuser_reserved_connections$$) t2,
  (SELECT setting::int max_conn FROM pg_settings WHERE name=$$max_connections$$) t3;
```

`max_conn` is the maximum number of connections available and `used` is the number of currently used connections.

### Getting information via configuration file

```nohighlight
grep 'max_connections' /var/lib/pgsql/{version_number}/data/postgresql.conf
```

### Increasing maximum connections

If you have max_connections set to 100, then you need to [increase that number](https://www.postgresql.org/docs/14/runtime-config-connection.html).  Please consider referring to these best practices for configuring your PostgreSQL.

### Symptoms of an issue

If the configured amount of database connections is not enough, you might see errors like this:

```nohighlight
> FATAL: sorry, too many clients already
> FATAL:  remaining connection slots are reserved for non-replication superuser connections
> pq: remaining connection slots are reserved for non-replication superuser connections
```

That will lead to variety of issues, so please make sure you've configured enough connections.

## MAAS, NTP, and chrony

Time sync complications can arise between Ubuntu's default `systemd-timesyncd` and MAAS `chrony`. If the NTP servers differ, you're asking for trouble. Consult the MAAS [installation guide](/t/how-to-install-maas/5128) for solutions.

## Test environment

For a single-host test setup assuming the latest two Ubuntu LTS releases:

| Component | Memory (MB) | CPU (GHz) | Disk (GB) |
|:---|----:|----:|----:|
| [Region controller](/t/reference-maas-glossary/5416) | 512 | 0.5 | 5 |
| PostgreSQL | 512 | 0.5 | 5 |
| [Rack controller](/t/reference-maas-glossary/5416) | 512 | 0.5 | 5 |
| Ubuntu Server | 512 | 0.5 | 5 |

Total? 2 GB RAM, 2 GHz CPU, 20 GB disk.

## Production environment

For large-scale, continuous client handling, plan as follows:

| Component | Memory (MB) | CPU (GHz) | Disk (GB) |
|:---|----:|----:|----:|
| [Region controller](/t/reference-maas-glossary/5416) | 2048 | 2.0 | 5 |
| PostgreSQL | 2048 | 2.0 | 20 |
| [Rack controller](/t/reference-maas-glossary/5416) | 2048 | 2.0 | 20 |
| Ubuntu Server | 512 | 0.5 | 5 |

You'll need about 4.5 GB RAM, 4.5 GHz CPU, and 45 GB disk per host for region controllers, and slightly less for rack controllers.

Additional notes:

- These specs are MAAS-specific and don't cover extra nodes.
- IPMI-based BMC controllers are recommended for power management.
  
Factors affecting these numbers:

- Client activity
- Service distribution
- Use of [high availability/load balancing](/t/how-to-enable-high-availability/5120).
- Number and type of stored images

Don't forget, a local image mirror could significantly increase disk requirements. Also, rack controllers have a 1000-machine cap per subnet. For larger networks, add more controllers.
