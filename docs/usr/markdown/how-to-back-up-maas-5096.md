> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/backing-up-maas" target = "_blank">Let us know.</a>*

MAAS uses standard command-line utilities to keep backups simple and familiar.

## Clean reset backup

This procedure does a clean reset backup using `pg_dumpall`. MAAS and PostgreSQL are fully overwritten on restore. You can also do a limited back and restore if other services are sharing your PostgreSQL database.

Generally, using `pg_dumpall` for a database dump doesn't require stopping PostgreSQL. It works with live databases, ensuring consistent backups and minimal service disruption. The PostgreSQL transactional model guarantees dump accuracy. You should be able to keep PostgreSQL running -- skipping the *optional* steps below -- but you should stop MAAS first to avoid conflicts during the dump. If you're concerned at all, just use the optional steps to stop and restart PostgreSQL.

Please note that the order of steps is important.

## Clean Snap backup

1. Use this command, if needed, to confirm the local PostgreSQL service name:

```nohighlight
   sudo systemctl list-units --type=service | grep postgres
```

2. Create an epoch-stamped directory on your external media to store the backup:

```nohighlight
   cd <external-backup-media>/maas-backups/
   mkdir $(date +%s)
```

3. Backup the database to your external backup media:

```nohighlight
   sudo -u postgres pg_dumpall -c > "<external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_dump.sql"
```

4. Stop MAAS:

```nohighlight
   sudo snap stop maas
```

5. (Optional) Confirm that no other PostgreSQL sessions are active:

```nohighlight
   sudo -u postgres psql -c  "SELECT * FROM pg_stat_activity"
```

6. (Optional) Stop PostgreSQL:

```nohighlight
   sudo systemctl stop postgresql.service
```

7. Take a snapshot of MAAS and note the snapshot ID:

```nohighlight
   sudo snap save maas
```

8. Verify the snapshot:

```nohighlight
   sudo snap check-snapshot <snapshot-id>
```

9. Export the snapshot to your external backup media:

```nohighlight
   sudo snap export-snapshot <snapshot-id> <external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_maas_snapshot_<snapshot-id>
```

10. (Optional) Restart PostgreSQL:

```nohighlight
   sudo systemctl start postgresql.service
```

11. (Optional) Verify that PostgreSQL is running:

```nohighlight
   sudo systemctl status postgresql
```

12. Restart MAAS:

```nohighlight
   sudo snap restart maas
```

## Clean Snap restore

1. Stop MAAS to clear any cache:

```nohighlight
   sudo snap stop maas 
```

2. Remove the current MAAS instance:

```nohighlight
   sudo snap remove maas
```

3. Do a clean restore of the database:

```nohighlight
   sudo -u postgres psql -f <external-backup-media>/maas-backups/<backup-timestamp>/<dump_epoch>_dump.sql postgres 
```

4. (Optional) Confirm that no other PostgreSQL sessions are active:

```nohighlight
   sudo -u postgres psql -c  "SELECT * FROM pg_stat_activity"
```

5. (Optional) Stop PostgreSQL:

```nohighlight
   sudo systemctl stop postgresql.service
```

6. Import the MAAS snapshot from external media: 

```nohighlight
   sudo snap import-snapshot <external-backup-media>/maas-backups/<backup-timestamp>/<snapshot-epoch>_maas_snapshot_<snapshot-id>
```

7. Restore the MAAS snapshot:

```nohighlight
   sudo snap restore <snapshot-id>
```

8. (Optional) Restart PostgreSQL:

```nohighlight
   sudo systemctl start postgresql.service
```

9. (Optional) Verify that PostgreSQL is running:

```nohighlight
   sudo systemctl status postgresql
```

10. Restart MAAS:

```nohighlight
   sudo snap restart maas
```

## Clean package backup

1. Use this command, if needed, to confirm the local PostgreSQL service name:

```nohighlight
   sudo systemctl list-units --type=service | grep postgres
```

2. Create an epoch-stamped directory on your external media to store the backup:

```nohighlight
   cd <external-backup-media>/maas-backups/
   mkdir $(date +%s)
```

3. Backup the database to your external backup media:

```nohighlight
   sudo -u postgres pg_dumpall -c > "<external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_dump.sql"
```

4. Stop MAAS services:

```nohighlight
   sudo systemctl stop maas-dhcpd.service
   sudo systemctl stop maas-rackd.service
   sudo systemctl stop maas-regiond.service
```

