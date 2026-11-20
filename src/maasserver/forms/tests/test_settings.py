# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from textwrap import dedent

from django import forms
from django.core.exceptions import ValidationError

from maasserver.forms.settings import (
    CONFIG_ITEMS,
    get_config_doc,
    get_config_field,
    get_config_form,
)
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.forms import compose_invalid_choice_text
from maasservicelayer.models import configurations


class TestGetConfigField(MAASServerTestCase):
    def test_get_config_field_validates_config_name(self):
        config_name = factory.make_string()
        self.assertRaises(forms.ValidationError, get_config_field, config_name)

    def test_get_config_field_creates_field(self):
        field = get_config_field("maas_name")
        label = CONFIG_ITEMS["maas_name"]["form_kwargs"]["label"]
        self.assertEqual(label, field.label)


class TestGetConfigForm(MAASServerTestCase):
    def test_get_config_form_returns_initialized_form(self):
        maas_name = factory.make_string()
        Config.objects.set_config("maas_name", maas_name)
        form = get_config_form("maas_name")
        # The form is populated with the value of the 'maas_name' config item.
        self.assertEqual({"maas_name": maas_name}, form.initial)


class TestGetConfigDoc(MAASServerTestCase):
    def test_get_config_doc(self):
        config_items = {
            "testitem": {
                "default": "foo",
                "form": forms.CharField,
                "form_kwargs": {
                    "label": "bar",
                    "choices": [
                        ("b", "B"),
                        ("a", "A"),
                    ],
                },
            },
        }
        doc = get_config_doc(config_items=config_items)
        # choices are returned in the correct order
        self.assertEqual(
            doc,
            dedent(
                """\
                Available configuration items:

                :testitem: bar. Available choices are: 'a' (A), 'b' (B).
                """
            ),
        )


class TestSpecificConfigSettings(MAASServerTestCase):
    def test_commissioning_distro_series_config(self):
        field = get_config_field("commissioning_distro_series")
        self.assertEqual(
            compose_invalid_choice_text(
                "commissioning_distro_series", field.choices
            ),
            field.error_messages["invalid_choice"],
        )

    def test_upstream_dns_accepts_ip_list(self):
        field = get_config_field("upstream_dns")
        ips1 = [factory.make_ip_address() for _ in range(3)]
        ips2 = [factory.make_ip_address() for _ in range(3)]
        input = " ".join(ips1) + " " + ",".join(ips2)
        self.assertEqual(" ".join(ips1 + ips2), field.clean(input))


class TestRemoteSyslogConfigSettings(MAASServerTestCase):
    def test_sets_empty_to_none(self):
        field = get_config_field("remote_syslog")
        self.assertIsNone(field.clean("   "))

    def test_adds_port(self):
        field = get_config_field("remote_syslog")
        self.assertEqual("192.168.1.1:514", field.clean("192.168.1.1"))

    def test_wraps_ipv6(self):
        field = get_config_field("remote_syslog")
        self.assertEqual("[::ffff]:514", field.clean("::ffff"))


class TestMAASSyslogPortConfigSettings(MAASServerTestCase):
    def test_allows_port_5247(self):
        field = get_config_field("maas_syslog_port")
        self.assertEqual(5247, field.clean("5247"))

    def test_doesnt_allow_port_5248(self):
        field = get_config_field("maas_syslog_port")
        self.assertRaises(ValidationError, field.clean, "5248")


class TestMAASThemeConfigSettings(MAASServerTestCase):
    def test_default_value(self):
        form = get_config_form("theme")
        self.assertEqual({"theme": ""}, form.initial)

    def test_theme_config(self):
        value = factory.make_hex_string(size=6)
        field = get_config_field("theme")
        self.assertEqual(value, field.clean(value))

    def test_theme_string_like(self):
        value = [1, 2, 3]
        field = get_config_field("theme")
        self.assertEqual(str(value), field.clean(value))


class TestMAASSessionTimeoutSettings(MAASServerTestCase):
    def test_default_value(self):
        form = get_config_form("session_length")
        self.assertEqual({"session_length": 1209600}, form.initial)

    def test_session_config(self):
        value = 300
        field = get_config_field("session_length")
        self.assertEqual(value, field.clean(value))


class TestRefreshTokenDurationConfigSettings(MAASServerTestCase):
    def test_default_value(self):
        form = get_config_form("refresh_token_duration")
        self.assertEqual({"refresh_token_duration": 2592000}, form.initial)

    def test_refresh_token_duration_config(self):
        value = 600
        field = get_config_field("refresh_token_duration")
        self.assertEqual(value, field.clean(value))


class TestIPMIKGConfigSettings(MAASServerTestCase):
    def test_default_value(self):
        form = get_config_form("maas_auto_ipmi_k_g_bmc_key")
        self.assertEqual({"maas_auto_ipmi_k_g_bmc_key": ""}, form.initial)

    def test_valid_nonhex_input(self):
        input_value = factory.make_string(20)
        field = get_config_field("maas_auto_ipmi_k_g_bmc_key")
        self.assertTrue(input_value, field.clean(input_value))

    def test_valid_hex_input(self):
        input_value = "0x" + factory.make_hex_string(40)
        field = get_config_field("maas_auto_ipmi_k_g_bmc_key")
        self.assertTrue(input_value, field.clean(input_value))

    def test_invalid_nonhex_input(self):
        input_value = factory.make_string(19)
        field = get_config_field("maas_auto_ipmi_k_g_bmc_key")
        self.assertRaises(ValidationError, field.clean, input_value)

    def test_invalid_hex_input(self):
        # Hex-based inputs must be prefixed with "0x"
        input_value = factory.make_hex_string(40)
        field = get_config_field("maas_auto_ipmi_k_g_bmc_key")
        self.assertRaises(ValidationError, field.clean, input_value)


class TestIPMICipherSuiteIDConfigSettings(MAASServerTestCase):
    def test_accepts_non_fips_suite_without_fips(self):
        self.patch(configurations, "is_fips_enabled").return_value = False
        field = get_config_field("maas_auto_ipmi_cipher_suite_id")
        self.assertEqual("3", field.clean("3"))

    def test_accepts_suite_17_with_fips(self):
        self.patch(configurations, "is_fips_enabled").return_value = True
        field = get_config_field("maas_auto_ipmi_cipher_suite_id")
        self.assertEqual("17", field.clean("17"))

    def test_rejects_non_fips_suite_with_fips(self):
        self.patch(configurations, "is_fips_enabled").return_value = True
        field = get_config_field("maas_auto_ipmi_cipher_suite_id")
        for value in ("3", ""):
            with self.subTest(value=value):
                error = self.assertRaises(ValidationError, field.clean, value)
                self.assertIn("not FIPS-approved", str(error))
