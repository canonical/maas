# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'import_images',
    'main',
    'make_arg_parser',
    'read_config',
    ]

from argparse import ArgumentParser
import errno
import os
from textwrap import dedent

from provisioningserver.boot import BootMethodRegistry
from provisioningserver.boot.tftppath import list_boot_images
from provisioningserver.config import BootConfig
from provisioningserver.import_images.download_descriptions import (
    download_all_image_descriptions,
    )
from provisioningserver.import_images.download_resources import (
    download_all_boot_resources,
    )
from provisioningserver.import_images.helpers import logger
from provisioningserver.import_images.product_mapping import map_products
from provisioningserver.utils import (
    atomic_write,
    call_and_check,
    locate_config,
    read_text_file,
    )


class NoConfig(Exception):
    """Raised when no configuration for the script has been specified."""


class NoConfigFile(Exception):
    """Raised when the config file for the script doesn't exist."""


def tgt_entry(osystem, arch, subarch, release, label, image):
    """Generate tgt target used to commission arch/subarch with release

    Tgt target used to commission arch/subarch machine with a specific Ubuntu
    release should have the following name: ephemeral-arch-subarch-release.
    This function creates target description in a format used by tgt-admin.
    It uses arch, subarch and release to generate target name and image as
    a path to image file which should be shared. Tgt target is marked as
    read-only. Tgt target has 'allow-in-use' option enabled because this
    script actively uses hardlinks to do image management and root images
    in different folders may point to the same inode. Tgt doesn't allow us to
    use the same inode for different tgt targets (even read-only targets which
    looks like a bug to me) without this option enabled.

    :param osystem: Operating System name we generate tgt target for
    :param arch: Architecture name we generate tgt target for
    :param subarch: Subarchitecture name we generate tgt target for
    :param release: Ubuntu release we generate tgt target for
    :param label: The images' label
    :param image: Path to the image which should be shared via tgt/iscsi
    :return Tgt entry which can be written to tgt-admin configuration file
    """
    prefix = 'iqn.2004-05.com.ubuntu:maas'
    target_name = 'ephemeral-%s-%s-%s-%s-%s' % (
        osystem,
        arch,
        subarch,
        release,
        label
        )
    entry = dedent("""\
        <target {prefix}:{target_name}>
            readonly 1
            allow-in-use yes
            backing-store "{image}"
            driver iscsi
        </target>
        """).format(prefix=prefix, target_name=target_name, image=image)
    return entry


def install_boot_loaders(destination):
    """Install the all the required file from each bootloader method.
    :param destination: Directory where the loaders should be stored.
    """
    for _, method in BootMethodRegistry:
        method.install_bootloader(destination)


def make_arg_parser(doc):
    """Create an `argparse.ArgumentParser` for this script."""

    parser = ArgumentParser(description=doc)
    default_config = locate_config("bootresources.yaml")
    parser.add_argument(
        '--config-file', action="store", default=default_config,
        help="Path to config file "
             "(defaults to %s)" % default_config)
    return parser


def compose_targets_conf(snapshot_path):
    """Produce the contents of a snapshot's tgt conf file.

    :param snapshot_path: Filesystem path to a snapshot of current upstream
        boot resources.
    :return: Contents for a `targets.conf` file.
    :rtype: bytes
    """
    # Use a set to make sure we don't register duplicate entries in tgt.
    entries = set()
    for item in list_boot_images(snapshot_path):
        osystem = item['osystem']
        arch = item['architecture']
        subarch = item['subarchitecture']
        release = item['release']
        label = item['label']
        entries.add((osystem, arch, subarch, release, label))
    tgt_entries = []
    for osystem, arch, subarch, release, label in sorted(entries):
        root_image = os.path.join(
            snapshot_path, osystem, arch, subarch,
            release, label, 'root-image')
        if os.path.isfile(root_image):
            entry = tgt_entry(
                osystem, arch, subarch, release, label, root_image)
            tgt_entries.append(entry)
    text = ''.join(tgt_entries)
    return text.encode('utf-8')


