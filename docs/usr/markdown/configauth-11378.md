Configure external authentication. 

```bash
maas configauth [-h] [--candid-agent-file CANDID_AGENT_FILE] [--candid-domain CANDID_DOMAIN] [--candid-admin-group CANDID_ADMIN_GROUP] [--rbac-url RBAC_URL]  [--rbac-service-name RBAC_SERVICE_NAME] [--json]
```
#### Command-line options
| Option                                  | Effect                                                |
|-----------------------------------------|-------------------------------------------------------|
| -h, --help                              | show this help message and exit                       |
| --candid-agent-file CANDID_AGENT_FILE   | Agent file containing Candid authentication           |
|                                         | information                                           |
| --candid-domain CANDID_DOMAIN           | The authentication domain to look up users in for the |
|                                         | external Candid server.                               |
| --candid-admin-group CANDID_ADMIN_GROUP | Group of users whose members are made admins in MAAS  |
| --rbac-url RBAC_URL                     | The URL for the Canonical RBAC service to use.        |
| --rbac-service-name RBAC_SERVICE_NAME   | Optionally, the name of the RBAC service to register  |
|                                         | this MAAS as. If not provided, a list with services   |
|                                         | that the user can register will be displayed, to      |
|                                         | choose from.                                          |
| --json                                  | Return the current authentication configuration as    |
|                                         | JSON                                                  |
