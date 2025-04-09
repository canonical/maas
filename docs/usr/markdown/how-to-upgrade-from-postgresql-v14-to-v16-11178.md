Starting with MAAS 3.6, you must upgrade PostgreSQL from version 14 to version 16.  This guide will explain the process.

## Create a data backup

Backup all existing data: optional, but strongly advised.

```bash
    sudo -u postgres pg_dumpall > backup.sql
```

## Perform the upgrade

If you're running PostgreSQL v14 on  your MAAS machine, you must upgrade before installing MAAS version 3.6.

### [Install](https://www.postgresql.org/download/linux/ubuntu/) PostgreSQL 16.

```bash
    sudo apt update
    sudo apt install -y postgresql-common
    sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
    sudo apt-get install -y postgresql-16 postgresql-server-dev-16
```

### Create and initialize a PostgreSQL 16 instance

Follow the PostgreSQL [setup](https://www.postgresql.org/docs/16/runtime.html) documentation, as server configurations vary.

### Halt the old server

```bash
    sudo systemctl stop postgresql
```

### Migrate the configuration files

The `pg_upgrade` command will write some files in the directory of execution. This command must be run by the `postgres` user, so run it a permitted directory (such as `/tmp`).

```bash
    cd /tmp
    # copy the data, bin and config files from the new to the old version
    sudo -u postgres /usr/lib/postgresql/16/bin/pg_upgrade \
    --old-datadir=/var/lib/postgresql/14/main \
    --new-datadir=/var/lib/postgresql/16/main \
    --old-bindir=/usr/lib/postgresql/14/bin \
    --new-bindir=/usr/lib/postgresql/16/bin \
    --old-options '-c config_file=/etc/postgresql/14/main/postgresql.conf' \
    --new-options '-c config_file=/etc/postgresql/16/main/postgresql.conf'
```

### Reconfigure the server ports

The current version of PostgreSQL should generally use port 5432.

```bash
    sudo vim /etc/postgresql/16/main/postgresql.conf # Set port to 5432
    sudo vim /etc/postgresql/14/main/postgresql.conf # Set port to 5433
```

### Activate the new server and verify version

Always check to make sure you are running the version you expect.

```bash
    sudo systemctl start postgresql
    sudo -u postgres psql -c "SELECT version();"
```

### Complete the upgrade

Vacuum the database to clean it up before using it routinely.

```bash
    sudo -u postgres /usr/lib/postgresql/16/bin/vacuumdb --all --analyze-in-stages
````

### Delete the old version

First, remove the old packages:

```bash
    sudo apt remove -y postgresql-14 postgresql-server-dev-14
```

Finally, delete configuration files and data from the old version:

```bash
    sudo rm -rf /etc/postgresql/14/
    sudo -u postgres /tmp/delete_old_cluster.sh
```

This completes the upgrade from PostgreSQL v14 to v16.
