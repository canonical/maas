# Upgrading MAAS

This guide outlines the steps to upgrade MAAS to the latest version

## General steps

1. Backup your system and database.
2. Verify Ubuntu release (`lsb_release -a`) and upgrade to the newer one if required.
3. Verify PostgreSQL version compatibility and upgrade it if required.
4. Upgrade rack nodes first, then region nodes.

## Upgrade commands

- Snap

  ```bash
  sudo snap refresh maas --channel=<version>/stable
  ```

- Debian package (PPA)

  ```bash
  sudo apt-add-repository ppa:maas/<version>
  sudo apt update && sudo apt upgrade maas
  ```

## Version-specific notes

- MAAS 3.6: PostgreSQL 14+ supported; PostgreSQL 16 recommended.
- MAAS 3.5: Requires PostgreSQL 14.
- MAAS 3.3: PostgreSQL 12 deprecated. Upgrade to 14 before proceeding.
- MAAS 2.8 or earlier: Full backup required. Fresh install recommended if upgrade fails.

## Verification

After upgrade:

```bash
sudo maas status # Verify services running
```
