# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Help functioners to send commissioning data to MAAS region."""


from collections import OrderedDict
from email.utils import parsedate
import json
import mimetypes
import os
from pathlib import Path
import platform
import random
import re
import selectors
import socket
import string
from subprocess import TimeoutExpired
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import oauthlib.oauth1 as oauth
import yaml

# Current MAAS metadata API version.
MD_VERSION = "2012-03-01"


# See fcntl(2), re. F_SETPIPE_SZ. By requesting this many bytes from a pipe on
# each read we can be sure that we are always draining its buffer completely.
PIPE_MAX_SIZE = int(Path("/proc/sys/fs/pipe-max-size").read_text())


class InvalidCredentialsFormat(Exception):
    """Raised when OAuth credentials string is in wrong format."""


# This would be a dataclass, but needs to support python3.5
class Credentials:
    KEYS = frozenset(
        ("token_key", "token_secret", "consumer_key", "consumer_secret")
    )

    _STRING_RE = re.compile(
        r"(?P<consumer_key>[^:]+)"
        r":(?P<token_key>[^:]+)"
        r":(?P<token_secret>[^:]+)"
        r"(:(?P<consumer_secret>[^:]+))?"
        r"$",
    )

    def __init__(self, **kwargs):
        for key in self.KEYS:
            setattr(self, key, kwargs.get(key) or "")

    def __eq__(self, other):
        return all(
            getattr(self, key) == getattr(other, key) for key in self.KEYS
        )

    def __bool__(self):
        return any(getattr(self, key) for key in self.KEYS)

    def __repr__(self):
        return "{name}({keys})".format(
            name=self.__class__.__name__,
            keys=", ".join(f"{key}={getattr(self, key)}" for key in self.KEYS),
        )

    @classmethod
    def from_string(cls, string):
        if not string:
            return cls()
        match = cls._STRING_RE.match(string)
        if not match:
            raise InvalidCredentialsFormat("Invalid OAuth credentials format")
        return cls(**match.groupdict())

    def update(self, config):
        """Update credentials from a config dict.

        Only empty keys are updated.
        """
        for key in self.KEYS:
            if key in config and not getattr(self, key, None):
                setattr(self, key, config[key])

    def oauth_headers(self, url, clockskew=0):
        """Return OAuth headers for credentials."""
        if not self.consumer_key:
            return {}

        timestamp = int(time.time()) + clockskew
        client = oauth.Client(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.token_key,
            resource_owner_secret=self.token_secret,
            signature_method=oauth.SIGNATURE_PLAINTEXT,
            timestamp=str(timestamp),
        )
        uri, signed_headers, body = client.sign(url)
        return signed_headers


class Config:
    def __init__(self, config=None, credentials=None):
        self.credentials = credentials or Credentials()
        self.metadata_url = None
        self.config_path = None
        if config:
            self.update(config)

    def update(self, config):
        """Update values from a config dict.

        Updates only values that are None with their corresponding values in
        the config.
        """
        # Support reading cloud-init config for MAAS datasource.
        if "datasource" in config:
            config = config["datasource"]["MAAS"]

        for key in ("metadata_url", "config_path"):
            if key in config and getattr(self, key, None) is None:
                setattr(self, key, config[key])

        if self.config_path is not None:
            self.config_path = Path(self.config_path)

        self.credentials.update(config)

    def update_from_url(self, url):
        """Read cloud-init config from given `url`.

        Updates only values that are None with their corresponding values in
        the config.
        """
        if url.startswith("http://") or url.startswith("https://"):
            data = urllib.request.urlopen(urllib.request.Request(url=url))
        else:
            if url.startswith("file://"):
                url = url[7:]
            data = Path(url).read_text()

        self.update(yaml.safe_load(data))


def debian_architecture():
    """Return the Debian architecture name for the machine."""
    kernel_to_debian_arches = {
        "i686": "i386",
        "x86_64": "amd64",
        "aarch64": "arm64",
        "ppc64le": "ppc64el",
        "s390x": "s390x",
        "mips": "mips",
        "mips64": "mips64el",
    }
    return kernel_to_debian_arches.get(platform.machine())


def warn(msg):
    sys.stderr.write(msg + "\n")


def get_base_url(url):
    """Return the base URL (no path) for the specified URL."""
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, "", "", "", "")
    )


