# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Setuptools installer for MAAS."""

from distutils.core import Command
from glob import glob
from os.path import (
    dirname,
    join,
)

from setuptools import (
    find_packages,
    setup,
)
from setuptools.command.build_py import build_py

# The directory in which setup.py lives.
here = dirname(__file__)


def read(filename):
    """Return the whitespace-stripped content of `filename`."""
    path = join(here, filename)
    with open(path, "r") as fin:
        return fin.read().strip()


def import_jsenums():
    """Import jsenums module without needing maasserver in the sys.path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "maasserver.utils.jsenums", "src/maasserver/utils/jsenums.py")
    jsenums = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jsenums)
    return jsenums


class EnumJSCommand(Command):
    """A custom command to run generate enum.js from all the enum.py files."""

    description = "generate enum.js from all the enum.py files"
    user_options = []

    def initialize_options(self):
        # Do nothing.
        pass

    def finalize_options(self):
        # Do nothing.
        pass

    def run(self):
        """Run command."""
        py_files = glob('src/*/enum.py')
        jsenums = import_jsenums()
        js_content = jsenums.dump(py_files)
        with open('src/maasserver/static/js/enums.js', 'w') as fp:
            fp.write(js_content)


class BuildPyCommand(build_py):
    """Override build_py to call enum_js."""

    def run(self):
        self.run_command('enum_js')
        super().run()


setup(
    name="maas",
    version="1.10a1",
    url="https://launchpad.net/maas",
    license="AGPLv3",
    description="Metal As A Service",
    long_description=read('README.rst'),

    author="MAAS Developers",
    author_email="maas-devel@lists.launchpad.net",

    cmdclass={
        'enum_js': EnumJSCommand,
        'build_py': BuildPyCommand,
    },
    packages=find_packages(
        where='src',
        exclude=[
            "*.testing",
            "*.tests",
            "maastesting",
            "maastesting.*",
        ],
    ),
    package_dir={'': 'src'},
    include_package_data=True,

    data_files=[
        ('/etc/maas',
            ['etc/maas/drivers.yaml']),
        ('/usr/share/maas',
            ['contrib/maas-rsyslog.conf',
             'contrib/maas-http.conf']),
        ('/etc/maas/preseeds',
            ['contrib/preseeds_v2/commissioning',
             'contrib/preseeds_v2/enlist',
             'contrib/preseeds_v2/enlist_userdata',
             'contrib/preseeds_v2/curtin',
             'contrib/preseeds_v2/curtin_userdata',
             'contrib/preseeds_v2/curtin_userdata_centos',
             'contrib/preseeds_v2/curtin_userdata_custom',
             'contrib/preseeds_v2/curtin_userdata_suse',
             'contrib/preseeds_v2/curtin_userdata_windows']),
        ('/usr/bin',
            ['scripts/maas-generate-winrm-cert',
             'scripts/uec2roottar']),
        ('/usr/sbin',
            ['scripts/maas-dhcp-helper']),
        ('/usr/lib/maas',
            ['scripts/dhcp-monitor',
             'scripts/beacon-monitor',
             'scripts/network-monitor',
             'scripts/maas-delete-file',
             'scripts/maas-test-enlistment',
             'scripts/maas-write-file']),
    ],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: JavaScript',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Systems Administration',
    ],
)
