# Install MAAS

There are multiple approaches to installing MAAS, depending on your needs, use case, and operating system. This document outlines how to install MAAS on a single machine in region+rack mode.

## Prerequisites

A physical or virtual machine intended to run MAAS must meet the following requirements:

- Ubuntu 22.04 LTS (Jammy) or newer.
- `sudo` privileges.
- `systemd-timesyncd` disabled — MAAS manages time synchronisation via `chrony` and the two conflict:
    ```bash
    sudo systemctl disable --now systemd-timesyncd
    ```

```{admonition} Older MAAS versions
:class: note

To install older versions of MAAS, see [Supported MAAS versions](/reference/supported-maas-versions.md) for compatible PostgreSQL channels and operating system versions. For this guide, we will use the latest version of MAAS.
```

## Install MAAS

Install the MAAS snap with:

```bash
sudo snap install maas --channel=3.8/stable
```

## Install PostgreSQL

If you already have a PostgreSQL database installed and configured, you can skip to [Initialize MAAS](#initialize-maas). Otherwise, install the PostgreSQL snap:

```bash
sudo snap install postgresql --channel=16/stable
```

Select credentials for the PostgreSQL database. Pick a strong password and store it securely:

```bash
export DBPASS=<strong-password>
export DBUSER=maas
export DBNAME=maas
```

Create a MAAS database role and database:

```bash
sudo postgresql.psql -U postgres -c "CREATE USER \"$DBUSER\" WITH ENCRYPTED PASSWORD '$DBPASS'"
sudo postgresql.createdb -U postgres -O "$DBUSER" "$DBNAME"
```

## Initialize MAAS

Initialize MAAS in region+rack mode with the PostgreSQL database credentials:

```bash
sudo maas init region+rack --database-uri "postgres://$DBUSER:$DBPASS@localhost/$DBNAME"
```

Press Enter when prompted to accept the default MAAS URL, or specify your own.

## Create an administrator user

Create an administrator user, specifying the username, email and [SSH import id](https://manpages.ubuntu.com/manpages/noble/man1/ssh-import-id.1.html) to import a public key (optional):

```bash
sudo maas createadmin \
  --username admin \
  --email admin@localhost \
  --ssh-import gh:<github-username>  # optional
```

Specify the password for your new administrator user when prompted. Store it securely. 

## Verify your installation

Verify the installation by creating a profile and logging in:

```bash
maas login admin "http://localhost:5240/MAAS" $(sudo maas apikey --username=admin)
```

You should see the following message:

```{terminal}

ubuntu@host-system:~$ maas login admin "http://localhost:5240/MAAS/api/2.0/" $(sudo maas apikey --username=admin)

You are now logged in to the MAAS server at
http://localhost:5240/MAAS/api/2.0/ with the profile name 'admin'.

For help with the available commands, try:

  maas admin --help

```

```{admonition} Profiles
:class: note

You have just created a profile in the MAAS CLI called `admin`, logged in using the credentials created in the previous step for your admin user. The rest of these docs will refer to this profile as `$PROFILE`.
```

## Access the MAAS UI

Open a browser and navigate to `http://<maas-ip>:5240/MAAS`, replacing `<maas-ip>` with the IP address of your MAAS machine. If you are on the same machine as the machine running MAAS, use `http://localhost:5240/MAAS`.

Log in with the administrator credentials you created in the previous steps.

## Alternative installation methods

An alternative to installing the MAAS snap is to install the MAAS deb package. Install it with the following commands:

```bash
sudo apt-add-repository ppa:maas/3.8
sudo apt update
sudo apt -y install maas
```

Once installed, [install PostgreSQL](#install-postgresql) and [initialize MAAS](#initialize-maas) as described in the previous sections.
