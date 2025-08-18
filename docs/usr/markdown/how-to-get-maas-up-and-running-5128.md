This guide shows you how to install MAAS, set it up for either a Proof-of-Concept (POC) or a production environment, and verify that it is working.

## Prerequisites
- A host running Ubuntu 22.04 LTS (Jammy) or newer.
- Administrative privileges (sudo) on the host.
- Network access to download snaps or packages.
- (Production only) A PostgreSQL server (version 14 or newer recommended).
- (Production only) A plan for DNS forwarder and DHCP scope.

## Install MAAS

### Option 1 – Snap (recommended)
```bash
sudo snap install --channel=<version>/stable maas
```
Replace `<version>` with the desired MAAS version (for example, `3.6`).

### Option 2 – Debian packages
```bash
sudo apt-add-repository ppa:maas/<version>
sudo apt update
sudo apt-get -y install maas
```

## Post-install setup

### POC setup
Install the test database and initialize MAAS:
```bash
sudo snap install maas-test-db
maas init --help
```
Follow the prompts to configure the POC environment.

### Production setup

1. Disable conflicting NTP services:
   ```bash
   sudo systemctl disable --now systemd-timesyncd
   ```

2. Install and configure PostgreSQL:
   ```bash
   sudo apt install -y postgresql
   sudo -i -u postgres psql -c "CREATE USER \"$DBUSER\" WITH ENCRYPTED PASSWORD '$DBPASS'"
   sudo -i -u postgres createdb -O "$DBUSER" "$DBNAME"
   ```

3. Edit PostgreSQL authentication:
   Add this line to `/etc/postgresql/14/main/pg_hba.conf`:
   ```
   host    $DBNAME    $DBUSER    0/0     md5
   ```

4. Initialize MAAS with the database:
   ```bash
   sudo maas init region+rack --database-uri "postgres://$DBUSER:$DBPASS@$HOSTNAME/$DBNAME"
   ```

5. Create an admin user:
   ```bash
   sudo maas createadmin --username=$PROFILE --email=$EMAIL_ADDRESS
   ```

## Configure and start MAAS

### Check MAAS service status
```bash
sudo maas status
```
Example:
```
bind9        RUNNING
dhcpd        STOPPED
postgresql   RUNNING
```

### Web UI setup
1. Open: `http://<API_HOST>:5240/MAAS`
2. Log in with your admin credentials.
3. Configure:
   - DNS forwarder (e.g., `8.8.8.8`)
   - At least one Ubuntu LTS image
   - SSH key (Launchpad, GitHub, or upload from `~/.ssh/id_rsa.pub`)

### CLI setup
1. Log in:
   ```bash
   maas login $PROFILE $MAAS_URL $(cat api-key-file)
   ```
2. Configure DNS:
   ```bash
   maas $PROFILE maas set-config name=upstream_dns value="8.8.8.8"
   ```
3. Add an SSH key:
   ```bash
   maas $PROFILE sshkeys create "key=$SSH_KEY"
   ```

## Enable DHCP

### Web UI
- Go to Subnets > VLAN > Configure DHCP
- Select options
- Save and apply

### CLI
```bash
maas $PROFILE vlan update $FABRIC_ID untagged dhcp_on=True primary_rack=$PRIMARY_RACK_CONTROLLER
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

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
- [About controllers](https://canonical.com/maas/docs/about-controllers)
- [Back up MAAS](https://canonical.com/maas/docs/how-to-back-up-maas)
- [Networking in MAAS](https://canonical.com/maas/docs/about-maas-networking)
