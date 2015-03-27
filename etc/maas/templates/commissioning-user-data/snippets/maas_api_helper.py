from __future__ import (
    absolute_import,
    print_function,
    # unicode_literals,
    )

str = None

__metaclass__ = type

from email.utils import parsedate
import sys
import time
import urllib2
import uuid

import oauth.oauth as oauth
import yaml


__all__ = [
    'geturl',
    'read_config',
    ]


def read_config(url, creds):
    """Read cloud-init config from given `url` into `creds` dict.

    Updates any keys in `creds` that are None with their corresponding
    values in the config.

    Important keys include `metadata_url`, and the actual OAuth
    credentials.
    """
    if url.startswith("http://") or url.startswith("https://"):
        cfg_str = urllib2.urlopen(urllib2.Request(url=url))
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
    consumer = oauth.OAuthConsumer(consumer_key, consumer_secret)
    token = oauth.OAuthToken(token_key, token_secret)

    timestamp = int(time.time()) + clockskew

    params = {
        'oauth_version': "1.0",
        'oauth_nonce': uuid.uuid4().get_hex(),
        'oauth_timestamp': timestamp,
        'oauth_token': token.key,
        'oauth_consumer_key': consumer.key,
    }
    req = oauth.OAuthRequest(http_url=url, parameters=params)
    req.sign_request(
        oauth.OAuthSignatureMethod_PLAINTEXT(), consumer, token)
    return(req.to_header())


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

    exc = Exception("Unexpected Error")
    for naptime in (1, 1, 2, 4, 8, 16, 32):
        authenticate_headers(url, headers, creds, clockskew)
        try:
            req = urllib2.Request(url=url, data=data, headers=headers)
            return urllib2.urlopen(req).read()
        except urllib2.HTTPError as exc:
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
            pass

        warn("request to %s failed. sleeping %d.: %s" % (url, naptime, exc))
        time.sleep(naptime)

    raise exc
