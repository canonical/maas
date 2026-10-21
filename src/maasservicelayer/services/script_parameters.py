#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass, field
from ipaddress import ip_address
from typing import Any

import structlog

from maascommon.utils.url import validate_url
from maasservicelayer.context import Context
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.configurations import (
    MAASAutoIPMICipherSuiteIDConfig,
)
from maasservicelayer.models.script import Script
from maasservicelayer.services.base import Service
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.scripts import (
    get_unmatched_selection,
    NO_USER_SCRIPTS,
    ScriptsService,
)

logger = structlog.getLogger(__name__)

PARAMETER_TYPES = (
    "boolean",
    "choice",
    "interface",
    "password",
    "runtime",
    "storage",
    "string",
    "url",
)

# Parameters of these types may produce one ScriptResult per selected device.
MULTI_RESULT_PARAMETER_TYPES = frozenset({"interface", "storage"})

# A parameter named like one of these MAAS configurations defaults to the
# configuration value. 30-maas-01-bmc-config relies on this.
DEFAULTS_FROM_MAAS_CONFIG = frozenset(
    {
        "maas_auto_ipmi_user",
        "maas_auto_ipmi_user_privilege_level",
        "maas_auto_ipmi_k_g_bmc_key",
        MAASAutoIPMICipherSuiteIDConfig.name,
    }
)

# Stands in for the MAAS configuration values when checking the given input,
# as they are only looked up, and checked, when the input is cleaned.
_ASSUMED_CONFIG_DEFAULTS = dict.fromkeys(DEFAULTS_FROM_MAAS_CONFIG, "assumed")

# The schemes supported by curl, used by the network validation test, and
# icmp.
URL_SCHEMES = (
    "icmp",
    "file",
    "ftp",
    "ftps",
    "gopher",
    "http",
    "https",
    "imap",
    "imaps",
    "ldap",
    "ldaps",
    "pop3",
    "pop3s",
    "rtmp",
    "rtsp",
    "scp",
    "sftp",
    "smb",
    "smbs",
    "smtp",
    "smtps",
    "telnet",
    "tftp",
)

_ARGUMENT_FORMAT_PLACEHOLDERS = {
    "storage": ("{input}", "{name}", "{path}", "{model}", "{serial}"),
    "interface": ("{input}", "{name}", "{mac}", "{vendor}", "{product}"),
}

# Schema defaults must be strings, so boolean parameters with a default
# carry "true" or "false" rather than a bool. Input must be a bool.
_BOOLEAN_STRINGS = frozenset({"true", "false"})

# Input values that count as not given, so that defaults apply.
_NOT_GIVEN = object()

# An error about a parameter, or about the script's input as a whole if the
# parameter is None.
type _InputError = tuple[str | None, str]


@dataclass
class ScriptParametersInput:
    result_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    multi_result_params: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )


def _error(field_name: str, message: str) -> BaseExceptionDetail:
    return BaseExceptionDetail(
        type=INVALID_ARGUMENT_VIOLATION_TYPE,
        field=field_name,
        message=message,
    )


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_valid_choice(choice: Any) -> bool:
    if not isinstance(choice, list):
        return True
    return len(choice) == 2 and all(isinstance(item, str) for item in choice)


