#!/usr/bin/env python2.7
# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Distribute/Setuptools installer for MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

from glob import glob
from os.path import (
    dirname,
    join,
    )
import sys

from setuptools import (
    find_packages,
    setup,
    )

# The source tree's location in the filesystem.
SOURCE_DIR = dirname(__file__)

# Allow the setup code to import from the source tree.
sys.path.append(join(SOURCE_DIR, 'src'))


def read(filename):
    """Return the whitespace-stripped content of `filename`."""
    path = join(SOURCE_DIR, filename)
    with open(path, "rb") as fin:
        return fin.read().strip()


__version__ = "0.1"

setup(
    name="maas",
    version=__version__,
    url="https://launchpad.net/maas",
    license="AGPLv3",
    description="Metal As A Service",
    long_description=read('README'),

    author="MAAS Developers",
    author_email="maas-devel@lists.launchpad.net",

    packages=find_packages(
        where=b'src',
        exclude=[
            b"*.testing",
            b"*.tests",
            b"maastesting",
            ],
        ),
    package_dir={'': b'src'},
    include_package_data=True,

    data_files=[
        ('/etc/maas',
            ['etc/maas/pserv.yaml',
             'etc/maas_cluster.conf',
             'etc/txlongpoll.yaml',
             'contrib/maas_local_celeryconfig.py',
             'contrib/maas_local_celeryconfig_cluster.py',
             'etc/maas/import_pxe_files',
             'contrib/maas-http.conf',
             'contrib/maas-cluster-http.conf',
             'contrib/maas_local_settings.py']),
        ('/etc/maas/templates/dhcp',
            glob('etc/maas/templates/dhcp/*.template')),
        ('/etc/maas/templates/dns',
            glob('etc/maas/templates/dns/*.template')),
        ('/etc/maas/templates/power',
            glob('etc/maas/templates/power/*.template') +
            glob('etc/maas/templates/power/*.conf')),
        ('/etc/maas/templates/pxe', glob('etc/maas/templates/pxe/*.template')),
        ('/etc/maas/templates/commissioning-user-data',
            glob('etc/maas/templates/commissioning-user-data/*.template')),
        ('/etc/maas/templates/commissioning-user-data/snippets',
            glob('etc/maas/templates/commissioning-user-data/snippets/*.py')),
        ('/usr/share/maas',
            ['contrib/wsgi.py',
             'etc/celeryconfig.py',
             'etc/celeryconfig_cluster.py',
             'etc/celeryconfig_common.py']),
        ('/etc/maas/preseeds',
            ['contrib/preseeds_v2/commissioning',
             'contrib/preseeds_v2/enlist',
             'contrib/preseeds_v2/generic',
             'contrib/preseeds_v2/enlist_userdata',
             'contrib/preseeds_v2/curtin',
             'contrib/preseeds_v2/curtin_userdata',
             'contrib/preseeds_v2/preseed_master']),
        ('/usr/sbin',
            ['scripts/maas-import-ephemerals',
             'scripts/maas-import-pxe-files']),
        ('/usr/bin',
            ['scripts/uec2roottar']),
    ],

    install_requires=[
        'setuptools',
        'Django == 1.3.1',
        'psycopg2',
        'avahi',
        'amqplib',
        'convoy',
        'dbus',
        'django-piston',
        'FormEncode',
        'oauth',
        'oops',
        'oops-datedir-repo',
        'oops-twisted',
        'PyYAML',
        'South',
        'Twisted',
        'txAMQP',
        'txlongpoll',
        ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Intended Audience :: Developers',
        "Intended Audience :: System Administrators",
        'License :: OSI Approved :: GPL License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        ],
    extras_require=dict(
        doc=[
            'collective.recipe.sphinxbuilder',
            'Sphinx',
            ],
        tests=[
            'coverage',
            'django-nose',
            'lxml',
            'sst',
            'fixtures',
            'mock',
            'nose',
            'nose-subunit',
            'python-subunit',
            'rabbitfixture',
            'testresources',
            'testscenarios',
            'testtools',
            ],
    )
)
