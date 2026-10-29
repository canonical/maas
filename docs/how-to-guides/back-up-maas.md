# Back up MAAS

MAAS uses standard command-line utilities for simple, familiar backups.  The options described here allow you to back up either a proof-of-concept test database or a complete production MAAS installation.

## Back up a POC database

In many proof-of-concept (POC) environments, the `maas_test_db` ends up serving as the foundation for production. Backing it up protects the effort you’ve already invested in setup and configuration. Fortunately, the procedure is a simple one-line command:

```bash
pg_dump maasdb -U maas -h /var/snap/maas-test-db/common/postgres/sockets > dump.sql
```

Be sure to use a memorable label for the dump file.

## Clean reset production backup

The method uses `pg_dumpall` the entire database and make a complete snapshot of MAAS.

### Back up procedure

1. Find the PostgreSQL service:

   ```sh
   sudo systemctl list-units --type=service | grep postgres
   ```

2. Create backup directory:

   ```sh
   mkdir -p <backup-path>/$(date +%s)
   ```

3. Dump database:

   ```sh
   sudo -u postgres pg_dumpall -c > "<backup-path>/$(date +%s)_dump.sql"
   ```

4. Stop MAAS:

   ```sh
   sudo snap stop maas
   ```

5. (Optional) Stop PostgreSQL:

   ```sh
   sudo systemctl stop postgresql.service
   ```

6. Snap backup:

   ```sh
   sudo snap save maas
   ```

7. Export snapshot:

   ```sh
   sudo snap export-snapshot <snapshot-id> <backup-path>/$(date +%s)_snapshot
   ```

8. Restart services:

   ```sh
   sudo systemctl start postgresql.service
   sudo snap restart maas
   ```

### Restore

1. Stop MAAS & remove instance:

   ```sh
   sudo snap stop maas && sudo snap remove maas
   ```

2. Restore database:

   ```sh
   sudo -u postgres psql -f <backup-path>/<dump.sql> postgres
   ```

3. Import & restore snapshot:

   ```sh
   sudo snap import-snapshot <backup-path>/<snapshot>
   sudo snap restore <snapshot-id>
   ```

4. Restart services:

   ```sh
   sudo systemctl start postgresql.service
   sudo snap restart maas
   ```
