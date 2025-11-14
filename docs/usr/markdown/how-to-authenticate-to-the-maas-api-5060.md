The MAAS API uses 0-legged OAuth for authentication.  Some endpoints can be accessed anonymously, but most require authenticated requests.  This page shows how to make authenticated API calls in different languages and tools.


## Your API key
Your API key has the format:

```
<consumer_key>:<consumer_token>:<secret>
```

Split this key into its components and pass them to your client library or tool.


## Python example
This example uses the `fades` library, but you can also use `requests_oauthlib` and `oauthlib`.  Replace `<MAAS_SERVER_IP>` and `<API-KEY>` with your own values.

```nohighlight
from oauthlib.oauth1 import SIGNATURE_PLAINTEXT
from requests_oauthlib import OAuth1Session

MAAS_HOST = "http://<MAAS_SERVER_IP>:5240/MAAS"
CONSUMER_KEY, CONSUMER_TOKEN, SECRET = "<API-KEY>".split(":")

maas = OAuth1Session(CONSUMER_KEY, resource_owner_key=CONSUMER_TOKEN, resource_owner_secret=SECRET, signature_method=SIGNATURE_PLAINTEXT)
nodes = maas.get(f"{MAAS_HOST}/api/2.0/machines/", params={"op": "list_allocated"})
nodes.raise_for_status()
print(nodes.json())
```


## Ruby example

```nohighlight
require 'oauth'
require 'oauth/signature/plaintext'

def perform_API_request(site, uri, key, secret, consumer_key)
    consumer = OAuth::Consumer.new(consumer_key, "", { :site => site, :scheme => :header, :signature_method => "PLAINTEXT"})
    access_token = OAuth::AccessToken.new(consumer, key, secret)
    return access_token.request(:get, uri)
end
response = perform_API_request("http://server:5240/MAAS/api/2.0", "/nodes/?op=list", "<key>", "<secret>", "consumer_key")
```


## cURL example

```nohighlight
curl --header "Authorization: OAuth oauth_version=1.0, oauth_signature_method=PLAINTEXT, oauth_consumer_key=$API_KEY[1], oauth_token=$API_KEY[2], oauth_signature=&$API_KEY[3], oauth_nonce=$(uuidgen), oauth_timestamp=$(date +%s)" $MAAS_URL/MAAS/api/2.0/users/
```


## HTTPie + fish shell example

```nohighlight
set API_KEY (string split : $API_KEY)
http $MAAS_URL/api/2.0/users/ Authorization:"OAuth oauth_version=1.0, oauth_signature_method=PLAINTEXT, oauth_consumer_key=$API_KEY[1], oauth_token=$API_KEY[2], oauth_signature=&$API_KEY[3], oauth_nonce=$(uuidgen), oauth_timestamp=$(date +%s)"
```


## Next steps
- Learn more about [MAAS API endpoints](https://canonical.com/maas/docs/api).
- Learn how to login to the [MAAS CLI](https://canonical.com/maas/docs/login).
