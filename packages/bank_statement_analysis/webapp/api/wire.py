"""How an API response leaves the process: the URL space the bearer token covers, and the one JSON writer."""
from __future__ import annotations

import json
from collections.abc import Mapping

from flask import Response
from pydantic import BaseModel

from .contract import ERRORS, ApiError, ErrorCode, ErrorResponse

API_PREFIX = "/api/v1"


def is_api_path(path: str) -> bool:
    """`path` is in the API's URL space, the bearer token's scope. `/api/settings` is not."""
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def json_response(body: BaseModel, status: int = 200, headers: Mapping[str, str] | None = None) -> Response:
    """`body` as JSON, never cached. Every API response leaves through here."""
    text = json.dumps(body.model_dump(mode="json"), allow_nan=False, separators=(",", ":"))
    response = Response(text, status=status, mimetype="application/json", headers=dict(headers or {}))
    response.headers["Cache-Control"] = "no-store"
    return response


def error_response(code: ErrorCode, *, filename: str | None = None,
                   headers: Mapping[str, str] | None = None) -> Response:
    """The error envelope of `code`, with the code's status and message (`contract.ERRORS`)."""
    status, message = ERRORS[code]
    return json_response(ErrorResponse(error=ApiError(code=code, message=message, filename=filename)), status, headers)
