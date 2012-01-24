#!/usr/bin/env python2.7
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Distutils installer for maas."""

from __future__ import (
    print_function,
    unicode_literals,
    )

from os.path import (
    dirname,
    join,
    )

import distribute_setup

# The version of distribute packaged in precise is not quite at 0.6.24
# final yet so we need to override the required version here to stop a
# recipe build from trying to download from pypi.
distribute_setup.use_setuptools(version="0.6.24dev-r0")

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
    license="GPL",
    description="Metal as as Service",
    long_description=read('README.txt'),

    author="MaaS Developers",
    author_email="juju@lists.ubuntu.com",

    packages=find_packages(b'src'),
    package_dir={'': b'src'},

    install_requires=['setuptools'],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Intended Audience :: Developers',
        "Intended Audience :: System Administrators",
        'License :: OSI Approved :: GPL License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
