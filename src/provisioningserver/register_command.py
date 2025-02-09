# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Register rack controller.

A MAAS region controller URL where this rack controller should connect
to will be prompted for when it has not been supplied.

Additionially, a shared secret required for communications with the region
controller will be prompted for (or read from stdin in a non-interactive
shell, see below) if one has not previously been installed. You can find it
at /var/lib/maas/secret on the region.

Only the shared secret can be supplied via stdin (non-interactive shell).
When this is the case, the user will need to supply the MAAS region
controller URL.
"""

from sys import stderr, stdin
from textwrap import dedent

from provisioningserver.config import ClusterConfiguration
from provisioningserver.security import InstallSharedSecretScript
from provisioningserver.utils.env import MAAS_ID, MAAS_SHARED_SECRET
from provisioningserver.utils.shell import call_and_check, ExternalProcessError

all_arguments = ("--url", "--secret")


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Examples of command usage (with interactive input):

        - Supplying both URL and shared secret (not prompted for either):

        # maas-rack register --secret <shared-secret> --url <your-url>

        - Supplying URL but not shared secret (prompted for shared secret):

        # maas-rack register --url <your-url>
        Secret (hex/base16 encoded): <shared-secret>
        Secret installed to /var/lib/maas/secret.

        - Supplying shared secret but not URL (prompted for URL):

        # maas-rack register --secret <shared-secret>
        MAAS region controller URL: <your-url>
        MAAS region controller URL saved as <your-url>

        - Not supplying URL or shared secret (prompted for both):

        # maas-rack register
        MAAS region controller URL: <your-url>
        MAAS region controller URL saved as <your-url>
        Secret (hex/base16 encoded): <shared-secret>
        Secret installed to /var/lib/maas/secret.

        - Supplying secret via stdin but not URL
          (error message printed as this is non-interactive shell):

        # echo <shared-secret> | maas-rack register
        MAAS region controller URL must be passed as an argument when supplying
        the shared secret via stdin with a non-interactive shell.

        - Supplying secret via stdin and URL (not prompted):

        # echo <shared-secret> | maas-rack register --url <your-url>
        Secret installed to /var/lib/maas/secret.
    """
    )
    parser.add_argument(
        "--url",
        action="append",
        required=False,
        help=(
            "URL of the region controller where to connect this "
            "rack controller."
        ),
    )
    parser.add_argument(
        "--secret",
        action="store",
        required=False,
        help=(
            "The shared secret required to connect to the region controller.  "
            "You can find it on /var/lib/maas/secret on the region.  "
            "The secret must be hex/base16 encoded."
        ),
    )


def run(args):
    """Register the rack controller with a region controller."""
    # If stdin supplied to program URL must be passed as argument.
    if not stdin.isatty() and args.url is None:
        print(
            "MAAS region controller URL must be given when supplying the "
            "shared secret via stdin with a non-interactive shell."
        )
        raise SystemExit(1)
    try:
        call_and_check(["systemctl", "stop", "maas-rackd"])
    except ExternalProcessError as e:
        print("Unable to stop maas-rackd service.", file=stderr)
        print("Failed with error: %s." % e.output_as_unicode, file=stderr)
        raise SystemExit(1)  # noqa: B904
    # maas_id could be stale so remove it
    MAAS_ID.set(None)
    if args.url is not None:
        with ClusterConfiguration.open_for_update() as config:
            config.maas_url = args.url
    else:
        try:
            url = input("MAAS region controller URL: ")
        except EOFError:
            print()  # So that the shell prompt appears on the next line.
            raise SystemExit(1)  # noqa: B904
        except KeyboardInterrupt:
            print()  # So that the shell prompt appears on the next line.
            raise
        with ClusterConfiguration.open_for_update() as config:
            config.maas_url = url
        print("MAAS region controller URL saved as %s." % url)
    if args.secret is not None:
        MAAS_SHARED_SECRET.set(args.secret)
    else:
        InstallSharedSecretScript.run(args)
    try:
        call_and_check(["systemctl", "enable", "maas-rackd"])
        call_and_check(["systemctl", "start", "maas-rackd"])
    except ExternalProcessError as e:
        print(
            "Unable to enable and start the maas-rackd service.", file=stderr
        )
        print("Failed with error: %s." % e.output_as_unicode, file=stderr)
        raise SystemExit(1)  # noqa: B904
