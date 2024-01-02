import pytest

from maasserver.triggers.models.dns_notifications import (
    DynamicDNSUpdateNotification,
    NotValidDNSNotificationPayload,
)
from maastesting.testcase import MAASTestCase


class TestDynamicDNSUpdateNotification(MAASTestCase):
    def test_is_valid(self):
        valid_payloads = [
            "5470596195891583856bdf849f2acfda RELOAD",
            "bedf5c93d7e7b82d45cfc555630cb8b1 INSERT maas taillow A 0 10.246.64.208",
            "adfbc39c6213a062afb584b90d508f52 DELETE mydomain mudkip A 192.168.33.163",
        ]
        for valid_payload in valid_payloads:
            notification = DynamicDNSUpdateNotification(valid_payload)
            assert notification.is_valid()

    def test_invalid_payloads(self):
        invalid_payloads = [
            "",
            "5470596195891583849f2acfda RELOAD",
            "ADFBC39c6213a062afb584B90D508F52 DELETE mydomain mudkip A 192.168.33.163",
        ]
        for invalid_payload in invalid_payloads:
            notification = DynamicDNSUpdateNotification(invalid_payload)
            assert not notification.is_valid()

    def test_get_decoded_message(self):
        payload = "adfbc39c6213a062afb584b90d508f52 DELETE mydomain mudkip A 192.168.33.163"
        notification = DynamicDNSUpdateNotification(payload)
        assert (
            notification.get_decoded_message()
            == "DELETE mydomain mudkip A 192.168.33.163"
        )

    def test_get_decoded_message_if_invalid(self):
        payload = ""
        notification = DynamicDNSUpdateNotification(payload)
        with pytest.raises(NotValidDNSNotificationPayload):
            notification.get_decoded_message()
