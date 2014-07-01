# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'DNSConfig',
    'DNSForwardZoneConfig',
    'DNSReverseZoneConfig',
    'MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME',
    'setup_rndc',
    'set_up_options_conf',
    ]


from abc import ABCMeta
from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime
import errno
from itertools import chain
import math
import os.path
import re

from celery.app import app_or_default
from netaddr import IPAddress
from netaddr.core import AddrFormatError
from provisioningserver.utils import (
    atomic_write,
    call_and_check,
    incremental_write,
    locate_config,
    )
import tempita


MAAS_NAMED_CONF_NAME = 'named.conf.maas'
MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME = 'named.conf.options.inside.maas'
MAAS_NAMED_RNDC_CONF_NAME = 'named.conf.rndc.maas'
MAAS_RNDC_CONF_NAME = 'rndc.conf.maas'


conf = app_or_default().conf


class DNSConfigDirectoryMissing(Exception):
    """The directory where the config was about to be written is missing."""


class DNSConfigFail(Exception):
    """Raised if there's a problem with a DNS config."""


SRVRecord = namedtuple('SRVRecord', [
    'service',
    'priority',
    'weight',
    'port',
    'target'
    ])


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
        "allow list as needed:\n")
    end_marker = '# End of named.conf'
    named_start = rndc_content.index(start_marker) + len(start_marker)
    named_end = rndc_content.index(end_marker)
    return rndc_content[named_start:named_end]


def uncomment_named_conf(named_comment):
    """Return an uncommented version of the commented-out 'named' config."""
    return re.sub('^# ', '', named_comment, flags=re.MULTILINE)


def generate_rndc(port=953, key_name='rndc-maas-key',
                  include_default_controls=True):
    """Use `rndc-confgen` (from bind9utils) to generate a rndc+named
    configuration.

    `rndc-confgen` generates the rndc configuration which also contains, in
    the form of a comment, the 'named' configuration we need.
    """
    # Generate the configuration:
    # - 256 bits is the recommended size for the key nowadays.
    # - Use urandom to avoid blocking on the random generator.
    rndc_content = call_and_check(
        ['rndc-confgen', '-b', '256', '-r', '/dev/urandom',
         '-k', key_name, '-p', unicode(port).encode("ascii")])
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


def setup_rndc():
    """Writes out the two files needed to enable MAAS to use rndc commands:
    MAAS_RNDC_CONF_NAME and MAAS_NAMED_RNDC_CONF_NAME, both stored in
    conf.DNS_CONFIG_DIR.
    """
    rndc_content, named_content = generate_rndc(
        port=conf.DNS_RNDC_PORT,
        include_default_controls=conf.DNS_DEFAULT_CONTROLS)

    target_file = get_rndc_conf_path()
    with open(target_file, "wb") as f:
        f.write(rndc_content)

    target_file = get_named_rndc_conf_path()
    with open(target_file, "wb") as f:
        f.write(named_content)


def execute_rndc_command(arguments):
    """Execute a rndc command."""
    rndc_conf = get_rndc_conf_path()
    rndc_cmd = ['rndc', '-c', rndc_conf]
    rndc_cmd.extend(arguments)
    call_and_check(rndc_cmd)


# Location of DNS templates, relative to the configuration directory.
TEMPLATES_DIR = 'templates/dns'


def set_up_options_conf(overwrite=True, **kwargs):
    """Write out the named.conf.options.inside.maas file.

    This file should be included by the top-level named.conf.options
    inside its 'options' block.  MAAS cannot write the options file itself,
    so relies on either the DNSFixture in the test suite, or the packaging.
    Both should set that file up appropriately to include our file.
    """
    template_path = os.path.join(
        locate_config(TEMPLATES_DIR),
        "named.conf.options.inside.maas.template")
    template = tempita.Template.from_filename(template_path)

    # Make sure "upstream_dns" is set at least to None.  It's a
    # special piece of config that can't be obtained in celery
    # task code and we don't want to require that every call site
    # has to specify it.  If it's not set, the substitution will
    # fail with the default template that uses this value.
    kwargs.setdefault("upstream_dns")
    try:
        rendered = template.substitute(kwargs)
    except NameError as error:
        raise DNSConfigFail(*error.args)

    target_path = compose_config_path(MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME)
    atomic_write(rendered, target_path, overwrite=overwrite, mode=0644)


def compose_config_path(filename):
    """Return the full path for a DNS config or zone file."""
    return os.path.join(conf.DNS_CONFIG_DIR, filename)


