# MAAS

MAAS (Metal as a Service) turns your bare-metal servers into an elastic, cloud-like resource.

MAAS discovers, commissions, deploys and recycles physical servers on demand. It provides network boot, DHCP, DNS, image management, storage and network configuration, and power management through a single REST API, CLI and web UI. You tell MAAS which machines to manage, and it boots them, inventories and tests their hardware, and keeps them ready to deploy Ubuntu, other Linux distributions, Windows or custom images.

MAAS scales from a single rack in a lab to large data centers, with highly available controllers and fine-grained access control. It integrates with the tools you already use, such as Terraform, Ansible and Juju, so you can provision bare metal with the same workflows you use for the cloud.

## Get started

See the [MAAS tutorial](https://canonical.com/maas/docs/stable/tutorial/) for a guided first deployment, or [Install MAAS](https://canonical.com/maas/docs/stable/how-to-guides/get-started/install-maas/) to set up a controller.

- Documentation: [`https://canonical.com/maas/docs`](https://canonical.com/maas/docs)
- Release notes and announcements: [`https://canonical.com/maas/docs/release-information`](https://canonical.com/maas/docs/release-information)
- Snap Store: [`https://snapcraft.io/maas`](https://snapcraft.io/maas)

## Status

Type          | Service     | Status
---           | ---         | ---
Snap          | Snapcraft   | [![maas](https://snapcraft.io/maas/badge.svg)](https://snapcraft.io/maas)
License       | AGPL-3.0    | [![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

## Installing MAAS

MAAS is distributed as a [snap](https://snapcraft.io/maas):

```bash
sudo snap install maas --channel=<version>/stable
```

MAAS requires a PostgreSQL database. For a complete walkthrough, including the database setup, initialization and the first administrator, see [Install MAAS](https://canonical.com/maas/docs/stable/how-to-guides/get-started/install-maas/).

The snap packaging files are available in the [`snap`](snap) directory. To build and run MAAS from source, see [HACKING.rst](HACKING.rst).

## Supported releases

Each MAAS release is supported on a specific Ubuntu LTS and PostgreSQL version. Use only supported MAAS releases in production. See [Supported MAAS versions](https://canonical.com/maas/docs/release-information/supported-maas-versions/) for the support matrix and end-of-life dates.

## API and client libraries

MAAS is fully driven by its REST API; the web UI and the `maas` CLI are clients of the same API.

Client          | Link
---             | ---
REST API        | [API reference](https://canonical.com/maas/docs/stable/reference/api-reference/)
CLI             | `maas`, included in the snap
Python          | [Script MAAS with Python](https://canonical.com/maas/docs/stable/how-to-guides/script-maas-with-python/)
Go              | [`gomaasclient`](https://github.com/canonical/gomaasclient)

## Tools for deploying MAAS

To deploy MAAS in high availability with Juju (Charmed MAAS), use the Terraform modules in [`canonical/maas-terraform-modules`](https://github.com/canonical/maas-terraform-modules).

## Tools for managing MAAS

Tool                  | Link
---                   | ---
Terraform provider    | [Terraform](https://canonical.com/maas/docs/stable/reference/configuration-guides/terraform/)
Ansible collection    | [`maas.maas`](https://galaxy.ansible.com/ui/repo/published/maas/maas/)
Juju                  | [MAAS cloud](https://documentation.ubuntu.com/juju/latest/reference/cloud/list-of-supported-clouds/the-maas-cloud-and-juju/)

## Security

Consider the following aspects to ensure that your MAAS installation is secure:

- Keep MAAS and its hosts up to date, and use only supported MAAS releases.
- Enable TLS on the region controller with a trusted certificate.
- Keep the number of administrators small and grant other users only the entitlements they need.
- Isolate the provisioning network and restrict the ports MAAS exposes.
- Back up MAAS and encrypt the backups.

See [Security](https://canonical.com/maas/docs/stable/explanation/security/) for detailed information, and [Security hardening](https://canonical.com/maas/docs/stable/reference/configuration-guides/security-hardening/) and [FIPS](https://canonical.com/maas/docs/stable/explanation/fips/) for STIG/CIS and FIPS deployments.

To report a vulnerability, see [SECURITY.md](SECURITY.md). Do not report security issues in public bug trackers.

## Community support

You can seek support from the MAAS developers as well as the wider community through the following channels.

### Forum

Ask questions or engage in discussions: [`https://discourse.maas.io`](https://discourse.maas.io)

### Documentation

Access the official documentation: [`https://canonical.com/maas/docs`](https://canonical.com/maas/docs)

### Bug reports and feature requests

To file a bug, [report it on Launchpad](https://bugs.launchpad.net/maas). See [Report a bug](https://canonical.com/maas/docs/stable/uncategorized/report-a-bug/) for the information and logs to include.

To request a feature, post in the [Features category on Discourse](https://discourse.maas.io/c/features/15).

## Commercial support

Commercial support for MAAS is provided as part of [Ubuntu Pro](https://ubuntu.com/pro). See [MAAS](https://canonical.com/maas) for details.

Managed solutions and consulting are also available. See [Managed services](https://ubuntu.com/managed).

## Contributing

Fixes and new features are greatly appreciated. Make sure to read our [contributing guidelines](CONTRIBUTING.md) first!

## License

MAAS is licensed under the [GNU Affero General Public License version 3](LICENSE).

Copyright © Canonical Ltd.
