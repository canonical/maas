#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from ipaddress import ip_address
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    PlainSerializer,
    StrictBool,
    StrictInt,
    StrictStr,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
)
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

_REQUIRED_BY_DEFAULT_TYPES = MULTI_RESULT_PARAMETER_TYPES | {"runtime"}

_UNBOUNDED_TYPES = frozenset({"choice", "interface", "storage", "url"})

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

# Schema defaults must be strings, so boolean parameters declare their
# default as "true" or "false".
_BOOLEAN_STRINGS = frozenset({"true", "false"})

ParameterValue = str | int | bool

# An error about a parameter, or about the script's input as a whole if the
# parameter is None.
type _InputError = tuple[str | None, str]


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


def _as_choice_pair(choice: Any) -> Any:
    # A choice is declared as a value, or as a [value, label] pair.
    return (choice, choice) if isinstance(choice, str) else choice


def _as_declared_choice(choice: tuple[str, str]) -> str | list[str]:
    value, label = choice
    return value if value == label else [value, label]


_Bound = Annotated[StrictInt, Field(ge=0)]
_Choice = Annotated[
    tuple[StrictStr, StrictStr],
    BeforeValidator(_as_choice_pair),
    PlainSerializer(_as_declared_choice),
]


class ParameterSchema(BaseModel):
    """The schema of a script parameter, as declared in the script's
    metadata.

    Fields are validated in the order they are declared, so each one can be
    checked against the fields before it. Unknown keys are kept, like the
    legacy API did, and serialized with the rest.
    """

    model_config = ConfigDict(extra="allow")

    required: StrictBool | None = None
    type: StrictStr
    min: _Bound | None = None
    max: _Bound | None = None
    allow_list: StrictBool | None = None
    choices: list[_Choice] | None = Field(default=None, validate_default=True)
    argument_format: StrictStr | None = None
    default: StrictStr | None = None
    title: StrictStr | None = None
    description: StrictStr | None = None

    @field_validator("type")
    @classmethod
    def _check_type(cls, type_: str, info: ValidationInfo) -> str:
        # Parameters of other types are passed on as given, if optional.
        if (
            type_ not in PARAMETER_TYPES
            and info.data.get("required") is not False
        ):
            raise ValueError(f"Must be one of {', '.join(PARAMETER_TYPES)}")
        return type_

    @field_validator("min", "max")
    @classmethod
    def _check_bounded(
        cls, bound: int | None, info: ValidationInfo
    ) -> int | None:
        if bound is not None and info.data.get("type") in _UNBOUNDED_TYPES:
            raise ValueError("Not supported by this type")
        return bound

    @field_validator("max")
    @classmethod
    def _check_max(cls, max_: int | None, info: ValidationInfo) -> int | None:
        min_ = info.data.get("min")
        if min_ is not None and max_ is not None and min_ > max_:
            raise ValueError("Must not be less than min")
        return max_

    @field_validator("allow_list")
    @classmethod
    def _check_allow_list(
        cls, allow_list: bool | None, info: ValidationInfo
    ) -> bool | None:
        if allow_list is not None and info.data.get("type") != "url":
            raise ValueError("Only supported with the url type")
        return allow_list

    @field_validator("choices")
    @classmethod
    def _check_choices(
        cls, choices: list[tuple[str, str]] | None, info: ValidationInfo
    ) -> list[tuple[str, str]] | None:
        is_choice = info.data.get("type") == "choice"
        if is_choice and not choices:
            raise ValueError("Required by the choice type")
        if choices is not None and not is_choice:
            raise ValueError("Only supported with the choice type")
        return choices

    @field_validator("argument_format")
    @classmethod
    def _check_argument_format(
        cls, argument_format: str | None, info: ValidationInfo
    ) -> str | None:
        placeholders = _ARGUMENT_FORMAT_PLACEHOLDERS.get(
            info.data.get("type", "")
        )
        if (
            argument_format is not None
            and placeholders is not None
            and not any(p in argument_format for p in placeholders)
        ):
            raise ValueError(f"Must contain one of {', '.join(placeholders)}")
        return argument_format

    @field_validator("default")
    @classmethod
    def _check_default(
        cls, default: str | None, info: ValidationInfo
    ) -> str | None:
        if (
            default
            and info.data.get("type") == "boolean"
            and default.lower() not in _BOOLEAN_STRINGS
        ):
            raise ValueError("Must be true or false")
        return default

    @property
    def is_required(self) -> bool:
        if self.required is None:
            return self.type in _REQUIRED_BY_DEFAULT_TYPES
        return self.required

    @property
    def is_multi_result(self) -> bool:
        return self.type in MULTI_RESULT_PARAMETER_TYPES

    @property
    def value_type(self) -> Any:
        """The type of the parameter's value, constrained by the schema."""
        match self.type:
            case "boolean":
                return StrictBool
            case "runtime":
                return Annotated[
                    StrictInt, Field(ge=self.min or 0, le=self.max)
                ]
            case "string" | "password":
                return Annotated[
                    StrictStr,
                    StringConstraints(
                        strip_whitespace=True,
                        min_length=self.min,
                        max_length=self.max,
                    ),
                ]
            case "url":
                return Annotated[
                    StrictStr,
                    StringConstraints(strip_whitespace=True),
                    AfterValidator(self._check_url),
                ]
            case "choice":
                return Annotated[StrictStr, AfterValidator(self._check_choice)]
        return Any

    def _check_url(self, value: str) -> str:
        urls = value.split(",") if self.allow_list else [value]
        if not all(_is_valid_url(url) for url in urls):
            raise ValueError("Invalid URL")
        return value

    def _check_choice(self, value: str) -> str:
        if value not in (choice for choice, _label in self.choices or ()):
            raise ValueError(f'Invalid choice "{value}"')
        return value

    def validate_value(self, value: Any) -> ParameterValue:
        """Return `value` as constrained by the schema.

        Raises:
            ValidationError: If `value` does not fit the schema.
        """
        return TypeAdapter(self.value_type).validate_python(value)

    def counts_as_given(self, value: ParameterValue) -> bool:
        """Whether `value` was given, rather than left for the default.

        Like the legacy API, empty values count as not given, rather than
        adding an empty argument.
        """
        match self.type:
            case "boolean":
                # Boolean parameters are usually flags, passed to the script
                # whenever they have a value, so false must leave them unset.
                return value is not False
            case "string" | "password" | "url":
                return str(value).strip() != ""
            case "runtime":
                # False equals 0, but is not a runtime, so it must fail.
                return value is False or value != 0
            case "choice" | "storage" | "interface":
                return value != ""
        return True

    def default_for(
        self, name: str, script: Script, config_defaults: Mapping[str, Any]
    ) -> Any:
        """Return the default value of the parameter, or None.

        As in the legacy ParametersForm, an empty default counts as none.
        Passing it on would add an empty argument to the script's command
        line, and the script runner expects storage and interface values to
        be devices.
        """
        if "default" in self.model_fields_set:
            match self.type:
                case "runtime":
                    # Schema defaults are strings, so never a valid runtime.
                    return None
                case "boolean":
                    # Unlike the legacy ParametersForm, which passed the
                    # string on, the default is a bool like the input. So
                    # "false" leaves a flag unset, as false input does.
                    if self.default and self.default.lower() == "true":
                        return True
                    return None
            return self.default or None
        match self.type:
            case "storage" | "interface":
                # A placeholder until commissioning discovers the devices.
                return "all"
            case "runtime":
                # The legacy ParametersForm used `timeout.seconds`, which
                # drops whole days, so a timeout of a day or more gave a
                # shorter runtime. The full timeout is used instead.
                return int(script.timeout.total_seconds())
        return config_defaults.get(name) or None

    def with_value(self, value: ParameterValue) -> "ParameterWithValue":
        return ParameterWithValue.model_validate(
            {**self.model_dump(exclude_unset=True), "value": value}
        )


