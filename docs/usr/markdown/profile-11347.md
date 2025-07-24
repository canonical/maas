In the MAAS CLI, an **API profile** represents a stored set of credentials and connection details for a specific MAAS server. Profiles enable users to manage multiple MAAS environments efficiently by maintaining separate authentication contexts.

## Managing API profiles:

- **Login** – Authenticate and create a profile using the `login` command.

- **List** – Display all stored profiles with the `list` command.

- **Switch** – Execute commands under a specific profile by prefixing the profile name to a command invocation.

- **Refresh** – Update the CLI's cached information about the MAAS server's API with the `refresh` command.

- **Logout** – Remove a profile and its credentials using the `logout` command.

Interact seamlessly with multiple MAAS environments by defining and managing profiles carefully.
