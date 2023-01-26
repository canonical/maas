# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS configuration."""


from collections import namedtuple
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import errno
from functools import cached_property
import grp
import os
import os.path
from pathlib import Path
import re
import sys
from typing import Optional

from netaddr import AddrFormatError, IPAddress

from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import load_template, locate_config
from provisioningserver.utils.fs import atomic_write
from provisioningserver.utils.isc import read_isc_file
from provisioningserver.utils.shell import call_and_check
from provisioningserver.utils.snap import running_in_snap

maaslog = get_maas_logger("dns")
NAMED_CONF_OPTIONS = "named.conf.options"
MAAS_NAMED_CONF_NAME = "named.conf.maas"
MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME = "named.conf.options.inside.maas"
MAAS_NAMED_RNDC_CONF_NAME = "named.conf.rndc.maas"
MAAS_RNDC_CONF_NAME = "rndc.conf.maas"
MAAS_NSUPDATE_KEY_NAME = "keys.conf.maas"
MAAS_ZONE_FILE_DIR = "/var/lib/bind/maas"
MAAS_ZONE_FILE_GROUP = "bind"


@dataclass
class DynamicDNSUpdate:
    operation: str
    name: str
    zone: str
    rectype: str
    ttl: Optional[int] = None
    subnet: Optional[str] = None  # for reverse updates
    answer: Optional[str] = None

    @classmethod
    def create_from_trigger(cls, **kwargs):
        answer = kwargs.get("answer")
        rectype = kwargs.pop("rectype")
        if answer:
            del kwargs["answer"]
        # the DB trigger is unable to figure out if an IP is v6, so we do it here instead
        try:
            ip = IPAddress(answer)
        except AddrFormatError:
            pass
        else:
            if ip.version == 6:
                rectype = "AAAA"
        if kwargs.get("ttl") == 0:  # default ttl
            kwargs["ttl"] = 30
        return cls(answer=answer, rectype=rectype, **kwargs)

    @classmethod
    def as_reverse_record_update(cls, fwd_update, subnet):
        if not fwd_update.answer_is_ip:
            return None
        ip = IPAddress(fwd_update.answer)
        name = ip.reverse_dns
        if (
            ip.version == 4 and subnet.prefixlen > 24
        ) or subnet.prefixlen > 64:
            name = "in-addr.arpa."
            addr_split = fwd_update.answer.split(".")
            idx = len(addr_split) - 1
            for i, octet in enumerate(addr_split):
                if i == idx:
                    name = f"{octet}.0-{subnet.prefixlen}.{name}"
                else:
                    name = f"{octet}.{name}"

        return cls(
            operation=fwd_update.operation,
            name=name,
            zone=fwd_update.zone,
            subnet=str(subnet.cidr),
            ttl=fwd_update.ttl,
            answer=fwd_update.name,
            rectype="PTR",
        )

    @cached_property
    def answer_as_ip(self):
        try:
            return IPAddress(self.answer)
        except AddrFormatError:
            return None

    @cached_property
    def answer_is_ip(self):
        return self.answer_as_ip is not None


def get_dns_config_dir():
    """Location of MAAS' bind configuration files."""
    setting = os.getenv(
        "MAAS_DNS_CONFIG_DIR", locate_config(os.path.pardir, "bind", "maas")
    )
    if isinstance(setting, bytes):
        fsenc = sys.getfilesystemencoding()
        return setting.decode(fsenc)
    else:
        return setting


def get_zone_file_config_dir():
    """
    Location of MAAS' zone files, separate from config files
    so that bind can write to the location as well
    """
    setting = os.getenv("MAAS_ZONE_FILE_CONFIG_DIR", MAAS_ZONE_FILE_DIR)
    if isinstance(setting, bytes):
        fsenc = sys.getfilesystemencoding()
        setting = setting.decode(fsenc)
    return Path(setting)


def get_bind_config_dir():
    """Location of bind configuration files."""
    setting = os.getenv(
        "MAAS_BIND_CONFIG_DIR", locate_config(os.path.pardir, "bind")
    )
    if isinstance(setting, bytes):
        fsenc = sys.getfilesystemencoding()
        return setting.decode(fsenc)
    else:
        return setting


def get_dns_rndc_port():
    """RNDC port to be configured by MAAS to communicate with BIND."""
    setting = os.getenv("MAAS_DNS_RNDC_PORT", "954")
    return int(setting)


def get_dns_default_controls():
    """Include the default RNDC controls (default RNDC key on port 953)?"""
    if running_in_snap():
        # The default controls don't work in a confined snap, since it
        # implicitly requires access to /etc/bind
        return False
    setting = os.getenv("MAAS_DNS_DEFAULT_CONTROLS", "1")
    return setting == "1"


class DNSConfigDirectoryMissing(Exception):
    """The directory where the config was about to be written is missing."""


