# Decommission MAAS

This guide shows you how to remove MAAS from your environment without leaving data, credentials, or references behind.

If your controllers run in virtual machines, you can delete the virtual machines instead of removing the snap and sanitizing their disks. The other steps still apply.

:::{warning}
This process erases all MAAS data. Back up any data that you need to keep before you start.
:::

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

Releasing a DPU does not erase its disks. To bring a DPU to a clean state, redeploy it before you release it. See [Releasing a DPU](/how-to-guides/deploy-dpus.md#releasing-a-dpu).

:::{warning}
Releasing a machine only erases its disks when you select an erase option. MAAS does not delete any other data automatically.
:::

## Remove the controllers

1. Delete the rack controllers from MAAS. See [Delete a rack controller](/how-to-guides/manage-high-availability.md#delete-a-rack-controller).

2. On every controller, remove the MAAS snap. Use the `--purge` flag, or snapd keeps a snapshot of the MAAS data:

   ```bash
   sudo snap remove maas --purge
   ```

3. Confirm that MAAS is no longer installed and that its data directory does not exist:

   ```bash
   snap list maas
   # expected output when the removal is complete
   error: no matching snaps installed
   ```

   ```bash
   ls /var/snap/maas/
   # expected output when the removal is complete:
   ls: cannot access '/var/snap/maas/': No such file or directory
   ```

## Delete data stored outside the controllers

MAAS stores data in other services. Delete it from each one:

- **PostgreSQL**: drop the MAAS database and the MAAS database user. This also deletes the API keys of all users.
- **MAAS CLI**: on every computer where you used the MAAS CLI, remove the stored API key with `maas logout $PROFILE`.
- **Vault**: see the [HashiCorp Vault documentation](https://developer.hashicorp.com/vault/docs/secrets/kv) for how to delete secrets permanently.
- **Logging and monitoring**: delete the MAAS logs and metrics from your logging and monitoring systems.
- **DNS**: remove any delegation to the MAAS DNS servers.
- **Identity provider**: if you use [single sign-on](/how-to-guides/sso.md), remove the MAAS client.
- **Certificate authority**: revoke the TLS certificate of MAAS.

## Destroy and sanitize the data

Deleted data remains readable on the disks, and someone with access to them can recover it. Follow your data destruction policy to erase or destroy the disks of the controllers, the PostgreSQL server, and the servers that store the backups.

## Related topics

- [Back up MAAS](/how-to-guides/back-up-maas.md)
- [Release or remove machines](/how-to-guides/manage-machines.md#release-or-remove-machines)
- [Security](/explanation/security.md)
