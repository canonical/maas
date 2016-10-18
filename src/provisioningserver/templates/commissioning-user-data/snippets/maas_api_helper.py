__all__ = [
    'geturl',
    'read_config',
    ]

from email.utils import parsedate
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import oauthlib.oauth1 as oauth
import yaml


def read_config(url, creds):
    """Read cloud-init config from given `url` into `creds` dict.

    Updates any keys in `creds` that are None with their corresponding
    values in the config.

    Important keys include `metadata_url`, and the actual OAuth
    credentials.
    """
    if url.startswith("http://") or url.startswith("https://"):
        cfg_str = urllib.request.urlopen(urllib.request.Request(url=url))
    else:
        if url.startswith("file://"):
            url = url[7:]
        cfg_str = open(url, "r").read()

    cfg = yaml.safe_load(cfg_str)

    # Support reading cloud-init config for MAAS datasource.
    if 'datasource' in cfg:
        cfg = cfg['datasource']['MAAS']

    for key in creds.keys():
        if key in cfg and creds[key] is None:
            creds[key] = cfg[key]


def oauth_headers(url, consumer_key, token_key, token_secret, consumer_secret,
                  clockskew=0):
    """Build OAuth headers using given credentials."""
    timestamp = int(time.time()) + clockskew
    client = oauth.Client(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=token_key,
        resource_owner_secret=token_secret,
        signature_method=oauth.SIGNATURE_PLAINTEXT,
        timestamp=str(timestamp))
    uri, signed_headers, body = client.sign(url)
    return signed_headers


def authenticate_headers(url, headers, creds, clockskew):
    """Update and sign a dict of request headers."""
    if creds.get('consumer_key', None) is not None:
        headers.update(oauth_headers(
            url,
            consumer_key=creds['consumer_key'],
            token_key=creds['token_key'],
            token_secret=creds['token_secret'],
            consumer_secret=creds['consumer_secret'],
            clockskew=clockskew))


def warn(msg):
    sys.stderr.write(msg + "\n")


def geturl(url, creds, headers=None, data=None):
    # Takes a dict of creds to be passed through to oauth_headers,
    #   so it should have consumer_key, token_key, ...
    if headers is None:
        headers = {}
    else:
        headers = dict(headers)

    clockskew = 0

    error = Exception("Unexpected Error")
    for naptime in (1, 1, 2, 4, 8, 16, 32):
        authenticate_headers(url, headers, creds, clockskew)
        try:
            req = urllib.request.Request(url=url, data=data, headers=headers)
            return urllib.request.urlopen(req).read()
        except urllib.error.HTTPError as exc:
            error = exc
            if 'date' not in exc.headers:
                warn("date field not in %d headers" % exc.code)
                pass
            elif exc.code in (401, 403):
                date = exc.headers['date']
                try:
                    ret_time = time.mktime(parsedate(date))
                    clockskew = int(ret_time - time.time())
                    warn("updated clock skew to %d" % clockskew)
                except:
                    warn("failed to convert date '%s'" % date)
        except Exception as exc:
            error = exc

        warn("request to %s failed. sleeping %d.: %s" % (url, naptime, error))
        time.sleep(naptime)

    raise error
