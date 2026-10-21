#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest

from maascommon.enums.ipmi import IPMICipherSuiteID
from maasservicelayer.context import Context
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.configurations import (
    MAASAutoIPMICipherSuiteIDConfig,
)
from maasservicelayer.models.script import Script
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.script_parameters import (
    clean_parameters_input,
    PARAMETER_TYPES,
    ScriptParametersService,
    validate_parameters_schema,
    validate_scripts_input,
)
from maasservicelayer.services.scripts import ScriptsService
from tests.fixtures.factories.script import make_script


def script_with(parameters: Any, **extra_details: Any) -> Script:
    extra_details.setdefault("timeout", timedelta(minutes=5))
    return make_script(parameters=parameters, **extra_details)


def errors_of(exc_info: pytest.ExceptionInfo) -> set[tuple[str, str]]:
    return {
        (detail.field, detail.message) for detail in exc_info.value.details
    }


class TestValidateParametersSchema:
    def test_accepts_all_parameter_types(self) -> None:
        parameters = {
            "boolean": {"type": "boolean", "argument_format": "--flag"},
            "choice": {
                "type": "choice",
                "choices": ["a", ["b", "Bee"]],
                "default": "a",
            },
            "interface": {
                "type": "interface",
                "argument_format": "--interface={name}",
            },
            "password": {"type": "password", "min": 8, "max": 64},
            "runtime": {"type": "runtime", "min": 0, "max": 60},
            "storage": {"type": "storage", "argument_format": "{path}"},
            "string": {"type": "string", "title": "T", "description": "D"},
            "url": {"type": "url", "allow_list": True, "required": False},
        }
        assert sorted(parameters) == sorted(PARAMETER_TYPES)

        assert validate_parameters_schema(parameters) == parameters

    def test_accepts_unsupported_type_when_not_required(self) -> None:
        validate_parameters_schema({"foo": {"type": "foo", "required": False}})

    def test_accepts_booleans_as_integers(self) -> None:
        validate_parameters_schema(
            {"runtime": {"type": "runtime", "min": False, "max": True}}
        )

    def test_accepts_choices_that_are_not_lists(self) -> None:
        validate_parameters_schema(
            {"choice": {"type": "choice", "choices": [1, {"a": "b"}]}}
        )

    def test_rejects_non_dict_schema(self) -> None:
        with pytest.raises(ValidationException) as exc_info:
            validate_parameters_schema(["runtime"])
        assert errors_of(exc_info) == {("parameters", "Must be a dictionary")}

    @pytest.mark.parametrize(
        "parameter, message",
        [
            ("not-a-dict", "param: must be a dictionary"),
            ({"type": 1, "required": False}, "1: type must be a string"),
            ({"type": "runtime", "min": "1"}, "1: min must be an integer"),
            ({"type": "runtime", "max": 1.5}, "1.5: max must be an integer"),
            ({"type": "string", "title": 1}, "1: title must be a string"),
            (
                {"type": "string", "description": 1},
                "1: description must be a string",
            ),
            (
                {"type": "string", "argument_format": []},
                "[]: argument_format must be a string",
            ),
            ({"type": "string", "default": 1}, "1: default must be a string"),
            (
                {"type": "string", "required": "yes"},
                "yes: required must be a boolean",
            ),
            (
                {"type": "url", "allow_list": "yes"},
                "yes: allow_list must be a boolean",
            ),
            (
                {"type": "string", "allow_list": True},
                "allow_list only supported with the url type.",
            ),
            (
                {"type": "choice", "choices": "a,b"},
                "choices must be a list",
            ),
            (
                {"type": "choice", "choices": [["a", "b", "c"]]},
                "choice must be a Django choice or string",
            ),
            (
                {"type": "choice", "choices": [["a", 1]]},
                "choice must be a Django choice or string",
            ),
            (
                {"type": "string", "choices": ["a"]},
                "choices only supported with the choice type.",
            ),
            (
                {"type": "choice"},
                'choices must be given with a "choice" parameter type!',
            ),
            (
                {"type": "foo"},
                f"foo: type must be one of {', '.join(PARAMETER_TYPES)}",
            ),
            (
                {"type": "storage", "min": 1},
                "Type doesn't support min or max",
            ),
            (
                {"type": "runtime", "min": -1},
                "runtime minimum must be greater than zero",
            ),
            (
                {"type": "runtime", "min": 10, "max": 5},
                "min must be less than max",
            ),
            (
                {"type": "storage", "argument_format": "--disk"},
                "storage: argument_format must contain one of {input}, "
                "{name}, {path}, {model}, {serial}",
            ),
            (
                {"type": "interface", "argument_format": "--nic"},
                "interface: argument_format must contain one of {input}, "
                "{name}, {mac}, {vendor}, {product}",
            ),
        ],
    )
    def test_rejects_invalid_parameter(
        self, parameter: Any, message: str
    ) -> None:
        with pytest.raises(ValidationException) as exc_info:
            validate_parameters_schema({"param": parameter})
        assert errors_of(exc_info) == {("parameters", message)}

    def test_reports_all_errors(self) -> None:
        with pytest.raises(ValidationException) as exc_info:
            validate_parameters_schema(
                {
                    "runtime": {"type": "runtime", "min": "1"},
                    "choice": {"type": "choice"},
                }
            )
        assert errors_of(exc_info) == {
            ("parameters", "1: min must be an integer"),
            (
                "parameters",
                'choices must be given with a "choice" parameter type!',
            ),
        }


