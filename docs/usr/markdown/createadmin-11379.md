Create a MAAS administrator account.

```bash
maas createadmin [-h] [--username USERNAME] [--password PASSWORD] [--email EMAIL] [--ssh-import SSH_IMPORT]
```

#### Command-line options | Option | Effect |
|-------------------------|-------------------------------------------------------|
| -h, --help              | show this help message and exit                       |
| --username USERNAME     | Username for the new account.                         |
| --password PASSWORD     | Force a given password instead of prompting.          |
| --email EMAIL           | Specifies the email for the admin.                    |
| --ssh-import SSH_IMPORT | Import SSH keys from Launchpad (lp:user-id) or Github |
|                         | (gh:user-id).                                         |

