# Install MAAS

There are multiple approaches to installing MAAS, depending on your needs, use case, and operating system. This document outlines how to install MAAS on a single machine in region+rack mode.

## Prerequisites

A physical or virtual machine intended to run MAAS must meet the following requirements:

- The Ubuntu LTS version required for MAAS 3.8 — see [Supported MAAS versions](/reference/supported-maas-versions.md).
- `sudo` privileges.
- `systemd-timesyncd` disabled for Ubuntu versions older than 25.10 — MAAS manages time synchronisation via `chrony` and the two conflict:
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

Create a MAAS database user named `maas` and database named `maas`. Pick a strong password for the database user when prompted, and store it securely:

```bash
postgresql.createuser -U postgres -h /tmp -P maas
postgresql.createdb -U postgres -h /tmp -O maas maas
```

## Initialize MAAS

Initialize MAAS in region+rack mode. Specify the password you created in the previous step in the `--database-uri`:

```bash
sudo maas init region+rack --database-uri "postgres://maas:<password>@localhost/maas"
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

You have just created a profile in the MAAS CLI called `admin`, logged in using the API key created in the previous step for your admin user. The rest of these docs will refer to this profile as `$PROFILE`.
```

## Access the MAAS UI

Open a browser and navigate to `http://<maas-ip>:5240/MAAS`, replacing `<maas-ip>` with the IP address of your MAAS region controller. If you are on the same machine as the machine running MAAS, use `http://localhost:5240/MAAS`.

Log in with the administrator credentials you created in the previous steps.

## Alternative installation methods

An alternative to installing the MAAS snap is to install the MAAS deb package. Install it with the following commands:

```bash
sudo apt-add-repository ppa:maas/3.8
sudo apt update
sudo apt -y install maas
```

Once installed, [install PostgreSQL](#install-postgresql) and [initialize MAAS](#initialize-maas) as described in the previous sections.