class TestCleanParametersInput:
    def test_rejects_invalid_schema_before_input(self) -> None:
        script = script_with({"choice": {"type": "choice"}})
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {"unknown": "value"})
        assert errors_of(exc_info) == {
            (
                "parameters",
                'choices must be given with a "choice" parameter type!',
            )
        }

    def test_rejects_non_dict_input(self) -> None:
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script_with({}), ["value"])
        assert errors_of(exc_info) == {("input", "Input must be a dictionary")}

    def test_rejects_unknown_parameter(self) -> None:
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script_with({}), {"unknown": "value"})
        assert errors_of(exc_info) == {
            ("input", "Unknown parameter 'unknown' for test-script")
        }

    def test_returns_empty_input_without_parameters(self) -> None:
        cleaned = clean_parameters_input(script_with({}), None)
        assert cleaned.result_params == {}
        assert cleaned.multi_result_params == {}

    def test_does_not_modify_script_parameters(self) -> None:
        parameters = {"string": {"type": "string"}}
        script = script_with(parameters)
        clean_parameters_input(script, {"string": "value"})
        assert script.parameters == {"string": {"type": "string"}}

    def test_reports_all_input_errors(self) -> None:
        script = script_with(
            {
                "runtime": {"type": "runtime"},
                "url": {"type": "url"},
                "required": {"type": "string", "required": True},
            }
        )
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(
                script, {"runtime": "soon", "url": "bad!url"}
            )
        assert errors_of(exc_info) == {
            ("runtime", "Must be an int"),
            ("url", "Invalid URL"),
            ("required", "Field is required"),
        }

    @pytest.mark.parametrize("value", [30, "30"])
    def test_runtime(self, value: int | str) -> None:
        script = script_with({"runtime": {"type": "runtime"}})
        cleaned = clean_parameters_input(script, {"runtime": value})
        assert cleaned.result_params == {
            "runtime": {"type": "runtime", "value": value}
        }

    def test_runtime_defaults_to_script_timeout(self) -> None:
        script = script_with(
            {"runtime": {"type": "runtime"}},
            timeout=timedelta(days=1, seconds=30),
        )
        cleaned = clean_parameters_input(script, {})
        assert cleaned.result_params == {
            "runtime": {"type": "runtime", "value": 86430}
        }

    def test_runtime_required_without_default(self) -> None:
        script = script_with({"runtime": {"type": "runtime", "default": None}})
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {})
        assert errors_of(exc_info) == {("runtime", "Field is required")}

    @pytest.mark.parametrize(
        "parameter, value, message",
        [
            ({}, "soon", "Must be an int"),
            ({}, 1.5, "Must be an int"),
            ({}, True, "Must be an int"),
            ({}, "²", "Must be an int"),
            ({}, -1, "Must be greater than 0"),
            ({"min": 10}, 9, "Must be greater than 10"),
            ({"max": 10}, 11, "Must be less than 10"),
        ],
    )
    def test_runtime_rejects_invalid_value(
        self, parameter: dict, value: Any, message: str
    ) -> None:
        script = script_with({"runtime": {"type": "runtime", **parameter}})
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {"runtime": value})
        assert errors_of(exc_info) == {("runtime", message)}

    @pytest.mark.parametrize(
        "value",
        [
            "10.0.0.1",
            "2001:db8::1",
            "maas.example.com",
            "maas",
            "icmp://10.0.0.1",
            "https://[2001:db8::1]:5240/MAAS",
            "tftp://maas.example.com/pxelinux.0",
        ],
    )
    def test_url(self, value: str) -> None:
        script = script_with({"url": {"type": "url"}})
        cleaned = clean_parameters_input(script, {"url": value})
        assert cleaned.result_params == {
            "url": {"type": "url", "value": value}
        }

    @pytest.mark.parametrize(
        "value",
        [
            "bad!url",
            "maas example",
            "unknown://maas",
            "10.0.0.1,maas",
            "http://maas:65536",
            167772161,
            1.5,
            None,
        ],
    )
    def test_url_rejects_invalid_value(self, value: Any) -> None:
        script = script_with({"url": {"type": "url"}})
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {"url": value})
        assert errors_of(exc_info) == {("url", "Invalid URL")}

    def test_url_allow_list(self) -> None:
        value = "10.0.0.1,2001:db8::1,maas.example.com,http://maas:5240"
        script = script_with({"url": {"type": "url", "allow_list": True}})
        cleaned = clean_parameters_input(script, {"url": value})
        assert cleaned.result_params["url"]["value"] == value

    @pytest.mark.parametrize("value", ["10.0.0.1,bad!url", 167772161])
    def test_url_allow_list_rejects_invalid_value(self, value: Any) -> None:
        script = script_with({"url": {"type": "url", "allow_list": True}})
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {"url": value})
        assert errors_of(exc_info) == {("url", "Invalid URL")}

    def test_url_is_omitted_without_input(self) -> None:
        script = script_with({"url": {"type": "url"}})
        assert clean_parameters_input(script, {}).result_params == {}

    def test_file_url_requires_host(self) -> None:
        script = script_with({"url": {"type": "url"}})
        clean_parameters_input(script, {"url": "file://localhost/etc/hosts"})
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {"url": "file:///etc/hosts"})
        assert errors_of(exc_info) == {("url", "Invalid URL")}

    @pytest.mark.parametrize(
        "param_type", ["string", "url", "storage", "interface"]
    )
    def test_empty_default_is_omitted(self, param_type: str) -> None:
        script = script_with(
            {
                param_type: {
                    "type": param_type,
                    "default": "",
                    "required": False,
                }
            }
        )
        cleaned = clean_parameters_input(script, {})
        assert cleaned.result_params == {}
        assert cleaned.multi_result_params == {}

    @pytest.mark.parametrize(
        "param_type", ["string", "url", "storage", "interface"]
    )
    def test_empty_default_does_not_satisfy_required(
        self, param_type: str
    ) -> None:
        script = script_with(
            {param_type: {"type": param_type, "default": "", "required": True}}
        )
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {})
        assert errors_of(exc_info) == {(param_type, "Field is required")}

    @pytest.mark.parametrize("param_type", ["string", "password"])
    def test_string(self, param_type: str) -> None:
        script = script_with({param_type: {"type": param_type}})
        cleaned = clean_parameters_input(script, {param_type: "secret"})
        assert cleaned.result_params[param_type]["value"] == "secret"

    @pytest.mark.parametrize("param_type", ["string", "password"])
    def test_string_default(self, param_type: str) -> None:
        script = script_with(
            {param_type: {"type": param_type, "default": "default"}}
        )
        cleaned = clean_parameters_input(script, {})
        assert cleaned.result_params[param_type]["value"] == "default"

    @pytest.mark.parametrize("param_type", ["string", "password"])
    def test_string_required(self, param_type: str) -> None:
        script = script_with(
            {param_type: {"type": param_type, "required": True}}
        )
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {})
        assert errors_of(exc_info) == {(param_type, "Field is required")}

    @pytest.mark.parametrize(
        "parameter, value, message",
        [
            ({"min": 5}, "abc", "Input too short"),
            ({"max": 2}, "abc", "Input too long"),
            ({}, 42, "Must be a string"),
            ({"max": 1}, ["a"], "Must be a string"),
            ({}, None, "Must be a string"),
        ],
    )
    def test_string_rejects_invalid_value(
        self, parameter: dict, value: Any, message: str
    ) -> None:
        script = script_with({"string": {"type": "string", **parameter}})
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {"string": value})
        assert errors_of(exc_info) == {("string", message)}

    @pytest.mark.parametrize(
        "parameter_name",
        ["maas_auto_ipmi_user", "maas_auto_ipmi_k_g_bmc_key"],
    )
    def test_defaults_to_maas_config(self, parameter_name: str) -> None:
        script = script_with({parameter_name: {"type": "string"}})
        cleaned = clean_parameters_input(
            script, {}, config_defaults={parameter_name: "from-config"}
        )
        assert cleaned.result_params[parameter_name]["value"] == "from-config"

    def test_schema_default_overrides_maas_config(self) -> None:
        script = script_with(
            {"maas_auto_ipmi_user": {"type": "string", "default": "schema"}}
        )
        cleaned = clean_parameters_input(
            script, {}, config_defaults={"maas_auto_ipmi_user": "config"}
        )
        assert cleaned.result_params["maas_auto_ipmi_user"]["value"] == (
            "schema"
        )

    @pytest.mark.parametrize("value", ["a", "b"])
    def test_choice(self, value: str) -> None:
        script = script_with(
            {"choice": {"type": "choice", "choices": ["a", ["b", "Bee"]]}}
        )
        cleaned = clean_parameters_input(script, {"choice": value})
        assert cleaned.result_params["choice"]["value"] == value

    def test_choice_default_is_validated(self) -> None:
        script = script_with(
            {"choice": {"type": "choice", "choices": ["a"], "default": "b"}}
        )
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {})
        assert errors_of(exc_info) == {("choice", 'Invalid choice "b"')}

    def test_choice_rejects_label(self) -> None:
        script = script_with(
            {"choice": {"type": "choice", "choices": [["b", "Bee"]]}}
        )
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {"choice": "Bee"})
        assert errors_of(exc_info) == {("choice", 'Invalid choice "Bee"')}

    def test_choice_not_given_as_string_or_list(self) -> None:
        script = script_with({"choice": {"type": "choice", "choices": [1]}})
        cleaned = clean_parameters_input(script, {"choice": 1})
        assert cleaned.result_params["choice"]["value"] == 1

    @pytest.mark.parametrize("value", [True, False, "true", "FALSE"])
    def test_boolean(self, value: bool | str) -> None:
        script = script_with({"flag": {"type": "boolean"}})
        cleaned = clean_parameters_input(script, {"flag": value})
        assert cleaned.result_params == {
            "flag": {"type": "boolean", "value": value}
        }

    @pytest.mark.parametrize("value", ["yes", "1", 1, 0, None, ["true"]])
    def test_boolean_rejects_invalid_value(self, value: Any) -> None:
        script = script_with({"flag": {"type": "boolean"}})
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {"flag": value})
        assert errors_of(exc_info) == {("flag", "Must be a boolean")}

    def test_boolean_default(self) -> None:
        script = script_with({"flag": {"type": "boolean", "default": "true"}})
        cleaned = clean_parameters_input(script, {})
        assert cleaned.result_params["flag"]["value"] == "true"

    def test_unsupported_type_is_not_validated(self) -> None:
        script = script_with({"foo": {"type": "foo", "required": False}})
        cleaned = clean_parameters_input(script, {"foo": ["any", "value"]})
        assert cleaned.result_params["foo"]["value"] == ["any", "value"]

    @pytest.mark.parametrize("param_type", ["storage", "interface"])
    def test_multi_result_params_default_to_all(self, param_type: str) -> None:
        script = script_with(
            {
                "runtime": {"type": "runtime"},
                param_type: {"type": param_type},
            }
        )
        cleaned = clean_parameters_input(script, {})
        assert cleaned.result_params == {
            "runtime": {"type": "runtime", "value": 300}
        }
        assert cleaned.multi_result_params == {
            param_type: {"type": param_type, "value": "all"}
        }

    @pytest.mark.parametrize("param_type", ["storage", "interface"])
    def test_multi_result_params_keep_input(self, param_type: str) -> None:
        script = script_with({param_type: {"type": param_type}})
        cleaned = clean_parameters_input(script, {param_type: "sda,sdb"})
        assert cleaned.result_params == {}
        assert cleaned.multi_result_params == {
            param_type: {"type": param_type, "value": "sda,sdb"}
        }

    @pytest.mark.parametrize("param_type", ["storage", "interface"])
    def test_multi_result_params_required(self, param_type: str) -> None:
        script = script_with(
            {param_type: {"type": param_type, "default": None}}
        )
        with pytest.raises(ValidationException) as exc_info:
            clean_parameters_input(script, {})
        assert errors_of(exc_info) == {(param_type, "Field is required")}


