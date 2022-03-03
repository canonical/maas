from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, Namespace
from datetime import timedelta
from importlib import import_module
import os
import time
from typing import Optional

import django
from django.conf import settings

from provisioningserver.config import is_dev_environment

from . import LOGGER
from .sampledata import generate


def parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Configure storage for a machine",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--db-name", help="database name")
    parser.add_argument("--db-host", help="database host")
    parser.add_argument(
        "--hostname-prefix",
        help=(
            "Prefix for machine hostname. If none is specified, a random one "
            "is generated"
        ),
        default="",
    )
    parser.add_argument(
        "--ownerdata-prefix",
        help=(
            "Prefix for ownerdata keys. If none is specified, a random one "
            "is generated"
        ),
        default="",
    )
    parser.add_argument(
        "--tag-prefix",
        help=(
            "Prefix for tag names. If none is specified, a random one "
            "is generated"
        ),
        default="",
    )
    parser.add_argument(
        "--redfish-address",
        help=(
            "Address of the redfish endpoint for machines. If not specified, "
            "the manual power driver will be set instead"
        ),
        default="",
    )
    parser.add_argument(
        "--machines",
        help="number of machines to create",
        type=int,
        default=1000,
    )
    parser.add_argument(
        "--log-queries",
        help="log SQL queries",
        action="store_true",
        default=False,
    )
    return parser.parse_args()


def setup_django(
    db_host: Optional[str] = None,
    db_name: Optional[str] = None,
    log_queries: bool = False,
):
    if "SNAP" in os.environ:
        os.environ["MAAS_REGION_CONFIG"] = os.path.join(
            os.environ["SNAP_DATA"], "regiond.conf"
        )
        setting = "snap"
    elif is_dev_environment():
        setting = "development"
    else:
        setting = "settings"

    settings_module = import_module(f"maasserver.djangosettings.{setting}")
    config = {
        key: value
        for key, value in settings_module.__dict__.items()
        if key.isupper()
    }
    # ensure logging is enabled
    log_config = config["LOGGING"]
    log_config["handlers"] = {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
        }
    }
    log_config["root"] = {
        "level": "DEBUG",
        "handlers": ["console"],
    }
    if log_queries:
        log_config["loggers"]["django.db.backends"] = {
            "level": "DEBUG",
            "handlers": ["console"],
        }
    # override db settings if specified
    db_config = config["DATABASES"]["default"]
    if db_host:
        db_config["HOST"] = db_host
    if db_name:
        db_config["NAME"] = db_name

    settings.configure(**config)
    django.setup()
    LOGGER.info(f"using database '{db_config['NAME']}' on {db_config['HOST']}")


def main():
    args = parse_args()
    setup_django(
        db_host=args.db_host,
        db_name=args.db_name,
        log_queries=args.log_queries,
    )
    start_time = time.monotonic()
    generate(
        args.machines,
        args.hostname_prefix,
        args.ownerdata_prefix,
        args.tag_prefix,
        args.redfish_address,
    )
    end_time = time.monotonic()
    LOGGER.info(
        f"sampledata generated in {timedelta(seconds=end_time - start_time)}"
    )
