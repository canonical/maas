# Get MAAS up and running

This guide shows you how to install MAAS, set it up for either a Proof-of-Concept (POC) or a production environment, and verify that it is working.

## Configure and start MAAS

### Web UI setup

1. Open: `http://<API_HOST>:5240/MAAS`
2. Log in with your admin credentials.
3. Configure:
   - DNS forwarder (e.g., `8.8.8.8`)
   - At least one Ubuntu LTS image
   - SSH key (Launchpad, GitHub, or upload from `~/.ssh/id_rsa.pub`)


## Upgrading MAAS

### General steps

1. Backup your system and database.
2. Verify Ubuntu release (`lsb_release -a`). Upgrade to 22.04 Jammy or 24.04 Noble as required.
3. Verify PostgreSQL version (14 required, 16 recommended).
4. Upgrade rack nodes first, then region nodes.

### Upgrade commands

- Snap

  ```bash
  sudo snap refresh maas --channel=<version>/stable
  ```

- Debian package (PPA)

  ```bash
  sudo apt-add-repository ppa:maas/<version>
  sudo apt update && sudo apt upgrade maas
  ```

### Version-specific notes

- MAAS 3.6: PostgreSQL 14+ supported; PostgreSQL 16 recommended.
- MAAS 3.5: Requires PostgreSQL 14.
- MAAS 3.3: PostgreSQL 12 deprecated. Upgrade to 14 before proceeding.
- MAAS 2.8 or earlier: Full backup required. Fresh install recommended if upgrade fails.

## Troubleshooting notes

- NTP conflicts:

  ```bash
  sudo systemctl disable --now systemd-timesyncd
  ```

- BMC migration (3.3+): Ensure unique BMC IP/username/password combinations.

## Verification

After installation or upgrade:

```bash
lsb_release -a   # Verify Ubuntu release
maas --version   # Verify MAAS version
sudo maas status # Verify services running
```

## Related documentation

- [About controllers](/explanation/controllers.md)
- [Back up MAAS](/how-to-guides/back-up-maas.md)
- [Networking in MAAS](/explanation/networking.md)

```{toctree}
:titlesonly:
:maxdepth: 2
:hidden:

install-maas
configure-maas
```
