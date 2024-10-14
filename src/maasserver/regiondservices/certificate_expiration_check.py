# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta, timezone

from twisted.internet.defer import inlineCallbacks

from maasserver.certificates import get_maas_certificate
from maasserver.models import Config, Notification
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.utils.services import SingleInstanceService

REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT = "regiond-reverse-proxy-cert-expire"
REGIOND_CERT_EXPIRED_NOTIFICATION_IDENT = "regiond-reverse-proxy-cert-expired"


def clear_tls_notifications():
    Notification.objects.filter(
        ident__in=(
            REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT,
            REGIOND_CERT_EXPIRED_NOTIFICATION_IDENT,
        )
    ).delete()


@transactional
def check_tls_certificate():
    config = Config.objects.get_configs(
        [
            "tls_cert_expiration_notification_enabled",
            "tls_cert_expiration_notification_interval",
        ]
    )
    if not config["tls_cert_expiration_notification_enabled"]:
        clear_tls_notifications()
        return

    cert = get_maas_certificate()
    if not cert or not cert.expiration():
        return

    interval = config["tls_cert_expiration_notification_interval"]
    expire_in = (cert.expiration() - datetime.now(timezone.utc)).days

    if expire_in <= 0:
        # cert already expired. remove previous notification about
        # "due to expire in {days}" and create "has expired"
        Notification.objects.filter(
            ident=REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT
        ).delete()
        message = (
            "The TLS certificate has expired. "
            "You can renew it following the "
            "<a href='https://maas.io/docs/how-to-enable-tls-encryption"
            "#heading--renew-your-tls-certificate'>renew certificate instructions</a>."
        )
        Notification.objects.update_or_create(
            ident=REGIOND_CERT_EXPIRED_NOTIFICATION_IDENT,
            defaults={
                "category": "warning",
                "message": message,
                "users": False,
                "admins": True,
                "dismissable": True,
            },
        )
        return

    if expire_in <= interval:
        # The certificate is within the expiration window, warn about
        # expiration and ensure there's no leftover "already expired"
        # notification.
        Notification.objects.filter(
            ident=REGIOND_CERT_EXPIRED_NOTIFICATION_IDENT
        ).delete()
        Notification.objects.update_or_create(
            ident=REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT,
            defaults={
                "category": "info",
                "message": "Your TLS certificate is due to expire in {days} days. Please, contact your admin to renew it.",
                "users": False,
                "admins": True,
                "dismissable": True,
                "context": {
                    "days": expire_in,
                },
            },
        )
        return

    # Certificate expires later than the interval, ensure there's no
    # leftover notification
    clear_tls_notifications()


class CertificateExpirationCheckService(SingleInstanceService):
    """Periodically check TLS cert expiration."""

    LOCK_NAME = SERVICE_NAME = "certificate-expiration-check"
    INTERVAL = timedelta(hours=12)

    @inlineCallbacks
    def do_action(self):
        yield deferToDatabase(check_tls_certificate)
