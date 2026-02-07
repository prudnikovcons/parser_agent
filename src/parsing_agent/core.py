from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Protocol, Sequence

from .models import MediaInfo, ParseResult, ParseResponse, ParseTask, ParsedMessage


@dataclass
class FloodWaitError(Exception):
    seconds: int

    def __str__(self) -> str:
        return f"FloodWaitError(seconds={self.seconds})"


class TelegramMessage(Protocol):
    id: int
    date: datetime
    message: Optional[str]


class TelegramClientProtocol(Protocol):
    async def fetch_messages(
        self,
        channel_id: int,
        since_id: int,
        limit: int,
        timeout: float,
    ) -> Sequence[TelegramMessage]:
        ...


def _is_service_message(message: TelegramMessage) -> bool:
    if hasattr(message, "is_service"):
        return bool(getattr(message, "is_service"))
    if hasattr(message, "service"):
        return bool(getattr(message, "service"))
    return message.__class__.__name__ == "MessageService"


def _render_text_html(message: TelegramMessage) -> Optional[str]:
    if hasattr(message, "text_html"):
        return getattr(message, "text_html")
    if hasattr(message, "html_text"):
        return getattr(message, "html_text")
    if hasattr(message, "to_html"):
        return message.to_html()
    if hasattr(message, "message"):
        return getattr(message, "message")
    return getattr(message, "text", None)


def _extract_media_info(message: TelegramMessage) -> Optional[MediaInfo]:
    media = getattr(message, "media", None)
    if media is None:
        return None

    media_type = None
    class_name = media.__class__.__name__.lower()
    if "photo" in class_name or hasattr(media, "photo"):
        media_type = "photo"
    elif "video" in class_name or hasattr(media, "video"):
        media_type = "video"
    elif "document" in class_name or hasattr(media, "document"):
        media_type = "document"
    else:
        media_type = "other"

    file_size = None
    for attr in ("file_size", "size"):
        if hasattr(media, attr):
            file_size = getattr(media, attr)
            break
    if file_size is None and hasattr(message, "file"):
        file_obj = getattr(message, "file")
        file_size = getattr(file_obj, "size", None)

    return MediaInfo(type=media_type, file_size=file_size)


def _forward_from_id(message: TelegramMessage) -> Optional[int]:
    for attr in ("forward_from_id", "forward_from", "fwd_from"):
        if hasattr(message, attr):
            value = getattr(message, attr)
            if isinstance(value, int):
                return value
            if value is None:
                return None
            return getattr(value, "from_id", None) or getattr(value, "sender_id", None)
    return None


def _views(message: TelegramMessage) -> Optional[int]:
    return getattr(message, "views", None)


def _forwards(message: TelegramMessage) -> Optional[int]:
    return getattr(message, "forwards", None)


def _reply_to_msg_id(message: TelegramMessage) -> Optional[int]:
    return getattr(message, "reply_to_msg_id", None)


def _normalize_messages(messages: Iterable[TelegramMessage]) -> List[TelegramMessage]:
    normalized = [msg for msg in messages if not _is_service_message(msg)]
    normalized.sort(key=lambda msg: msg.id)
    return normalized


async def _parse_task(
    client: TelegramClientProtocol,
    task: ParseTask,
    timeout: float,
) -> ParseResult:
    try:
        raw_messages = await client.fetch_messages(
            channel_id=task.channel_id,
            since_id=task.since_id,
            limit=task.limit + 1,
            timeout=timeout,
        )
    except FloodWaitError as exc:
        return ParseResult(
            channel_id=task.channel_id,
            since_id=task.since_id,
            last_msg_id=task.since_id,
            has_more=False,
            messages=[],
            error=str(exc),
            retry_after=exc.seconds,
        )
    except Exception as exc:  # noqa: BLE001
        return ParseResult(
            channel_id=task.channel_id,
            since_id=task.since_id,
            last_msg_id=task.since_id,
            has_more=False,
            messages=[],
            error=str(exc),
            retry_after=None,
        )

    normalized = _normalize_messages(raw_messages)
    has_more = len(normalized) > task.limit
    trimmed = normalized[: task.limit]

    parsed_messages: List[ParsedMessage] = []
    for message in trimmed:
        media_info = _extract_media_info(message)
        forward_from_id = _forward_from_id(message)
        parsed_messages.append(
            ParsedMessage(
                id=message.id,
                date=message.date,
                text_html=_render_text_html(message),
                has_media=media_info is not None,
                media=media_info,
                is_forward=forward_from_id is not None,
                forward_from_id=forward_from_id,
                views=_views(message),
                forwards=_forwards(message),
                reply_to_msg_id=_reply_to_msg_id(message),
            )
        )

    last_msg_id = task.since_id
    if parsed_messages:
        last_msg_id = parsed_messages[-1].id

    return ParseResult(
        channel_id=task.channel_id,
        since_id=task.since_id,
        last_msg_id=last_msg_id,
        has_more=has_more,
        messages=parsed_messages,
        error=None,
        retry_after=None,
    )


async def parse_tasks(
    client: TelegramClientProtocol,
    tasks: Sequence[ParseTask],
    *,
    concurrency: int = 5,
    timeout: float = 15.0,
) -> ParseResponse:
    semaphore = asyncio.Semaphore(concurrency)

    async def _run(task: ParseTask) -> ParseResult:
        async with semaphore:
            return await _parse_task(client, task, timeout=timeout)

    results = await asyncio.gather(*[_run(task) for task in tasks])
    return ParseResponse(results=results, errors=[])
