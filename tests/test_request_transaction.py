from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

from app.api.request_transaction import (
    request_session,
    transactional_handler,
)


class FakeRoot:
    def __init__(self) -> None:
        self.is_active = True
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1
        self.is_active = False

    def rollback(self) -> None:
        self.rollbacks += 1
        self.is_active = False


class FakeSession:
    def __init__(self) -> None:
        self.root = FakeRoot()
        self.closed = 0

    def begin(self) -> FakeRoot:
        return self.root

    def close(self) -> None:
        self.closed += 1


class BeginFailureSession(FakeSession):
    def begin(self):
        raise RuntimeError("begin failed")


class CloseFailureSession(FakeSession):
    def close(self) -> None:
        self.closed += 1
        raise RuntimeError("close failed")


def _request(session_factory=None) -> Request:
    app = SimpleNamespace(state=SimpleNamespace())
    if session_factory is not None:
        app.state.session_factory = session_factory
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/private",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "app": app,
        }
    )


@pytest.mark.asyncio
async def test_success_commits_after_serialized_response_and_closes_once() -> None:
    session = FakeSession()
    request = _request(lambda: session)

    async def handler(received: Request):
        assert request_session(received) is session
        return JSONResponse({"ok": True})

    response = await transactional_handler(request, handler)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert session.root.commits == 1 and session.root.rollbacks == 0
    assert session.closed == 1
    assert getattr(request.state, "db_session") is None


@pytest.mark.asyncio
async def test_error_response_rolls_back() -> None:
    session = FakeSession()
    response = await transactional_handler(
        _request(lambda: session), lambda request: asyncio.sleep(0, result=JSONResponse({}, status_code=409))
    )
    assert response.status_code == 409
    assert session.root.commits == 0 and session.root.rollbacks == 1
    assert session.closed == 1


@pytest.mark.asyncio
async def test_handler_failure_rolls_back_and_closes() -> None:
    session = FakeSession()

    async def handler(request):
        raise ValueError("synthetic failure")

    response = await transactional_handler(_request(lambda: session), handler)
    assert response.status_code == 500 and response.headers["cache-control"] == "no-store"
    assert session.root.commits == 0 and session.root.rollbacks == 1
    assert session.closed == 1


@pytest.mark.asyncio
async def test_cancellation_rolls_back() -> None:
    session = FakeSession()

    async def handler(request):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await transactional_handler(_request(lambda: session), handler)
    assert session.root.rollbacks == 1 and session.closed == 1


@pytest.mark.asyncio
async def test_streaming_and_background_responses_are_rejected() -> None:
    for response in (StreamingResponse(iter([b"x"])), JSONResponse({}, background=object())):
        session = FakeSession()
        result = await transactional_handler(
            _request(lambda: session), lambda request, response=response: asyncio.sleep(0, result=response)
        )
        assert result.status_code == 500 and result.headers["cache-control"] == "no-store"
        assert session.root.rollbacks == 1 and session.closed == 1


@pytest.mark.asyncio
async def test_missing_runtime_factory_fails_closed() -> None:
    response = await transactional_handler(
        _request(), lambda request: asyncio.sleep(0, result=JSONResponse({}))
    )
    assert response.status_code == 503 and response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_begin_failure_still_closes_session_once() -> None:
    session = BeginFailureSession()
    response = await transactional_handler(
        _request(lambda: session), lambda request: asyncio.sleep(0, result=JSONResponse({}))
    )
    assert response.status_code == 500 and response.headers["cache-control"] == "no-store"
    assert session.closed == 1


@pytest.mark.asyncio
async def test_close_failure_is_generic_no_store_and_clears_request_state() -> None:
    session = CloseFailureSession()
    request = _request(lambda: session)
    response = await transactional_handler(
        request, lambda received: asyncio.sleep(0, result=JSONResponse({"ok": True}))
    )
    assert response.status_code == 500 and response.headers["cache-control"] == "no-store"
    assert session.closed == 1
    assert request.state.db_session is None


@pytest.mark.asyncio
async def test_cancellation_survives_close_failure() -> None:
    session = CloseFailureSession()

    async def handler(request):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await transactional_handler(_request(lambda: session), handler)
    assert session.closed == 1
