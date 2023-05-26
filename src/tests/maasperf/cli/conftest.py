# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from copy import deepcopy

from django.core.serializers import serialize
from django.http import HttpResponse
from pytest import fixture


@fixture()
def maas_user(factory):
    return factory.make_User()


@fixture()
def cli_profile(maas_user):
    from maasserver.api.doc import get_api_description
    from maasserver.models.user import get_auth_tokens

    token = get_auth_tokens(maas_user).first()

    description = deepcopy(get_api_description())
    for resource in description["resources"]:
        for handler_type in ("anon", "auth"):
            handler = resource[handler_type]
            if handler is not None:
                handler["uri"] = "http://localhost:5240/MAAS" + handler["path"]

    return {
        "name": "localmaas",
        "url": "http://localhost:5240/MAAS",
        "credentials": [token.consumer.key, token.key, token.secret],
        "description": description,
    }


@fixture()
def cli_machines_api_response(factory):
    return HttpResponse(
        serialize("json", [factory.make_Machine() for _ in range(30)])
    )
