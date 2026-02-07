from __future__ import annotations

import os
from typing import cast

from fastapi import FastAPI, HTTPException

from .core import TelegramClientProtocol, parse_tasks
from .models import ParseRequest, ParseResponse

app = FastAPI()

DEFAULT_CONCURRENCY = int(os.getenv("PARSER_CONCURRENCY", "5"))
DEFAULT_TIMEOUT = float(os.getenv("PARSER_TIMEOUT", "15"))


def get_client() -> TelegramClientProtocol:
    client = getattr(app.state, "telegram_client", None)
    if client is None:
        raise RuntimeError("Telegram client is not configured")
    return cast(TelegramClientProtocol, client)


@app.post("/parse", response_model=ParseResponse)
async def parse_endpoint(request: ParseRequest) -> ParseResponse:
    try:
        response = await parse_tasks(
            get_client(),
            request.tasks,
            concurrency=DEFAULT_CONCURRENCY,
            timeout=DEFAULT_TIMEOUT,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return response
