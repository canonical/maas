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
    'InactiveDNSConfig',
    'setup_rndc',
    ]


from abc import (
    ABCMeta,
    abstractproperty,
    )
import os.path
from subprocess import (
    check_call,
    check_output,
    )

from celery.conf import conf
from provisioningserver.utils import atomic_write
import tempita


class DNSConfigFail(Exception):
    """Raised if there's a problem with a DNS config."""


def generate_rndc():
    """Use `rndc-confgen` (from bind9utils) to generate a rndc+named
    configuration.

    `rndc-confgen` generates the rndc configuration which also contains (that
    part is commented out) the named configuration.
    """
    # Generate the configuration:
    # - 256 bits is the recommanded size for the key nowadays;
    # - Use the unlocked random source to make the executing
    # non-blocking.
    rndc_content = check_output(
        ['rndc-confgen', '-b', '256', '-r', '/dev/urandom',
         '-k', 'rndc-maas-key'])
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
    return os.path.join(conf.DNS_CONFIG_DIR, 'named.conf.rndc')


def get_rndc_conf_path():
    return os.path.join(conf.DNS_CONFIG_DIR, 'rndc.conf')


def setup_rndc():
    """Writes out the two files needed to enable MAAS to use rndc commands:
    rndc.conf and named.conf.rndc, both stored in conf.DNS_CONFIG_DIR.
    """
    rndc_content, named_content = generate_rndc()

    target_file = get_rndc_conf_path()
    with open(target_file, "wb") as f:
        f.write(rndc_content)

    target_file = get_named_rndc_conf_path()
    with open(target_file, "wb") as f:
        f.write(named_content)


def execute_rndc_command(*arguments):
    """Execute a rndc command."""
    rndc_conf = os.path.join(conf.DNS_CONFIG_DIR, 'rndc.conf')
    check_call(['rndc', '-c', rndc_conf] + map(str, arguments))


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

    def get_extra_context(self):
        """Dictionary containing extra parameters to be included in the
        parameters used when rendering the template."""
        return {}

    def write_config(self, **kwargs):
        """Write out this DNS config file."""
        template = self.get_template()
        kwargs.update(self.get_extra_context())
        rendered = self.render_template(template, **kwargs)
        atomic_write(rendered, self.target_path)


class DNSConfig(DNSConfigBase):
    """A DNS configuration file.

    Encapsulation of DNS config templates and parameter substitution.
    """

    template_file_name = 'named.conf.template'
    target_file_name = 'named.conf'

    def __init__(self, zone_ids=(), reverse_zone_ids=()):
        self.zone_ids = zone_ids
        self.reverse_zone_ids = reverse_zone_ids

    @property
    def template_path(self):
        return os.path.join(self.template_dir, self.template_file_name)

    @property
    def target_path(self):
        return os.path.join(self.target_dir, self.target_file_name)

    def get_extra_context(self):
        return {
            'zones': [DNSZoneConfig(zone_id) for zone_id in self.zone_ids],
            'rev_zones': [
                RevDNSZoneConfig(reverse_zone_id)
                for reverse_zone_id in self.reverse_zone_ids],
            'DNS_CONFIG_DIR': conf.DNS_CONFIG_DIR,
            'named_rndc_conf_path':  get_named_rndc_conf_path()
        }


class InactiveDNSConfig(DNSConfig):
    """A specialized version of DNSConfig that simply writes a blank/empty
    configuration file.
    """

    def get_template(self):
        """Return an empty template."""
        return tempita.Template('', 'empty template')


class DNSZoneConfig(DNSConfig):
    """A specialized version of DNSConfig that writes zone files."""

    template_file_name = 'zone.template'
    zone_name_string = '%d'
    zone_filename_string = 'zone.%d'

    def __init__(self, zone_id):
        self.zone_id = zone_id

    @property
    def name(self):
        return self.zone_name_string % self.zone_id

    @property
    def template_path(self):
        return os.path.join(self.template_dir, self.template_file_name)

    @property
    def target_path(self):
        return os.path.join(
            self.target_dir, self.zone_filename_string % self.zone_id)

    def get_extra_context(self):
        return {}


class RevDNSZoneConfig(DNSZoneConfig):
    """A specialized version of DNSZoneConfig that writes reverse zone
    files.
    """

    template_file_name = 'zone.template'
    # TODO: create a proper reverse zone template, create test for this class.
    zone_name_string = '%d.rev'
    zone_filename_string = 'zone.rev.%d'