def meta_contains(storage, content):
    """Does the `maas.meta` file match `content`?

    If the file's contents match the latest data, there is no need to update.
    """
    current_meta = os.path.join(storage, 'current', 'maas.meta')
    return (
        os.path.isfile(current_meta) and
        content == read_text_file(current_meta)
        )


def update_current_symlink(storage, latest_snapshot):
    """Symlink `latest_snapshot` as the "current" snapshot."""
    symlink_path = os.path.join(storage, 'current')
    if os.path.lexists(symlink_path):
        os.unlink(symlink_path)
    os.symlink(latest_snapshot, symlink_path)


def write_snapshot_metadata(snapshot, meta_file_content, targets_conf,
                            targets_conf_content):
    """Write "meta" file and tgt config for `snapshot`."""
    meta_file = os.path.join(snapshot, 'maas.meta')
    atomic_write(meta_file_content, meta_file, mode=0644)
    atomic_write(targets_conf_content, targets_conf, mode=0644)


def read_config(config_file=None):
    """Read boot resources config file.

    :param config_file: Path to the config file.  Defaults to
        `bootresources.yaml` in the configuration directory.
    :return: A dict representing the boot-resources configuration.
    :raise NoConfigFile: If the configuration file was not present.
    """
    # The config file is required.  We do not fall back to defaults if it's
    # not there.
    if config_file is None:
        config_file = locate_config("bootresources.yaml")
    try:
        return BootConfig.load_from_cache(filename=config_file)
    except IOError as ex:
        if ex.errno == errno.ENOENT:
            # No config file. We have helpful error output for this.
            raise NoConfigFile(ex)
        else:
            # Unexpected error.
            raise


def parse_config(config):
    """Given a YAML `config` string, return a `BootConfig` for it."""
    from StringIO import StringIO
    config_stream = StringIO(config)
    return BootConfig.parse(config_stream)


def import_images(config):
    """Import images.  Callable from both command line and Celery task.

    :param config: A dict representing the boot-resources configuration.
    """
    logger.info("Importing boot resources.")
    sources = config['boot']['sources']
    if len(sources) == 0:
        logger.warn("Can't import: no Simplestreams sources configured.")
        return

    image_descriptions = download_all_image_descriptions(config)
    if image_descriptions.is_empty():
        logger.warn(
            "No boot resources found.  Check configuration and connectivity.")
        return

    storage = config['boot']['storage']
    meta_file_content = image_descriptions.dump_json()
    if meta_contains(storage, meta_file_content):
        # The current maas.meta already contains the new config.  No need to
        # rewrite anything.
        return

    product_mapping = map_products(image_descriptions)

    snapshot_path = download_all_boot_resources(
        sources, storage, product_mapping)
    targets_conf = os.path.join(snapshot_path, 'maas.tgt')

    targets_conf_content = compose_targets_conf(snapshot_path)

    logger.info("Writing metadata and updating iSCSI targets.")
    write_snapshot_metadata(
        snapshot_path, meta_file_content, targets_conf, targets_conf_content)
    call_and_check([
        'sudo',
        '/usr/sbin/tgt-admin',
        '--conf', targets_conf,
        '--update', 'ALL',
        ])

    logger.info("Installing boot images snapshot %s.", snapshot_path)
    install_boot_loaders(snapshot_path)

    # If we got here, all went well.  This is now truly the "current" snapshot.
    update_current_symlink(storage, snapshot_path)
    logger.info("Import done.")


def main(args):
    """Entry point for the command-line import script.

    :param args: Command-line arguments as parsed by the `ArgumentParser`
        returned by `make_arg_parser`.
    :raise NoConfigFile: If a config file is specified but doesn't exist.
    :raise NoConfig: If no config is specified at the command line and
        no config file is provided.
    """
    if args.config:
        config = parse_config(args.config)
    elif args.config_file:
        config = read_config(args.config_file)
    else:
        raise NoConfig()
    import_images(config=config)