def _parameter_schema_errors(name: Any, fields: Any) -> list[str]:
    if not isinstance(fields, dict):
        return [f"{name}: must be a dictionary"]

    param_type = fields.get("type")
    param_min = fields.get("min")
    param_max = fields.get("max")
    argument_format = fields.get("argument_format")
    allow_list = fields.get("allow_list")
    choices = fields.get("choices")
    required = fields.get("required", True)
    errors = []

    if not isinstance(name, str):
        errors.append(f"{name}: parameter must be a string")
    if not isinstance(param_type, str):
        errors.append(f"{param_type}: type must be a string")
    if param_min is not None and not isinstance(param_min, int):
        errors.append(f"{param_min}: min must be an integer")
    if param_max is not None and not isinstance(param_max, int):
        errors.append(f"{param_max}: max must be an integer")
    for key in ("title", "description", "argument_format", "default"):
        value = fields.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"{value}: {key} must be a string")
    if required is not None and not isinstance(required, bool):
        errors.append(f"{required}: required must be a boolean")
    if allow_list is not None:
        if not isinstance(allow_list, bool):
            errors.append(f"{allow_list}: allow_list must be a boolean")
        if param_type != "url":
            errors.append("allow_list only supported with the url type.")
    if choices is not None:
        if not isinstance(choices, list):
            errors.append("choices must be a list")
        elif not all(_is_valid_choice(choice) for choice in choices):
            errors.append("choice must be a Django choice or string")
        if param_type != "choice":
            errors.append("choices only supported with the choice type.")
    if param_type == "choice" and not choices:
        errors.append('choices must be given with a "choice" parameter type!')
    if param_type not in PARAMETER_TYPES and required:
        errors.append(
            f"{param_type}: type must be one of {', '.join(PARAMETER_TYPES)}"
        )
    if param_type in ("storage", "interface", "url", "choice") and (
        param_min is not None or param_max is not None
    ):
        errors.append("Type doesn't support min or max")
    if (
        param_type == "runtime"
        and isinstance(param_min, int)
        and param_min < 0
    ):
        errors.append("runtime minimum must be greater than zero")
    if (
        isinstance(param_min, int)
        and isinstance(param_max, int)
        and param_min > param_max
    ):
        errors.append("min must be less than max")
    placeholders = (
        _ARGUMENT_FORMAT_PLACEHOLDERS.get(param_type)
        if isinstance(param_type, str)
        else None
    )
    if (
        placeholders is not None
        and isinstance(argument_format, str)
        and not any(p in argument_format for p in placeholders)
    ):
        errors.append(
            f"{param_type}: argument_format must contain one of "
            f"{', '.join(placeholders)}"
        )
    return errors