5. (Optional) Confirm that no other PostgreSQL sessions are active:

```nohighlight
   sudo -u postgres psql -c  "SELECT * FROM pg_stat_activity"
```

6. (Optional) Stop PostgreSQL:

```nohighlight
   sudo systemctl stop postgresql.service
```

7. Write a verified archive of the key MAAS files to your external backup:

```nohighlight
   sudo tar cvpzWf <external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_maas_backup.tgz --exclude=/var/lib/maas/boot-resources /etc/maas /var/lib/maas
```

8. (Optional) Restart PostgreSQL:

```nohighlight
   sudo systemctl start postgresql.service
```

9. (Optional) Verify that PostgreSQL is running:

```nohighlight
   sudo systemctl status postgresql
```

10. Restart MAAS:

```nohighlight
   sudo snap restart maas
```

## Clean package restore

1. (Optional, but recommended if possible) Begin with a fresh Ubuntu install.

2. Make sure the required PostgreSQL version is installed.

3. Use this command, if needed, to confirm the local PostgreSQL service name:

```nohighlight
   sudo systemctl list-units --type=service | grep postgres
```

4. Do a clean restore of the database:

```nohighlight
   sudo -u postgres psql -f <external-backup-media>/maas-backups/<backup-timestamp>/<dump_epoch>_dump.sql postgres 
```

5. Install [MAAS from packages](/t/how-to-install-maas/5128).

6. Once fully operational, stop these MAAS services:

```nohighlight
   sudo systemctl stop maas-dhcpd.service
   sudo systemctl stop maas-rackd.service
   sudo systemctl stop maas-regiond.service
```

7. (Optional) Confirm that no other PostgreSQL sessions are active:

```nohighlight
   sudo -u postgres psql -c  "SELECT * FROM pg_stat_activity"
```

8. (Optional) Stop PostgreSQL:

```nohighlight
   sudo systemctl stop postgresql.service
```

9. Untar the backup to a temporary directory:

```nohighlight
   mkdir /tmp/maas_backup
   sudo tar xvzpf <external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_maas_backup.tgz -C /tmp/maas_backup
```

10. Create epoch-stamped backup directories:

```nohighlight
   backup_dir="/var/backups/maas_backup/$(date +%s)"
   sudo mkdir -p "$backup_dir"
```

11. Move current MAAS directories to backup:

```nohighlight
   sudo mv /etc/maas "$backup_dir/etc_maas"
   sudo mv /var/lib/maas "$backup_dir/var_lib_maas"
```

12. Restore MAAS configuration from backup:

```nohighlight
   sudo cp -prf /tmp/maas_backup/etc/maas /etc/
   sudo cp -prf /tmp/maas_backup/var/lib/maas /var/lib/
```

13. Do a clean restore of the database:

```nohighlight
   sudo -u postgres psql -f <external-backup-media>/maas-backups/<backup-timestamp>/<dump_epoch>_dump.sql postgres 
```

14. (Optional) Restart PostgreSQL:

```nohighlight
   sudo systemctl start postgresql.service
```

15. (Optional) Verify that PostgreSQL is running:

```nohighlight
   sudo systemctl status postgresql
```

16. Restart MAAS services:

```nohighlight
   sudo systemctl stop maas-dhcpd.service
   sudo systemctl stop maas-rackd.service
   sudo systemctl stop maas-regiond.service
```

## Limited backup

For MAAS and PostgreSQL setups which are shared with other services, follow these backup and restore guidelines.

## Limited Snap backup

1. Use this command, if needed, to confirm the local PostgreSQL service name:

```nohighlight
   sudo systemctl list-units --type=service | grep postgres
```

2. Create an epoch-stamped directory on your external media to store the backup:

```nohighlight
   cd <external-backup-media>/maas-backups/
   mkdir $(date +%s)
```

3. Identify the MAAS database that you want to back up:

```nohighlight
   sudo -u postgres psql
   \l
   # identifying the MAAS database is up to you
   \q 
```

4. Backup the database to your external backup media:

```nohighlight
   sudo -u postgres pg_dump [maas_database_name] > "<external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_maas_only_backup.sql"
```

5. Stop MAAS:

```nohighlight
   sudo snap stop maas
```

6. Take a snapshot of MAAS and note the snapshot ID:

