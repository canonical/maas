#!/usr/bin/env python3

import os
import sys

from maas_api_helper import Config, MD_VERSION, signal, SignalException

VALID_STATUS = ("OK", "FAILED", "WORKING", "TESTING", "COMMISSIONING")
POWER_TYPES = ("ipmi", "virsh", "manual", "moonshot", "wedge")


def fail(msg_or_exc):
    sys.stderr.write("FAIL: %s" % msg_or_exc)
    sys.exit(1)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Send signal operation and optionally post files to MAAS"
    )
    parser.add_argument(
        "--config", metavar="file", help="Specify config file", default=None
    )
    parser.add_argument(
        "--ckey",
        metavar="key",
        help="The consumer key to auth with",
        default=None,
    )
    parser.add_argument(
        "--tkey",
        metavar="key",
        help="The token key to auth with",
        default=None,
    )
    parser.add_argument(
        "--csec",
        metavar="secret",
        help="The consumer secret (likely '')",
        default="",
    )
    parser.add_argument(
        "--tsec",
        metavar="secret",
        help="The token secret to auth with",
        default=None,
    )
    parser.add_argument(
        "--apiver",
        metavar="version",
        help='The apiver to use ("" can be used)',
        default=MD_VERSION,
    )
    parser.add_argument(
        "--url", metavar="url", help="The data source to query", default=None
    )
    parser.add_argument(
        "--script-name",
        metavar="script_name",
        type=str,
        dest="script_name",
        help="The name of the Script this signal is about.",
    )
    parser.add_argument(
        "--script-result-id",
        metavar="script_result_id",
        type=int,
        dest="script_result_id",
        help="The ScriptResult database id this signal is about.",
    )
    parser.add_argument(
        "--file",
        dest="files",
        help="File to post",
        action="append",
        default=[],
    )
    parser.add_argument(
        "--runtime",
        metavar="runtime",
        type=float,
        dest="runtime",
        help="How long the script took to run.",
    )
    parser.add_argument(
        "--exit-status",
        metavar="exit_status",
        type=int,
        dest="exit_status",
        help="The exit return code of the script this signal is about.",
    )
    parser.add_argument(
        "--script-version-id",
        metavar="script_version_id",
        type=int,
        dest="script_version_id",
        help="The Script VersionTextFile database id this signal is about.",
    )
    parser.add_argument(
        "--power-type",
        dest="power_type",
        help="Power type.",
        choices=POWER_TYPES,
        default=None,
    )
    parser.add_argument(
        "--power-parameters",
        dest="power_params",
        help="Power parameters.",
        default=None,
    )

    parser.add_argument("status", help="Status", choices=VALID_STATUS)
    parser.add_argument(
        "error", help="Optional error message", nargs="?", default=None
    )

    args = parser.parse_args()

    config = Config()
    config.update(
        {
            "consumer_key": args.ckey,
            "token_key": args.tkey,
            "token_secret": args.tsec,
            "consumer_secret": args.csec,
            "metadata_url": args.url,
        }
    )

    if args.config:
        config.update_from_url(args.config)

    url = config.metadata_url
    if url is None:
        fail("URL must be provided either in --url or in config\n")
    url = f"{url}/{args.apiver}/"

    files = {}
    for fpath in args.files:
        files[os.path.basename(fpath)] = open(fpath, "rb")

    try:
        signal(
            url,
            config.credentials,
            args.status,
            args.error,
            args.script_name,
            args.script_result_id,
            files,
            args.runtime,
            args.exit_status,
            args.script_version_id,
            args.power_type,
            args.power_params,
        )
    except SignalException as e:
        fail(str(e))


if __name__ == "__main__":
    main()
