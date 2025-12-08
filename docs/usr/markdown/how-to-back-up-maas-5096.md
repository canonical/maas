This guide explains how to back up and restore MAAS.  You can either create a full backup (database + snap state) or a package-level backup (database + key files).

## Back up a POC database

In many proof-of-concept (POC) environments, the `maas_test_db` ends up serving as the foundation for production.  Backing it up protects the effort you’ve already invested in setup and configuration.  Fortunately, the procedure is a simple one-line command:

```bash
pg_dump maasdb -U maas -h /var/snap/maas-test-db/common/postgres/sockets > dump.sql
```

Be sure to use a memorable label for the dump file.

## Clean reset production backup

- Administrator privileges on the MAAS host.
- Access to the PostgreSQL service used by MAAS.
- Sufficient storage space in `<backup-path>` for database dumps and snapshots.
- Installed utilities: `pg_dumpall`, `systemctl`, `snap`, `tar`.

## Option 1: Full backup and restore (snap + database)

This method creates a complete backup of MAAS, including the PostgreSQL database and the snap environment.

### Back up MAAS

1.  Identify the PostgreSQL service:
   ```bash
   sudo systemctl list-units --type=service | grep postgres
   ```

2.  Create a backup directory:
   ```bash
   mkdir -p <backup-path>/$(date +%s)
   ```

3.  Dump the database:
   ```bash
   sudo -u postgres pg_dumpall -c > "<backup-path>/$(date +%s)_dump.sql"
   ```

4.  Stop MAAS:
   ```bash
   sudo snap stop maas
   ```

5. (Optional) Stop PostgreSQL:
   ```bash
   sudo systemctl stop postgresql.service
   ```

6.  Save a snap backup:
   ```bash
   sudo snap save maas
   ```

7.  Export the snapshot:
   ```bash
   sudo snap export-snapshot <snapshot-id> <backup-path>/$(date +%s)_snapshot
   ```

8.  Restart services:
   ```bash
   sudo systemctl start postgresql.service
   sudo snap restart maas
   ```

### Restore MAAS

1.  Stop and remove the MAAS snap:
   ```bash
   sudo snap stop maas && sudo snap remove maas
   ```

2.  Restore the database:
   ```bash
   sudo -u postgres psql -f <backup-path>/<dump.sql> postgres
   ```

3.  Import and restore the snapshot:
   ```bash
   sudo snap import-snapshot <backup-path>/<snapshot>
   sudo snap restore <snapshot-id>
   ```

4.  Restart services:
   ```bash
   sudo systemctl start postgresql.service
   sudo snap restart maas
   ```

**Verification:**
- Run `maas status` to confirm services are running.
- Log in to the MAAS web UI to confirm data integrity.

## Option 2: Package-level backup and restore

This method backs up only the PostgreSQL database and key MAAS configuration/data files.

### Back up MAAS

1.  Identify the PostgreSQL service:
   ```bash
   sudo systemctl list-units --type=service | grep postgres
   ```

2.  Create a backup directory:
   ```bash
   mkdir -p <backup-path>/$(date +%s)
   ```

3.  Dump the database:
   ```bash
   sudo -u postgres pg_dumpall -c > "<backup-path>/$(date +%s)_dump.sql"
   ```

4.  Stop MAAS services:
   ```bash
   sudo systemctl stop maas-dhcpd.service maas-rackd.service maas-regiond.service
   ```

5. (Optional) Stop PostgreSQL:
   ```bash
   sudo systemctl stop postgresql.service
   ```

6.  Archive MAAS files:
   ```bash
   sudo tar cvpzWf <backup-path>/$(date +%s)_maas_backup.tgz        --exclude=/var/lib/maas/boot-resources        /etc/maas /var/lib/maas
   ```

7.  Restart services:
   ```bash
   sudo systemctl start postgresql.service
   sudo snap restart maas
   ```

### Restore MAAS

1.  Reinstall Ubuntu (if required).
2.  Ensure PostgreSQL is installed.
3.  Restore the database:
   ```bash
   sudo -u postgres psql -f <backup-path>/<dump.sql> postgres
   ```

4.  Install [MAAS from packages](https://canonical.com/maas/docs/how-to-get-maas-up-and-running#p-9034-install-maas-snap-or-packages).

5.  Stop MAAS services:
   ```bash
   sudo systemctl stop maas-dhcpd.service maas-rackd.service maas-regiond.service
   ```

6.  Extract the backup archive:
   ```bash
   sudo tar xvzpf <backup-path>/<backup.tgz> -C /
   ```

7.  Restart services:
   ```bash
   sudo systemctl start postgresql.service
   sudo systemctl restart maas-dhcpd.service maas-rackd.service maas-regiond.service
   ```

**Verification:**
- Run `systemctl status maas-*` to confirm services are active.
- Check that `/etc/maas` and `/var/lib/maas` contain the expected configuration and data.

## Next steps

- Discover how to [manage MAAS networks](https://canonical.com/maas/docs/how-to-manage-networks).
- Learn more about [about controllers in MAAS](https://canonical.com/maas/docs/about-controllers).
- Continue with the [provisioning ladder overview](https://canonical.com/maas/how-it-works) to understand the MAAS lifecycle.
