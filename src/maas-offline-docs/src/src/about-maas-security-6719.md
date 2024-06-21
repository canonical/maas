> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/ensuring-security-in-maas" target = "_blank">Let us know.</a>*

As a MAAS administrator, it's crucial to avoid storing secrets associated with your MAAS instance in the database. This includes secrets like the OMAPI key and the RPC secret.

Beginning with version 3.3, MAAS secrets are stored in [HashiCorp Vault](https://www.hashicorp.com/products/vault). 

## HashiCorp Vault

Vault employs identity for securing secrets and encryption keys. Its core component is the `kv` secrets engine, which utilises key-value pairs to store secrets within an encrypted storage managed by Vault. You can explore more about [secrets engines](https://developer.hashicorp.com/vault/docs/secrets) if you're interested.

Vault safeguards the secrets engine using a [barrier view](https://developer.hashicorp.com/vault/docs/secrets#barrier-view), creating a folder with a randomly-generated UUID as the absolute root directory for that engine. This prevents the engine from accessing secrets outside its UUID folder.

For detailed information, it's recommended to refer to the [Vault documentation](https://developer.hashicorp.com/vault/docs) and consider [Vault certification](https://developer.hashicorp.com/vault/tutorials/associate-cert).

## Multi-tenancy

Likewise, you want to grant fine-grained access-controls to different users, based on assigned roles. Working in concert with RBAC and [Candid](https://github.com/canonical/candid#readme), MAAS can restrict user access and actions based on four roles:

- Administrator: can access all settings and perform any operation on any machine in any resource pool.
- Operator: can only act as a MAAS administrator within an assigned resource pool. Machines in other resource pools -- and system settings -- are not accessible.
- User: can access and manipulate machines that are not allocated to other users, within the confines of an assigned resource pool. Users cannot access any settings.
- Auditor: can view information for all machines within an assigned resource pool; cannot make any changes or alter any settings.

MAAS controls access with the help of RBAC (Role-Based Access Control), Candid (Canonical Identity Manager), and an identity service of your choice, such as SSO (Single Sign-On). You can design and deploy a controlled MAAS environment using MAAS/RBAC.

## Resource pools and RBAC

Resource pools group machines. Each machine is assigned to exactly one resource pool. If you control access to resource pools, and you assign roles properly, you control user access.

Note that just using resource pools to hide machines is a flawed access control approach, known as "security by obscurity." What users don't know will hurt you when the users figure it out -- usually entirely by accident, while trying to do the right thing.

Consequently, there must also be some means of active authorisation that allows access to a resource pool. That authorisation must be based on user identity. There must be some way of controlling what the user can do with that resource pool. In the parlance of standard security model, "what the user can do" would be called "privilege", but for the purposes of MAAS, we simply call them "permissions."  

## Identity services

MAAS/RBAC will interface with many identity services, using Candid as a mediator. The choice of identity service is up to you. As an example, let's take a closer look at [Ubuntu Single Sign-On (SSO)](https://help.ubuntu.com/community/SingleSignOn).

SSO permits users to log in once to access many network services. SSO centralises authentication (via Kerberos), account management (via LDAP), resource-sharing (via `pam_mount`), and limited authorisation through group memberships in LDAP, coupled with file permissions.

RBAC (Role-based access control) does not authenticate users or verify their identity; that function is assigned to the identity service you choose. RBAC does receive an identity token or "macaroon" (via Candid) that RBAC uses to assign user roles. MAAS uses these roles, in turn, to control user access and actions.

## Candid

Direct authentication involves a user entering something uncommon or unique in response to a challenge, in order to gain access. "Something uncommon" means "something you know" or "something you have, like a password or a hardware key. "Something unique" means "something you are", like a fingerprint. Authentication can be automated with private/public key exchanges, protected with a password on the first exchange. Adding another access point (another trusted client) usually means providing a public key, setting a password, or registering some biometric data. Direct authentication works well when there are a limited number of clients and not a lot of user turnover.

Increase users and services that need to authenticate, and direct authentication requires more effort: generating access requests; validating requests; setting up authentication; and then managing access as users move around the organisation. [Candid](https://github.com/canonical/candid), the Canonical identity service, was designed to meet this need. Candid acts as an authentication gateway that connects a service (e.g., RBAC) to your chosen identity service.

Candid manages authenticated users via special access tokens ([macaroons](https://askubuntu.com/questions/940640/what-is-a-macaroon)) that confirm user identity. Unlike standard access tokens, macaroons

 can be verified independently, in a standard way, reducing network traffic and repeated queries. Traditional access tokens must be short-lived; macaroons are valid for much longer and more easily refreshed. Macaroons can also be bound to TLS certificates, and used by multiple clients and services with no loss of security.

Candid can do the following things:

- find users by various identity parameters, such as e-mail, full name, last login time, etc.
- show details for a user, based on e-mail or username.
- add or remove users from ACLs (access control lists), or list members of an ACL.
- add or remove users from arbitrary groups.
- clear the multi-factor authentication (MFA) credentials for a specific user.
- manage Candid agents.

Candid can use certificates and agents, if desired. You specify the identity provider by URL when instantiating the program.

When a user logs into an RBAC-enabled MAAS server, that login is redirected to RBAC. RBAC authenticates via Candid, which consults the chosen identity server. If the user is authenticated, Candid constructs a macaroon and passes it to RBAC -- and on to MAAS. This macaroon serves as the user's authentication token until it expires.

To find out more about Candid and how to use it, consult the [github README](https://github.com/canonical/candid#readme) or get in touch with your sales representative.

## RBAC

RBAC uses a database to associate a given role with a properly-authenticated user identity. With RBAC, permissions are associated with roles, not individual users. Within a given resource pool, the role assigned to a properly authenticated user controls user access and actions. MAAS becomes an RBAC service, while each resource pool becomes a scope. RBAC/MAAS also recognises scopes that are not tied to machines, including:

- DNS
- Availability zones
- Images
- Settings

RBAC also helps MAAS control access to these "non-machine resources".

Any given user may be an operator for one resource pool, a user for another, and an auditor for still another, all with no ability to change system settings or manipulate images. RBAC permits such arrangements.

## Permissions

Here is a thumbnail sketch of the permissions model:

- MAAS maintains resource pools, which are a machine attribute. Each machine is assigned to one resource pool.
- RBAC maintains roles associated with user identities. For a given user identity to carry out a particular operation in MAAS, that user identity must correspond to a role that has permission to carry out that operation in a given resource pool.
- Candid vouches for the user with a macaroon.
- Some identity service (e.g., SSO) authenticates the user to Candid; macaroons are not generated for unrecognised users.

Relationships among roles, resource pools, and users are maintained by RBAC as a source of truth. MAAS mediates access to resource pools, based on user roles, using information obtained from RBAC.

## RBAC architecture

The following diagram will give you a graphical view of how MAAS, RBAC, Candid, and an identity provider work together to control access to MAAS resources:

![image](https://discourse.maas.io/uploads/default/original/2X/4/4433c6995c342efebe565f4888a46d7107d1525f.png)

Here is a step-by-step walk-through of the MAAS/RBAC relationship:

- When MAAS is initiated with RBAC connected, MAAS pushes a list of resource pools and a global resource key to RBAC. The global resource key covers things that are not added to resource pools, such as devices or settings.
- When a user tries to login, MAAS redirects that login request to RBAC.
- RBAC, in turn, requests an authentication check from Candid.
- Candid attempts to authenticate the user via whatever identity provider was configured when Candid was started (e.g., SSO).
- If Candid authenticates the user, Candid creates a macaroon as a temporary identity token for the user.
- Candid passes the macaroon back to RBAC.
- RBAC passes the macaroon, in turn, to MAAS, along with a dictionary of groups, role(s), and resource pools corresponding to that user.
- As needed, MAAS then mediates access to resource pools, using the macaroon to recognise the user and their group(s), and using the role/resource pool pairs to adjudicate access.

Note that RBAC does not adjudicate individual permissions against resource pools. RBAC sends MAAS the combination of users, roles, and related resource pools to MAAS when requested. The MAAS code has a built-in understanding of the four roles (user, administrator, operator, and auditor) and what those roles can and cannot do with a given item.

## Four MAAS RBAC roles

MAAS RBAC roles prevent users from seeing or interacting with machines in non-permitted resource pools. Even if a user knows the name or system ID of a machine in a non-permitted resource pool, that user can't access it. Removing non-permitted machines from view prevents confusion.

- Administrator: an administrator can do anything that a normal MAAS administrator can do in the absence of RBAC. This means an admin can see all resource pools, take any action against any machine, and change any MAAS settings.
- Operator: an operator can administer only the machines in their permitted resource pools. An operator cannot see or change system settings.
- User: a user has no special privileges. They can only view and allocate machines that aren't allocated to someone else. Users can't change or access settings at all.
- Auditor: an auditor can view anything about machines in the resource pool(s) for which they are permitted. Auditors cannot change or access settings.

MAAS makes no assumptions about how these roles might be used in the day-to-day operation of your MAAS instance.