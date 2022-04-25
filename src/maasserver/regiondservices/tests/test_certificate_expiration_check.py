# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

from django.db import transaction
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver.models.config import Config
from maasserver.models.notification import Notification
from maasserver.regiondservices.certificate_expiration_check import (
    CertificateExpirationCheckService,
    REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT,
    REGIOND_CERT_EXPIRED_NOTIFICATION_IDENT,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from provisioningserver.testing.certificates import get_sample_cert

wait_for_reactor = wait_for()


class TestCertificateExpirationCheckService(MAASTransactionServerTestCase):
    def set_config(self, cert, enabled=True, interval=10):
        with transaction.atomic():
            Config.objects.set_config("tls_key", cert.private_key_pem())
            Config.objects.set_config("tls_cert", cert.certificate_pem())
            Config.objects.set_config(
                "tls_cert_expiration_notification_enabled", enabled
            )
            Config.objects.set_config(
                "tls_cert_expiration_notification_interval", interval
            )

    def get_notifications(self):
        notifications = Notification.objects.filter(
            ident__in=[
                REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT,
                REGIOND_CERT_EXPIRED_NOTIFICATION_IDENT,
            ]
        ).order_by("ident")
        return list(notifications)

    @wait_for_reactor
    @inlineCallbacks
    def test_no_notifications_when_not_enabled(self):
        yield deferToDatabase(
            Config.objects.set_config,
            "tls_cert_expiration_notification_enabled",
            False,
        )
        yield deferToDatabase(
            factory.make_Notification,
            ident=REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT,
            admins=True,
            dismissable=True,
        )

        service = CertificateExpirationCheckService(reactor)
        yield service.startService()
        yield service.stopService()

        notifications = yield deferToDatabase(self.get_notifications)
        self.assertEqual(0, len(notifications))

    @wait_for_reactor
    @inlineCallbacks
    def test_notify_when_certificate_will_expire(self):
        sample_cert = get_sample_cert(validity=timedelta(days=5))
        yield deferToDatabase(self.set_config, cert=sample_cert)

        service = CertificateExpirationCheckService(reactor)
        yield service.startService()
        yield service.stopService()

        notifications = yield deferToDatabase(self.get_notifications)
        self.assertEqual(1, len(notifications))
        notification = notifications[0]
        self.assertIsNotNone(notification)
        self.assertEqual("info", notification.category)
        self.assertTrue(notification.dismissable)
        self.assertTrue(notification.admins)
        self.assertFalse(notification.users)
        self.assertEqual(4, notification.context["days"])

    @wait_for_reactor
    @inlineCallbacks
    def test_notify_when_certificate_will_expire_update(self):
        sample_cert = get_sample_cert(validity=timedelta(days=5))
        yield deferToDatabase(self.set_config, cert=sample_cert)
        yield deferToDatabase(
            factory.make_Notification,
            ident=REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT,
            category="info",
            admins=True,
            dismissable=True,
            context={"days": 10},
        )
        service = CertificateExpirationCheckService(reactor)
        yield service.startService()
        yield service.stopService()

        notifications = yield deferToDatabase(self.get_notifications)
        self.assertEqual(1, len(notifications))
        notification = notifications[0]
        self.assertIsNotNone(notification)
        self.assertEqual("info", notification.category)
        self.assertTrue(notification.dismissable)
        self.assertTrue(notification.admins)
        self.assertFalse(notification.users)
        self.assertEqual(4, notification.context["days"])

    @wait_for_reactor
    @inlineCallbacks
    def test_notify_when_certificate_expired(self):
        sample_cert = get_sample_cert(validity=timedelta(days=0))
        yield deferToDatabase(self.set_config, cert=sample_cert)
        yield deferToDatabase(
            factory.make_Notification,
            ident=REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT,
            admins=True,
            dismissable=True,
        )
        service = CertificateExpirationCheckService(reactor)
        yield service.startService()
        yield service.stopService()

        notifications = yield deferToDatabase(self.get_notifications)
        self.assertEqual(1, len(notifications))
        notification = notifications[0]
        self.assertIsNotNone(notification)
        self.assertEqual("warning", notification.category)
        self.assertTrue(notification.dismissable)
        self.assertTrue(notification.admins)
        self.assertFalse(notification.users)
        self.assertEqual(
            REGIOND_CERT_EXPIRED_NOTIFICATION_IDENT, notification.ident
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_notify_when_certificate_renewed_after_expired(self):
        sample_cert = get_sample_cert(validity=timedelta(days=30))
        yield deferToDatabase(self.set_config, cert=sample_cert)
        yield deferToDatabase(
            factory.make_Notification,
            ident=REGIOND_CERT_EXPIRED_NOTIFICATION_IDENT,
            admins=True,
            dismissable=True,
        )
        service = CertificateExpirationCheckService(reactor)
        yield service.startService()
        yield service.stopService()

        notifications = yield deferToDatabase(self.get_notifications)
        self.assertEqual(0, len(notifications))

    @wait_for_reactor
    @inlineCallbacks
    def test_notify_when_certificate_renewed_before_expired(self):
        sample_cert = get_sample_cert(validity=timedelta(days=30))
        yield deferToDatabase(self.set_config, cert=sample_cert)
        yield deferToDatabase(
            factory.make_Notification,
            ident=REGIOND_CERT_EXPIRE_NOTIFICATION_IDENT,
            admins=True,
            dismissable=True,
        )
        service = CertificateExpirationCheckService(reactor)
        yield service.startService()
        yield service.stopService()

        notifications = yield deferToDatabase(self.get_notifications)
        self.assertEqual(0, len(notifications))
