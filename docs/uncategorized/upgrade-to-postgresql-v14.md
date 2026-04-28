# Upgrade to PostgreSQL v14

## Create a data backup

Optional but strongly advised: backup all existing data.

```text
sudo -u postgres pg_dumpall > backup.sql
```

## Perform the upgrade

1. **Update and install packages**

```text
    sudo apt-get update
    sudo apt-get install postgresql-14 postgresql-server-dev-14
```
  
1. **Halt the old server**

```text
    sudo systemctl stop postgresql.service
```
  
1. **Migrate configuration files**

```text
    sudo -u postgres /usr/lib/postgresql/14/bin/pg_upgrade \
    --old-datadir=/var/lib/postgresql/12/main \
    --new-datadir=/var/lib/postgresql/14/main \
    --old-bindir=/usr/lib/postgresql/12/bin \
    --new-bindir=/usr/lib/postgresql/14/bin \
    --old-options '-c config_file=/etc/postgresql/12/main/postgresql.conf' \
    --new-options '-c config_file=/etc/postgresql/14/main/postgresql.conf'
```

Note the output of this step as it may contain instructions that you need to do to finish the migration (see step 6).
  
1. **Reconfigure server ports**

```text
    sudo vim /etc/postgresql/14/main/postgresql.conf  # Set port to 5432
    sudo vim /etc/postgresql/12/main/postgresql.conf  # Set port to 5433
```
  
1. **Activate new server and verify version**

```text
    sudo systemctl start postgresql.service
    sudo -u postgres psql -c "SELECT version();"
```

1. **Execute new cluster script**

On Postgres 13 and below do

```text
    sudo -u postgres ./analyze_new_cluster.sh
```

On Postgres 14 and above run the output from step 3 above.

## Reset user passwords

PostgreSQL v14 defaults to `scram-sha-256` for password hashing. Redefine all existing passwords.

```text
sudo -u postgres psql
postgres=# \password $USER
```

Or, modify `/etc/postgresql/14/main/pg_hba.conf` to switch back to `md5`. But be cautious, as future versions may not support MD5.

## Remove old version

1. **Remove old packages**

```text
    sudo apt-get remove postgresql-12 postgresql-server-dev-12
```

1. **Delete configuration and data**

```text
    sudo rm -rf /etc/postgresql/12/
    sudo -u postgres ./delete_old_cluster.sh
```