class TestValidateScriptsInput:
    def test_reports_errors_of_all_scripts(self) -> None:
        scripts = [
            script_with({"runtime": {"type": "runtime"}}, name="runtime"),
            script_with({"url": {"type": "url"}}, name="url"),
            script_with({}, name="not-a-dict"),
        ]

        with pytest.raises(ValidationException) as exc_info:
            validate_scripts_input(
                scripts,
                {
                    "runtime": {"runtime": "soon"},
                    "url": {"unknown": "value"},
                    "not-a-dict": ["value"],
                },
            )

        assert errors_of(exc_info) == {
            ("script_input.runtime.runtime", "Must be an int"),
            ("script_input.url", "Unknown parameter 'unknown' for url"),
            ("script_input.not-a-dict", "Input must be a dictionary"),
        }

    def test_skips_script_with_invalid_schema(self) -> None:
        script = script_with({"choice": {"type": "choice"}})

        validate_scripts_input([script], {script.name: {"unknown": "value"}})

    @pytest.mark.parametrize("parameter_name", ["input", "parameters"])
    def test_scopes_errors_to_parameter(self, parameter_name: str) -> None:
        script = script_with({parameter_name: {"type": "runtime"}})

        with pytest.raises(ValidationException) as exc_info:
            validate_scripts_input(
                [script], {script.name: {parameter_name: "soon"}}
            )

        assert errors_of(exc_info) == {
            (f"script_input.{script.name}.{parameter_name}", "Must be an int")
        }

    def test_skips_for_hardware_without_input(self) -> None:
        script = script_with(
            {"version": {"type": "string", "required": True}},
            name="update-firmware",
            for_hardware=["pci:8086:1918"],
        )

        validate_scripts_input([script], {})

        with pytest.raises(ValidationException) as exc_info:
            validate_scripts_input(
                [script], {"update-firmware": {"unknown": "value"}}
            )
        assert errors_of(exc_info) == {
            ("script_input.update-firmware.version", "Field is required"),
            (
                "script_input.update-firmware",
                "Unknown parameter 'unknown' for update-firmware",
            ),
        }

    @pytest.mark.parametrize(
        "parameter",
        [
            {"type": "choice", "choices": ["a"], "default": "b"},
            {"type": "string", "default": "too long", "max": 2},
            {"type": "runtime", "max": 1},
            {"type": "string", "required": True, "default": "default"},
        ],
    )
    def test_does_not_check_defaults(self, parameter: dict) -> None:
        validate_scripts_input([script_with({"param": parameter})])

    @pytest.mark.parametrize(
        "parameter_name",
        ["maas_auto_ipmi_user", MAASAutoIPMICipherSuiteIDConfig.name],
    )
    def test_maas_config_counts_as_default(self, parameter_name: str) -> None:
        script = script_with(
            {parameter_name: {"type": "string", "required": True}}
        )

        validate_scripts_input([script])

    @pytest.mark.parametrize(
        "parameter",
        [
            {"type": "string", "required": True},
            {"type": "string", "required": True, "default": ""},
            {"type": "runtime", "default": None},
            {"type": "storage", "default": ""},
            {"type": "interface", "default": None},
        ],
    )
    def test_required_without_default(self, parameter: dict) -> None:
        with pytest.raises(ValidationException) as exc_info:
            validate_scripts_input([script_with({"param": parameter})])

        assert errors_of(exc_info) == {
            ("script_input.test-script.param", "Field is required")
        }