def render_dns_template(template_name, *parameters):
    """Generate contents for a DNS configuration or zone file.

    :param template_name: Name of the template file that should be rendered.
        It must be in `TEMPLATES_DIR`.
    :param parameters: One or more dicts of paramaters to be passed to the
        template.  Each adds to (and may overwrite) the previous ones.
    """
    template_path = locate_config(TEMPLATES_DIR, template_name)
    template = tempita.Template.from_filename(template_path)
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
    except (IOError, OSError) as e:
        if e.errno == errno.ENOENT:
            raise DNSConfigDirectoryMissing(
                "The directory where the DNS config files should be "
                "written does not exist.  Make sure the 'maas-dns' "
                "package is installed on this region controller.")
        else:
            raise


def get_fqdn_or_ip_address(target):
    """Returns the ip address is target is a valid ip address, otherwise
    returns the target with appended '.' if missing."""
    try:
        return IPAddress(target).format()
    except AddrFormatError:
        return target.rstrip('.') + '.'


class DNSConfig:
    """A DNS configuration file.

    Encapsulation of DNS config templates and parameter substitution.
    """

    template_file_name = 'named.conf.template'
    target_file_name = MAAS_NAMED_CONF_NAME

    def __init__(self, zones=None):
        if zones is None:
            zones = ()
        self.zones = zones

    def write_config(self, overwrite=True, **kwargs):
        """Write out this DNS config file.

        :raises DNSConfigDirectoryMissing: if the DNS configuration directory
            does not exist.
        """
        context = {
            'zones': self.zones,
            'DNS_CONFIG_DIR': conf.DNS_CONFIG_DIR,
            'named_rndc_conf_path': get_named_rndc_conf_path(),
            'modified': unicode(datetime.today()),
        }
        content = render_dns_template(self.template_file_name, kwargs, context)
        target_path = compose_config_path(self.target_file_name)
        with report_missing_config_dir():
            atomic_write(content, target_path, overwrite=overwrite, mode=0644)

    @classmethod
    def get_include_snippet(cls):
        target_path = compose_config_path(cls.target_file_name)
        assert '"' not in target_path, (
            "DNS config path contains quote: %s." % target_path)
        return 'include "%s";\n' % target_path


class DNSZoneConfigBase:
    """Base class for zone writers."""

    __metaclass__ = ABCMeta

    template_file_name = 'zone.template'

    def __init__(self, domain, zone_name, serial=None):
        """
        :param domain: The domain name of the forward zone.
        :param zone_name: Fully-qualified zone name.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        """
        self.domain = domain
        self.zone_name = zone_name
        self.serial = serial
        self.target_path = compose_config_path('zone.%s' % self.zone_name)

    def make_parameters(self):
        """Return a dict of the common template parameters."""
        return {
            'domain': self.domain,
            'serial': self.serial,
            'modified': unicode(datetime.today()),
        }

    @classmethod
    def write_zone_file(cls, output_file, *parameters):
        """Write a zone file based on the zone file template.

        There is a subtlety with zone files: their filesystem timestamp must
        increase with every rewrite.  Some filesystems (ext3?) only seem to
        support a resolution of one second, and so this method may set an
        unexpected modification time in order to maintain that property.
        """
        content = render_dns_template(cls.template_file_name, *parameters)
        with report_missing_config_dir():
            incremental_write(content, output_file, mode=0644)


