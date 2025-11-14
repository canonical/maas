Create an authorisation token

```bash
maas $PROFILE account create-authorisation-token [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create an authorisation OAuth token and OAuth consumer.

##### Keyword "name"
Optional String. name of the token that<br>will be generated.


Note: This command accepts JSON.


Delete an authorisation token

```bash
maas $PROFILE account delete-authorisation-token [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete an authorisation OAuth token and the related OAuth<br>consumer.

##### Keyword "token_key"
Optional String. The key of the token to be<br>deleted.


Note: This command accepts JSON.


List authorisation tokens

```bash
maas $PROFILE account list-authorisation-tokens [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List authorisation tokens available to the currently<br>logged-in user.





Modify authorisation token

```bash
maas $PROFILE account update-token-name [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Modify the consumer name of an authorisation OAuth token.

##### Keyword "token"
Optional String. Can be the whole token or only<br>the token key.
##### Keyword "name"
Optional String. New name of the token.


Note: This command accepts JSON.
