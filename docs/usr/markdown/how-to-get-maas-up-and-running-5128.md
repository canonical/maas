MAAS can be installed from snap or Debian packages, and configured for a Proof-of-Concept (POC) or a production-capable environment.

## Install MAAS (snap or packages)

[Snap](https://snapcraft.io/maas) is the preferred method for installing MAAS.  It offers simple installation & updates, strong isolation and security, and predictable file paths.  To install MAAS using snap:

```nohighlight
sudo snap install --channel=$VERSION maas
```
   
Replace `$VERSION` with the desired MAAS version.

MAAS can also be installed using the more traditional Debian package:

```nohighlight
sudo apt-add-repository ppa:maas/<version>
sudo apt update
sudo apt-get -y install maas
```
## Post-install setup (POC)

The MAAS snap can use a POC configuration with the [`maas-test-db`](https://snapcraft.io/maas-test-db) snap. Enter `maas init --help` and follow the instructions to set up this configuration.

## Post-install setup (production-capable)

Setting up MAAS for a production-capable environment is a little more involved than a POC, but not particularly difficult to accomplish using the following steps:

1. **Disable conflicting NTP:**
   ```nohighlight
   sudo systemctl disable --now systemd-timesyncd
   ```

2. **Create a production-capable PostgreSQL configuration:**
   ```nohighlight
   sudo apt install -y postgresql
   sudo -i -u postgres psql -c "CREATE USER \"$DBUSER\" WITH ENCRYPTED PASSWORD '$DBPASS'"
   sudo -i -u postgres createdb -O "$DBUSER" "$DBNAME"
   ```
3. **Edit `/etc/postgresql/16/main/pg_hba.conf`**, adding a line for the newly created database:
   ```nohighlight
    host    $MAAS_DBNAME    $MAAS_DBUSER    0/0     md5

4. **Initialize MAAS with the database:**
   ```nohighlight
   sudo maas init region+rack --database-uri "postgres://$DBUSER:$DBPASS@$HOSTNAME/$DBNAME"
   ```

   ```
5. **Create an admin user:**
   ```bash
   sudo maas create admin --username=$PROFILE --email=$EMAIL_ADDRESS
   ```

## Configuring and starting MAAS

Once MAAS is up and running successfully, there are a few additional steps to fully enable it.

### Checking MAAS status

To check the status of MAAS services, use:

```bash
sudo maas status
```
Output example:
```bash
bind9        RUNNING   pid 7999, uptime 0:09:17
dhcpd        STOPPED   Not started
postgresql   RUNNING   pid 8001, uptime 0:09:17
...
```

### MAAS UI setup

You can set up MAAS using the Web UI:

1. Access the UI:
   ```http://$API_HOST:5240/MAAS```
   Log in with the credentials created during installation.
2. DNS forwarder: Set to a suitable value (e.g., 8.8.8.8).
3. Image import: Select at least one Ubuntu LTS image.
4. SSH key import: Choose between Launchpad, GitHub, or upload a key from `.ssh/id_rsa.pub`.

### MAAS CLI setup

You can also set up MAAS with the CLI:

1. Login:
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

## Enabling DHCP

DHCP must be enabled before MAAS can commission and deploy machines.

**UI**
*Subnets* > *VLAN* > *Configure DHCP* > Select options > *Save and apply changes*

**CLI**
1. Enable DHCP:
   ```bash
   maas $PROFILE vlan update $FABRIC_ID untagged dhcp_on=True \
       primary_rack=$PRIMARY_RACK_CONTROLLER
   ```
<<<<<<< HEAD
2. Set the default gateway:
   ```bash
   maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
   ```
## Notes on upgrading MAAS

The following general notes apply to an upgrade:

- **Review PostgreSQL Requirements:** MAAS 3.6 and later require PostgreSQL 16. [Upgrade instructions here](/t/how-to-upgrade-from-postgresql-v14-to-v16/11178).
- **Upgrade Ubuntu if needed:** Ensure you're running Ubuntu 24.04 (Noble) before upgrading MAAS.
- **Backup your data:** Always create a backup before upgrading.
- **Multi-node setups:** Upgrade rack nodes first, then region nodes.

## Upgrade to MAAS 3.6

### Upgrade Snap (region + rack)

```bash
sudo snap refresh maas --channel=3.6/stable
```

### Upgrade package (PPA-based installations)

```bash
sudo apt-add-repository ppa:maas/3.6
sudo apt update && sudo apt upgrade maas
```

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