def validate_parameters_schema(parameters: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(parameters, dict):
        raise ValidationException(
            details=[_error("parameters", "Must be a dictionary")]
        )
    details = [
        _error("parameters", message)
        for name, fields in parameters.items()
        for message in _parameter_schema_errors(name, fields)
    ]
    if details:
        raise ValidationException(details=details)
    return parameters


def _with_value(param: dict[str, Any], value: Any) -> dict[str, Any]:
    param = copy.deepcopy(param)
    param["value"] = value
    return param


def _given_value(param_type: str, value: Any) -> tuple[Any, str | None]:
    """Return the value given for a parameter of `param_type`, or
    `_NOT_GIVEN` if it counts as not given, and an error if its type is
    wrong."""
    match param_type:
        case "boolean":
            if not isinstance(value, bool):
                return _NOT_GIVEN, "Must be a boolean"
            # Boolean parameters are usually flags, passed to the script
            # whenever they have a value, so false must leave them unset. The
            # legacy API dropped false values for the same reason.
            return (value if value else _NOT_GIVEN), None
        case "string" | "password" | "url":
            # Like the legacy API's form fields, surrounding whitespace is
            # dropped, and empty values count as not given rather than adding
            # an empty argument.
            if isinstance(value, str):
                value = value.strip()
            return (_NOT_GIVEN if value == "" else value), None
        case "choice" | "storage" | "interface":
            return (_NOT_GIVEN if value == "" else value), None
        case "runtime":
            # The legacy API dropped a runtime of 0, so the default applies.
            if _is_int(value) and value == 0:
                return _NOT_GIVEN, None
    return value, None


def _given_values(
    script: Script, parameters: dict[str, dict[str, Any]], script_input: dict
) -> tuple[dict[str, Any], list[_InputError]]:
    """Return the values of `script_input` that count as given."""
    given = {}
    errors: list[_InputError] = []
    for name, value in script_input.items():
        if name not in parameters:
            errors.append(
                (None, f"Unknown parameter '{name}' for {script.name}")
            )
            continue
        value, error = _given_value(parameters[name]["type"], value)
        if error is not None:
            errors.append((name, error))
        elif value is not _NOT_GIVEN:
            given[name] = value
    return given, errors


def _default_for(
    script: Script,
    name: str,
    param: dict[str, Any],
    config_defaults: Mapping[str, Any],
) -> Any:
    """Return the default value of a parameter, or `_NOT_GIVEN`."""
    param_type = param["type"]
    if param_type in MULTI_RESULT_PARAMETER_TYPES:
        # A placeholder until commissioning discovers the devices.
        default = param.get("default", "all")
    elif param_type == "runtime":
        # The legacy ParametersForm used `timeout.seconds`, which drops whole
        # days, so a timeout of a day or more gave a shorter runtime. The
        # full timeout is used instead.
        default = param.get("default", int(script.timeout.total_seconds()))
        # Schema defaults are strings, so only the timeout is a valid one.
        return default if _is_int(default) else _NOT_GIVEN
    else:
        default = param.get("default", config_defaults.get(name, ""))
    # As in the legacy ParametersForm, an empty default counts as no default.
    # Schema defaults must be strings, so this only affects "". Passing it on
    # would add an empty argument to the script's command line, and the
    # script runner expects storage and interface values to be devices.
    return default if default else _NOT_GIVEN


def _set_up_input(
    script: Script,
    parameters: dict[str, dict[str, Any]],
    script_input: dict[str, Any],
    config_defaults: Mapping[str, Any],
) -> tuple[ScriptParametersInput, list[_InputError]]:
    cleaned = ScriptParametersInput()
    given, errors = _given_values(script, parameters, script_input)
    for name, value in given.items():
        param = parameters[name]
        if param["type"] in MULTI_RESULT_PARAMETER_TYPES:
            cleaned.multi_result_params[name] = _with_value(param, value)
        else:
            cleaned.result_params[name] = _with_value(param, value)

    invalid = {name for name, _ in errors}
    for name, param in parameters.items():
        if name in given or name in invalid:
            continue
        default = _default_for(script, name, param, config_defaults)
        if default is _NOT_GIVEN:
            if _is_required(param):
                errors.append((name, "Field is required"))
        elif param["type"] in MULTI_RESULT_PARAMETER_TYPES:
            cleaned.multi_result_params[name] = _with_value(param, default)
        else:
            cleaned.result_params[name] = _with_value(param, default)
    return cleaned, errors


def _runtime_errors(param: dict[str, Any]) -> list[str]:
    value = param["value"]
    if not _is_int(value):
        return ["Must be an int"]
    min_value = param.get("min")
    if min_value is None:
        min_value = 0
    max_value = param.get("max")
    errors = []
    if value < min_value:
        errors.append(f"Must be greater than {min_value}")
    if max_value is not None and value > max_value:
        errors.append(f"Must be less than {max_value}")
    return errors


def _is_valid_url(url: str) -> bool:
    # Bare hostnames and IP addresses are accepted, so give them a scheme
    # before validating.
    try:
        ip = ip_address(url)
    except ValueError:
        if "://" not in url:
            url = f"http://{url}"
    else:
        url = f"http://{url}" if ip.version == 4 else f"http://[{url}]"
    try:
        validate_url(url, schemes=URL_SCHEMES)
    except ValueError:
        return False
    return True


def _url_errors(param: dict[str, Any]) -> list[str]:
    value = param["value"]
    if not isinstance(value, str):
        return ["Invalid URL"]
    urls = value.split(",") if param.get("allow_list", False) else [value]
    if not all(_is_valid_url(url) for url in urls):
        return ["Invalid URL"]
    return []


def _string_errors(param: dict[str, Any]) -> list[str]:
    value = param["value"]
    if not isinstance(value, str):
        return ["Must be a string"]
    min_length = param.get("min")
    max_length = param.get("max")
    errors = []
    if min_length is not None and len(value) < min_length:
        errors.append("Input too short")
    if max_length is not None and len(value) > max_length:
        errors.append("Input too long")
    return errors


def _choice_errors(param: dict[str, Any]) -> list[str]:
    value = param["value"]
    if not isinstance(value, str):
        return ["Must be a string"]
    choices = [
        choice[0] if isinstance(choice, (list, tuple)) else choice
        for choice in param["choices"]
    ]
    if value not in choices:
        return [f'Invalid choice "{value}"']
    return []


def _boolean_errors(param: dict[str, Any]) -> list[str]:
    value = param["value"]
    if isinstance(value, bool) or (
        isinstance(value, str) and value.lower() in _BOOLEAN_STRINGS
    ):
        return []
    return ["Must be a boolean"]


def _value_errors(param: dict[str, Any]) -> list[str]:
    match param["type"]:
        case "runtime":
            return _runtime_errors(param)
        case "url":
            return _url_errors(param)
        case "string" | "password":
            return _string_errors(param)
        case "choice":
            return _choice_errors(param)
        case "boolean":
            return _boolean_errors(param)
    return []


def _clean_input(
    script: Script,
    parameters: dict[str, dict[str, Any]],
    script_input: Any,
    config_defaults: Mapping[str, Any],
) -> tuple[ScriptParametersInput, list[_InputError]]:
    if script_input is None:
        script_input = {}
    if not isinstance(script_input, dict):
        return ScriptParametersInput(), [(None, "Input must be a dictionary")]
    cleaned, errors = _set_up_input(
        script, parameters, script_input, config_defaults
    )
    for name, param in cleaned.result_params.items():
        errors.extend((name, message) for message in _value_errors(param))
    return cleaned, errors


def clean_parameters_input(
    script: Script,
    script_input: Any,
    config_defaults: Mapping[str, Any] | None = None,
) -> ScriptParametersInput:
    parameters = validate_parameters_schema(script.parameters)
    cleaned, errors = _clean_input(
        script, parameters, script_input, config_defaults or {}
    )
    if errors:
        raise ValidationException(
            details=[
                _error(name or "input", message) for name, message in errors
            ]
        )
    return cleaned


def _is_required(param: dict[str, Any]) -> bool:
    required_by_default = (
        param["type"] in MULTI_RESULT_PARAMETER_TYPES
        or param["type"] == "runtime"
    )
    return param.get("required", required_by_default)


def _given_input_errors(
    script: Script, parameters: dict[str, dict[str, Any]], script_input: Any
) -> list[_InputError]:
    if script_input is None:
        script_input = {}
    if not isinstance(script_input, dict):
        return [(None, "Input must be a dictionary")]
    given, errors = _given_values(script, parameters, script_input)
    for name, value in given.items():
        errors.extend(
            (name, message)
            for message in _value_errors(_with_value(parameters[name], value))
        )
    invalid = {name for name, _ in errors}
    errors.extend(
        (name, "Field is required")
        for name, param in parameters.items()
        if name not in given
        and name not in invalid
        and _is_required(param)
        and _default_for(script, name, param, _ASSUMED_CONFIG_DEFAULTS)
        is _NOT_GIVEN
    )
    return errors


def _scripts_with_input_to_check(
    scripts: Sequence[Script], script_input: Mapping[str, Any]
) -> list[Script]:
    # TODO: like the legacy ScriptSet, check for_hardware scripts if and
    # only if they match the machine's known hardware, and resolve storage
    # and interface parameters to its devices.
    return [
        script
        for script in scripts
        if not script.for_hardware or script.name in script_input
    ]


def _scoped_to_script(
    script: Script, errors: list[_InputError]
) -> list[BaseExceptionDetail]:
    script_field = f"script_input.{script.name}"
    return [
        _error(f"{script_field}.{name}" if name else script_field, message)
        for name, message in errors
    ]


def validate_scripts_input(
    scripts: Sequence[Script], script_input: Mapping[str, Any] | None = None
) -> None:
    """Check the input given to `scripts`, keyed by script name.

    Only the given values are checked. Defaults are assigned, and checked,
    when the input is cleaned, so that problems with a script's defaults,
    its parameters schema or the MAAS configuration are not reported as
    invalid input.
    """
    script_input = script_input or {}
    details: list[BaseExceptionDetail] = []
    for script in _scripts_with_input_to_check(scripts, script_input):
        try:
            parameters = validate_parameters_schema(script.parameters)
        except ValidationException as e:
            # Schemas are checked when scripts are uploaded, so this is not a
            # problem with the request. It is reported when the input is
            # cleaned, failing the operation.
            logger.warning(
                "Not checking the input of a script with invalid parameters",
                script=script.name,
                errors=[detail.message for detail in e.details or []],
            )
            continue
        details.extend(
            _scoped_to_script(
                script,
                _given_input_errors(
                    script, parameters, script_input.get(script.name)
                ),
            )
        )
    if details:
        raise ValidationException(details=details)


def _selection_errors(
    field_name: str, selection: list[str] | None, selected: list[Script]
) -> list[BaseExceptionDetail]:
    if not selection:
        return []
    if NO_USER_SCRIPTS in selection:
        # The other entries are not looked up when `none` is selected, so
        # reporting them as unmatched would be misleading.
        if len(set(selection)) > 1:
            return [
                _error(
                    field_name,
                    f"'{NO_USER_SCRIPTS}' cannot be combined with other "
                    "scripts",
                )
            ]
        return []
    return [
        _error(field_name, f"No script with the name or tag '{item}'")
        for item in get_unmatched_selection(selection, selected)
    ]


class ScriptParametersService(Service):
    def __init__(
        self,
        context: Context,
        configurations_service: ConfigurationsService,
        scripts_service: ScriptsService,
    ):
        super().__init__(context)
        self.configurations_service = configurations_service
        self.scripts_service = scripts_service

    async def validate_commissioning_input(
        self,
        commissioning_scripts: list[str] | None = None,
        testing_scripts: list[str] | None = None,
        script_input: Mapping[str, Any] | None = None,
    ) -> None:
        script_input = script_input or {}
        details: list[BaseExceptionDetail] = []
        # Like the legacy API, 'none' is only accepted for testing scripts.
        # ScriptsService still supports it for commissioning, for internal
        # use.
        if commissioning_scripts and NO_USER_SCRIPTS in commissioning_scripts:
            details.append(
                _error(
                    "commissioning_scripts",
                    f"'{NO_USER_SCRIPTS}' is not a valid choice for "
                    "commissioning scripts",
                )
            )
            commissioning_scripts = [
                item
                for item in commissioning_scripts
                if item != NO_USER_SCRIPTS
            ]
        commissioning = await self.scripts_service.get_commissioning_scripts(
            commissioning_scripts
        )
        testing = await self.scripts_service.get_testing_scripts(
            testing_scripts
        )
        scripts = [*commissioning, *testing]
        details.extend(
            _selection_errors(
                "commissioning_scripts", commissioning_scripts, commissioning
            )
        )
        details.extend(
            _selection_errors("testing_scripts", testing_scripts, testing)
        )
        selected_names = {script.name for script in scripts}
        details.extend(
            _error(f"script_input.{name}", f"Script '{name}' is not selected")
            for name in script_input
            if name not in selected_names
        )
        try:
            validate_scripts_input(scripts, script_input)
        except ValidationException as e:
            details.extend(e.details or [])
        if details:
            raise ValidationException(details=details)

    async def clean_scripts_input(
        self,
        scripts: Sequence[Script],
        script_input: Mapping[str, Any] | None = None,
    ) -> dict[str, ScriptParametersInput]:
        """Validate `script_input` and assign defaults, including those from
        the MAAS configuration, for preparing the scripts to run."""
        script_input = script_input or {}
        cleaned = {}
        details: list[BaseExceptionDetail] = []
        for script in _scripts_with_input_to_check(scripts, script_input):
            try:
                parameters = validate_parameters_schema(script.parameters)
            except ValidationException as e:
                details.extend(
                    detail.model_copy(
                        update={"field": f"script_input.{script.name}"}
                    )
                    for detail in e.details or []
                )
                continue
            cleaned[script.name], errors = _clean_input(
                script,
                parameters,
                script_input.get(script.name),
                await self._get_config_defaults(parameters),
            )
            details.extend(_scoped_to_script(script, errors))
        if details:
            raise ValidationException(details=details)
        return cleaned

    async def _get_config_defaults(
        self, parameters: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        names = DEFAULTS_FROM_MAAS_CONFIG.intersection(parameters)
        if not names:
            return {}
        defaults = await self.configurations_service.get_many(set(names))
        cipher_suite = MAASAutoIPMICipherSuiteIDConfig.name
        if cipher_suite in defaults and defaults[cipher_suite] is None:
            defaults[cipher_suite] = MAASAutoIPMICipherSuiteIDConfig.default
        return defaults