```nohighlight
   sudo snap save maas
```

8. Verify the snapshot:

```nohighlight
   sudo snap check-snapshot <snapshot-id>
```

9. Export the snapshot to your external backup media:

```nohighlight
   sudo snap export-snapshot <snapshot-id> <external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_maas_snapshot_<snapshot-id>
```

10. Restart MAAS:

```nohighlight
   sudo snap restart maas
```

## Limited Snap restore

1. Stop MAAS to clear any cache:

```nohighlight
   sudo snap stop maas 
```

2. Remove the current MAAS instance:

```nohighlight
   sudo snap remove maas
```

3. Do a limited restore of the MAAS database only:

```nohighlight
   sudo -u postgres psql [maas_database_name] < <external-backup-media>/maas-backups/<backup-timestamp>/<dump_epoch>_maas_only_backup.sql
```

4. Import the MAAS snapshot from external media: 

```nohighlight
   sudo snap import-snapshot <external-backup-media>/maas-backups/<backup-timestamp>/<snapshot-epoch>_maas_snapshot_<snapshot-id>
```

5. Restore the MAAS snapshot:

```nohighlight
   sudo snap restore <snapshot-id>
```

6. Restart MAAS:

```nohighlight
   sudo snap restart maas
```

## Limited package backup

1. Use this command, if needed, to confirm the local PostgreSQL service name:

```nohighlight
   sudo systemctl list-units --type=service | grep postgres
```

2. Create an epoch-stamped directory on your external media to store the backup:

```nohighlight
   cd <external-backup-media>/maas-backups/
   mkdir $(date +%s)
```

3. Identify the MAAS database that you want to back up:

```nohighlight
   sudo -u postgres psql
   \l
   # identifying the MAAS database is up to you
   \q 
```

4. Backup the database to your external backup media:

```nohighlight
   sudo -u postgres pg_dump [maas_database_name] > "<external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_maas_only_backup.sql"
```

5. Stop MAAS services:

```nohighlight
   sudo systemctl stop maas-dhcpd.service
   sudo systemctl stop maas-rackd.service
   sudo systemctl stop maas-regiond.service
```

6. Write a verified archive of the key MAAS files to your external backup:

```nohighlight
   sudo tar cvpzWf <external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_maas_backup.tgz --exclude=/var/lib/maas/boot-resources /etc/maas /var/lib/maas
```

7. Restart MAAS:

```nohighlight
   sudo snap restart maas
```

## Limited package restore

1. Use this command, if needed, to confirm the local PostgreSQL service name:

```nohighlight
   sudo systemctl list-units --type=service | grep postgres
```

2. Do a limited restore of the MAAS database only:

```nohighlight
   sudo -u postgres psql [maas_database_name] < <external-backup-media>/maas-backups/<backup-timestamp>/<dump_epoch>_maas_only_backup.sql
```

3. Untar the MAAS backup to a temporary directory:

```nohighlight
   mkdir /tmp/maas_backup
   sudo tar xvzpf <external-backup-media>/maas-backups/<backup-timestamp>/$(date +%s)_maas_backup.tgz -C /tmp/maas_backup
```

4. Create epoch-stamped backup directories:

```nohighlight
   backup_dir="/var/backups/maas_backup/$(date +%s)"
   sudo mkdir -p "$backup_dir"
```

5. Move current MAAS directories to backup:

```nohighlight
   sudo mv /etc/maas "$backup_dir/etc_maas"
   sudo mv /var/lib/maas "$backup_dir/var_lib_maas"
```

6. Remove the current MAAS installation

```nohighlight
   sudo apt-get remove --purge maas
   sudo apt-get autoremove
```

6. Install [MAAS from packages](/t/how-to-install-maas/5128).

7. Once fully operational, stop these MAAS services:

```nohighlight
   sudo systemctl stop maas-dhcpd.service
   sudo systemctl stop maas-rackd.service
   sudo systemctl stop maas-regiond.service
```

8. Restore MAAS configuration from backup:

```nohighlight
   sudo cp -prf /tmp/maas_backup/etc/maas /etc/
   sudo cp -prf /tmp/maas_backup/var/lib/maas /var/lib/
```
 
9. Restart MAAS services:

```nohighlight
   sudo systemctl stop maas-dhcpd.service
   sudo systemctl stop maas-rackd.service
   sudo systemctl stop maas-regiond.service
```