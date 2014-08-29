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
    'MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME',
    'setup_rndc',
    'set_up_options_conf',
    ]


from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime
import errno
import os.path
import re

from celery.app import app_or_default
from provisioningserver.utils import locate_config
from provisioningserver.utils.fs import atomic_write
from provisioningserver.utils.shell import call_and_check
import tempita


MAAS_NAMED_CONF_NAME = 'named.conf.maas'
MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME = 'named.conf.options.inside.maas'
MAAS_NAMED_RNDC_CONF_NAME = 'named.conf.rndc.maas'
MAAS_RNDC_CONF_NAME = 'rndc.conf.maas'


celery_conf = app_or_default().conf


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
    celery_conf.DNS_CONFIG_DIR.
    """
    rndc_content, named_content = generate_rndc(
        port=celery_conf.DNS_RNDC_PORT,
        include_default_controls=celery_conf.DNS_DEFAULT_CONTROLS)

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
    return os.path.join(celery_conf.DNS_CONFIG_DIR, filename)


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
        trusted_networks = kwargs.pop("trusted_networks", "")
        context = {
            'zones': self.zones,
            'DNS_CONFIG_DIR': celery_conf.DNS_CONFIG_DIR,
            'named_rndc_conf_path': get_named_rndc_conf_path(),
            'trusted_networks': trusted_networks,
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
