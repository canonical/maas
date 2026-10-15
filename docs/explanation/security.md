# Security

MAAS enforces strict access control and secure secret management to protect system integrity.

## Security architecture

A MAAS deployment is made of region controllers, rack controllers, a PostgreSQL database, and the machines that MAAS manages. Each of these components sits on one side of a trust boundary, and every boundary is protected by its own security controls.

```{mermaid}
flowchart LR
    subgraph EXT["External"]
        USERS["Administrators, users<br/>and API clients"]
        IDP["Identity provider<br/>(OIDC)"]
        IMG["Image and package<br/>repositories"]
    end

    subgraph CP["MAAS control plane"]
        REGION["Region controller<br/>(web UI and API)"]
        DB[("PostgreSQL")]
        VAULT[("Vault<br/>(optional)")]
        RACK["Rack controller"]
    end

    subgraph PN["Provisioning network"]
        MACHINES["Machines"]
        BMC["BMCs"]
    end

    USERS -->|"HTTP or HTTPS"| REGION
    IDP -->|"Single sign-on"| REGION
    IMG -->|"Signed images"| REGION
    REGION --> DB
    REGION --> VAULT
    RACK <-->|"RPC with shared secret"| REGION
    RACK -->|"DHCP, TFTP and HTTP"| MACHINES
    RACK -->|"Power drivers"| BMC
```

### Components

