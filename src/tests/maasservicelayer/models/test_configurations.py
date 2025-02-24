#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
import re

from pydantic import ValidationError
import pytest

from maasservicelayer.models.configurations import (
    ConfigFactory,
    DNSTrustedAclConfig,
    HttpProxyConfig,
    MAASAutoIPMIKGBmcKeyConfig,
    MAASProxyPortConfig,
    MAASSyslogPortConfig,
    NTPServersConfig,
    RemoteSyslogConfig,
    UpstreamDnsConfig,
)
from tests.utils.assertions import assert_unordered_items_equal


class TestMAASProxyPortConfig:
    @pytest.mark.parametrize(
        "port, expected",
        [
            (8000, 8000),  # Valid default port
            (1024, 1024),  # Valid non-reserved port
            (65535, 65535),  # Upper limit valid port
            (5238, 5238),  # Valid
            (5285, 5285),  # Valid
            (None, None),  # None should be accepted
        ],
    )
    def test_valid_ports(self, port, expected):
        config = MAASProxyPortConfig(value=port)
        assert config.value == expected

    @pytest.mark.parametrize(
        "port",
        [
            (-1),  # Negative port
            (0),  # Reserved port
            (1023),  # Reserved port
            (65536),  # Above valid range
            (80),  # Reserved system port
            (5239),  # Reserved MAAS service port
            (5248),  # Reserved MAAS service port
            (5284),  # Reserved MAAS service port
        ],
    )
    def test_invalid_ports(self, port):
        with pytest.raises(
            ValidationError, match="Unable to change port number"
        ):
            MAASProxyPortConfig(value=port)


class TestHttpProxyConfig:
    @pytest.mark.parametrize(
        "proxy_url",
        [
            ("http://proxy.example.com"),
            ("https://secure-proxy.com"),
        ],
    )
    def test_valid_http_proxy(self, proxy_url):
        config = HttpProxyConfig(value=proxy_url)
        assert config.value == proxy_url

    @pytest.mark.parametrize(
        "proxy_url",
        [
            ("invalid-url"),
            ("ftp://proxy.example.com"),
            ("not_a_url"),
            ("10.0.0.1:5240"),  # No protocol.
        ],
    )
    def test_invalid_http_proxy(self, proxy_url):
        with pytest.raises(ValidationError):
            HttpProxyConfig(value=proxy_url)


class TestUpstreamDnsConfig:
    @pytest.mark.parametrize(
        "dns_addresses",
        [
            (["8.8.8.8", "8.8.4.4"]),
            (["2001:4860:4860::8888", "2001:4860:4860::8844"]),
        ],
    )
    def test_valid_upstream_dns(self, dns_addresses):
        config = UpstreamDnsConfig(value=dns_addresses)
        config_ip_addresses = [str(ip) for ip in config.value]
        assert_unordered_items_equal(config_ip_addresses, dns_addresses)

    @pytest.mark.parametrize(
        "dns_addresses",
        [
            (["invalid-ip"]),
            (["999.999.999.999"]),  # Out of range IP
            (["2001:xyz::1"]),  # Invalid IPv6
        ],
    )
    def test_invalid_upstream_dns(self, dns_addresses):
        with pytest.raises(ValidationError):
            UpstreamDnsConfig(value=dns_addresses)


class TestDNSTrustedAclConfig:
    @pytest.mark.parametrize(
        "trusted_acl, expected",
        [
            (
                "10.0.0.0/24, 11.0.0.0/24",
                "10.0.0.0/24 11.0.0.0/24",
            ),
            ("an-hostname", "an-hostname"),
            ("8.8.8.8, 8.8.4.4", "8.8.8.8 8.8.4.4"),
            (
                "2001:4860:4860::8888, 2001:4860:4860::8844",
                "2001:4860:4860::8888 2001:4860:4860::8844",
            ),
            ("example.com", "example.com"),
        ],
    )
    def test_valid_dns_trusted_acl(self, trusted_acl, expected):
        config = DNSTrustedAclConfig(value=trusted_acl)
        assert config.value == expected

    @pytest.mark.parametrize(
        "trusted_acl",
        [
            "invalid-hostname$$$",
            "999.999.999.999",  # Out of range IP
            "2001:xyz::1",  # Invalid IPv6
        ],
    )
    def test_invalid_dns_trusted_acl(self, trusted_acl):
        with pytest.raises(ValidationError):
            DNSTrustedAclConfig(value=trusted_acl)

    def test_separators_dont_conflict_with_ipv4_address(self):
        assert re.search(DNSTrustedAclConfig._separators, "10.0.0.1") is None

    def test_separators_dont_conflict_with_ipv6_address(self):
        assert (
            re.search(
                DNSTrustedAclConfig._separators,
                "2001:4860:4860::8888",
            )
            is None
        )


class TestNTPServersConfig:
    @pytest.mark.parametrize(
        "input_value, expected",
        [
            ("192.168.0.1", "192.168.0.1"),
            ("ntp.example.com", "ntp.example.com"),
            ("192.168.0.1, ntp.example.com", "192.168.0.1 ntp.example.com"),
            ("192.168.0.1 ,  ntp.example.com", "192.168.0.1 ntp.example.com"),
            (
                "192.168.0.1, 2001:db8::1, ntp.example.com",
                "192.168.0.1 2001:db8::1 ntp.example.com",
            ),
        ],
    )
    def test_validate_value(self, input_value, expected):
        config = NTPServersConfig(value=input_value)
        assert config.value == expected

    @pytest.mark.parametrize(
        "input_value, expected_exception",
        [
            ("999.999.999.999", ValueError),
            ("ntp..example.com", ValueError),
            ("[2001:db8::g1]", ValueError),
        ],
    )
    def test_invalid_ntp_servers(self, input_value, expected_exception):
        with pytest.raises(expected_exception):
            NTPServersConfig(value=input_value)

    @pytest.mark.parametrize(
        "input_value, expected",
        [
            ("192.168.0.1 , ntp.example.com", "192.168.0.1 ntp.example.com"),
            (
                " ntp.example.com  , 192.168.0.1 , ",
                "ntp.example.com 192.168.0.1",
            ),
            ("   192.168.0.1 , 192.168.0.2", "192.168.0.1 192.168.0.2"),
        ],
    )
    def test_separator(self, input_value, expected):
        config = NTPServersConfig(value=input_value)
        assert config.value == expected

    @pytest.mark.parametrize(
        "input_value, expected_exception",
        [
            ("http://ntp.example.com", ValueError),  # Invalid scheme in URL
            ("ntp:example.com", ValueError),  # Invalid scheme format
        ],
    )
    def test_invalid_formats(self, input_value, expected_exception):
        with pytest.raises(expected_exception):
            NTPServersConfig(value=input_value)

    def test_separators_dont_conflict_with_ipv4_address(self):
        assert re.search(NTPServersConfig._separators, "10.0.0.1") is None

    def test_separators_dont_conflict_with_ipv6_address(self):
        assert (
            re.search(
                NTPServersConfig._separators,
                "2001:4860:4860::8888",
            )
            is None
        )


class TestRemoteSyslogConfig:
    @pytest.mark.parametrize(
        "input_value",
        [
            ("invalid_host:port:extra"),  # Invalid format, extra parts
            ("localhost::"),  # Empty port after the colon
            ("validhost:abcd"),  # Non numeric port
        ],
    )
    def test_invalid_values(self, input_value):
        with pytest.raises(ValidationError):
            RemoteSyslogConfig(value=input_value)

    @pytest.mark.parametrize(
        "input_value, expected",
        [
            ("", None),  # Empty string, should revert to None
            (None, None),  # None, should stay None
            (
                "127.0.0.1:10000",
                "127.0.0.1:10000",
            ),  # Specific port, should remain the same
        ],
    )
    def test_field_initialization(self, input_value, expected):
        config = RemoteSyslogConfig(value=input_value)
        assert config.value == expected


class TestMAASSyslogPortConfig:
    @pytest.mark.parametrize(
        "port, expected",
        [
            (5247, 5247),  # Allow internal syslog port
            (1024, 1024),  # Valid non-reserved port
            (65535, 65535),  # Upper limit valid port
            (5238, 5238),  # Valid
            (5285, 5285),  # Valid
        ],
    )
    def test_valid_ports(self, port, expected):
        config = MAASSyslogPortConfig(value=port)
        assert config.value == expected

    @pytest.mark.parametrize(
        "port",
        [
            (-1),  # Negative port
            (0),  # Reserved port
            (1023),  # Reserved port
            (65536),  # Above valid range
            (80),  # Reserved system port
            (5239),  # Reserved MAAS service port
            (5248),  # Reserved MAAS service port
            (5284),  # Reserved MAAS service port
        ],
    )
    def test_invalid_ports(self, port):
        with pytest.raises(
            ValidationError, match="Unable to change port number"
        ):
            MAASSyslogPortConfig(value=port)


class TestMAASAutoIPMIKGBmcKeyConfig:
    @pytest.mark.parametrize(
        "input_value",
        [
            (""),  # Empty string should be allowed
            ("abcdefghijklmnopqrst"),  # Valid 20 character key
            ("0x" + "a" * 40),  # Valid 40 character hex key
        ],
    )
    def test_valid_ipmi_key(self, input_value):
        config = MAASAutoIPMIKGBmcKeyConfig(value=input_value)
        assert config.value == input_value

    @pytest.mark.parametrize(
        "input_value",
        [
            "shortkey",  # Too short (less than 20 characters)
            "a" * 21,  # One character too long for the 20 character limit
            "0x"
            + "a" * 39,  # Hexadecimal key with 39 characters (should be 40)
            "0x12345g6789abcdef",  # Invalid hex key (contains non-hex character 'g')
            "some_invalid_key_which_is_way_too_long",  # Key too long, not hex or 20 characters
        ],
    )
    def test_invalid_ipmi_key(self, input_value):
        with pytest.raises(ValueError):
            MAASAutoIPMIKGBmcKeyConfig(value=input_value)


class TestConfigFactory:
    def test_parse_public_config_none_values(self):
        for name, config in ConfigFactory.ALL_CONFIGS.items():
            if config.is_public:
                ConfigFactory.parse_public_config(name=name, value=None)

    def test_parse_public_config_unknown_config(self):
        with pytest.raises(ValueError):
            ConfigFactory.parse_public_config("_not_a_valid_config", None)

    def test_parse_public_config_values(self):
        for name, config in ConfigFactory.ALL_CONFIGS.items():
            if config.is_public:
                ConfigFactory.parse_public_config(
                    name=name, value=config.default
                )

    @pytest.mark.parametrize(
        "name",
        [
            "active_discovery_last_scan",
            "commissioning_osystem",
            "maas_url",
            "omapi_key",
            "rpc_shared_secret",
            "tls_port",
            "uuid",
            "vault_enabled",
        ],
    )
    def test_private_config(self, name: str):
        # The difference between the set of possible configuration keys and
        # those permitted via the Web API is small but important to security.
        with pytest.raises(ValueError):
            ConfigFactory.parse_public_config(name, None)

    def test_parse_config_none_values(self):
        for config in ConfigFactory.ALL_CONFIGS:
            ConfigFactory.parse(name=config, value=None)

    def test_parse_config_unknown_config(self):
        with pytest.raises(ValueError):
            ConfigFactory.parse("_not_a_valid_config", None)

    def test_parse_config_values(self):
        for name, clazz in ConfigFactory.ALL_CONFIGS.items():
            ConfigFactory.parse(name=name, value=clazz.default)
