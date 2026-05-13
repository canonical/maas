# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
import json
import os
from urllib.request import Request, urlopen

from fastapi import Depends, Header

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.events_summary import (
    EventsSummaryFiltersParams,
)
from maasapiserver.v3.api.public.models.responses.events_summary import (
    EventsSummaryResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.models.events import Event
from maasservicelayer.services import ServiceCollectionV3

_MAX_ROWS = 500
_DEFAULT_MODEL = "mistralai/mistral-small-24b-instruct-2501"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_HEADER = [
    "id", "created", "type", "node_system_id", "node_hostname",
    "owner", "action", "description",
]


def _to_table(events: list[Event]) -> str:
    rows = [
        [
            str(e.id), str(e.created), e.type.name,
            e.node_system_id or "", e.node_hostname,
            e.owner, e.action, e.description,
        ]
        for e in events
    ]
    return "\n".join(["\t".join(_HEADER)] + ["\t".join(r) for r in rows])


def _call_openrouter(api_key: str, model: str, table: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You analyze MAAS infrastructure event logs. "
                    "The user message contains tab-separated event data. "
                    "Answer from the data only; say if something cannot be determined."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Produce a summary of this MAAS events dataset."
                    f"\n\n--- Events (tab-separated) ---\n{table}"
                ),
            },
        ],
    }).encode()

    req = Request(
        _OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(req, timeout=120) as resp:
        body = json.load(resp)
    return body["choices"][0]["message"]["content"]


async def _llm_summarize(api_key: str, table: str) -> str:
    model = os.getenv("MAAS_EVENTS_SUMMARY_MODEL", _DEFAULT_MODEL)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _call_openrouter, api_key, model, table
    )


class EventsSummaryHandler(Handler):
    """Events summary API handler."""

    TAGS = ["Events"]

    @handler(
        path="/events/summary",
        methods=["GET"],
        tags=TAGS,
        responses={200: {"model": EventsSummaryResponse}},
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES
                )
            )
        ],
    )
    async def get_events_summary(
        self,
        filters: EventsSummaryFiltersParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        openrouter_api_key: str = Header(alias="x-openrouter-api-key"),  # noqa: B008
    ) -> EventsSummaryResponse:
        result = await services.events.list(
            page=1,
            size=_MAX_ROWS,
            query=QuerySpec(where=filters.to_clause()),
        )

        events = result.items
        if filters.created_after:
            events = [e for e in events if e.created >= filters.created_after]
        if filters.created_before:
            events = [e for e in events if e.created <= filters.created_before]

        if not events:
            return EventsSummaryResponse(
                summary="No events found matching the given filters."
            )

        summary = await _llm_summarize(openrouter_api_key, _to_table(events))
        return EventsSummaryResponse(summary=summary)
