# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import contextmanager

from httplib2 import Response
import pytest

from maascli import api
from maascli.config import ProfileConfig
from maascli.parser import get_deepest_subparser, prepare_parser


@pytest.mark.usefixtures("maasdb")
def test_perf_list_machines_CLI(
    perf, cli_profile, monkeypatch, cli_machines_api_response
):
    @contextmanager
    def mock_ProfileConfig_enter(*args):
        yield {cli_profile["name"]: cli_profile}

    def mock_http_response(*args, **kwargs):
        return (
            Response(
                {
                    key: value
                    for (key, value) in cli_machines_api_response.items()
                    if key != "content"
                }
            ),
            cli_machines_api_response.content,
        )

    monkeypatch.setattr(ProfileConfig, "open", mock_ProfileConfig_enter)
    monkeypatch.setattr(api, "http_request", mock_http_response)

    args = ["maas", cli_profile["name"], "machines", "read"]
    with perf.record("test_perf_list_machines_CLI"):
        parser = prepare_parser(args)
        with perf.record("test_perf_list_machines_CLI.parse"):
            options = parser.parse_args(args[1:])
        if hasattr(options, "execute"):
            with perf.record("test_perf_list_machines_CLI.execute"):
                options.execute(options)
        else:
            sub_parser = get_deepest_subparser(parser, args[1:])
            sub_parser.error("too few arguments")
