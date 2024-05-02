# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Commands for managing enrolment with a Site Manager instance."""

import argparse
from contextlib import closing
from datetime import datetime
from ssl import CertificateError
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from jose import ExpiredSignatureError, JOSEError, jwt
from jsonschema import validate, ValidationError
import yaml

from maascli.init import prompt_yes_no
from maasserver.msm import msm_enrol, msm_status, msm_withdraw
from maasserver.utils.certificates import get_ssl_certificate
from maasserver.utils.orm import with_connection


class Command(BaseCommand):
    help = "Configure enrolment with a Site Manager instance"
    ENROL_COMMAND = "enrol"
    STATUS_COMMAND = "status"
    WITHDRAW_COMMAND = "withdraw"
    CFG_SCHEMA = {
        "type": "object",
        "properties": {
            "metadata": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "country": {"type": "string"},
                    "note": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "address": {"type": "string"},
                    "postal_code": {"type": "string"},
                    "timezone": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "required": ["metadata"],
        "additionalProperties": False,
    }

    def _withdraw(self, options):
        msm_withdraw()

    def _status(self, options):
        print(msm_status())

    @with_connection
    def _enrol(self, options):
        # We don't know exactly what to expect from these claims, so don't verify them
        decode_opts = {
            "verify_signature": False,
            "verify_aud": False,
            "verify_sub": False,
            "verify_iss": False,
        }
        enrolment_token = options["enrolment_token"]
        config = ""
        if options["config_file"] is not None:
            with closing(options["config_file"]) as cfg_file:
                config = cfg_file.read()
        try:
            decoded = jwt.decode(
                enrolment_token,
                "",
                algorithms=["HS256"],
                options=decode_opts,
            )
        except ExpiredSignatureError:
            raise CommandError("Enrolment token is expired.")
        except JOSEError:
            raise CommandError("Invalid enrolment token.")
        # validate the yaml config
        if config:
            try:
                cfg = yaml.safe_load(config)
                validate(cfg, self.CFG_SCHEMA)
            except ValidationError as e:
                raise CommandError(f"Invalid config file: {e.message}")
            except yaml.error.MarkedYAMLError as e:
                raise CommandError(
                    f"Invalid config file: {e.problem}: line {e.problem_mark.line}, column: {e.problem_mark.column}"
                )
        # strip the path
        enrolment_url = decoded["enrolment-url"]
        parsed = urlparse(enrolment_url)
        base_url = f"{parsed.scheme}://{parsed.hostname}"
        msg = get_cert_verify_msg(base_url)
        if not prompt_yes_no(msg):
            return
        try:
            msm_enrol(options["enrolment_token"], metainfo=config)
        except Exception as ex:
            raise CommandError(str(ex)) from None

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="command")
        subparsers.required = True

        enrol_subparser = subparsers.add_parser(
            self.ENROL_COMMAND,
            help="Enrol to a Site Manager instance.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        enrol_subparser.add_argument(
            "enrolment_token",
            metavar="enrolment-token",
            help=(
                "A token to authenticate with the MAAS Site Manager. "
                "It can be generated in the settings/tokens page of the "
                "MAAS Site Manager"
            ),
        )
        enrol_subparser.add_argument(
            "config_file",
            metavar="config-file",
            nargs="?",
            type=argparse.FileType(),
            help=(
                "An optional config file where additional "
                "metadata of a specific MAAS region can be given. "
                "It can be downloaded in our documentation."
            ),
        )

        subparsers.add_parser(
            self.STATUS_COMMAND,
            help="Check the status of enrolment with a Site Manager instance.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

        subparsers.add_parser(
            self.WITHDRAW_COMMAND,
            help="Withdraw an enrolment request with a Site Manager instance.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

    def handle(self, *args, **options):
        handlers = {
            self.ENROL_COMMAND: self._enrol,
            self.STATUS_COMMAND: self._status,
            self.WITHDRAW_COMMAND: self._withdraw,
        }
        return handlers[options["command"]](options)


def get_cert_verify_msg(base_url: str) -> str:
    """
    Retrieve the SSL certificate from the given url, and compose a
    message to the user with details about the certificate.
    """
    try:
        cert, fingerprint = get_ssl_certificate(base_url)
    except CertificateError as e:
        if "verify failed: self-signed" in str(e):
            print(
                f"\nThe certificate provided by {base_url} is not trusted. Cannot proceed with enrolment.\n"
            )
        else:
            print(f"\nCould not retrieve a certificate from {base_url}.\n")
        raise

    # http
    if cert is None:
        msg = (
            f"\nThe URL of the Site Manager you want to enrol with is {base_url}\n\n"
            "Are you sure you want to enrol with this site? [Y] [n]"
        )
        return msg

    # https
    subject = cert.get_subject().CN
    expiration = datetime.strptime(
        cert.get_notAfter().decode(), "%Y%m%d%H%M%SZ"
    ).strftime("%a, %d %b. %Y")
    issuer = cert.get_issuer().CN
    msg = (
        f"The URL of the Site Manager you want to enrol with is {base_url}.\n\n"
        "The certificate of the Site Manager you want to enrol with is "
        "the following:\n\n"
        f"\tCN:\t\t\t{subject}\n"
        f"\tExpiration date:\t{expiration}\n"
        f"\tFingerprint:\t\t{fingerprint}\n"
        f"\tIssued By:\t\t{issuer}\n\n"
        "You can verify its authenticity by comparing the certificate "
        "shown above with the certificate shown in the settings/"
        "tokens page of Site Manager.\nAre you sure you want to enrol "
        "with this site? [Y] [n]"
    )
    return msg
