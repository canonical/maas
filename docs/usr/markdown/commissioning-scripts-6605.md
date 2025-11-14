Delete a commissioning script. This operation has been deprecated in favour of &#39;Node-Script delete&#39;.

```bash
maas $PROFILE commissioning-script delete [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |






Read a commissioning script. This operation has been deprecated in favour of &#39;Node-Script read&#39;.

```bash
maas $PROFILE commissioning-script read [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |






Update a commissioning script. This operation has been deprecated in favour of &#39;Node-Script update&#39;.

```bash
maas $PROFILE commissioning-script update [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |






Create a new commissioning script.

```bash
maas $PROFILE commissioning-scripts create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Each commissioning script is identified by a unique name. By convention the name should consist of a two-digit number, a dash,<br>        and a brief descriptive identifier consisting only of ASCII<br>        characters. You don't need to follow this convention, but not doing<br>        so opens you up to risks w.r.t. encoding and ordering. The name must<br>        not contain any whitespace, quotes, or apostrophes. A commissioning machine will run each of the scripts in lexicographical<br>        order. There are no promises about how non-ASCII characters are<br>        sorted, or even how upper-case letters are sorted relative to<br>        lower-case letters. So where ordering matters, use unique numbers. Scripts built into MAAS will have names starting with “00-maas” or<br>        “99-maas” to ensure that they run first or last, respectively. Usually a commissioning script will be just that, a script. Ideally a<br>        script should be ASCII text to avoid any confusion over encoding. But<br>        in some cases a commissioning script might consist of a binary tool<br>        provided by a hardware vendor. Either way, the script gets passed to<br>        the commissioning machine in the exact form in which it was uploaded.

##### Keyword "name"
Optional. Unique identifying name for the script. Names should<br>follow the pattern of “25-burn-in-hard-disk” (all ASCII, and with<br>numbers greater than zero, and generally no “weird” characters).
##### Keyword "content"
Optional. A script file, to be uploaded in binary form. Note:<br>this is not a normal parameter, but a file upload. Its filename<br>is ignored; MAAS will know it by the name you pass to the request. This operation has been deprecated in favour of 'Node-Scripts create'.


Note: This command accepts JSON.


List commissioning scripts. This operation has been deprecated in favour of &#39;Node-Scripts read&#39;.

```bash
maas $PROFILE commissioning-scripts read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |
