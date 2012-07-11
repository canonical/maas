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
    # - 256 bits is the recommanded size for the key nowadays;
    # - Use the unlocked random source to make the executing
    # non-blocking.
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
    rndc_content, named_content = generate_rndc()

    target_file = get_rndc_conf_path()
    with open(target_file, "wb") as f:
        f.write(rndc_content)

    target_file = get_named_rndc_conf_path()
    with open(target_file, "wb") as f:
        f.write(named_content)


def execute_rndc_command(*arguments):
    """Execute a rndc command."""
    rndc_conf = os.path.join(
        conf.DNS_CONFIG_DIR, MAAS_RNDC_CONF_NAME)
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
    target_file_name = MAAS_NAMED_CONF_NAME

    def __init__(self, zone_names=(), reverse_zone_names=()):
        self.zone_names = zone_names
        self.reverse_zone_names = reverse_zone_names

    @property
    def template_path(self):
        return os.path.join(self.template_dir, self.template_file_name)

    @property
    def target_path(self):
        return os.path.join(self.target_dir, self.target_file_name)

    def get_extra_context(self):
        return {
            'zones': [
                DNSZoneConfig(zone_name)
                for zone_name in self.zone_names],
            'rev_zones': [
                RevDNSZoneConfig(reverse_zone_name)
                for reverse_zone_name in self.reverse_zone_names],
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
    zone_name_string = '%s'
    zone_filename_string = 'zone.%s'

    def __init__(self, zone_name):
        self.zone_name = zone_name

    @property
    def name(self):
        return self.zone_name_string % self.zone_name

    @property
    def template_path(self):
        return os.path.join(self.template_dir, self.template_file_name)

    @property
    def target_path(self):
        return os.path.join(
            self.target_dir, self.zone_filename_string % self.zone_name)

    def get_extra_context(self):
        return {}


class RevDNSZoneConfig(DNSZoneConfig):
    """A specialized version of DNSZoneConfig that writes reverse zone
    files.
    """

    template_file_name = 'zone.template'
    # TODO: create a proper reverse zone template, create test for this class.
    zone_name_string = '%s.rev'
    zone_filename_string = 'zone.rev.%s'
