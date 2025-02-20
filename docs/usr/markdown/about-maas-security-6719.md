> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/about-maas-security" target = "_blank">Let us know.</a>*

MAAS enforces strict access control and secure secret management to protect system integrity.

## Avoid storing secrets in MAAS  

Never store secrets (e.g., OMAPI key, RPC secret) in the database. Since MAAS 3.3, secrets are stored in [HashiCorp Vault](https://www.hashicorp.com/products/vault).  

### Vault overview  

Vault secures secrets using identity-based encryption. The `kv` engine stores encrypted key-value pairs. Secrets are isolated by randomly generated UUID folders.

> *Learn more about [Hashicorp Vault](https://developer.hashicorp.com/vault/docs).*  

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
