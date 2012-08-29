# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'DNSConfig',
    'DNSZoneConfig',
    'setup_rndc',
    ]


from abc import (
    ABCMeta,
    abstractproperty,
    )
from datetime import datetime
import os.path
from subprocess import (
    check_call,
    check_output,
    )

from celery.conf import conf
from netaddr import IPRange
from provisioningserver.dns.utils import generated_hostname
from provisioningserver.utils import (
    atomic_write,
    incremental_write,
    )
import tempita


MAAS_NAMED_CONF_NAME = 'named.conf.maas'
MAAS_NAMED_RNDC_CONF_NAME = 'named.conf.rndc.maas'
MAAS_RNDC_CONF_NAME = 'rndc.conf.maas'


class DNSConfigFail(Exception):
    """Raised if there's a problem with a DNS config."""


def generate_rndc(port=953, key_name='rndc-maas-key'):
    """Use `rndc-confgen` (from bind9utils) to generate a rndc+named
    configuration.

    `rndc-confgen` generates the rndc configuration which also contains (that
    part is commented out) the named configuration.
    """
    # Generate the configuration:
    # - 256 bits is the recommended size for the key nowadays.
    # - Use urandom to avoid blocking on the random generator.
    rndc_content = check_output(
        ['rndc-confgen', '-b', '256', '-r', '/dev/urandom',
         '-k', key_name, '-p', str(port)])
    # Extract from the result the part which corresponds to the named
    # configuration.
    start_marker = (
        "# Use with the following in named.conf, adjusting the "
        "allow list as needed:")
    end_marker = '# End of named.conf'
    named_start = rndc_content.index(start_marker) + len(start_marker)
    named_end = rndc_content.index(end_marker)
    named_conf = rndc_content[named_start:named_end].replace('\n# ', '\n')
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
        conf.DNS_RNDC_PORT)

    target_file = get_rndc_conf_path()
    with open(target_file, "wb") as f:
        f.write(rndc_content)

    target_file = get_named_rndc_conf_path()
    with open(target_file, "wb") as f:
        f.write(named_content)


def execute_rndc_command(arguments):
    """Execute a rndc command."""
    rndc_conf = os.path.join(conf.DNS_CONFIG_DIR, MAAS_RNDC_CONF_NAME)
    with open(os.devnull, "ab") as devnull:
        check_call(
            ['rndc', '-c', rndc_conf] + map(str, arguments),
            stdout=devnull)


# Directory where the DNS configuration template files can be found.
TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), 'templates')


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
        return TEMPLATES_PATH

    @property
    def target_dir(self):
        return conf.DNS_CONFIG_DIR

    def get_template(self):
        with open(self.template_path, "r") as f:
            return tempita.Template(f.read(), name=self.template_path)

    def render_template(self, template, **kwargs):
        try:
            return template.substitute(kwargs)
        except NameError as error:
            raise DNSConfigFail(*error.args)

    def get_context(self):
        """Dictionary containing parameters to be included in the
        parameters used when rendering the template."""
        return {}

    def write_config(self, overwrite=True, **kwargs):
        """Write out this DNS config file."""
        template = self.get_template()
        kwargs.update(self.get_context())
        rendered = self.render_template(template, **kwargs)
        atomic_write(rendered, self.target_path, overwrite=overwrite)


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
            'named_rndc_conf_path':  get_named_rndc_conf_path(),
            'modified': unicode(datetime.today()),
        }

    def get_include_snippet(self):
        return '\ninclude "%s";\n' % self.target_path


def shortened_reversed_ip(ip, byte_num):
    """Get a reversed version of this IP with only the significant bytes.

    This method is a utility used when generating reverse zone files.

    >>> shortened_reversed_ip('192.156.0.3', 2)
    '3.0'
    """
    assert 0 <= byte_num <= 4, ("byte_num should be >=0 and <= 4.")
    ip_octets = ip.split('.')
    significant_octets = list(
    reversed(ip_octets))[:byte_num]
    return '.'.join(significant_octets)


