#!/usr/bin/python

from __future__ import (
    absolute_import,
    print_function,
    # unicode_literals,
    )

str = None

__metaclass__ = type

import sys

from maas_api_helper import (
    geturl,
    read_config,
)


MD_VERSION = "2012-03-01"


def main():
    """Authenticate, and download file from MAAS metadata API."""
    import argparse

    parser = argparse.ArgumentParser(
        description="GET file from MAAS metadata API.")
    parser.add_argument(
        "--config", metavar="file",
        help="Config file containing MAAS API credentials", default=None)
    parser.add_argument(
        "--apiver", metavar="version", help="Use given API version",
        default=MD_VERSION)
    parser.add_argument('path')

    args = parser.parse_args()

    creds = {
        'consumer_key': None,
        'token_key': None,
        'token_secret': None,
        'consumer_secret': '',
        'metadata_url': None,
    }
    read_config(args.config, creds)
    url = "%s/%s/%s" % (
        creds['metadata_url'],
        args.apiver,
        args.path,
        )

    sys.stdout.write(geturl(url, creds))

if __name__ == '__main__':
    main()