def geturl(
    url, credentials=None, headers=None, data=None, post_data=None, retry=True
):
    # This would be a dataclass, but needs to support python3.5
    class ExecuteState:
        def __init__(self, headers=None):
            self.headers = dict(headers) if headers else {}
            self.clockskew = 0

    def execute(url, data, post_data, state):
        state.headers.update(credentials.oauth_headers(url, state.clockskew))
        try:
            req = urllib.request.Request(
                url=url, data=data, headers=state.headers
            )
            return urllib.request.urlopen(req, data=post_data)
        except urllib.error.HTTPError as exc:
            if "date" not in exc.headers:
                warn("date field not in %d headers" % exc.code)
            elif exc.code in (401, 403):
                date = exc.headers["date"]
                try:
                    ret_time = time.mktime(parsedate(date))
                    state.clockskew = int(ret_time - time.time())
                    warn("updated clock skew to %d" % state.clockskew)
                except Exception:
                    warn("failed to convert date '%s'" % date)
                    raise
            raise

    if credentials is None:
        credentials = Credentials()
    if post_data:
        post_data = urllib.parse.urlencode(post_data)
        post_data = post_data.encode("ascii")

    state = ExecuteState(headers=headers)

    if retry:
        error = None
        for naptime in (1, 1, 2, 4, 8, 16, 32, 0):
            try:
                return execute(url, data, post_data, state)
            except Exception as e:
                error = e
                warn(
                    "request to %s failed. sleeping %d.: %s"
                    % (url, naptime, error)
                )
                time.sleep(naptime)
        if error:
            raise error
    else:
        return execute(url, data, post_data, state)


def _encode_field(field_name, data, boundary):
    assert isinstance(field_name, bytes)
    assert isinstance(data, bytes)
    assert isinstance(boundary, bytes)
    return (
        b"--" + boundary,
        b'Content-Disposition: form-data; name="' + field_name + b'"',
        b"",
        data,
    )


def _encode_file(name, file, boundary):
    assert isinstance(name, str)
    assert isinstance(boundary, bytes)
    byte_name = name.encode("utf-8")
    return (
        b"--" + boundary,
        (
            b'Content-Disposition: form-data; name="'
            + byte_name
            + b'"; '
            + b'filename="'
            + byte_name
            + b'"'
        ),
        b"Content-Type: " + _get_content_type(name).encode("utf-8"),
        b"",
        file if isinstance(file, bytes) else file.read(),
    )


def _random_string(length):
    return b"".join(
        random.choice(string.ascii_letters).encode("ascii")
        for ii in range(length + 1)
    )


def _get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def encode_multipart_data(data, files=None):
    """Create a MIME multipart payload from L{data} and L{files}.

    @param data: A mapping of names (ASCII strings) to data (byte string).
    @param files: A mapping of names (ASCII strings) to file objects ready to
        be read.
    @return: A 2-tuple of C{(body, headers)}, where C{body} is a a byte string
        and C{headers} is a dict of headers to add to the enclosing request in
        which this payload will travel.
    """
    if not files:
        files = {}
    boundary = _random_string(30)

    lines = []
    for name in data:
        lines.extend(_encode_field(name, data[name], boundary))
    for name in files:
        lines.extend(_encode_file(name, files[name], boundary))
    lines.extend((b"--" + boundary + b"--", b""))
    body = b"\r\n".join(lines)

    headers = {
        "Content-Type": (
            "multipart/form-data; boundary=" + boundary.decode("ascii")
        ),
        "Content-Length": str(len(body)),
    }

    return body, headers


class SignalException(Exception):
    pass


def signal(
    url,
    credentials,
    status,
    error=None,
    script_name=None,
    script_result_id=None,
    files: dict = None,
    runtime=None,
    exit_status=None,
    script_version_id=None,
    power_type=None,
    power_params=None,
    retry=True,
):
    """Send a node signal to a given maas_url."""
    params = {b"op": b"signal", b"status": status.encode("utf-8")}

    if error is not None:
        params[b"error"] = error.encode("utf-8")

    if script_result_id is not None:
        params[b"script_result_id"] = str(script_result_id).encode("utf-8")

    if runtime is not None:
        params[b"runtime"] = str(runtime).encode("utf-8")

    if exit_status is not None:
        params[b"exit_status"] = str(exit_status).encode("utf-8")

    if script_name is not None:
        params[b"name"] = str(script_name).encode("utf-8")

    if script_version_id is not None:
        params[b"script_version_id"] = str(script_version_id).encode("utf-8")

    if None not in (power_type, power_params):
        params[b"power_type"] = power_type.encode("utf-8")
        # XXX ltrager - 2020-08-18 - Assume dict once BMC detection scripts
        # have been converted into commissioning scripts.
        if not isinstance(power_params, dict):
            if power_type == "moonshot":
                user, power_pass, power_address, driver = power_params.split(
                    ","
                )
            else:
                (
                    user,
                    power_pass,
                    power_address,
                    driver,
                    boot_type,
                ) = power_params.split(",")
            # OrderedDict is used to make testing easier.
            power_params = OrderedDict(
                [
                    ("power_user", user),
                    ("power_pass", power_pass),
                    ("power_address", power_address),
                ]
            )
            if power_type == "moonshot":
                power_params["power_hwaddress"] = driver
            else:
                power_params["power_driver"] = driver
                power_params["power_boot_type"] = boot_type
        params[b"power_parameters"] = json.dumps(power_params).encode()

    data, headers = encode_multipart_data(params, files=files)

    try:
        ret = geturl(
            url,
            credentials=credentials,
            headers=headers,
            data=data,
            retry=retry,
        )
        if ret.status != 200:
            raise SignalException(
                "Unexpected status(%d) sending region commissioning data: %s"
                % (ret.status, ret.read().decode())
            )
    except urllib.error.HTTPError as exc:
        raise SignalException("HTTP error [%s]" % exc.code)
    except urllib.error.URLError as exc:
        raise SignalException("URL error [%s]" % exc.reason)
    except socket.timeout as exc:
        raise SignalException("Socket timeout [%s]" % exc)
    except TypeError as exc:
        raise SignalException(str(exc))
    except Exception as exc:
        raise SignalException("Unexpected error [%s]" % exc)