_PARAMETERS_SCHEMA = TypeAdapter(dict[str, ParameterSchema])


class ParameterWithValue(ParameterSchema):
    """A parameter's schema with its value, stored in ScriptResult.parameters
    as dumped with `exclude_unset=True`.
    """

    value: ParameterValue


@dataclass
class ScriptParametersInput:
    result_params: dict[str, ParameterWithValue] = field(default_factory=dict)
    multi_result_params: dict[str, ParameterWithValue] = field(
        default_factory=dict
    )


def _error(field_name: str, message: str) -> BaseExceptionDetail:
    return BaseExceptionDetail(
        type=INVALID_ARGUMENT_VIOLATION_TYPE,
        field=field_name,
        message=message,
    )


def _messages(error: ValidationError) -> list[str]:
    """Return the messages of `error`, prefixed by where each one is, if not
    at the top."""
    messages = []
    for detail in error.errors(include_url=False):
        location = ".".join(str(part) for part in detail["loc"])
        message = detail["msg"].removeprefix("Value error, ")
        messages.append(f"{location}: {message}" if location else message)
    return messages


def validate_parameters_schema(
    parameters: Any,
) -> dict[str, ParameterSchema]:
    """Check a script's parameters schema.

    Raises:
        ValidationException: With every error under `parameters`.
    """
    try:
        return _PARAMETERS_SCHEMA.validate_python(parameters)
    except ValidationError as e:
        raise ValidationException(
            details=[_error("parameters", message) for message in _messages(e)]
        ) from e


def _given_values(
    script: Script,
    schemas: Mapping[str, ParameterSchema],
    script_input: Mapping[str, ParameterValue],
) -> tuple[dict[str, ParameterValue], list[_InputError]]:
    """Return the validated values of `script_input` that count as
    given."""
    given: dict[str, ParameterValue] = {}
    errors: list[_InputError] = []
    for name, value in script_input.items():
        schema = schemas.get(name)
        if schema is None:
            errors.append(
                (None, f"Unknown parameter '{name}' for {script.name}")
            )
        elif schema.counts_as_given(value):
            try:
                given[name] = schema.validate_value(value)
            except ValidationError as e:
                errors.extend((name, message) for message in _messages(e))
    return given, errors