class DNSConfigFail(Exception):
    """Raised if there's a problem with a DNS config."""


SRVRecord = namedtuple(
    "SRVRecord", ["service", "priority", "weight", "port", "target"]
)


# Default 'controls' stanza to be included in the Bind configuration, to
# enable "remote" administration (well, only locally) for the init scripts,
# so that they can control the DNS daemon over port 953.
# This is in addition to a similar 'controls' stanza that allows MAAS itself
# to control the daemon.  That stanza is always present.
DEFAULT_CONTROLS = """
controls {
    inet 127.0.0.1 port 953 allow { localhost; };
};
"""


def extract_suggested_named_conf(rndc_content):
    """Extract 'named' configuration from the generated rndc configuration."""
    start_marker = (
        "# Use with the following in named.conf, adjusting the "
        "allow list as needed:\n"
    )
    end_marker = "# End of named.conf"
    named_start = rndc_content.index(start_marker) + len(start_marker)
    named_end = rndc_content.index(end_marker)
    return rndc_content[named_start:named_end]


def uncomment_named_conf(named_comment):
    """Return an uncommented version of the commented-out 'named' config."""
    return re.sub("^# ", "", named_comment, flags=re.MULTILINE)


def generate_rndc(
    port=953, key_name="rndc-maas-key", include_default_controls=True
):
    """Use `rndc-confgen` (from bind9utils) to generate a rndc+named
    configuration.

    `rndc-confgen` generates the rndc configuration which also contains, in
    the form of a comment, the 'named' configuration we need.
    """
    # Generate the configuration:
    # - 256 bits is the recommended size for the key nowadays.
    # - Use urandom to avoid blocking on the random generator.
    rndc_content = call_and_check(
        [
            "rndc-confgen",
            "-b",
            "256",
            "-k",
            key_name,
            "-p",
            str(port).encode("ascii"),
        ]
    )
    rndc_content = rndc_content.decode("ascii")
    named_comment = extract_suggested_named_conf(rndc_content)
    named_conf = uncomment_named_conf(named_comment)

    # The 'named' configuration contains a 'control' statement to enable
    # remote management by MAAS.  If appropriate, add one to enable remote
    # management by the init scripts as well.
    if include_default_controls:
        named_conf += DEFAULT_CONTROLS

    # Return a tuple of the two configurations.
    return rndc_content, named_conf


def get_named_rndc_conf_path():
    return compose_config_path(MAAS_NAMED_RNDC_CONF_NAME)


def get_rndc_conf_path():
    return compose_config_path(MAAS_RNDC_CONF_NAME)


def get_nsupdate_key_path():
    return compose_config_path(MAAS_NSUPDATE_KEY_NAME)


def set_up_nsupdate_key():
    tsig = call_and_check(["tsig-keygen", "-a", "HMAC-SHA512", "maas."])
    atomic_write(tsig, get_nsupdate_key_path(), overwrite=True, mode=0o644)


def clean_old_zone_files():
    for path in get_zone_file_config_dir().glob("zone.*"):
        if path.is_file():
            path.unlink()


def set_up_zone_file_dir():
    path = get_zone_file_config_dir()
    if not path.exists():
        path.mkdir(mode=0o775)

        uid = os.getuid()
        gid = 0
        group = grp.getgrnam(MAAS_ZONE_FILE_GROUP)
        if group:
            gid = group.gr_gid

        os.chown(path, uid, gid)
    else:
        clean_old_zone_files()


def set_up_rndc():
    """Writes out the two files needed to enable MAAS to use rndc commands:
    MAAS_RNDC_CONF_NAME and MAAS_NAMED_RNDC_CONF_NAME.
    """
    rndc_content, named_content = generate_rndc(
        port=get_dns_rndc_port(),
        include_default_controls=get_dns_default_controls(),
    )

    target_file = get_rndc_conf_path()
    with open(target_file, "w", encoding="ascii") as f:
        f.write(rndc_content)

    target_file = get_named_rndc_conf_path()
    with open(target_file, "w", encoding="ascii") as f:
        f.write(named_content)


def execute_rndc_command(arguments, timeout=None):
    """Execute a rndc command."""
    rndc_conf = get_rndc_conf_path()
    rndc_cmd = ["rndc", "-c", rndc_conf]
    rndc_cmd.extend(arguments)
    call_and_check(rndc_cmd, timeout=timeout)