* **Region controller**: serves the web UI and the API, and orchestrates the rest of MAAS. See [Region controllers](/explanation/controllers.md#region-controllers).
* **Rack controller**: provides DHCP, TFTP, HTTP boot, and power management to the machines on its fabrics. See [Rack controllers](/explanation/controllers.md#rack-controllers).
* **PostgreSQL**: stores the state of MAAS, including credentials. See [PostgreSQL security](#postgresql-security).
* **HashiCorp Vault**: optionally stores MAAS secrets outside the database. See [HashiCorp Vault](#hashicorp-vault).
* **Temporal**: orchestrates MAAS workflows. The Temporal server runs on the region controller, and the MAAS Agent on each rack controller connects to it.
* **Machines and BMCs**: the servers that MAAS commissions and deploys, and the baseboard management controllers that MAAS uses to power them on and off. See [The machine life cycle](/explanation/the-machine-life-cycle.md).

### Access to the region controller

Administrators, users, and API clients only interact with the region controller, through the web UI, the CLI, or the API. Users authenticate with a password, an API key, or [single sign-on](/how-to-guides/sso.md), and each request is authorized against the user's [entitlements](#fine-grained-authorization).

By default, the web UI and the API use HTTP. To encrypt this traffic, [enable TLS](/how-to-guides/enhance-maas-security.md#use-tls-termination-maas-33).

### External services

The region controller downloads boot images from image repositories and verifies them with a GPG keyring. See [Configure boot sources](/how-to-guides/manage-images.md#configure-boot-sources). When single sign-on is configured, the region controller also trusts an external OIDC identity provider to authenticate users.

### Communication between controllers

Rack controllers have no direct access to the database. They communicate with the region controller over RPC, authenticated with the [shared secret](#shared-secrets). To limit which interfaces these services listen on, see [Harden a rack controller](/how-to-guides/harden-a-rack-controller.md).

### Provisioning network

Rack controllers boot machines over DHCP, TFTP, and HTTP, and control them through their BMCs with power drivers. Network boot protocols do not authenticate the machines, so keep the provisioning network isolated from untrusted networks. To restrict the ports that MAAS exposes, see [Manage network ports](/how-to-guides/enhance-maas-security.md#manage-network-ports).

## TLS termination

SSL should be replaced with Transport Layer Security (TLS).  A TLS-terminated load balancer routes incoming Web UI and API requests across region controllers, reducing workload and latency.  Encryption and decryption occur at the edge of the network; in this case, right at the load balancer. TLS better ensures privacy and data integrity through symmetric cryptography and message authentication codes.

### Certificate expiration

When the specified number of days remain until certificate expiration (as defined in the notification reminder), all administrators will see the certificate expiration notification. This notification enumerates the number of days until certificate expiration. It can be dismissed, but once dismissed, it won't appear again.

A certificate expiration check runs every twelve hours. When the certificate has expired, the notification will change to “certificate has expired”.

> Note that MAAS does not auto-renew certificates.

## Security hardening and FIPS mode

MAAS can apply STIG- and CIS-aligned transport-security controls to its controllers. These controls activate automatically when a controller's host is in FIPS mode, and you can also activate them on any other host. When a prerequisite is missing, MAAS keeps running and reports the problem as a non-dismissable notification for administrators.

For the concepts, see [FIPS mode and security hardening](/explanation/fips.md). To set up a hardened controller, see [Activate MAAS hardening](/how-to-guides/activate-maas-hardening.md).

## Shared secrets

When you add a new rack or region controller, MAAS asks for a shared secret it will use to communicate with the rest of MAAS. This secret is also exposed in the web UI when you click the 'Add rack controller' button on the Controllers page. MAAS automatically generates this secret when your first region controller installed, and stores the secret in a plain text file. This file is automatically protected with the correct permissions, so there is no need for any action on your part.

As a MAAS administrator, it's crucial to avoid storing secrets associated with your MAAS instance in the database. This includes secrets like the OMAPI key and the RPC secret.

## HashiCorp Vault

Beginning with version 3.3, MAAS secrets are stored in [HashiCorp Vault](https://www.hashicorp.com/products/vault).

Vault employs identity for securing secrets and encryption keys. Its core component is the `kv` secrets engine, which utilizes key-value pairs to store secrets within an encrypted storage managed by Vault. You can explore more about [secrets engines](https://developer.hashicorp.com/vault/docs/secrets) if you're interested.

Vault safeguards the secrets engine using a [barrier view](https://developer.hashicorp.com/vault/docs/secrets#barrier-view), creating a folder with a randomly-generated UUID as the absolute root directory for that engine. This prevents the engine from accessing secrets outside its UUID folder.

Vault is compatible with MAAS version 3.3 and above. Please upgrade if you're using an older version of MAAS and want to use Vault.

> *Learn more about [Hashicorp Vault](https://developer.hashicorp.com/vault/docs).*  

## PostgreSQL security

PostgreSQL contains secrets, and should be encrypted for maximum protection. You should consider [full disk encryption](https://help.ubuntu.com/community/Full_Disk_Encryption_Howto_2019). Also recommended is [TLS encryption between MAAS and PostgreSQL](https://www.postgresql.org/docs/current/ssl-tcp.html).

## Strong passwords

You should pick good passwords and store them securely (e.g. in a KeePassX password database). Perform user administration only via the web UI. Only share the `maas` and `root` user passwords with administrators.

## Valid permissions

MAAS configuration files should be set to have permission `640`: readable by logins belonging to the `maas` group and writeable only by the `root` user. Currently, the `regiond.conf` file contains the login credentials for the PostgreSQL database used by MAAS to keep track of all machines, networks, and configuration.

| File                                   | Permissions  |
|----------------------------------------|--------------|
| `/var/snap/maas/current/regiond.conf`  | `-rw-r-----` |
| `/var/snap/maas/current/rackd.conf`    | `-rw-r-----` |

## Snap security

Snaps are fully confined or 'sandboxed,' offering inherent security for the enclosed application. For more detailed information, see [this snap blog](https://snapcraft.io/blog/where-eagles-snap-a-closer-look).

## Fine-grained authorization

MAAS 3.8 introduces a built-in relationship-based access control (ReBAC) system for fine-grained authorization. Access follows the chain **user → group → entitlement → resource**: users belong to groups, and groups are granted entitlements (permissions) on resources.

Entitlements are scoped either globally (the `maas` resource) or per resource pool (the `pool` resource). Resource pools are therefore the unit of access control: you can grant a group per-pool entitlements such as `can_view_machines`, `can_deploy_machines`, or `can_edit_machines`, restricting that group to just the machines in the pool. Global machine permissions cascade to every pool, while per-pool entitlements grant additional access to specific pools only.

MAAS enforces these entitlements on every request, so users cannot access machines they are not entitled to, even if they know the system ID. Hiding machines is not security—proper authorization is required.

For the full permission model, the list of available entitlements, and CLI examples, see [User groups and entitlements](/how-to-guides/user-groups-and-entitlements.md).

## Security consulting

If you need help implementing MAAS security, please [contact us](/uncategorized/contact-us.md). We will be happy to assist you in arranging security consulting appropriate to your needs.
