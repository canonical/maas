MAAS API utilises 0-legged OAuth for authentication. While some endpoints allow anonymous access, others require authenticated requests. This page provides examples in Python, Ruby, curl, and HTTP for fetching the list of nodes.

## Python
 
The example employs the `fades` library, but you can also use `requests_oauthlib` and `oauthlib`. Replace `<MAAS_SERVER_IP>` and `<API-KEY>` with appropriate values.

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

## Ruby

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

## cURL

```nohighlight
curl --header "Authorization: OAuth oauth_version=1.0, oauth_signature_method=PLAINTEXT, oauth_consumer_key=$API_KEY[1], oauth_token=$API_KEY[2], oauth_signature=&$API_KEY[3], oauth_nonce=$(uuidgen), oauth_timestamp=$(date +%s)" $MAAS_URL/MAAS/api/2.0/users/
```

## HTTPie and fish

```nohighlight
set API_KEY (string split : $API_KEY)
http $MAAS_URL/api/2.0/users/ Authorization:"OAuth oauth_version=1.0, oauth_signature_method=PLAINTEXT, oauth_consumer_key=$API_KEY[1], oauth_token=$API_KEY[2], oauth_signature=&$API_KEY[3], oauth_nonce=$(uuidgen), oauth_timestamp=$(date +%s)"
```

Your API key comprises `<consumer_key>:<consumer_token>:<secret>`; use it to perform authenticated requests.
