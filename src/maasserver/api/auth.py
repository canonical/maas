# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OAuth authentication for the various APIs."""

from dataclasses import dataclass
from enum import Enum
from itertools import chain
from operator import xor
from typing import Literal, Optional

from django.test.client import WSGIRequest
from piston3.authentication import OAuthAuthentication, send_oauth_error
from piston3.oauth import OAuthError, OAuthMissingParam
from piston3.utils import rc

from maasserver.exceptions import MAASAPIBadRequest, Unauthorized
from maasserver.macaroon_auth import (
    MacaroonAPIAuthentication,
    validate_user_external_auth,
)
from maasserver.models.user import SYSTEM_USERS

_NECESSARY_OAUTH_PARAMS = [
    "oauth_" + s
    for s in [
        "consumer_key",
        "token",
        "signature",
        "signature_method",
        "timestamp",
        "nonce",
    ]
]


class OAuthBadRequest(MAASAPIBadRequest):
    """BadRequest error for OAuth signed requests with invalid parameters."""

    def __init__(self, error):
        super().__init__()
        self.error = error
        self.error.message = f"Bad Request: {error.message}"

    def __str__(self):
        return repr(self.error.message)


class OAuthUnauthorized(Unauthorized):
    """Unauthorized error for OAuth signed requests with invalid tokens."""

    def __init__(self, error):
        super().__init__()
        self.error = error
        # When the error is an authentication error, use a more
        # user-friendly error message.
        if error.message == "Invalid consumer.":
            self.error.message = "Authorization Error: Invalid API key."
        else:
            self.error.message = "Authorization Error: %r" % error.message

    def make_http_response(self):
        return send_oauth_error(self.error)

    def __str__(self):
        return repr(self.error.message)


class ParamIssue(str, Enum):
    MISSING = "missing"
    UNEXPECTED_TYPE = "unexpected type"


def report_issue(param: str, issue: ParamIssue) -> str:
    if issue == ParamIssue.MISSING:
        return f"{param} is missing"
    elif issue == ParamIssue.UNEXPECTED_TYPE:
        return f"{param} has an unexpected type"
    else:
        # Should be unreachable, but putting it here
        # in case a new enum value is added and this
        # is not updated.
        return f"{param} has an issue"


@dataclass(slots=True)
class RequestValidityReport:
    problematic_auth_params: dict[str, ParamIssue]
    problematic_get_params: dict[str, ParamIssue]
    problematic_post_params: dict[str, ParamIssue]

    def represents_valid_request(self) -> bool:
        "Determines if there is a set of params without identified problems."
        return not (
            self.problematic_auth_params
            and self.problematic_get_params
            and self.problematic_post_params
        )

    def contains_invalid_type_issues(self) -> bool:
        return any(
            problem == ParamIssue.UNEXPECTED_TYPE
            for problem in chain(
                self.problematic_auth_params.values(),
                self.problematic_get_params.values(),
                self.problematic_post_params.values(),
            )
        )

    def _is_report_necessary(
        self, attempt_type: Literal["auth", "get", "post"]
    ) -> bool:
        """Determines if the attempt should be included in the error message.

        If there is any necessary parameter that is specified in the attempt,
        then this decides that the report is necessary. Otherwise, if all
        necessary parameters are missing, it considers that there wasn't a
        real attempt to do authentication through those means.
        """
        if attempt_type == "get":
            params = self.problematic_get_params
        elif attempt_type == "post":
            params = self.problematic_post_params
        else:
            params = self.problematic_auth_params

        return sum(
            issue == ParamIssue.MISSING for issue in params.values()
        ) < len(_NECESSARY_OAUTH_PARAMS)

    def generate_error_message(self) -> str:
        """Generates an error message showing problematic parameters.

        Should only be used if `is_request_valid` returns false. For safety, we
        make this return an empty string in case `is_request_valid` is True.
        """
        if self.represents_valid_request():
            return ""

        if self.problematic_auth_params != {"OAuth": ParamIssue.MISSING}:
            auth_message = (
                f"the following problems were found among the auth params: {', '.join(report_issue(*x) for x in self.problematic_auth_params.items())}"
                if self._is_report_necessary("auth")
                else ""
            )
        else:
            auth_message = (
                "missing starting 'OAuth' from 'Authentication' header"
            )

        get_message = (
            f"the following problems were found among the query params: {', '.join(report_issue(*x) for x in self.problematic_get_params.items())}"
            if self._is_report_necessary("get")
            else ""
        )
        post_message = (
            f"the following problems were found among the query params: {', '.join(report_issue(*x) for x in self.problematic_post_params.items())}"
            if self._is_report_necessary("post")
            else ""
        )

        return "; ".join(
            message
            for message in (auth_message, get_message, post_message)
            if message
        )