class DNSForwardZoneConfig(DNSZoneConfigBase):
    """Writes forward zone files.

    A forward zone config contains two kinds of mappings: "A" records map all
    possible IP addresses within each of its networks to generated hostnames
    based on those addresses.  "CNAME" records map configured hostnames to the
    matching generated IP hostnames.  An additional "A" record maps the domain
    to the name server itself.
    """

    def __init__(self, domain, **kwargs):
        """See `DNSZoneConfigBase.__init__`.

        :param domain: The domain name of the forward zone.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        :param dns_ip: The IP address of the DNS server authoritative for this
            zone.
        :param mapping: A hostname:ip-address mapping for all known hosts in
            the zone.  They will be mapped as A records.
        :param srv_mapping: Set of SRVRecord mappings.
        """
        self._dns_ip = kwargs.pop('dns_ip', None)
        self._mapping = kwargs.pop('mapping', {})
        self._network = None
        self._srv_mapping = kwargs.pop('srv_mapping', [])
        super(DNSForwardZoneConfig, self).__init__(
            domain, zone_name=domain, **kwargs)

    @classmethod
    def get_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses.

        This includes the record for the name server's IP.
        :param mapping: A dict mapping host names to IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP addresses).
        """
        return chain([('%s.' % domain, dns_ip)], mapping.items())

    @classmethod
    def get_A_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses for all
        the IPv4 addresses in `mapping`.

        The returned mapping is meant to be used to generate A records in
        the forward zone file.

        This includes the A record for the name server's IP.
        :param mapping: A dict mapping host names to IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP addresses).
        """
        mapping = cls.get_mapping(mapping, domain, dns_ip)
        return (item for item in mapping if IPAddress(item[1]).version == 4)

    @classmethod
    def get_AAAA_mapping(cls, mapping, domain, dns_ip):
        """Return a generator mapping hostnames to IP addresses for all
        the IPv6 addresses in `mapping`.

        The returned mapping is meant to be used to generate AAAA records
        in the forward zone file.

        :param mapping: A dict mapping host names to IP addresses.
        :param domain: Zone's domain name.
        :param dns_ip: IP address for the zone's authoritative DNS server.
        :return: A generator of tuples: (host name, IP addresses).
        """
        mapping = cls.get_mapping(mapping, domain, dns_ip)
        return (item for item in mapping if IPAddress(item[1]).version == 6)

    @classmethod
    def get_srv_mapping(cls, mappings):
        """Return a generator mapping srv entries to hostnames.

        :param mappings: Set of SRVRecord.
        :return: A generator of tuples:
            (service, 'priority weight port target').
        """
        for record in mappings:
            target = get_fqdn_or_ip_address(record.target)
            item = '%s %s %s %s' % (
                record.priority,
                record.weight,
                record.port,
                target)
            yield (record.service, item)

    def write_config(self):
        """Write the zone file."""
        self.write_zone_file(
            self.target_path, self.make_parameters(),
            {
                'mappings': {
                    'SRV': self.get_srv_mapping(
                        self._srv_mapping),
                    'A': self.get_A_mapping(
                        self._mapping, self.domain, self._dns_ip),
                    'AAAA': self.get_AAAA_mapping(
                        self._mapping, self.domain, self._dns_ip),
                },
            })


class DNSReverseZoneConfig(DNSZoneConfigBase):
    """Writes reverse zone files.

    A reverse zone mapping contains "PTR" records, each mapping
    reverse-notation IP addresses within a network to the matching generated
    hostname.
    """

    def __init__(self, domain, **kwargs):
        """See `DNSZoneConfigBase.__init__`.

        :param domain: The domain name of the forward zone.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        :param mapping: A hostname:ip mapping for all known hosts in
            the reverse zone.  They will be mapped as PTR records.  IP
            addresses not in `network` will be dropped.
        :param network: The network that the mapping exists within.
        :type network: :class:`netaddr.IPNetwork`
        """
        self._mapping = kwargs.pop('mapping', {})
        self._network = kwargs.pop("network", None)
        zone_name = self.compose_zone_name(self._network)
        super(DNSReverseZoneConfig, self).__init__(
            domain, zone_name=zone_name, **kwargs)

    @classmethod
    def compose_zone_name(cls, network):
        """Return the name of the reverse zone."""
        # Generate the name of the reverse zone file:
        # Use netaddr's reverse_dns() to get the reverse IP name
        # of the first IP address in the network and then drop the first
        # octets of that name (i.e. drop the octets that will be specified in
        # the zone file).
        first = IPAddress(network.first)
        if first.version == 6:
            # IPv6.
            # Use float division and ceil to cope with network sizes that
            # are not divisible by 4.
            rest_limit = int(math.ceil((128 - network.prefixlen) / 4.))
        else:
            # IPv4.
            # Use float division and ceil to cope with splits not done on
            # octets boundaries.
            rest_limit = int(math.ceil((32 - network.prefixlen) / 8.))
        reverse_name = first.reverse_dns.split('.', rest_limit)[-1]
        # Strip off trailing '.'.
        return reverse_name[:-1]

    @classmethod
    def get_PTR_mapping(cls, mapping, domain, network):
        """Return reverse mapping: reverse IPs to hostnames.

        The reverse generated mapping is the mapping between the reverse
        IP addresses and the hostnames for all the IP addresses in the given
        `mapping`.

        The returned mapping is meant to be used to generate PTR records in
        the reverse zone file.

        :param mapping: A hostname:ip-address mapping for all known hosts in
            the reverse zone.
        :param domain: Zone's domain name.
        :param network: Zone's network.
        :type network: :class:`netaddr.IPNetwork`
        """
        return (
            (
                IPAddress(ip).reverse_dns,
                '%s.%s.' % (hostname, domain),
            )
            for hostname, ip in mapping.items()
            # Filter out the IP addresses that are not in `network`.
            if IPAddress(ip) in network
        )

    def write_config(self):
        """Write the zone file."""
        self.write_zone_file(
            self.target_path, self.make_parameters(),
            {
                'mappings': {
                    'PTR': self.get_PTR_mapping(
                        self._mapping, self.domain, self._network),
                },
            }
        )
