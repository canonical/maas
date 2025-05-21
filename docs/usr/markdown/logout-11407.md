Log out of a remote API, purging any stored credentials.

```bash
maas logout [-h] profile-name 
```

#### Positional arguments 
| Argument     | Effect                                                      |
|--------------|-------------------------------------------------------------|
| profile-name | The name with which a remote server and its credentials are |
|              | referred to within this tool.                               |

#### Command-line options
| Option     | Effect                          |
|------------|---------------------------------|
| -h, --help | show this help message and exit |

This will remove the given profile from your command-line  client.  You can re-create it by logging in again later.

