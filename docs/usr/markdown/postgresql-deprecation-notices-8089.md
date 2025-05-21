## Use of PostgreSQL 12 deprecated in MAAS 3.3

| Since | Removed | 
|:---:|:---:|
| 3.3.0 | 3.5.0 |

This notice is raised when MAAS is using a PostgreSQL version older than 14.

Up to the 3.2 versions of MAAS, the default PostgreSQL version in use was 12 (older versions were no longer supported).

Starting from 3.3, with MAAS running on 22.04, the default 22.04 version of Postgres (14) is the default, and older versions are deprecated.

PostgreSQL 12-based installs of 3.3 will still work correctly, but support for version 12 will be dropped in MAAS 3.5.

See [the upgrade procedure](/t/how-to-upgrade-postgresql-v12-to-v14/7203) for a detailed description on how to perform the PostgreSQL upgrade.

## Use of MAAS database owned by 'postgres' user is deprecated in MAAS 3.4

| Since | Removed |
|:---:|:---:|
| 3.4.1 | 3.5.0 |

This notice is raised when MAAS PostgreSQL database is owned by incorrect user.

Starting from 3.5, MAAS will require `maas` user to be the owner of the `maasdb` database.

You can change database owner with the following command:

```nohighlight
sudo -u postgres \
    psql -c "ALTER DATABASE maasdb OWNER TO maas"
```