def _clean_input(
    script: Script,
    schemas: Mapping[str, ParameterSchema],
    script_input: Mapping[str, ParameterValue],
    config_defaults: Mapping[str, Any],
) -> tuple[ScriptParametersInput, list[_InputError]]:
    given, errors = _given_values(script, schemas, script_input)
    values = dict(given)
    invalid = {name for name, _ in errors}
    for name, schema in schemas.items():
        if name in given or name in invalid:
            continue
        default = schema.default_for(name, script, config_defaults)
        if default is None:
            if schema.is_required:
                errors.append((name, "Field is required"))
            continue
        try:
            values[name] = schema.validate_value(default)
        except ValidationError as e:
            errors.extend((name, message) for message in _messages(e))

    cleaned = ScriptParametersInput()
    for name, value in values.items():
        schema = schemas[name]
        params = (
            cleaned.multi_result_params
            if schema.is_multi_result
            else cleaned.result_params
        )
        params[name] = schema.with_value(value)
    return cleaned, errors


def clean_parameters_input(
    script: Script,
    script_input: Mapping[str, ParameterValue],
    config_defaults: Mapping[str, Any] | None = None,
) -> ScriptParametersInput:
    """Check the input given to a script and assign defaults.

    Raises:
        ValidationException: With schema errors under `parameters`, unknown
            parameters under `input`, and the others under their parameter.
    """
    schemas = validate_parameters_schema(script.parameters)
    cleaned, errors = _clean_input(
        script, schemas, script_input, config_defaults or {}
    )
    if errors:
        raise ValidationException(
            details=[
                _error(name or "input", message) for name, message in errors
            ]
        )
    return cleaned


def _given_input_errors(
    script: Script,
    schemas: Mapping[str, ParameterSchema],
    script_input: Mapping[str, ParameterValue],
) -> list[_InputError]:
    given, errors = _given_values(script, schemas, script_input)
    invalid = {name for name, _ in errors}
    errors.extend(
        (name, "Field is required")
        for name, schema in schemas.items()
        if name not in given
        and name not in invalid
        and schema.is_required
        and schema.default_for(name, script, _ASSUMED_CONFIG_DEFAULTS) is None
    )
    return errors


def _scripts_with_input_to_check(
    scripts: Sequence[Script],
    script_input: Mapping[str, Mapping[str, ParameterValue]],
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
    scripts: Sequence[Script],
    script_input: Mapping[str, Mapping[str, ParameterValue]] | None = None,
) -> None:
    """Check the given input of `scripts`, without assigning defaults.

    Defaults and schemas are only checked when the input is cleaned, so that
    problems with them are not reported as invalid input.

    Raises:
        ValidationException: With unknown parameters under
            `script_input.<script>`, the others under
            `script_input.<script>.<parameter>`.
    """
    script_input = script_input or {}
    details: list[BaseExceptionDetail] = []
    for script in _scripts_with_input_to_check(scripts, script_input):
        try:
            schemas = validate_parameters_schema(script.parameters)
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
                    script, schemas, script_input.get(script.name, {})
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
        script_input: Mapping[str, Mapping[str, ParameterValue]] | None = None,
    ) -> None:
        """Check the script selections and input of a commission request.

        Nothing is returned; the request is valid if this does not raise.

        Raises:
            ValidationException: With all of the request's errors. Selection
                errors are under `commissioning_scripts` or
                `testing_scripts`, input errors as in
                `validate_scripts_input`.
        """
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
            # Check script_input against the scripts the request asked for:
            # the other entries, or else only the built-in scripts.
            commissioning_scripts = [
                item
                for item in commissioning_scripts
                if item != NO_USER_SCRIPTS
            ] or [NO_USER_SCRIPTS]
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
        script_input: Mapping[str, Mapping[str, ParameterValue]] | None = None,
    ) -> dict[str, ScriptParametersInput]:
        """Check the input given to `scripts` and assign defaults, including
        those from the MAAS configuration, for preparing the scripts to run.

        Raises:
            ValidationException: Like `validate_scripts_input`, but also for
                invalid defaults, and with schema errors under
                `script_input.<script>`.
        """
        script_input = script_input or {}
        cleaned = {}
        details: list[BaseExceptionDetail] = []
        for script in _scripts_with_input_to_check(scripts, script_input):
            try:
                schemas = validate_parameters_schema(script.parameters)
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
                schemas,
                script_input.get(script.name, {}),
                await self._get_config_defaults(schemas),
            )
            details.extend(_scoped_to_script(script, errors))
        if details:
            raise ValidationException(details=details)
        return cleaned

    async def _get_config_defaults(
        self, schemas: Mapping[str, ParameterSchema]
    ) -> dict[str, Any]:
        names = DEFAULTS_FROM_MAAS_CONFIG.intersection(schemas)
        if not names:
            return {}
        defaults = await self.configurations_service.get_many(set(names))
        cipher_suite = MAASAutoIPMICipherSuiteIDConfig.name
        if cipher_suite in defaults and defaults[cipher_suite] is None:
            defaults[cipher_suite] = MAASAutoIPMICipherSuiteIDConfig.default
        return defaults