class DNSZoneConfig(DNSConfig):
    """A specialized version of DNSConfig that writes zone files."""

    template_file_name = 'zone.template'

    def __init__(self, zone_name, serial=None, mapping=None, dns_ip=None,
                 subnet_mask=None, broadcast_ip=None, ip_range_low=None,
                 ip_range_high=None):
        self.zone_name = zone_name
        self.serial = serial
        if mapping is None:
            self.mapping = {}
        else:
            self.mapping = mapping
        self.dns_ip = dns_ip
        self.subnet_mask = subnet_mask
        self.broadcast_ip = broadcast_ip
        self.ip_range_low = ip_range_low
        self.ip_range_high = ip_range_high

    @property
    def byte_num(self):
        """Number of significant octets for the IPs of this zone."""
        return 4 - len(
            [byte for byte in self.subnet_mask.split('.')
             if byte == '255'])

    @property
    def reverse_zone_name(self):
        """Return the name of the reverse zone."""
        significant_bits = self.broadcast_ip.split('.')[:4 - self.byte_num]
        return '%s.in-addr.arpa' % '.'.join(reversed(significant_bits))

    def get_mapping(self):
        """Return the mapping: hostname->generated hostname."""
        return {
            hostname: generated_hostname(ip)
            for hostname, ip in self.mapping.items()
        }

    def get_generated_mapping(self):
        """Return the generated mapping: fqdn->ip.

        The generated mapping is the mapping between the generated hostnames
        and the IP addresses for all the possible IP addresses in zone.
        """
        return {
            generated_hostname(str(ip)): str(ip)
            for ip in IPRange(self.ip_range_low, self.ip_range_high)
        }

    def get_generated_reverse_mapping(self):
        """Return the reverse generated mapping: (shortened) ip->fqdn.

        The reverse generated mapping is the mapping between the IP addresses
        and the generated hostnames for all the possible IP addresses in zone.
        """
        return dict(
            (
                shortened_reversed_ip(ip, self.byte_num),
                '%s.%s.' % (hostname, self.zone_name)
            )
            for hostname, ip in self.get_generated_mapping().items())

    @property
    def template_path(self):
        return os.path.join(self.template_dir, self.template_file_name)

    @property
    def target_path(self):
        """Return the full path of the DNS zone config file."""
        return os.path.join(
            self.target_dir, 'zone.%s' % self.zone_name)

    @property
    def target_reverse_path(self):
        """Return the full path of the DNS reverse zone config file."""
        return os.path.join(
            self.target_dir, 'zone.rev.%s' % self.reverse_zone_name)

    def get_base_context(self):
        """Return the dict used to render both zone files."""
        return {
            'domain': self.zone_name,
            'serial': self.serial,
            'modified': unicode(datetime.today()),
        }

    def get_context(self):
        """Return the dict used to render the DNS zone file.

        That context dict is used to render the DNS zone file.
        """
        context = self.get_base_context()
        mapping = self.get_generated_mapping()
        # Add A record for the name server's IP.
        mapping['%s.' % self.zone_name] = self.dns_ip
        mappings = {
            'CNAME': self.get_mapping(),
            'A': mapping,
        }
        context.update(mappings=mappings)
        return context

    def get_reverse_context(self):
        """Return the dict used to render the DNS reverse zone file.

        That context dict is used to render the DNS reverse zone file.
        """
        context = self.get_base_context()
        mappings = {'PTR': self.get_generated_reverse_mapping()}
        context.update(mappings=mappings)
        return context

    def write_config(self, **kwargs):
        """Write out the DNS config file for this zone."""
        template = self.get_template()
        kwargs.update(self.get_context())
        rendered = self.render_template(template, **kwargs)
        incremental_write(rendered, self.target_path)

    def write_reverse_config(self, **kwargs):
        """Write out the DNS reverse config file for this zone."""
        template = self.get_template()
        kwargs.update(self.get_reverse_context())
        rendered = self.render_template(template, **kwargs)
        incremental_write(rendered, self.target_reverse_path)
