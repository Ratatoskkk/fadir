"""FastAPI route boundary for one caller-owned request transaction."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from app.api.csrf import no_store
from app.api.request_authority import (
    RequestAuthorityConfigurationError,
    RequestAuthorityError,
)
from app.api.csrf import CsrfError


SESSION_FACTORY_STATE_KEY = "session_factory"


class RequestTransactionError(RuntimeError):
    """Raised when the request transaction boundary cannot be honored."""


class RequestTransactionConfigurationError(RequestTransactionError):
    """Raised when the application did not inject the required runtime dependency."""


def request_session(request: Request) -> Session:
    session = getattr(request.state, "db_session", None)
    if session is None:
        raise RequestTransactionConfigurationError("request database session is unavailable")
    return session


def _factory(request: Request):
    factory = getattr(request.app.state, SESSION_FACTORY_STATE_KEY, None)
    if not callable(factory):
        raise RequestTransactionConfigurationError("request transaction is not configured")
    return factory


def _rollback(root: Any) -> None:
    try:
        if root is not None and root.is_active:
            root.rollback()
    except Exception:
        pass


def _error_response(status_code: int) -> Response:
    if isinstance(status_code, int) and 400 <= status_code < 500:
        status = status_code
    else:
        status = 500
    return no_store(JSONResponse(status_code=status, content={"detail": "request rejected"}))


def _exception_response(error: Exception) -> Response:
    if isinstance(error, RequestAuthorityConfigurationError):
        return no_store(JSONResponse(status_code=503, content={"detail": "request unavailable"}))
    if isinstance(error, RequestAuthorityError):
        return no_store(JSONResponse(status_code=401, content={"detail": "request rejected"}))
    if isinstance(error, CsrfError):
        return no_store(JSONResponse(status_code=403, content={"detail": "request rejected"}))
    if isinstance(error, RequestTransactionConfigurationError):
        return no_store(JSONResponse(status_code=503, content={"detail": "request unavailable"}))
    if isinstance(error, RequestValidationError):
        return _error_response(422)
    if isinstance(error, ResponseValidationError):
        return _error_response(500)
    if isinstance(error, StarletteHTTPException):
        return _error_response(error.status_code)
    return _error_response(500)


async def transactional_handler(
    request: Request,
    original_handler: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Run a route handler and commit only after its serialized Response exists."""
    session = None
    root = None
    result: Response | None = None
    pending: BaseException | None = None
    try:
        session = _factory(request)()
        root = session.begin()
        request.state.db_session = session
        response = await original_handler(request)
        if isinstance(response, StreamingResponse) or getattr(response, "background", None) is not None:
            raise RequestTransactionError("streaming and late background work are unsupported")
        response = no_store(response)
        if response.status_code >= 400:
            _rollback(root)
            result = _error_response(response.status_code)
        else:
            try:
                root.commit()
            except asyncio.CancelledError:
                _rollback(root)
                raise
            except Exception as error:
                _rollback(root)
                result = _exception_response(error)
            else:
                result = response
    except asyncio.CancelledError:
        _rollback(root)
        pending = asyncio.CancelledError()
    except Exception as error:
        _rollback(root)
        result = _exception_response(error)
    finally:
        if session is not None:
            try:
                session.close()
            except asyncio.CancelledError as error:
                if pending is None:
                    pending = error
            except Exception:
                if pending is None:
                    result = _error_response(500)
            finally:
                request.state.db_session = None
    if pending is not None:
        raise pending
    if result is None:
        raise RequestTransactionError("request transaction produced no response")
    return result


class RequestTransactionRoute(APIRoute):
    """Opt-in APIRoute that gives dependencies and handlers one root transaction."""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            return await transactional_handler(request, original_handler)

        return handler
