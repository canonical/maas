> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/fresh-installation-of-maas" target = "_blank">Let us know.</a>*


## Install MAAS (snap or packages)

* **Install from [snap](https://snapcraft.io/maas):**
   ```nohighlight
   sudo snap install --channel=<version> maas
   ```
   Replace `<version>` with the desired MAAS version.

* **Install from packages:**
   ```nohighlight
   sudo apt-add-repository ppa:maas/<version>
   sudo apt update
   sudo apt-get -y install maas
   ```
## Post-install setup (POC)

There is a proof-of-concept configuration defined ***for the MAAS snap version only***. To initialise the MAAS snap in this POC configuration, use the `--help` flag with `maas init` and follow the instructions. This POC uses the [`maas-test-db`](https://snapcraft.io/maas-test-db).

## Post-install setup (production)

1. **Disable conflicting NTP:**
   ```nohighlight
   sudo systemctl disable --now systemd-timesyncd
   ```

2. **Configure PostgreSQL for production:**
   ```nohighlight
   sudo apt install -y postgresql
   sudo -i -u postgres psql -c "CREATE USER \"$DBUSER\" WITH ENCRYPTED PASSWORD '$DBPASS'"
   sudo -i -u postgres createdb -O "$DBUSER" "$DBNAME"
   ```
3. **Edit `/etc/postgresql/14/main/pg_hba.conf`**, adding a line for the newly created database:
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

## Upgrading MAAS

* **Upgrade MAAS (snap):**
   ```bash
   sudo snap refresh maas --channel=<version>/stable
   ```

* **Upgrade MAAS (packages):**
   ```bash
   sudo apt-add-repository ppa:maas/<version>
   sudo do-release-upgrade --allow-third-party
   ```

### Notes

- For PostgreSQL 12 users, [upgrade to PostgreSQL 14](/t/how-to-upgrade-postgresql-v12-to-v14/7203) before installing or upgrading to MAAS 3.5+.
- Review the new PostgreSQL requirements in the [installation requirements document](/t/reference-installation-requirements/6233) before installing MAAS.
- For Ubuntu 20.04 LTS users, upgrade to Ubuntu 22.04 before moving to MAAS 3.5+.
- Always [back up your MAAS](/t/how-to-back-up-maas/5096) server before upgrading.

## Special upgrade situations

For multi-node setups, upgrade rack nodes before region nodes. For BMC setups with duplicate IP/username combos, ensure unique combinations to avoid migration failures.

## Configuring and starting MAAS

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

1. **Access the UI:**
   ```http://$API_HOST:5240/MAAS```
   Log in with the credentials created during installation.
2. **DNS forwarder:** Set to a suitable value (e.g., 8.8.8.8).
3. **Image import:** Select at least one Ubuntu LTS image.
4. **SSH key import:** Choose between Launchpad, GitHub, or upload a key from `.ssh/id_rsa.pub`.

### MAAS CLI setup

1. **Login:**
   ```bash
   maas login $PROFILE $MAAS_URL $(cat api-key-file)
   ```
2. **Configure DNS:**
   ```bash
   maas $PROFILE maas set-config name=upstream_dns value="8.8.8.8"
   ```
3. **Add SSH key:**
   ```bash
   maas $PROFILE sshkeys create "key=$SSH_KEY"
   ```

## Enabling DHCP

### UI
1. **Navigate to Subnets > VLAN > Configure DHCP.**
2. **Select the appropriate DHCP options (Managed or Relay).**
3. **Save and apply changes.**

### CLI
1. **Enable DHCP:**
   ```bash
   maas $PROFILE vlan update $FABRIC_ID untagged dhcp_on=True \
       primary_rack=$PRIMARY_RACK_CONTROLLER
   ```
2. **Set default gateway:**
   ```bash
   maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
   ```