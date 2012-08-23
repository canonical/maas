#!/usr/bin/env python2.7
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Distribute/Setuptools installer for MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

from os.path import (
    dirname,
    join,
    )

from setuptools import (
    find_packages,
    setup,
    )


def read(filename):
    """Return the whitespace-stripped content of `filename`."""
    path = join(dirname(__file__), filename)
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
            ['etc/pserv.yaml',
             'etc/txlongpoll.yaml',
             'etc/celeryconfig.py',
             'etc/maas/import_ephemerals',
             'etc/maas/import_pxe_files',
             'etc/maas/commissioning-user-data',
             'contrib/maas-http.conf',
             'contrib/maas_local_settings.py']),
        ('/etc/cron.d',
            ['etc/cron.d/maas-gc']),
        ('/usr/share/maas',
            ['contrib/wsgi.py']),
        ('/usr/share/maas/preseeds',
            ['contrib/preseeds_v2/commissioning',
             'contrib/preseeds_v2/enlist',
             'contrib/preseeds_v2/generic',
             'contrib/preseeds_v2/preseed_master']),
        ('/usr/sbin',
            ['scripts/maas-import-ephemerals',
             'scripts/maas-import-pxe-files']),
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
