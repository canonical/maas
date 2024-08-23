# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Start-up utilities for the MAAS server."""

import logging

from django.db.utils import DatabaseError
from twisted.internet.defer import inlineCallbacks

from maasserver import locks, security
from maasserver.bootresources import initialize_image_storage
from maasserver.config import get_db_creds_vault_path, RegionConfiguration
from maasserver.deprecations import (
    log_deprecations,
    sync_deprecation_notifications,
)
from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE
from maasserver.models import (
    Config,
    ControllerInfo,
    Interface,
    Notification,
    RegionController,
)
from maasserver.models.config import ensure_uuid_in_config
from maasserver.models.domain import dns_kms_setting_changed
from maasserver.secrets import SecretManager, SecretNotFound
from maasserver.utils import synchronised
from maasserver.utils.certificates import (
    generate_ca_certificate,
    generate_signed_certificate,
)
from maasserver.utils.orm import (
    get_psycopg2_exception,
    post_commit_do,
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from maasserver.vault import (
    clear_vault_client_caches,
    get_region_vault_client,
    VaultClient,
)
from metadataserver.builtin_scripts import load_builtin_scripts
from provisioningserver.certificates import (
    Certificate,
    get_maas_cluster_cert_paths,
    store_maas_cluster_cert_tuple,
)
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.utils.env import (
    MAAS_SECRET,
    MAAS_SHARED_SECRET,
    MAAS_UUID,
)
from provisioningserver.utils.twisted import asynchronous, FOREVER, pause
from provisioningserver.utils.version import get_versions_info

maaslog = get_maas_logger("start-up")
logger = logging.getLogger(__name__)
log = LegacyLogger()


def migrate_db_credentials_if_necessary(client: VaultClient) -> None:
    """Checks if Vault is enabled on cluster and migrates the DB credentials accordingly."""
    vault_enabled = Config.objects.get_config("vault_enabled", False)
    delete_path = None

    with RegionConfiguration.open_for_update() as config:
        db_creds_on_disk = bool(config.database_name)
        if db_creds_on_disk ^ vault_enabled:
            logger.debug("DB credentials migration not required")
            # No operation required when:
            # - db credentials are on disk and vault_enabled is False
            # - db credentials are not on disk and vault_enabled is True
            return

        if db_creds_on_disk:
            # Migrate from config to Vault
            client.set(
                get_db_creds_vault_path(),
                {
                    "user": config.database_user,
                    "pass": config.database_pass,
                    "name": config.database_name,
                },
            )
            config.database_user = ""
            config.database_pass = ""
            config.database_name = ""
            logger.info("Migrated DB credentials from local config to vault")
            # No need to defer anything in case we failed to save
            # the config here, as we now have two copies of these secrets,
            # not zero. Failure to save the config will raise an exception
            # that will prevent region from starting up, and we'll get rid
            # of the local creds once config is successfully saved.
        else:
            # Migrate from Vault to config
            delete_path = get_db_creds_vault_path()
            creds = client.get(delete_path)
            config.database_user = creds["user"]
            config.database_pass = creds["pass"]
            config.database_name = creds["name"]
            logger.info("Migrated DB credentials from vault to local config")
            # We defer deletion of creds from the Vault because
            # the context manager calls `save` afterwards,
            # and it might fail, meaning we shouldn't delete
            # secrets from the Vault.

    if delete_path:
        # By that moment config should be saved successfully
        client.delete(delete_path)
        logger.info("Deleted DB credentials from vault")


def _cleanup_expired_discovered_ip_addresses() -> None:
    """
    This startup cleanup is needed for the following reasons:
    - Major cleanup for https://bugs.launchpad.net/maas/+bug/2049508
    - In case we missed some DHCP notifications related to discovered IP addresses, we clean up all the resources here.
    """

    # Delete all the dummy interfaces and IP addresses that have expired.
    # The related DNS records will be deleted when the django post_delete signal is handled.
    Interface.objects.filter(
        type=INTERFACE_TYPE.UNKNOWN,
        ip_addresses__ip__isnull=True,
        ip_addresses__alloc_type=IPADDRESS_TYPE.DISCOVERED,
    ).delete()


def _get_certificate_from_database(
    secret_manager: SecretManager, secret_name: str
) -> Certificate | None:
    try:
        raw_certificate = secret_manager.get_composite_secret(secret_name)
        return Certificate.from_pem(
            raw_certificate["key"],
            raw_certificate["cert"],
            ca_certs_material=raw_certificate.get("cacerts", ""),
        )
    except SecretNotFound:
        return None


def _create_cluster_certificate_if_necessary(
    client: VaultClient | None = None,
) -> Certificate:
    # Use the vault if configured.
    secret_manager = SecretManager(client)

    # The PK/certificate for the maas CA are not in the db yet
    maas_ca = _get_certificate_from_database(
        secret_manager, "maas-ca-certificate"
    )
    if not maas_ca:
        maas_ca = generate_ca_certificate("maas-ca")
        secrets = {
            "key": maas_ca.private_key_pem(),
            "cert": maas_ca.certificate_pem(),
        }
        secret_manager.set_composite_secret("maas-ca-certificate", secrets)

    # The PK/certificate for the cluster are not in the db yet
    cluster_certificate = _get_certificate_from_database(
        secret_manager, "cluster-certificate"
    )
    if not cluster_certificate:
        cluster_certificate = generate_signed_certificate(
            maas_ca, "maas-cluster", b"DNS:maas"
        )
        secrets = {
            "key": cluster_certificate.private_key_pem(),
            "cert": cluster_certificate.certificate_pem(),
            "cacerts": cluster_certificate.ca_certificates_pem(),
        }
        secret_manager.set_composite_secret("cluster-certificate", secrets)

    return cluster_certificate


@asynchronous(timeout=FOREVER)
@inlineCallbacks
def start_up(master=False):
    """Perform start-up tasks for this MAAS server.

    This is used to:
    - make sure the singletons required by the application are created
    - sync the configuration of the external systems driven by MAAS

    The method will be executed multiple times if multiple processes are used
    but this method uses database locking to ensure that the methods it calls
    internally are not run concurrently.
    """
    while True:
        try:
            # Since start_up now can be called multiple times in a process lifetime,
            # vault client caches should be cleared in order to re-read the configuration.
            # This prevents fetching shared secret from DB when Vault is already enabled.
            clear_vault_client_caches()

            # Ensure the shared secret is configured
            secret = yield security.get_shared_secret()
            MAAS_SECRET.set(secret)

            # Execute other start-up tasks that must not run concurrently with
            # other invocations of themselves, across the whole of this MAAS
            # installation.
            yield deferToDatabase(inner_start_up, master=master)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            raise
        except DatabaseError as e:
            psycopg2_exception = get_psycopg2_exception(e)
            if psycopg2_exception is None:
                maaslog.warning(
                    "Database error during start-up; " "pausing for 3 seconds."
                )
            elif psycopg2_exception.pgcode is None:
                maaslog.warning(
                    "Database error during start-up (PostgreSQL error "
                    "not reported); pausing for 3 seconds."
                )
            else:
                maaslog.warning(
                    "Database error during start-up (PostgreSQL error %s); "
                    "pausing for 3 seconds.",
                    psycopg2_exception.pgcode,
                )
            logger.error("Database error during start-up", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        except Exception:
            maaslog.warning("Error during start-up; pausing for 3 seconds.")
            logger.error("Error during start-up.", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        else:
            break


@with_connection  # Needed by the following lock.
@synchronised(locks.startup)
@transactional
def inner_start_up(master=False):
    """Startup jobs that must run serialized w.r.t. other starting servers."""
    # All commissioning and testing scripts are stored in the database. For
    # a commissioning ScriptSet to be created Scripts must exist first. Call
    # this early, only on the master process, to ensure they exist and are
    # only created once. If get_or_create_running_controller() is called before
    # this it will fail on first run.
    if master:
        load_builtin_scripts()

    # Ensure the this region is represented in the database. The first regiond
    # to pass through inner_start_up on this host can do this; it should NOT
    # be restricted to masters only. This also ensures that the MAAS ID is set
    # on the filesystem; it will be done in a post-commit hook and will thus
    # happen before `locks.startup` is released.
    node = RegionController.objects.get_or_create_running_controller()
    # Update region version
    ControllerInfo.objects.set_versions_info(node, get_versions_info())
    # Ensure the UUID is available, and set it to the local file
    MAAS_UUID.set(ensure_uuid_in_config())

    # Ensure the shared secret is written to file. This should only be written
    # if the node is also a rack, but observe-beacons (which also runs on
    # regions) requires it for the encryption key
    secret = MAAS_SECRET.get()
    MAAS_SHARED_SECRET.set(security.to_hex(secret))

    # Only perform the following if the master process for the
    # region controller.
    if master:
        # Cleanup in case we missed some DHCP notifications related to discovered ip addresses
        _cleanup_expired_discovered_ip_addresses()

        # Migrate DB credentials to Vault and set the flag if Vault client is configured
        client = get_region_vault_client()
        if client is not None:
            migrate_db_credentials_if_necessary(client)

        certificate = _create_cluster_certificate_if_necessary(client)

        def _store_certificates_on_disk(cluster_certificate: Certificate):
            # If the certificates are not on the disk yet store them.
            if not get_maas_cluster_cert_paths():
                store_maas_cluster_cert_tuple(
                    private_key=cluster_certificate.private_key_pem().encode(),
                    certificate=cluster_certificate.certificate_pem().encode(),
                    cacerts=cluster_certificate.ca_certificates_pem().encode(),
                )

        # Write the certificates on the disk only after the transaction is committed
        post_commit_do(_store_certificates_on_disk, certificate)

        ControllerInfo.objects.filter(node_id=node.id).update(
            vault_configured=bool(client)
        )
        # Freshen the kms SRV records.
        dns_kms_setting_changed()

        # Make sure the commissioning distro series is still a supported LTS.
        commissioning_distro_series = Config.objects.get_config(
            name="commissioning_distro_series"
        )
        ubuntu = UbuntuOS()
        if commissioning_distro_series not in (
            ubuntu.get_supported_commissioning_releases()
        ):
            Config.objects.set_config(
                "commissioning_distro_series",
                ubuntu.get_default_commissioning_release(),
            )
            Notification.objects.create_info_for_admins(
                "Ubuntu %s is no longer a supported commissioning "
                "series. Ubuntu %s has been automatically selected."
                % (
                    commissioning_distro_series,
                    ubuntu.get_default_commissioning_release(),
                ),
                ident="commissioning_release_deprecated",
            )

        with RegionConfiguration.open() as config:
            Config.objects.set_config("maas_url", config.maas_url)

        # Log deprecations and Update related notifications if needed
        log_deprecations(logger=log)
        sync_deprecation_notifications()

        # initialize the image storage
        initialize_image_storage(node)