def capture_script_output(
    proc,
    combined_path,
    stdout_path,
    stderr_path,
    timeout_seconds=None,
    console_output=None,
):
    """Capture stdout and stderr from `proc`.

    Standard output is written to a file named by `stdout_path`, and standard
    error is written to a file named by `stderr_path`. Both are also written
    to a file named by `combined_path`.

    If the given subprocess forks additional processes, and these write to the
    same stdout and stderr, their output will be captured only as long as
    `proc` is running.

    Optionally a timeout can be given in seconds. This time is padded by 5
    minutes to allow for script cleanup. If the script runs past the timeout
    the process is killed and an exception is raised. Forked processes are not
    subject to the timeout.

    If console_output is set to True or False, script output/error will be
    printed or not accordingly. By default, it's printed output is a tty.

    :return: The exit code of `proc`.

    """
    if timeout_seconds in (None, 0):
        timeout = None
    else:
        # Pad the timeout by 5 minutes to allow for cleanup.
        timeout = time.monotonic() + timeout_seconds + (60 * 5)

    stdout_path = Path(stdout_path)
    stderr_path = Path(stderr_path)
    combined_path = Path(combined_path)
    # Create the file and then open it in read write mode for terminal
    # emulation.
    for path in (stdout_path, stderr_path, combined_path):
        path.touch()
    with stdout_path.open("r+b") as out, stderr_path.open("r+b") as err:
        with combined_path.open("r+b") as combined:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ, out)
                selector.register(proc.stderr, selectors.EVENT_READ, err)
                while selector.get_map() and proc.poll() is None:
                    # Select with a short timeout so that we don't tight loop.
                    _select_script_output(
                        selector, combined, 0.1, proc, console_output
                    )
                    if timeout is not None and time.monotonic() > timeout:
                        break
                # Process has finished or has closed stdout and stderr.
                # Process anything still sitting in the latter's buffers.
                _select_script_output(
                    selector, combined, 0.0, proc, console_output
                )

    now = time.monotonic()
    # Wait for the process to finish.
    if timeout is None:
        # No timeout just wait until the process finishes.
        return proc.wait()
    elif now >= timeout:
        # Loop above detected time out execeed, kill the process.
        proc.kill()
        raise TimeoutExpired(proc.args, timeout_seconds)
    else:
        # stdout and stderr have been closed but the timeout has not been
        # exceeded. Run with the remaining amount of time.
        try:
            return proc.wait(timeout=(timeout - now))
        except TimeoutExpired:
            # Make sure the process was killed
            proc.kill()
            raise


def _select_script_output(selector, combined, timeout, proc, console_output):
    """Helper for `capture_script_output`."""
    if console_output is None:
        console_output = sys.stdout.isatty()

    for key, event in selector.select(timeout):
        if event & selectors.EVENT_READ:
            # Read from the _raw_ file. Ordinarily Python blocks until a
            # read(n) returns n bytes or the stream reaches end-of-file,
            # but here we only want to get what's there without blocking.
            chunk = key.fileobj.raw.read(PIPE_MAX_SIZE)
            if not chunk:  # EOF
                selector.unregister(key.fileobj)
            else:
                # Output to console if specified
                if chunk != b"" and console_output:
                    fd = (
                        sys.stdout
                        if key.fileobj == proc.stdout
                        else sys.stderr
                    )
                    fd.write(chunk.decode())
                    fd.flush()

                # The list comprehension is needed to get byte objects instead
                # of their numeric value.
                for i in [chunk[i : i + 1] for i in range(len(chunk))]:
                    for f in [key.data, combined]:
                        # Some applications don't properly detect that they are
                        # not being run in a terminal and refresh output for
                        # progress bars, counters, and spinners. These
                        # characters quickly add up making the log difficult to
                        # read. When writing output from an application emulate
                        # a terminal so readable data is captured.
                        if i == b"\b":
                            # Backspace - Go back one space, if we can.
                            if f.tell() != 0:
                                f.seek(-1, os.SEEK_CUR)
                        elif i == b"\r":
                            # Carriage return - Seek to the beginning of the
                            # line, as indicated by a line feed, or file.
                            while f.tell() != 0:
                                f.seek(-1, os.SEEK_CUR)
                                if f.read(1) == b"\n":
                                    # Check if line feed was found.
                                    break
                                else:
                                    # The read advances the file position by
                                    # one so seek back again.
                                    f.seek(-1, os.SEEK_CUR)
                        elif i == b"\n":
                            # Line feed - Some applications do a carriage
                            # return and then a line feed. The data on the line
                            # should be saved, not overwritten.
                            f.seek(0, os.SEEK_END)
                            f.write(i)
                            f.flush()
                        else:
                            f.write(i)
                            f.flush()
