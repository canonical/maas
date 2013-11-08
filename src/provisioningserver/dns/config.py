# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
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
    'setup_rndc',
    'set_up_options_conf',
    ]


from abc import (
    ABCMeta,
    abstractproperty,
    )
from datetime import datetime
import errno
from itertools import (
    chain,
    imap,
    islice,
    )
import os.path
import re

from celery.conf import conf
from provisioningserver.dns.utils import generated_hostname
from provisioningserver.utils import (
    atomic_write,
    call_and_check,
    call_capture_and_check,
    incremental_write,
    locate_config,
    )
import tempita


MAAS_NAMED_CONF_NAME = 'named.conf.maas'
MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME = 'named.conf.options.inside.maas'
MAAS_NAMED_RNDC_CONF_NAME = 'named.conf.rndc.maas'
MAAS_RNDC_CONF_NAME = 'rndc.conf.maas'


class DNSConfigDirectoryMissing(Exception):
    """The directory where the config was about to be written is missing."""


class DNSConfigFail(Exception):
    """Raised if there's a problem with a DNS config."""


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
    rndc_content = call_capture_and_check(
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
    return os.path.join(
        conf.DNS_CONFIG_DIR, MAAS_NAMED_RNDC_CONF_NAME)


def get_rndc_conf_path():
    return os.path.join(conf.DNS_CONFIG_DIR, MAAS_RNDC_CONF_NAME)


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
    rndc_conf = os.path.join(conf.DNS_CONFIG_DIR, MAAS_RNDC_CONF_NAME)
    rndc_cmd = ['rndc', '-c', rndc_conf]
    rndc_cmd.extend(arguments)
    with open(os.devnull, "ab") as devnull:
        call_and_check(rndc_cmd, stdout=devnull)


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

    target_path = os.path.join(
        conf.DNS_CONFIG_DIR, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME)
    atomic_write(rendered, target_path, overwrite=overwrite, mode=0644)


class DNSConfigBase:
    __metaclass__ = ABCMeta

    @abstractproperty
    def template_path(self):
        """Return the full path of the template to be used."""

    @abstractproperty
    def target_path(self):
        """Return the full path of the target file to be written."""

    @property
    def template_dir(self):
        return locate_config(TEMPLATES_DIR)

    @property
    def access_permissions(self):
        """The access permissions for the config file."""
        return 0644

    @property
    def target_dir(self):
        return conf.DNS_CONFIG_DIR

    def get_template(self):
        with open(self.template_path, "r") as f:
            return tempita.Template(f.read(), name=self.template_path)

    def render_template(self, template, **kwargs):
        """Substitute supplied kwargs into the supplied Tempita template."""
        try:
            return template.substitute(kwargs)
        except NameError as error:
            raise DNSConfigFail(*error.args)

    def get_context(self):
        """Dictionary containing parameters to be included in the
        parameters used when rendering the template."""
        return {}

    def write_config(self, overwrite=True, **kwargs):
        """Write out this DNS config file.

        This raises DNSConfigDirectoryMissing if any
        "No such file or directory" error is raised because that would mean
        that the directory containing the write to be written does not exist.
        """
        try:
            self.inner_write_config(overwrite=overwrite, **kwargs)
        except OSError as exception:
            # Only raise a DNSConfigDirectoryMissing exception if this error
            # is a "No such file or directory" exception.
            if exception.errno == errno.ENOENT:
                raise DNSConfigDirectoryMissing(
                    "The directory where the DNS config files should be "
                    "written does not exist.  Make sure the 'maas-dns' "
                    "package is installed on this region controller.")
            else:
                raise

    def inner_write_config(self, overwrite=True, **kwargs):
        """Write out this DNS config file."""
        template = self.get_template()
        kwargs.update(self.get_context())
        rendered = self.render_template(template, **kwargs)
        atomic_write(
            rendered, self.target_path, overwrite=overwrite,
            mode=self.access_permissions)


class DNSConfig(DNSConfigBase):
    """A DNS configuration file.

    Encapsulation of DNS config templates and parameter substitution.
    """

    template_file_name = 'named.conf.template'
    target_file_name = MAAS_NAMED_CONF_NAME

    def __init__(self, zones=()):
        self.zones = zones
        return super(DNSConfig, self).__init__()

    @property
    def template_path(self):
        return os.path.join(self.template_dir, self.template_file_name)

    @property
    def target_path(self):
        return os.path.join(self.target_dir, self.target_file_name)

    def get_context(self):
        return {
            'zones': self.zones,
            'DNS_CONFIG_DIR': conf.DNS_CONFIG_DIR,
            'named_rndc_conf_path': get_named_rndc_conf_path(),
            'modified': unicode(datetime.today()),
        }

    def get_include_snippet(self):
        assert '"' not in self.target_path, self.target_path
        return 'include "%s";\n' % self.target_path


def shortened_reversed_ip(ip, byte_num):
    """Get a reversed version of this IP with only the significant bytes.

    This method is a utility used when generating reverse zone files.

    >>> shortened_reversed_ip('192.156.0.3', 2)
    '3.0'

    :type ip: :class:`netaddr.IPAddress`
    """
    assert 0 <= byte_num <= 4, ("byte_num should be >=0 and <= 4.")
    significant_octets = islice(reversed(ip.words), byte_num)
    return '.'.join(imap(unicode, significant_octets))


class DNSZoneConfigBase(DNSConfigBase):
    """Base class for zone writers."""

    template_file_name = 'zone.template'

    def __init__(self, domain, serial=None, mapping=None, dns_ip=None):
        """
        :param domain: The domain name of the forward zone.
        :param serial: The serial to use in the zone file. This must increment
            on each change.
        :param mapping: A hostname:ip-address mapping for all known hosts in
            the zone.
        :param dns_ip: The IP address of the DNS server authoritative for this
            zone.
        """
        super(DNSZoneConfigBase, self).__init__()
        self.domain = domain
        self.serial = serial
        self.mapping = {} if mapping is None else mapping
        self.dns_ip = dns_ip

    @abstractproperty
    def zone_name(self):
        """Return the zone's fully-qualified name."""

    @property
    def template_path(self):
        return os.path.join(self.template_dir, self.template_file_name)

    @property
    def target_path(self):
        """Return the full path of the DNS zone file."""
        return os.path.join(
            self.target_dir, 'zone.%s' % self.zone_name)

    def inner_write_config(self, **kwargs):
        """Write out the DNS config file for this zone."""
        template = self.get_template()
        kwargs.update(self.get_context())
        rendered = self.render_template(template, **kwargs)
        incremental_write(
            rendered, self.target_path, mode=self.access_permissions)


class DNSForwardZoneConfig(DNSZoneConfigBase):
    """Writes forward zone files."""

    def __init__(self, *args, **kwargs):
        """See `DNSZoneConfigBase.__init__`.

        :param networks: The networks that the mapping exists within.
        :type networks: Sequence of :class:`netaddr.IPNetwork`
        """
        networks = kwargs.pop("networks", None)
        self.networks = [] if networks is None else networks
        super(DNSForwardZoneConfig, self).__init__(*args, **kwargs)

    @property
    def zone_name(self):
        """Return the name of the forward zone."""
        return self.domain

    def get_cname_mapping(self):
        """Return a generator with the mapping: hostname->generated hostname.

        The mapping only contains hosts for which the two host names differ.

        :return: A generator of tuples: (host name, generated host name).
        """
        # We filter out cases where the two host names are identical: it
        # would be wrong to define a CNAME that maps to itself.
        for hostname, ip in self.mapping.items():
            generated_name = generated_hostname(ip)
            if generated_name != hostname:
                yield (hostname, generated_name)

    def get_static_mapping(self):
        """Return a generator with the mapping fqdn->ip for the generated ips.

        The generated mapping is the mapping between the generated hostnames
        and the IP addresses for all the possible IP addresses in zone.
        Note that we return a list of tuples instead of a dictionary in order
        to be able to return a generator.
        """
        ips = imap(unicode, chain.from_iterable(self.networks))
        static_mapping = ((generated_hostname(ip), ip) for ip in ips)
        # Add A record for the name server's IP.
        return chain([('%s.' % self.domain, self.dns_ip)], static_mapping)

    def get_context(self):
        """Return the dict used to render the DNS zone file.

        That context dict is used to render the DNS zone file.
        """
        return {
            'domain': self.domain,
            'serial': self.serial,
            'modified': unicode(datetime.today()),
            'mappings': {
                'CNAME': self.get_cname_mapping(),
                'A': self.get_static_mapping(),
                }
            }


class DNSReverseZoneConfig(DNSZoneConfigBase):
    """Writes reverse zone files."""

    def __init__(self, *args, **kwargs):
        """See `DNSZoneConfigBase.__init__`.

        :param network: The network that the mapping exists within.
        :type network: :class:`netaddr.IPNetwork`
        """
        self.network = kwargs.pop("network", None)
        super(DNSReverseZoneConfig, self).__init__(*args, **kwargs)

    @property
    def zone_name(self):
        """Return the name of the reverse zone."""
        broadcast, netmask = self.network.broadcast, self.network.netmask
        octets = broadcast.words[:netmask.words.count(255)]
        return '%s.in-addr.arpa' % '.'.join(imap(unicode, reversed(octets)))

    def get_static_mapping(self):
        """Return the reverse generated mapping: (shortened) ip->fqdn.

        The reverse generated mapping is the mapping between the IP addresses
        and the generated hostnames for all the possible IP addresses in zone.
        """
        byte_num = 4 - self.network.netmask.words.count(255)
        return (
            (shortened_reversed_ip(ip, byte_num),
                '%s.%s.' % (generated_hostname(ip), self.domain))
            for ip in self.network
            )

    def get_context(self):
        """Return the dict used to render the DNS reverse zone file.

        That context dict is used to render the DNS reverse zone file.
        """
        return {
            'domain': self.domain,
            'serial': self.serial,
            'modified': unicode(datetime.today()),
            'mappings': {
                'PTR': self.get_static_mapping(),
                }
            }
