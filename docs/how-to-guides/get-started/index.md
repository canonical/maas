# Get started

The following how-to guides cover the initial steps for installing and configuring MAAS.

There are a number of different ways to install MAAS with different requirements and use cases. Provided in this section is the simplest way to install MAAS: on a single machine, in region+rack mode. This is a good starting point for setting up a homelab, a small proof of concept, or a small production environment.

- [Install MAAS](/how-to-guides/get-started/install-maas.md)
- [Configure MAAS](/how-to-guides/get-started/configure-maas.md)

A more complex installation might include deploying the MAAS region on a separate machine to the database. See [Configure PostgreSQL for remote connections](/how-to-guides/get-started/configure-postgresql-for-remote-connections.md) for more information.

## Get started with high availability

For more advanced use cases, you may want to deploy multiple region controllers separately to rack controllers for high availability. This can be achieved with manual installation of MAAS snaps onto each machine and configuring them as region or rack controllers respectively. See [Manage high availability](/how-to-guides/manage-high-availability.md) for more information.

An alternative approach is to use [Juju](https://canonical.com/juju) to deploy high availability Charmed MAAS. This simplifies the installation process and provides a consistent and repeatable way to deploy MAAS at scale. See the [GitHub repository](https://github.com/canonical/maas-terraform-modules) for more information.

## Troubleshooting notes

- NTP conflicts:

  ```bash
  sudo systemctl disable --now systemd-timesyncd
  ```

- BMC migration (3.3+): Ensure unique BMC IP/username/password combinations.

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
configure-postgresql-for-remote-connections
```
