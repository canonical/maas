# Configure PostgreSQL for remote connections

This guide covers how to configure PostgreSQL for remote connections. This is useful when deploying MAAS on a separate machine to the database.

## Requirements

You will need two machines:

- **MAAS Machine**: Install the MAAS snap on this machine by following [Install MAAS](/how-to-guides/get-started/install-maas.md#install-the-maas-snap), ensuring the requirements outlined in the guide are met.
- **Database Machine**: Install the PostgreSQL snap on this machine by following [Install PostgreSQL](/how-to-guides/get-started/install-maas.md#install-postgresql).
- Network connectivity between the two machines.

## Configure PostgreSQL

On the database machine, ensure the following environment variables are set to the same values used to set up the PostgreSQL database:

```bash
export DBPASS=<strong-password>
export DBUSER=maas
export DBNAME=maas
```

Configure remote access authentication:

```bash
echo "host    $DBNAME    $DBUSER    0/0    scram-sha-256" | sudo tee -a /var/snap/postgresql/common/etc/postgresql/16/main/pg_hba.conf
```

Set the listen address to all available IP interfaces using the `*` wildcard, or specify specific IP addresses for improved security:

```bash
echo "listen_addresses = '*'" | sudo tee -a /var/snap/postgresql/common/etc/postgresql/16/main/postgresql.conf
```

Restart PostgreSQL to apply the changes:

```bash
sudo snap restart postgresql
```

You can verify the changes by checking the listen address:

```bash
sudo postgresql.psql -U postgres -c "SHOW listen_addresses;"
```

An example output of the process is shown below:

```{terminal}
ubuntu@host-system:~$ echo "host    $DBNAME    $DBUSER    0/0    scram-sha-256" | sudo tee -a /var/snap/postgresql/common/etc/postgresql/16/main/pg_hba.conf
CREATE ROLE
host    maas    maas    0/0    scram-sha-256
ubuntu@host-system:~$ sudo postgresql.psql -U postgres -c "SHOW listen_addresses;"
 listen_addresses
------------------
 localhost
(1 row)

ubuntu@host-system:~$ echo "listen_addresses = '*'" | sudo tee -a /var/snap/postgresql/common/etc/postgresql/16/main/postgresql.conf
listen_addresses = '*'
ubuntu@host-system:~$ sudo snap restart postgresql
Restarted.
ubuntu@host-system:~$ sudo postgresql.psql -U postgres -c "SHOW listen_addresses;"
 listen_addresses
------------------
 *
(1 row)

```

## Initialize MAAS

You can now initialize MAAS on your other machine with the remote database credentials, specifying the IP address of the database machine:

```bash
sudo maas init region+rack --database-uri "postgres://$DBUSER:$DBPASS@<database-machine-ip>/$DBNAME"
```

Press Enter when prompted to accept the default MAAS URL, or specify your own.
