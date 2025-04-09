> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/upgrading-postgresql-12-to-version-14" target = "_blank">Let us know.</a>*

## Create a data backup

Optional but strongly advised: backup all existing data.

```nohighlight
sudo -u postgres pg_dumpall > backup.sql
```

## Perform the upgrade

1. **Update and install packages**

```nohighlight
    sudo apt-get update
    sudo apt-get install postgresql-14 postgresql-server-dev-14
```
  
2. **Halt the old server**

```nohighlight
    sudo systemctl stop postgresql.service
```
  
3. **Migrate configuration files**

```nohighlight
    sudo -u postgres /usr/lib/postgresql/14/bin/pg_upgrade \
    --old-datadir=/var/lib/postgresql/12/main \
    --new-datadir=/var/lib/postgresql/14/main \
    --old-bindir=/usr/lib/postgresql/12/bin \
    --new-bindir=/usr/lib/postgresql/14/bin \
    --old-options '-c config_file=/etc/postgresql/12/main/postgresql.conf' \
    --new-options '-c config_file=/etc/postgresql/14/main/postgresql.conf'
```
  
4. **Reconfigure server ports**

```nohighlight
    sudo vim /etc/postgresql/14/main/postgresql.conf  # Set port to 5432
    sudo vim /etc/postgresql/12/main/postgresql.conf  # Set port to 5433
```
  
5. **Activate new server and verify version**

```nohighlight
    sudo systemctl start postgresql.service
    sudo -u postgres psql -c "SELECT version();"
```

6. **Execute new cluster script**

```nohighlight
    sudo -u postgres ./analyze_new_cluster.sh
```

## Reset user passwords

PostgreSQL v14 defaults to `scram-sha-256` for password hashing. Redefine all existing passwords.

```nohighlight
sudo -u postgres psql
postgres=# \password $USER
```

Or, modify `/etc/postgresql/14/main/pg_hba.conf` to switch back to `md5`. But be cautious, as future versions may not support MD5.

## Remove old version

1. **Remove old packages**

```nohighlight
    sudo apt-get remove postgresql-12 postgresql-server-dev-12
```

2. **Delete configuration and data**

```nohighlight
    sudo rm -rf /etc/postgresql/12/
    sudo -u postgres ./delete_old_cluster.sh
```
