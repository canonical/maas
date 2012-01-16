import os
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read().strip()

__version__ = open("src/maas/version.txt").read().strip()

setup(
    name="maas",
    version=read('src/maas/version.txt'),
    url="https://launchpad.net/maas",
    license="GPL",
    description="Metal as as Service",
    long_description = read('README.txt'),

    author="MaaS Developers",
    author_email="juju@lists.ubuntu.com",

    packages = find_packages('src'),
    package_dir = {'': 'src'},

    install_requires = ['setuptools'],

    classifiers = [
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
