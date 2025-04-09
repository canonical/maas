MAAS enforces strict access control and secure secret management to protect system integrity.

## TLS termination

SSL should be replaced with Transport Layer Security (TLS).  A TLS-terminated load balancer routes incoming Web UI and API requests across region controllers, reducing workload and latency.  Encryption and decryption occur at the edge of the network; in this case, right at the load balancer. TLS better ensures privacy and data integrity through symmetric cryptography and message authentication codes.

### Certificate expiration

When the specified number of days remain until certificate expiration (as defined in the notification reminder), all administrators will see the certificate expiration notification. This notification enumerates the number of days until certificate expiration. It can be dismissed, but once dismissed, it won't appear again.

A certificate expiration check runs every twelve hours. When the certificate has expired, the notification will change to “certificate has expired”.

> Note that MAAS does not auto-renew certificates.

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

PostgreSQL contains secrets, and should be encrypted for maximum protection. You should consider [full disk encryption ](https://help.ubuntu.com/community/Full_Disk_Encryption_Howto_2019)**^**. Also recommended is [TLS encryption between MAAS and PostgreSQL ](https://www.postgresql.org/docs/current/ssl-tcp.html)**^**.

## Strong passwords

You should pick good passwords and store them securely (e.g. in a KeePassX password database). Perform user administration only via the web UI. Only share the `maas` and `root` user passwords with administrators.

## Valid permissions

MAAS configuration files should be set to have permission `640`: readable by logins belonging to the `maas` group and writeable only by the `root` user. Currently, the `regiond.conf` file contains the login credentials for the PostgreSQL database used by MAAS to keep track of all machines, networks, and configuration.

| Pkg Fmt  | chmod 640 on files...                | Final Perms  |
|----------|---------------------------------------|--------------|
| Snap     | `/var/snap/maas/current/regiond.conf` | `-rw-r-----` |
|          | `/var/snap/maas/current/rackd.conf`   | `-rw-r-----` |
| Packages | `/etc/maas/rackd.conf/regiond.conf`   | `-rw-r-----` |
|          | `/etc/maas/rackd.conf/rackd.conf`     | `-rw-r-----` | 

## Snap security

Snaps are fully confined or 'sandboxed,' offering inherent security for the enclosed application. For more detailed information, see [this snap blog](https://snapcraft.io/blog/where-eagles-snap-a-closer-look)**^**.

## Role-Based Access Control (RBAC)  

MAAS assigns access based on roles:  
- Administrator – Full access to all settings and machines.  
- Operator – Admin privileges within assigned resource pools.  
- User – Access to unallocated machines but no settings.  
- Auditor – Read-only access to assigned resource pools.  

RBAC, Candid, and an identity provider (e.g., SSO) manage authentication.  

### Resource pools & permissions  

Each machine belongs to one resource pool. Users access machines based on roles. Hiding machines is not security—proper authorization is required.  

### Identity services & Candid  

MAAS supports multiple identity services via Candid, Canonical’s authentication gateway. Candid issues macaroons—tokens that verify users without repeated authentication requests.  

### RBAC & MAAS integration  

RBAC associates roles with authenticated identities, not individual users. It governs:  
- Machines in resource pools  
- DNS, availability zones, images, and settings  

A user can have different roles across pools—e.g., Operator in one, Auditor in another.  

### RBAC workflow  

1. MAAS syncs resource pools with RBAC.  
2. User login is redirected to RBAC.  
3. RBAC authenticates via Candid.  
4. Candid validates the user via an identity provider (e.g., SSO).  
5. If authenticated, Candid issues a macaroon.  
6. RBAC sends the macaroon and role details to MAAS.  
7. MAAS grants access based on role-resource pairings.  

RBAC does not check permissions per resource pool—MAAS enforces them based on roles.  

### RBAC roles summary  

| Role        | Permissions |
|------------|-------------|
| Administrator | Full access (all settings, machines, pools). |
| Operator | Admin privileges within assigned resource pools. |
| User | Can allocate machines but can’t change settings. |
| Auditor | Read-only access to permitted resource pools. |

MAAS enforces role-based visibility. Users cannot access non-permitted machines, even if they know the system ID.

## Security consulting

If you need help implementing MAAS security, please [contact us](https://maas.io/docs/how-to-contact-us). We will be happy to assist you in arranging security consulting appropriate to your needs.
