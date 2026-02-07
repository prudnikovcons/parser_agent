from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, conint, validator


class ParseTask(BaseModel):
    channel_id: int
    since_id: int
    limit: conint(ge=1, le=100) = 10


class ParseRequest(BaseModel):
    tasks: List[ParseTask]

    @validator("tasks")
    def validate_task_count(cls, value: List[ParseTask]) -> List[ParseTask]:
        if len(value) > 20:
            raise ValueError("maximum 20 tasks per request")
        return value


class MediaInfo(BaseModel):
    type: Optional[str]
    file_size: Optional[int]


class ParsedMessage(BaseModel):
    id: int
    date: datetime
    text_html: Optional[str]
    has_media: bool
    media: Optional[MediaInfo]
    is_forward: bool
    forward_from_id: Optional[int] = None
    views: Optional[int] = None
    forwards: Optional[int] = None
    reply_to_msg_id: Optional[int] = None


class ParseResult(BaseModel):
    channel_id: int
    since_id: int
    last_msg_id: int
    has_more: bool
    messages: List[ParsedMessage]
    error: Optional[str] = None
    retry_after: Optional[int] = None


class ParseResponse(BaseModel):
    results: List[ParseResult]
    errors: List[Any] = Field(default_factory=list)
