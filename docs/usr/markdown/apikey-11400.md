Manage a user's API keys. Shows existing keys unless --generate or --delete is passed.

```bash
maas apikey [-h] [--username USERNAME] [--generate] [--delete DELETE] [--update UPDATE] [--name API_KEY_NAME] [--with-names]
```

#### Command-line options 
| Option              | Effect                                               |
|---------------------|------------------------------------------------------|
| -h, --help          | show this help message and exit                      |
| --username USERNAME | Specifies the username for the admin                 |
| --generate          | Generate a new api key                               |
| --delete DELETE     | Delete the supplied api key                          |
| --update UPDATE     | Update the supplied api key name                     |
| --name API_KEY_NAME | Name of the token. This argument should be passed to |
|                     | --update or --generate options                       |
| --with-names        | Display tokens with their names                      |
|                     |                                                      |

