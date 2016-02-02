# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Help functioners to send commissioning data to MAAS region."""

__all__ = [
    'encode_multipart_data',
    'geturl',
    ]

from email.utils import parsedate
import mimetypes
import random
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import oauthlib.oauth1 as oauth


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


def authenticate_headers(url, headers, creds, clockskew=0):
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


def _encode_field(field_name, data, boundary):
    assert isinstance(field_name, bytes)
    assert isinstance(data, bytes)
    assert isinstance(boundary, bytes)
    return (
        b'--' + boundary,
        b'Content-Disposition: form-data; name=\"' + field_name + b'\"',
        b'', data,
        )


def _encode_file(name, file, boundary):
    assert isinstance(name, str)
    assert isinstance(boundary, bytes)
    byte_name = name.encode("utf-8")
    return (
        b'--' + boundary,
        (
            b'Content-Disposition: form-data; name=\"' + byte_name + b'\"; ' +
            b'filename=\"' + byte_name + b'\"'
        ),
        b'Content-Type: ' + _get_content_type(name).encode("utf-8"),
        b'',
        file if isinstance(file, bytes) else file.read(),
        )


def _random_string(length):
    return b''.join(
        random.choice(string.ascii_letters).encode("ascii")
        for ii in range(length + 1)
    )


def _get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'


def encode_multipart_data(data, files):
    """Create a MIME multipart payload from L{data} and L{files}.

    @param data: A mapping of names (ASCII strings) to data (byte string).
    @param files: A mapping of names (ASCII strings) to file objects ready to
        be read.
    @return: A 2-tuple of C{(body, headers)}, where C{body} is a a byte string
        and C{headers} is a dict of headers to add to the enclosing request in
        which this payload will travel.
    """
    boundary = _random_string(30)

    lines = []
    for name in data:
        lines.extend(_encode_field(name, data[name], boundary))
    for name in files:
        lines.extend(_encode_file(name, files[name], boundary))
    lines.extend((b'--' + boundary + b'--', b''))
    body = b'\r\n'.join(lines)

    headers = {
        'Content-Type': (
            'multipart/form-data; boundary=' + boundary.decode("ascii")),
        'Content-Length': str(len(body)),
    }

    return body, headers
