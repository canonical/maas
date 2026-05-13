#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler


class LLMSearchRequest(BaseModel):
    text: str


class LLMSearchResponse(BaseModel):
    query: str


class LLMSearchHandler(Handler):
    """LLM Search API handler."""

    TAGS = ["LLM Search"]

    @handler(
        path="/llm_search",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": LLMSearchResponse,
            },
        },
        response_model=LLMSearchResponse,
        status_code=200,
    )
    async def llm_search(
        self,
        search_request: LLMSearchRequest,
    ) -> LLMSearchResponse:
        return LLMSearchResponse(query="pool:(=default) status:(=ready)")