class MAASAPIAuthentication(OAuthAuthentication):
    """Use the currently logged-in user; resort to OAuth if there isn't one.

    There may be a user already logged-in via another mechanism, like a
    familiar in-browser user/pass challenge.
    """

    def is_authenticated(self, request):
        user = request.user
        if user.is_authenticated:
            # only authenticate if user is local and external auth is disabled
            # or viceversa
            return xor(
                bool(request.external_auth_info), user.userprofile.is_local
            )

        # The following is much the same as is_authenticated from Piston's
        # OAuthAuthentication, with the difference that an OAuth request that
        # does not validate is rejected instead of being silently downgraded.
        validity_report = self.check_validity(request)
        if validity_report.represents_valid_request():
            try:
                consumer, token, _ = self.validate_token(request)
            except OAuthError as error:
                raise OAuthUnauthorized(error)  # noqa: B904
            except OAuthMissingParam as error:
                raise OAuthBadRequest(error)  # noqa: B904

            if consumer and token:
                user = token.user
                if user.username not in SYSTEM_USERS:
                    external_auth_info = request.external_auth_info
                    is_local_user = user.userprofile.is_local
                    if external_auth_info:
                        if is_local_user:
                            return False
                        if not validate_user_external_auth(
                            user, external_auth_info
                        ):
                            return False
                    elif not is_local_user:
                        return False

                request.user = user
                request.consumer = consumer
                request.throttle_extra = token.consumer.id
                return True

            else:
                return False
        # Raising a 400 in case we find type issues.
        # At time of writing, this only happens with oauth_timestamp.
        # Arguably, we should raise this error also with missing params,
        # but this would break previous expectations.
        elif validity_report.contains_invalid_type_issues():
            raise OAuthBadRequest(
                RequestParamsError(validity_report.generate_error_message())
            )
        else:
            # This is here mainly for maintaining previous behavior, which
            # some tests expect. Specifically, ultimately raising 401
            # in case the if check fails.
            #
            # Arguably, both OAuthError in the if block and this should
            # become 400's.
            return False

    def challenge(self, request):
        # Beware: this returns 401: Unauthorized, not 403: Forbidden
        # as the name implies.
        return rc.FORBIDDEN

    @staticmethod
    def check_validity(
        request: WSGIRequest,
    ) -> RequestValidityReport:
        """Generates a RequestValidityReport, containing missing/problematic fields.

        This is basically a stricter check than what is seen in OAuthAuthentications's `is_valid_request`.
        Piston seems to assume things it simply doesn't check for. For example, that `oauth_timestamp` is
        parseable to an int in case it is nonempty.
        """
        raw_auth_params = request.META.get("HTTP_AUTHORIZATION", "")
        get_params = request.GET
        post_params = request.POST

        auth_params = parse_auth_params(raw_auth_params)
        if auth_params is None:
            problematic_auth_params = {"OAuth": ParamIssue.MISSING}
        else:
            problematic_auth_params = get_problematic_params(auth_params)
        problematic_get_params = get_problematic_params(get_params)
        problematic_post_params = get_problematic_params(post_params)

        return RequestValidityReport(
            problematic_auth_params,
            problematic_get_params,
            problematic_post_params,
        )


class RequestParamsError(RuntimeError):
    def __init__(self, message: str):
        self.message = message


def parse_auth_params(params: str) -> Optional[dict[str, str]]:
    """Parses auth params in a comma-separated string of keys and values.

    The string is something of the form
        'OAuth oauth_timestamp="1764850000", oauth_consumer_key="_",
         oauth_token="_", oauth_signature="_", oauth_signature_method="_",
         oauth_nonce="_"'

    Returns None if the string does not begin with 'OAuth'.
    """
    params = params.strip()

    if not params.startswith("OAuth"):
        return None

    params = params.lstrip("OAuth").strip()

    split_params = (x.strip() for x in params.split(","))
    keys_and_values = {}
    for param in split_params:
        split_on_equal = param.split("=", 1)
        if len(split_on_equal) != 2:
            continue

        key, value = split_on_equal
        keys_and_values[key.strip()] = value.strip().strip('"')

    return keys_and_values


def get_problematic_params(params: dict[str, str]) -> dict[str, ParamIssue]:
    """Detects missing parameters, or parameters with unexpected values."""
    problems: dict[str, ParamIssue] = {}
    for param in _NECESSARY_OAUTH_PARAMS:
        value = params.get(param)
        if value is None:
            problems[param] = ParamIssue.MISSING
        elif param == "oauth_timestamp":
            try:
                int(value)
            except ValueError:
                problems[param] = ParamIssue.UNEXPECTED_TYPE

    return problems


# OAuth and macaroon-based authentication for the APIs.
api_auth = (
    MAASAPIAuthentication(realm="MAAS API"),
    MacaroonAPIAuthentication(),
)
