##  General notes

- **Review PostgreSQL Requirements:** MAAS 3.5 and later require PostgreSQL 14. [Upgrade instructions here](/t/how-to-upgrade-postgresql-v12-to-v14/7203).
- **Upgrade Ubuntu if needed:** Ensure you're running Ubuntu 22.04 (Jammy) before upgrading MAAS.
- **Backup your data:** Always create a backup before upgrading.
- **Multi-node setups:** Upgrade rack nodes first, then region nodes.

##  Upgrade to MAAS 3.5

### Upgrade Snap (region + rack)
```nohighlight
sudo snap refresh maas --channel=3.5/stable
```

### Upgrade package (PPA-based installations)
```nohighlight
sudo apt-add-repository ppa:maas/3.5
sudo apt update && sudo apt upgrade maas
```

###  Upgrade packages from MAAS versions 2.9-3.3

1. **Upgrade PostgreSQL**: If running PostgreSQL 12, [upgrade to 14](/t/how-to-upgrade-postgresql-v12-to-v14/7203).
2. **Ensure Ubuntu 22.04 (Jammy)**:
   ```nohighlight
   lsb_release -a
   ```
   If on Ubuntu 20.04, upgrade:
   ```nohighlight
   sudo do-release-upgrade --allow-third-party
   ```
3. **Add PPA and Upgrade:**
   ```nohighlight
   sudo apt-add-repository ppa:maas/3.5
   sudo apt update && sudo apt upgrade maas
   ```
4. **Verify Installation:**
   ```nohighlight
   maas --version
   ```

### Upgrade packages from MAAS 2.8 or earlier

1. **Backup your system** completely.
2. **Ensure Ubuntu 22.04** (see steps above).
3. **Add PPA and Upgrade:**
   ```nohighlight
   sudo apt-add-repository ppa:maas/3.5
   sudo apt update && sudo apt upgrade maas
   ```
4. **If the upgrade fails**, restore from backup and consider a fresh installation.
   
## Upgrade to MAAS 3.4

### Upgrade snap
```nohighlight
sudo snap refresh maas --channel=3.4/stable
```

### Upgrade package
```nohighlight
sudo apt-add-repository ppa:maas/3.4
sudo apt update && sudo apt upgrade maas
```

- **Follow the same Ubuntu and PostgreSQL upgrade steps as above.**

## Upgrade to MAAS 3.3

### Upgrade snap
```nohighlight
sudo snap refresh maas --channel=3.3/stable
```

### Upgrade packages
```nohighlight
sudo apt-add-repository ppa:maas/3.3
sudo apt update && sudo apt upgrade maas
```

- **PostgreSQL 12 is deprecated in MAAS 3.3 and unsupported in 3.5.** Upgrade to PostgreSQL 14 before proceeding.

## Additional notes

### Avoiding NTP conflicts

If you experience time synchronization issues:

```nohighlight
sudo systemctl disable --now systemd-timesyncd
```

### BMC migration issue (MAAS 3.3+)

Ensure unique BMC IP/username/password combinations before upgrading to avoid migration failures.

### Verification steps

After upgrading, confirm MAAS is running correctly:
```nohighlight
lsb_release -a  # Ensure Ubuntu version is correct
maas --version  # Verify MAAS version
```
	
