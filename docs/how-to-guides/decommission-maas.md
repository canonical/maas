# Decommission MAAS

This guide shows you how to remove MAAS from your environment without leaving data, credentials, or references behind.

```{important}
This process erases all MAAS data. Back up any data that you need to keep before you start.
```

## Before you begin

You need:

- Administrator access to MAAS.
- `sudo` access to every region and rack controller, and to the PostgreSQL server.
- Access to the external services that MAAS uses, such as Vault or your identity provider.

Check the [supported MAAS versions](https://canonical.com/maas/docs/release-information/supported-maas-versions/). A version that reached the end of its support period no longer receives security updates.

## Export your data

Back up the MAAS database and configuration before you remove anything. Backups contain credentials, so encrypt them and store them in a location with restricted access. See [Back up MAAS](/how-to-guides/back-up-maas.md).

## Release the machines

Release every machine that MAAS manages, and erase its disks so that the next user cannot read the previous data. See [Release or remove machines](/how-to-guides/manage-machines.md#release-or-remove-machines).

Releasing a machine only erases its disks when you select an erase option. MAAS does not delete any other data automatically.

## Revoke access

Revoke the credentials that give access to MAAS:

- Delete the API keys of every user. See [Manage API keys](/how-to-guides/enhance-maas-security.md#manage-api-keys).
- If you use [single sign-on](/how-to-guides/sso.md), remove the MAAS client from your identity provider.
- Revoke the TLS certificate of MAAS with your certificate authority.

## Remove the controllers

1. Delete the rack controllers from MAAS. See [Delete a rack controller](/how-to-guides/manage-high-availability.md#delete-a-rack-controller).

2. On every controller, remove the MAAS snap. Use the `--purge` flag, or snapd keeps a snapshot of the MAAS data:

   ```bash
   sudo snap remove maas --purge
   ```

3. Confirm that MAAS is no longer installed and that its data directory does not exist:

   ```bash
   snap list maas
   ls /var/snap/maas/
   ```

## Delete data stored outside the controllers

MAAS stores data in other services. Delete it from each one:

- **PostgreSQL**: drop the MAAS database and the MAAS database user.
- **Vault**: delete the secrets that MAAS stored, and the AppRole that MAAS used. See [config-vault](/reference/cli-reference/config-vault.md).
- **Logging and monitoring**: delete the MAAS logs and metrics from your remote syslog server, Loki, and Prometheus.
- **DNS**: remove any delegation to the MAAS DNS servers.

## Destroy and sanitize the data

Deleted data remains readable on the disks, and someone with access to them can recover it. Follow your data destruction policy to erase or destroy the disks of the controllers, the PostgreSQL server, and the servers that store the backups.

## Related topics

- [Back up MAAS](/how-to-guides/back-up-maas.md)
- [Release or remove machines](/how-to-guides/manage-machines.md#release-or-remove-machines)
- [Security](/explanation/security.md)