@pytest.mark.asyncio
class TestScriptParametersService:
    @pytest.fixture
    def configurations_service(self) -> Mock:
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get_many.return_value = {}
        return configurations_service

    @pytest.fixture
    def scripts_service(self) -> Mock:
        scripts_service = Mock(ScriptsService)
        scripts_service.get_commissioning_scripts.return_value = []
        scripts_service.get_testing_scripts.return_value = []
        return scripts_service

    @pytest.fixture
    def service(
        self, configurations_service: Mock, scripts_service: Mock
    ) -> ScriptParametersService:
        return ScriptParametersService(
            context=Context(),
            configurations_service=configurations_service,
            scripts_service=scripts_service,
        )

    async def test_uses_maas_config_defaults(
        self, service: ScriptParametersService, configurations_service: Mock
    ) -> None:
        configurations_service.get_many.return_value = {
            "maas_auto_ipmi_user": "maas"
        }
        script = script_with(
            {
                "maas_auto_ipmi_user": {"type": "string"},
                "other": {"type": "string", "default": "other"},
            }
        )

        cleaned = await service.clean_scripts_input([script])

        configurations_service.get_many.assert_awaited_once_with(
            {"maas_auto_ipmi_user"}
        )
        assert cleaned[script.name].result_params == {
            "maas_auto_ipmi_user": {"type": "string", "value": "maas"},
            "other": {"type": "string", "default": "other", "value": "other"},
        }

    async def test_skips_config_lookup_without_config_parameters(
        self, service: ScriptParametersService, configurations_service: Mock
    ) -> None:
        script = script_with({"runtime": {"type": "runtime"}})

        await service.clean_scripts_input([script])

        configurations_service.get_many.assert_not_called()

    async def test_unset_cipher_suite_uses_config_default(
        self, service: ScriptParametersService, configurations_service: Mock
    ) -> None:
        name = MAASAutoIPMICipherSuiteIDConfig.name
        configurations_service.get_many.return_value = {name: None}
        script = script_with({name: {"type": "string"}})

        cleaned = await service.clean_scripts_input([script])

        assert cleaned[script.name].result_params[name]["value"] == (
            MAASAutoIPMICipherSuiteIDConfig.default
        )

    async def test_set_cipher_suite_is_kept(
        self, service: ScriptParametersService, configurations_service: Mock
    ) -> None:
        name = MAASAutoIPMICipherSuiteIDConfig.name
        configurations_service.get_many.return_value = {
            name: IPMICipherSuiteID.SUITE_17
        }
        script = script_with({name: {"type": "string"}})

        cleaned = await service.clean_scripts_input([script])

        assert cleaned[script.name].result_params[name]["value"] == "17"

    async def test_clean_scripts_input_by_script_name(
        self, service: ScriptParametersService
    ) -> None:
        runtime = script_with({"runtime": {"type": "runtime"}}, name="runtime")
        url = script_with({"url": {"type": "url"}}, name="url")

        cleaned = await service.clean_scripts_input(
            [runtime, url],
            {"url": {"url": "maas"}, "unselected": {"foo": "bar"}},
        )

        assert cleaned["runtime"].result_params == {
            "runtime": {"type": "runtime", "value": 300}
        }
        assert cleaned["url"].result_params == {
            "url": {"type": "url", "value": "maas"}
        }

    async def test_clean_scripts_input_validates_defaults(
        self, service: ScriptParametersService
    ) -> None:
        script = script_with(
            {"choice": {"type": "choice", "choices": ["a"], "default": "b"}},
            name="script",
        )

        with pytest.raises(ValidationException) as exc_info:
            await service.clean_scripts_input([script])

        assert errors_of(exc_info) == {
            ("script_input.script.choice", 'Invalid choice "b"')
        }

    async def test_clean_scripts_input_validates_schema(
        self, service: ScriptParametersService
    ) -> None:
        script = script_with({"choice": {"type": "choice"}}, name="script")

        with pytest.raises(ValidationException) as exc_info:
            await service.clean_scripts_input([script])

        assert errors_of(exc_info) == {
            (
                "script_input.script",
                'choices must be given with a "choice" parameter type!',
            )
        }

    async def test_validate_commissioning_input_does_not_check_defaults(
        self,
        service: ScriptParametersService,
        scripts_service: Mock,
        configurations_service: Mock,
    ) -> None:
        scripts_service.get_commissioning_scripts.return_value = [
            script_with(
                {
                    "choice": {
                        "type": "choice",
                        "choices": ["a"],
                        "default": "b",
                    },
                    "maas_auto_ipmi_user": {
                        "type": "string",
                        "max": 2,
                        "required": True,
                    },
                }
            )
        ]

        await service.validate_commissioning_input()

        configurations_service.get_many.assert_not_called()

    async def test_validate_commissioning_input(
        self, service: ScriptParametersService, scripts_service: Mock
    ) -> None:
        commissioning = script_with(
            {"url": {"type": "url"}}, id=1, name="commissioning"
        )
        testing = script_with(
            {"runtime": {"type": "runtime"}},
            id=2,
            name="testing",
            tags=["storage"],
        )
        scripts_service.get_commissioning_scripts.return_value = [
            commissioning
        ]
        scripts_service.get_testing_scripts.return_value = [testing]

        await service.validate_commissioning_input(
            commissioning_scripts=["1"],
            testing_scripts=["storage"],
            script_input={"commissioning": {"url": "maas"}},
        )

        scripts_service.get_commissioning_scripts.assert_awaited_once_with(
            ["1"]
        )
        scripts_service.get_testing_scripts.assert_awaited_once_with(
            ["storage"]
        )

    async def test_validate_commissioning_input_accepts_none_for_testing(
        self, service: ScriptParametersService, scripts_service: Mock
    ) -> None:
        await service.validate_commissioning_input(testing_scripts=["none"])

        scripts_service.get_testing_scripts.assert_awaited_once_with(["none"])

    async def test_validate_commissioning_input_rejects_none_with_other_tests(
        self, service: ScriptParametersService
    ) -> None:
        with pytest.raises(ValidationException) as exc_info:
            await service.validate_commissioning_input(
                testing_scripts=["none", "smartctl"]
            )

        assert errors_of(exc_info) == {
            ("testing_scripts", "'none' cannot be combined with other scripts")
        }

    @pytest.mark.parametrize(
        "selection, resolved",
        [(["none"], []), (["none", "user"], ["user"])],
    )
    async def test_validate_commissioning_input_rejects_none_for_commissioning(
        self,
        service: ScriptParametersService,
        scripts_service: Mock,
        selection: list[str],
        resolved: list[str],
    ) -> None:
        scripts_service.get_commissioning_scripts.return_value = [
            script_with({}, name="user")
        ]

        with pytest.raises(ValidationException) as exc_info:
            await service.validate_commissioning_input(
                commissioning_scripts=selection
            )

        assert errors_of(exc_info) == {
            (
                "commissioning_scripts",
                "'none' is not a valid choice for commissioning scripts",
            )
        }
        scripts_service.get_commissioning_scripts.assert_awaited_once_with(
            resolved
        )

    async def test_validate_commissioning_input_reports_all_errors(
        self, service: ScriptParametersService, scripts_service: Mock
    ) -> None:
        scripts_service.get_commissioning_scripts.return_value = [
            script_with({"url": {"type": "url"}}, name="commissioning")
        ]

        with pytest.raises(ValidationException) as exc_info:
            await service.validate_commissioning_input(
                commissioning_scripts=["commissioning", "typo"],
                testing_scripts=["missing"],
                script_input={
                    "commissioning": {"url": "bad!url"},
                    "unselected": {"foo": "bar"},
                },
            )

        assert errors_of(exc_info) == {
            (
                "commissioning_scripts",
                "No script with the name, tag or id 'typo'",
            ),
            (
                "testing_scripts",
                "No script with the name, tag or id 'missing'",
            ),
            ("script_input.unselected", "Script 'unselected' is not selected"),
            ("script_input.commissioning.url", "Invalid URL"),
        }
