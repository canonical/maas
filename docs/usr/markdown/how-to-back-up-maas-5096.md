MAAS uses standard command-line utilities for simple, familiar backups.

## Clean reset backup

Uses `pg_dumpall`. Fully overwrites MAAS and PostgreSQL on restore.

### Backup

1. **Find PostgreSQL service:**
   ```sh
   sudo systemctl list-units --type=service | grep postgres
   ```
2. **Create backup directory:**
   ```sh
   mkdir -p <backup-path>/$(date +%s)
   ```
3. **Dump database:**
   ```sh
   sudo -u postgres pg_dumpall -c > "<backup-path>/$(date +%s)_dump.sql"
   ```
4. **Stop MAAS:**
   ```sh
   sudo snap stop maas
   ```
5. **(Optional) Stop PostgreSQL:**
   ```sh
   sudo systemctl stop postgresql.service
   ```
6. **Snap backup:**
   ```sh
   sudo snap save maas
   ```
7. **Export snapshot:**
   ```sh
   sudo snap export-snapshot <snapshot-id> <backup-path>/$(date +%s)_snapshot
   ```
8. **Restart services:**
   ```sh
   sudo systemctl start postgresql.service
   sudo snap restart maas
   ```

### Restore

1. **Stop MAAS & remove instance:**
   ```sh
   sudo snap stop maas && sudo snap remove maas
   ```
2. **Restore database:**
   ```sh
   sudo -u postgres psql -f <backup-path>/<dump.sql> postgres
   ```
3. **Import & restore snapshot:**
   ```sh
   sudo snap import-snapshot <backup-path>/<snapshot>
   sudo snap restore <snapshot-id>
   ```
4. **Restart services:**
   ```sh
   sudo systemctl start postgresql.service
   sudo snap restart maas
   ```

## Clean package backup

Backs up PostgreSQL and key MAAS files.

### Backup

1. **Find PostgreSQL service:**
   ```sh
   sudo systemctl list-units --type=service | grep postgres
   ```
2. **Create backup directory:**
   ```sh
   mkdir -p <backup-path>/$(date +%s)
   ```
3. **Dump database:**
   ```sh
   sudo -u postgres pg_dumpall -c > "<backup-path>/$(date +%s)_dump.sql"
   ```
4. **Stop MAAS services:**
   ```sh
   sudo systemctl stop maas-dhcpd.service maas-rackd.service maas-regiond.service
   ```
5. **(Optional) Stop PostgreSQL:**
   ```sh
   sudo systemctl stop postgresql.service
   ```
6. **Archive MAAS files:**
   ```sh
   sudo tar cvpzWf <backup-path>/$(date +%s)_maas_backup.tgz --exclude=/var/lib/maas/boot-resources /etc/maas /var/lib/maas
   ```
7. **Restart services:**
   ```sh
   sudo systemctl start postgresql.service
   sudo snap restart maas
   ```

### Restore

1. **Reinstall Ubuntu (if possible).**
2. **Ensure PostgreSQL is installed.**
3. **Restore database:**
   ```sh
   sudo -u postgres psql -f <backup-path>/<dump.sql> postgres
   ```
4. **Install [MAAS from packages](https://maas.io/docs/how-to-install-maas#p-9034-install-maas-snap-or-packages).**
5. **Stop MAAS services:**
   ```sh
   sudo systemctl stop maas-dhcpd.service maas-rackd.service maas-regiond.service
   ```
6. **Extract backup:**
   ```sh
   sudo tar xvzpf <backup-path>/<backup.tgz> -C /
   ```
7. **Restart services:**
   ```sh
   sudo systemctl start postgresql.service
   sudo systemctl restart maas-dhcpd.service maas-rackd.service maas-regiond.service
   ```