def set_up_options_conf(overwrite=True, **kwargs):
    """Write out the named.conf.options.inside.maas file.

    This file should be included by the top-level named.conf.options
    inside its 'options' block.  MAAS cannot write the options file itself,
    so relies on either the DNSFixture in the test suite, or the packaging.
    Both should set that file up appropriately to include our file.
    """
    template = load_template("dns", "named.conf.options.inside.maas.template")

    # Make sure "upstream_dns" is set at least to None. It's a special piece
    # of config and we don't want to require that every call site has to
    # specify it. If it's not set, the substitution will fail with the default
    # template that uses this value.
    kwargs.setdefault("upstream_dns")
    kwargs.setdefault("dnssec_validation", "auto")

    # Parse the options file and make sure MAAS doesn't define any options
    # that the user has already customized.
    allow_user_override_options = [
        "allow-query",
        "allow-recursion",
        "allow-query-cache",
    ]

    try:
        parsed_options = read_isc_file(
            compose_bind_config_path(NAMED_CONF_OPTIONS)
        )
    except OSError:
        parsed_options = {}

    options = parsed_options.get("options", {})
    for option in allow_user_override_options:
        kwargs["upstream_" + option.replace("-", "_")] = option in options

    try:
        rendered = template.substitute(kwargs)
    except NameError as error:
        raise DNSConfigFail(*error.args)
    else:
        # The rendered configuration is Unicode text but should contain only
        # ASCII characters. Non-ASCII records should have been treated using
        # the rules for IDNA (Internationalized Domain Names in Applications).
        rendered = rendered.encode("ascii")

    target_path = compose_config_path(MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME)
    atomic_write(rendered, target_path, overwrite=overwrite, mode=0o644)


def compose_config_path(filename):
    """Return the full path for a DNS config"""
    return os.path.join(get_dns_config_dir(), filename)


def compose_zone_file_config_path(filename):
    return os.path.join(get_zone_file_config_dir(), filename)


def compose_bind_config_path(filename):
    """Return the full path for a DNS config"""
    return os.path.join(get_bind_config_dir(), filename)


def render_dns_template(template_name, *parameters):
    """Generate contents for a DNS configuration or zone file.

    :param template_name: Name of the template file that should be rendered.
        It must be in provisioningserver/templates/dns/.
    :param parameters: One or more dicts of paramaters to be passed to the
        template.  Each adds to (and may overwrite) the previous ones.
    """
    template = load_template("dns", template_name)
    combined_params = {}
    for params_dict in parameters:
        combined_params.update(params_dict)
    try:
        return template.substitute(combined_params)
    except NameError as error:
        raise DNSConfigFail(*error.args)


@contextmanager
def report_missing_config_dir():
    """Report missing DNS config dir as `DNSConfigDirectoryMissing`.

    Use this around code that writes a new DNS configuration or zone file.
    It catches a "no such file or directory" error and raises a more helpful
    `DNSConfigDirectoryMissing` in its place.
    """
    try:
        yield
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise DNSConfigDirectoryMissing(
                "The directory where the DNS config files should be "
                "written does not exist.  Make sure the 'maas-dns' "
                "package is installed on this region controller."
            )
        else:
            raise


class DNSConfig:
    """A DNS configuration file.

    Encapsulation of DNS config templates and parameter substitution.
    """

    template_file_name = "named.conf.template"
    target_file_name = MAAS_NAMED_CONF_NAME

    def __init__(self, zones=None, forwarded_zones=None):
        if zones is None:
            zones = ()
        if forwarded_zones is None:
            forwarded_zones = ()
        self.zones = zones
        self.forwarded_zones = forwarded_zones

    def write_config(self, overwrite=True, **kwargs):
        """Write out this DNS config file.

        :raises DNSConfigDirectoryMissing: if the DNS configuration directory
            does not exist.
        """
        trusted_networks = kwargs.pop("trusted_networks", "")
        context = {
            "zones": self.zones,
            "forwarded_zones": self.forwarded_zones,
            "DNS_CONFIG_DIR": get_dns_config_dir(),
            "named_rndc_conf_path": get_named_rndc_conf_path(),
            "nsupdate_keys_conf_path": get_nsupdate_key_path(),
            "trusted_networks": trusted_networks,
            "modified": str(datetime.today()),
        }
        content = render_dns_template(self.template_file_name, kwargs, context)
        # The rendered configuration is Unicode text but should contain only
        # ASCII characters. Non-ASCII records should have been treated using
        # the rules for IDNA (Internationalized Domain Names in Applications).
        content = content.encode("ascii")
        target_path = compose_config_path(self.target_file_name)
        with report_missing_config_dir():
            atomic_write(content, target_path, overwrite=overwrite, mode=0o644)

    @classmethod
    def get_include_snippet(cls):
        snippet = ""
        if isinstance(cls.target_file_name, list):
            target_file_names = cls.target_file_name
        else:
            target_file_names = [cls.target_file_name]
        for target_file_name in target_file_names:
            target_path = compose_config_path(target_file_name)
            if '"' in target_path:
                maaslog.error(
                    "DNS config path contains quote: %s." % target_path
                )
            else:
                snippet += 'include "%s";\n' % target_path
        return snippet
