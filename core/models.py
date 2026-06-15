from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Product(BaseModel):
    nmId: int
    imtId: Optional[int] = None
    name: str
    brand: str
    price: float = Field(ge=0, default=0.0)
    feedbacks: int = Field(ge=0, default=0)
    rating: float = Field(ge=0, le=5, default=0.0)
    img_url: Optional[str] = None
    url: Optional[str] = None


class Review(BaseModel):
    id: str
    nmId: Optional[int] = None
    text: str
    rating: float = Field(ge=0, le=5, default=0.0)
    date: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    photo_urls: list[str] = Field(default_factory=list)
    video_url: Optional[str] = None


class Candidate(BaseModel):
    site: str
    title: str
    url: Optional[str] = None
    thumb_url: str
    price: float = Field(ge=0, default=0.0)
    similarity: float = Field(ge=0, le=1, default=0.0)
    has_video: bool = False
    video_url: Optional[str] = None


class VocItem(BaseModel):
    text: str
    frequency: int = 0


class VoC(BaseModel):
    боли: list[VocItem] = Field(default_factory=list)
    желания: list[VocItem] = Field(default_factory=list)
    страхи: list[VocItem] = Field(default_factory=list)
    триггеры: list[VocItem] = Field(default_factory=list)
    восторги: list[VocItem] = Field(default_factory=list)
    возражения: list[VocItem] = Field(default_factory=list)
    язык_клиента: list[VocItem] = Field(default_factory=list)


class VideoAsset(BaseModel):
    source: Literal["wb_review", "china"]
    nmId: int
    local_path: str
    src_url: str
    description: Optional[str] = None
