#!/usr/bin/env python
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Distutils installer for maas."""

import os

import distribute_setup
distribute_setup.use_setuptools()

from setuptools import (
    find_packages,
    setup,
    )


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read().strip()

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

    packages=find_packages('src'),
    package_dir={'': 'src'},

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
